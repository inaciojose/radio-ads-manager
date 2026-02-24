"""
log_monitor/monitor.py - Monitor de Logs do Zara Studio

Este módulo monitora os arquivos de log do Zara Studio e 
registra automaticamente as veiculações de propagandas.

COMO FUNCIONA:
1. Monitora uma pasta de logs em tempo real
2. Quando detecta mudança, lê o arquivo
3. Extrai informações das propagandas tocadas
4. Cria veiculações via API
5. Processa as veiculações nos contratos
"""

import os
import time
import re
import unicodedata
import ntpath
import requests
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from dotenv import load_dotenv
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import logging

# Carrega backend/.env antes de qualquer leitura com os.getenv.
ENV_PATH = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(ENV_PATH)

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# ============================================
# CONFIGURAÇÕES
# ============================================

class Config:
    """Configurações do monitor"""
    
    # URL da API
    API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")
    MONITOR_API_KEY = os.getenv("MONITOR_API_KEY")
    # Compatibilidade legada: token Bearer manual.
    API_TOKEN = os.getenv("API_TOKEN")
    
    # Mapa frequência->diretório de logs (separado por ';')
    # Exemplo:
    #   LOG_SOURCES="102.7=K:\\Registro FM;104.7=K:\\Registro 104_7"
    LOG_SOURCES = os.getenv(
        "LOG_SOURCES",
        "102.7=K:\\Registro FM;104.7=K:\\Registro 104_7"
    )
    
    # Padrão do nome dos arquivos de log
    # Exemplo: 2026-02-16.log
    LOG_FILE_PATTERN = r"\d{4}-\d{2}-\d{2}\.log$"
    
    # Intervalo para processar veiculações (em segundos)
    PROCESS_INTERVAL = 300  # 5 minutos

    # Timeout HTTP por requisição (segundos)
    REQUEST_TIMEOUT = float(os.getenv("REQUEST_TIMEOUT", "8"))

    # Tentativas para requisições HTTP
    REQUEST_RETRIES = int(os.getenv("REQUEST_RETRIES", "3"))

    # Quantidade máxima por lote na ingestão
    INGEST_BATCH_SIZE = int(os.getenv("INGEST_BATCH_SIZE", "100"))

    # Debounce para eventos de alteração de arquivo (watch mode)
    WATCH_DEBOUNCE_SECONDS = float(os.getenv("WATCH_DEBOUNCE_SECONDS", "1.5"))
    
    # Prefixo canônico para identificar propagandas nos logs da rádio.
    # Aceita subpastas dentro desse caminho.
    CHAMADAS_BASE_PATH = os.getenv("CHAMADAS_BASE_PATH", r"J:\AZARASTUDIO\CHAMADAS")

    def parse_log_sources(self) -> List[Tuple[str, str]]:
        sources: List[Tuple[str, str]] = []
        raw = self.LOG_SOURCES
        for chunk in raw.split(";"):
            item = chunk.strip()
            if not item or "=" not in item:
                continue
            freq, path = item.split("=", 1)
            freq = freq.strip()
            path = path.strip()
            if freq and path:
                sources.append((freq, path))
        return sources


# ============================================
# CLASSE: Parser de Logs
# ============================================

class ZaraLogParser:
    """
    Parse dos arquivos de log do Zara Studio.
    Extrai informações sobre arquivos tocados.
    """
    
    def __init__(self, config: Config):
        self.config = config
        self.log_pattern = re.compile(r"^\d{2}:\d{2}:\d{2}$")

    def _normalizar_texto(self, valor: str) -> str:
        texto = unicodedata.normalize("NFKD", valor)
        texto = "".join(ch for ch in texto if not unicodedata.combining(ch))
        return texto.lower().strip()

    def _normalizar_path(self, valor: str) -> str:
        return valor.replace("/", "\\").strip().lower()
    
    def parse_file(self, filepath: str, date: datetime, frequencia: str) -> List[Dict]:
        """
        Lê um arquivo de log e extrai as propagandas tocadas.
        
        Args:
            filepath: Caminho do arquivo de log
            date: Data do arquivo (para construir datetime completo)
        
        Returns:
            Lista de dicionários com informações das propagandas
        """
        propagandas = []
        
        try:
            with open(filepath, "r", encoding="cp1252", errors="ignore") as f:
                for line_num, line in enumerate(f, 1):
                    try:
                        propaganda = self.parse_line(line, date, frequencia)
                        if propaganda:
                            propagandas.append(propaganda)
                    except Exception as e:
                        logger.warning(f"Erro ao processar linha {line_num}: {e}")
                        continue
        
        except Exception as e:
            logger.error(f"Erro ao ler arquivo {filepath}: {e}")
        
        return propagandas
    
    def parse_line(self, line: str, date: datetime, frequencia: str) -> Optional[Dict]:
        """
        Faz parse de uma linha do log.
        
        Args:
            line: Linha do arquivo de log
            date: Data base para construir datetime
        
        Returns:
            Dicionário com informações da propaganda ou None
        """
        linha = line.strip()
        if not linha or linha.startswith("LOG FILE") or linha.startswith("="):
            return None

        colunas = re.split(r"\t+", linha)
        if len(colunas) < 5:
            return None

        hora_str = colunas[0].strip()
        action = self._normalizar_texto(colunas[1])
        caminho_tocado = colunas[-1].strip()

        if not self.log_pattern.match(hora_str):
            return None

        # Só considera exatamente eventos de início.
        if action not in {"inicio", "in"}:
            return None

        # Só considera chamadas dentro da pasta padrão da rádio.
        if not self.is_propaganda(caminho_tocado):
            return None

        hora_parts = hora_str.split(":")
        data_hora = date.replace(
            hour=int(hora_parts[0]),
            minute=int(hora_parts[1]),
            second=int(hora_parts[2])
        )

        nome_arquivo = ntpath.basename(caminho_tocado)

        return {
            "nome_arquivo": nome_arquivo,
            "data_hora": data_hora,
            "tipo_programa": None,
            "frequencia": frequencia,
        }
    
    def is_propaganda(self, caminho_arquivo: str) -> bool:
        """
        Verifica se o arquivo é uma propaganda baseado no nome.
        
        Lógica:
        1. Se contém palavra de IGNORE → não é propaganda
        2. Se contém palavra de PROPAGANDA → é propaganda
        3. Se não tem nenhuma das duas → considera como propaganda (conservador)
        """
        caminho_normalizado = self._normalizar_path(caminho_arquivo)
        base_normalizada = self._normalizar_path(self.config.CHAMADAS_BASE_PATH)
        if not base_normalizada.endswith("\\"):
            base_normalizada = f"{base_normalizada}\\"
        return caminho_normalizado.startswith(base_normalizada)


# ============================================
# CLASSE: Cliente da API
# ============================================

class APIClient:
    """
    Cliente para comunicação com a API do Radio Ads Manager.
    """
    
    def __init__(
        self,
        base_url: str,
        api_key: Optional[str] = None,
        token: Optional[str] = None,
        timeout: float = 8.0,
        retries: int = 3,
    ):
        self.base_url = base_url
        self.timeout = timeout
        self.retries = max(1, retries)
        self.session = requests.Session()
        if api_key:
            self.session.headers.update({"X-API-Key": api_key})
        elif token:
            self.session.headers.update({"Authorization": f"Bearer {token}"})

    def _log_auth_failure(self, endpoint: str, response: requests.Response):
        logger.error(
            "Falha de autenticação ao acessar %s: HTTP %s. "
            "Verifique MONITOR_API_KEY (preferencial) ou API_TOKEN.",
            endpoint,
            response.status_code,
        )

    def _request_with_retry(self, method: str, url: str, **kwargs):
        last_exc: Optional[Exception] = None
        for attempt in range(1, self.retries + 1):
            try:
                response = self.session.request(
                    method,
                    url,
                    timeout=kwargs.pop("timeout", self.timeout),
                    **kwargs,
                )
                if response.status_code >= 500 and attempt < self.retries:
                    time.sleep(0.2 * attempt)
                    continue
                return response
            except requests.RequestException as exc:
                last_exc = exc
                if attempt < self.retries:
                    time.sleep(0.2 * attempt)
                    continue
        raise last_exc if last_exc else RuntimeError("Falha HTTP sem exceção registrada")
    
    def get_arquivo_by_nome(self, nome_arquivo: str) -> Optional[Dict]:
        """
        Busca um arquivo de áudio pelo nome.
        
        Returns:
            Dicionário com dados do arquivo ou None se não encontrado
        """
        try:
            response = self.session.get(
                f"{self.base_url}/arquivos",
                params={"busca": nome_arquivo, "limit": 100},
                timeout=self.timeout,
            )
            
            if response.status_code == 200:
                arquivos = response.json()
                if arquivos:
                    nome_normalizado = nome_arquivo.strip().lower()
                    for arquivo in arquivos:
                        if str(arquivo.get("nome_arquivo", "")).strip().lower() == nome_normalizado:
                            return arquivo
            elif response.status_code == 401:
                self._log_auth_failure("/arquivos", response)
            
            return None
        
        except Exception as e:
            logger.error(f"Erro ao buscar arquivo '{nome_arquivo}': {e}")
            return None
    
    def create_veiculacao(self, veiculacao_data: Dict) -> Optional[Dict]:
        """
        Cria uma nova veiculação via API.
        
        Args:
            veiculacao_data: Dados da veiculação
        
        Returns:
            Veiculação criada ou None em caso de erro
        """
        try:
            response = self.session.post(
                f"{self.base_url}/veiculacoes/",
                json=veiculacao_data,
                timeout=self.timeout,
            )
            
            if response.status_code in (200, 201):
                payload = response.json()
                payload["_created"] = response.status_code == 201
                return payload
            if response.status_code == 401:
                self._log_auth_failure("/veiculacoes/", response)
                return None
            else:
                logger.warning(f"Erro ao criar veiculação: {response.status_code} - {response.text}")
                return None
        
        except Exception as e:
            logger.error(f"Erro ao criar veiculação: {e}")
            return None

    def create_veiculacoes_batch(self, payload: List[Dict]) -> Dict:
        """
        Cria várias veiculações em lote.
        Faz fallback para chamadas unitárias caso endpoint não exista.
        """
        if not payload:
            return {"criadas": 0, "existentes": 0, "falhas": 0}
        try:
            response = self._request_with_retry(
                "POST",
                f"{self.base_url}/veiculacoes/ingest/lote",
                json=payload,
            )
            if response.status_code == 200:
                detalhes = response.json().get("detalhes", {})
                return {
                    "criadas": int(detalhes.get("criadas", 0)),
                    "existentes": int(detalhes.get("existentes", 0)),
                    "falhas": int(detalhes.get("falhas", 0)),
                }
            if response.status_code == 401:
                self._log_auth_failure("/veiculacoes/ingest/lote", response)
                return {"criadas": 0, "existentes": 0, "falhas": len(payload)}
            if response.status_code == 404:
                return self._create_veiculacoes_fallback(payload)
            logger.warning(
                "Erro na ingestão em lote: %s - %s",
                response.status_code,
                response.text,
            )
            return self._create_veiculacoes_fallback(payload)
        except Exception as e:
            logger.warning(f"Falha no lote, usando fallback unitário: {e}")
            return self._create_veiculacoes_fallback(payload)

    def _create_veiculacoes_fallback(self, payload: List[Dict]) -> Dict:
        criadas = 0
        existentes = 0
        falhas = 0
        for item in payload:
            resp = self.create_veiculacao(item)
            if not resp:
                falhas += 1
                continue
            if resp.get("_created", True):
                criadas += 1
            else:
                existentes += 1
        return {"criadas": criadas, "existentes": existentes, "falhas": falhas}
    
    def process_veiculacoes(self, data_inicio: str, data_fim: str) -> bool:
        """
        Processa veiculações (contabiliza nos contratos).
        
        Args:
            data_inicio: Data início (formato YYYY-MM-DD)
            data_fim: Data fim (formato YYYY-MM-DD)
        
        Returns:
            True se processou com sucesso
        """
        try:
            response = self.session.post(
                f"{self.base_url}/veiculacoes/processar",
                params={
                    "data_inicio": data_inicio,
                    "data_fim": data_fim
                },
                timeout=self.timeout,
            )
            
            if response.status_code == 200:
                logger.info(f"Veiculações processadas: {response.json()}")
                return True
            if response.status_code == 401:
                self._log_auth_failure("/veiculacoes/processar", response)
                return False
            else:
                logger.warning(f"Erro ao processar veiculações: {response.status_code}")
                return False
        
        except Exception as e:
            logger.error(f"Erro ao processar veiculações: {e}")
            return False
    
    def check_health(self) -> bool:
        """Verifica se a API está online"""
        try:
            response = self._request_with_retry(
                "GET",
                f"{self.base_url}/health",
                timeout=5,
            )
            if response.status_code == 401:
                self._log_auth_failure("/health", response)
                return False
            return response.status_code == 200
        except:
            return False


# ============================================
# CLASSE: Monitor de Logs
# ============================================

class LogMonitor:
    """
    Monitor principal que coordena tudo.
    """
    
    def __init__(self, config: Config):
        self.config = config
        self.parser = ZaraLogParser(config)
        self.api_client = APIClient(
            config.API_BASE_URL,
            api_key=config.MONITOR_API_KEY,
            token=config.API_TOKEN,
            timeout=config.REQUEST_TIMEOUT,
            retries=config.REQUEST_RETRIES,
        )
        self.log_sources = config.parse_log_sources()
        self.veiculacoes_criadas = 0
        self.erros = 0
        self.last_process_time = None
        self._dedupe_cache = set()
        self._arquivo_id_cache: Dict[str, Optional[int]] = {}
        self._file_offsets: Dict[Tuple[str, str], int] = {}
        self._pending_events: Dict[Tuple[str, str], Dict] = {}
    
    def process_log_file(self, filepath: str, date: datetime, frequencia: str, incremental: bool = False):
        """
        Processa um arquivo de log completo.
        
        Args:
            filepath: Caminho do arquivo
            date: Data do arquivo
        """
        logger.info(f"Processando arquivo: {filepath} (incremental={incremental})")
        key = (frequencia, filepath)
        propagandas: List[Dict] = []
        lidas = 0

        try:
            with open(filepath, "r", encoding="cp1252", errors="ignore") as f:
                start_offset = self._file_offsets.get(key, 0) if incremental else 0
                if incremental:
                    tamanho_atual = os.path.getsize(filepath)
                    if start_offset > tamanho_atual:
                        start_offset = 0  # arquivo truncado/rotacionado
                    f.seek(start_offset)

                for line in f:
                    lidas += 1
                    propaganda = self.parser.parse_line(line, date, frequencia)
                    if propaganda:
                        propagandas.append(propaganda)

                self._file_offsets[key] = f.tell()
        except Exception as e:
            logger.error(f"Erro ao ler arquivo {filepath}: {e}")
            self.erros += 1
            return

        logger.info(f"Linhas lidas: {lidas}. Propagandas detectadas: {len(propagandas)}")
        if not propagandas:
            return

        self.create_veiculacoes_from_logs(propagandas)
        logger.info(
            "Processamento concluído. Criadas: %s, Erros: %s",
            self.veiculacoes_criadas,
            self.erros,
        )

    def create_veiculacoes_from_logs(self, propagandas: List[Dict]):
        """
        Cria veiculações em lote a partir dos dados do log.
        Registra todas as propagandas detectadas, inclusive arquivos não cadastrados.
        """
        payload: List[Dict] = []
        for propaganda in propagandas:
            nome_arquivo = propaganda["nome_arquivo"]
            nome_key = nome_arquivo.strip().lower()

            if nome_key in self._arquivo_id_cache:
                arquivo_id = self._arquivo_id_cache[nome_key]
            else:
                arquivo = self.api_client.get_arquivo_by_nome(nome_arquivo)
                if arquivo:
                    arquivo_id = arquivo["id"]
                else:
                    arquivo_id = None
                    logger.debug(f"Arquivo '{nome_arquivo}' não encontrado no cadastro - registrando como não identificado")
                self._arquivo_id_cache[nome_key] = arquivo_id

            # Dedupe: usa arquivo_id quando cadastrado, nome_key quando não
            dedupe_id = arquivo_id if arquivo_id is not None else nome_key
            dedupe_key = (dedupe_id, propaganda["data_hora"].isoformat(), propaganda.get("frequencia"))
            if dedupe_key in self._dedupe_cache:
                continue

            item: Dict = {
                "data_hora": propaganda["data_hora"].isoformat(),
                "frequencia": propaganda.get("frequencia"),
                "tipo_programa": propaganda["tipo_programa"],
                "fonte": "zara_log",
            }
            if arquivo_id is not None:
                item["arquivo_audio_id"] = arquivo_id
            else:
                item["nome_arquivo_raw"] = nome_arquivo

            payload.append(item)
            self._dedupe_cache.add(dedupe_key)

        if not payload:
            return

        batch_size = max(1, self.config.INGEST_BATCH_SIZE)
        for i in range(0, len(payload), batch_size):
            chunk = payload[i:i + batch_size]
            resultado = self.api_client.create_veiculacoes_batch(chunk)
            self.veiculacoes_criadas += resultado.get("criadas", 0)
            self.erros += resultado.get("falhas", 0)
    
    def process_pending_veiculacoes(self):
        """
        Processa veiculações pendentes (contabiliza nos contratos).
        Executa periodicamente.
        """
        hoje = datetime.now().date()
        
        logger.info("Processando veiculações pendentes...")
        success = self.api_client.process_veiculacoes(
            data_inicio=str(hoje),
            data_fim=str(hoje)
        )
        
        if success:
            self.last_process_time = datetime.now()
    
    def should_process_veiculacoes(self) -> bool:
        """Verifica se deve processar veiculações agora"""
        if not self.last_process_time:
            return True
        
        elapsed = (datetime.now() - self.last_process_time).total_seconds()
        return elapsed >= self.config.PROCESS_INTERVAL
    
    def run_batch_mode(self):
        """
        Modo batch: Processa arquivos existentes e sai.
        Útil para processar logs históricos.
        """
        logger.info("Iniciando em modo BATCH")
        logger.info(f"Fontes de logs: {self.log_sources}")
        
        # Verificar se API está online
        if not self.api_client.check_health():
            logger.error("API não está respondendo! Certifique-se de que está rodando.")
            return
        
        logger.info("API online ✓")
        
        # Listar arquivos de log
        for frequencia, log_dir_raw in self.log_sources:
            log_dir = Path(log_dir_raw)
            if not log_dir.exists():
                logger.warning(f"Diretório não encontrado para frequência {frequencia}: {log_dir_raw}")
                continue

            log_files = sorted(
                f for f in log_dir.glob("*.log")
                if re.match(self.config.LOG_FILE_PATTERN, f.name)
            )
            logger.info(f"[{frequencia}] Encontrados {len(log_files)} arquivos de log")

            for log_file in log_files:
                try:
                    date_match = re.search(r"(\d{4})-(\d{2})-(\d{2})", log_file.name)
                    if date_match:
                        date = datetime(
                            int(date_match.group(1)),
                            int(date_match.group(2)),
                            int(date_match.group(3))
                        )
                    else:
                        date = datetime.now()

                    self.process_log_file(str(log_file), date, frequencia)
                except Exception as e:
                    logger.error(f"Erro ao processar {log_file}: {e}")
                    continue
        
        # Processar veiculações
        logger.info("\nProcessando veiculações nos contratos...")
        self.process_pending_veiculacoes()
        
        logger.info("\n" + "="*60)
        logger.info("PROCESSAMENTO BATCH CONCLUÍDO")
        logger.info(f"Total de veiculações criadas: {self.veiculacoes_criadas}")
        logger.info(f"Total de erros: {self.erros}")
        logger.info("="*60)
    
    def run_watch_mode(self):
        """
        Modo watch: Monitora pasta em tempo real.
        Processa automaticamente quando detecta mudanças.
        """
        logger.info("Iniciando em modo WATCH (monitoramento em tempo real)")
        logger.info(f"Monitorando: {self.log_sources}")
        logger.info("Pressione Ctrl+C para parar")
        
        # Verificar se API está online
        if not self.api_client.check_health():
            logger.error("API não está respondendo! Certifique-se de que está rodando.")
            return
        
        logger.info("API online ✓")
        
        # Configurar watchdog
        observer = Observer()
        for frequencia, log_dir_raw in self.log_sources:
            if not Path(log_dir_raw).exists():
                logger.warning(f"Diretório não encontrado para frequência {frequencia}: {log_dir_raw}")
                continue
            event_handler = LogFileEventHandler(self, frequencia)
            observer.schedule(event_handler, log_dir_raw, recursive=False)
        observer.start()
        
        try:
            while True:
                time.sleep(1)
                self.flush_pending_file_events()
                
                # Processar veiculações periodicamente
                if self.should_process_veiculacoes():
                    self.process_pending_veiculacoes()
        
        except KeyboardInterrupt:
            logger.info("\nParando monitor...")
            observer.stop()
        
        observer.join()
        logger.info("Monitor parado")

    def enqueue_file_event(self, filepath: str, date: datetime, frequencia: str):
        key = (frequencia, filepath)
        self._pending_events[key] = {
            "filepath": filepath,
            "date": date,
            "frequencia": frequencia,
            "last_event_at": time.time(),
        }

    def flush_pending_file_events(self):
        if not self._pending_events:
            return
        now = time.time()
        debounce = max(0.0, self.config.WATCH_DEBOUNCE_SECONDS)
        keys_processar = [
            key for key, ev in self._pending_events.items()
            if now - ev["last_event_at"] >= debounce
        ]
        for key in keys_processar:
            ev = self._pending_events.pop(key, None)
            if not ev:
                continue
            try:
                self.process_log_file(
                    ev["filepath"],
                    ev["date"],
                    ev["frequencia"],
                    incremental=True,
                )
            except Exception as e:
                logger.error(f"Erro ao processar arquivo em debounce: {e}")


# ============================================
# CLASSE: Event Handler (Watchdog)
# ============================================

class LogFileEventHandler(FileSystemEventHandler):
    """
    Handler de eventos do watchdog.
    Detecta quando arquivos de log são modificados.
    """
    
    def __init__(self, monitor: LogMonitor, frequencia: str):
        self.monitor = monitor
        self.config = monitor.config
        self.frequencia = frequencia
    
    def on_modified(self, event):
        """Chamado quando um arquivo é modificado"""
        if event.is_directory:
            return
        
        # Verificar se é um arquivo de log
        if not re.match(self.config.LOG_FILE_PATTERN, os.path.basename(event.src_path)):
            return
        
        logger.info(f"Arquivo modificado: {event.src_path}")
        
        # Extrair data do nome do arquivo
        date_match = re.search(r'(\d{4})-(\d{2})-(\d{2})', event.src_path)
        if date_match:
            date = datetime(
                int(date_match.group(1)),
                int(date_match.group(2)),
                int(date_match.group(3))
            )
        else:
            date = datetime.now()
        
        # Enfileira para processamento com debounce e leitura incremental.
        self.monitor.enqueue_file_event(event.src_path, date, self.frequencia)


# ============================================
# FUNÇÃO PRINCIPAL
# ============================================

def main():
    """Função principal - ponto de entrada"""
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Monitor de Logs do Zara Studio',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemplos de uso:

  # Processar logs históricos (modo batch)
  python monitor.py batch

  # Monitorar em tempo real (modo watch)
  python monitor.py watch

  # Especificar diretório customizado
  python monitor.py batch --log-sources "102.7=/logs/fm;104.7=/logs/104_7"

  # Especificar URL da API
  python monitor.py watch --api-url http://192.168.1.100:8000
        """
    )
    
    parser.add_argument(
        'mode',
        choices=['batch', 'watch'],
        help='Modo de operação: batch (processar existentes) ou watch (monitorar tempo real)'
    )
    
    parser.add_argument(
        '--log-sources',
        type=str,
        help='Mapa frequência=diretório separado por ";" (ex: "102.7=/logs/fm;104.7=/logs/104_7")'
    )
    
    parser.add_argument(
        '--api-url',
        type=str,
        help='URL da API (padrão: http://localhost:8000)'
    )
    
    args = parser.parse_args()
    
    # Configurar
    config = Config()
    
    if args.log_sources:
        config.LOG_SOURCES = args.log_sources
    
    if args.api_url:
        config.API_BASE_URL = args.api_url
    
    # Criar monitor
    monitor = LogMonitor(config)
    
    # Executar no modo escolhido
    if args.mode == 'batch':
        monitor.run_batch_mode()
    else:
        monitor.run_watch_mode()


if __name__ == '__main__':
    main()
