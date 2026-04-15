"""
log_monitor/monitor.py - Monitor de Logs do Zara Studio

COMO FUNCIONA:
1. Monitora os diretórios de logs configurados em LOG_SOURCES (.env)
2. Quando detecta mudança, lê o arquivo incrementalmente
3. Extrai chamadas via padrão: arquivo deve estar em CHAMADAS_BASE_PATH
   e o nome do arquivo deve começar com (N) onde N é o código do cliente
4. Vincula a veiculação ao cliente com codigo_chamada = N (se existir e ativo)
5. Define status_chamada:
   - verde   → código (N) encontrado e cliente ativo existe
   - vermelho → código (N) encontrado mas sem cliente ativo correspondente
   - amarelo  → arquivo na pasta correta mas sem código (N) no nome
6. Registra todas as veiculações via API
"""

import os
import json
import time
import re
import unicodedata
import ntpath
import requests
from datetime import datetime
from zoneinfo import ZoneInfo
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

    # Secret em memória passado pela API pai via variável de ambiente.
    # Não precisa ser configurado manualmente no .env.
    MONITOR_SECRET = os.getenv("RADIO_ADS_MONITOR_SECRET")

    # Mapa frequência->diretório de logs (separado por ';')
    # Exemplo:
    #   LOG_SOURCES="102.7=K:\\Registro FM;104.7=K:\\Registro 104_7"
    LOG_SOURCES = os.getenv(
        "LOG_SOURCES",
        "102.7=K:\\Registro FM;104.7=K:\\Registro 104_7"
    )

    # Padrão do nome dos arquivos de log: 2026-02-16.log
    LOG_FILE_PATTERN = r"\d{4}-\d{2}-\d{2}\.log$"

    # Intervalo de processamento periódico (segundos) — só como fallback
    PROCESS_INTERVAL = 300

    # Timeout HTTP por requisição (segundos)
    REQUEST_TIMEOUT = float(os.getenv("REQUEST_TIMEOUT", "8"))

    # Tentativas para requisições HTTP
    REQUEST_RETRIES = int(os.getenv("REQUEST_RETRIES", "3"))

    # Quantidade máxima por lote na ingestão
    INGEST_BATCH_SIZE = int(os.getenv("INGEST_BATCH_SIZE", "100"))

    # Debounce para eventos de alteração de arquivo (watch mode)
    WATCH_DEBOUNCE_SECONDS = float(os.getenv("WATCH_DEBOUNCE_SECONDS", "1.5"))

    # Prefixo canônico para identificar propagandas nos logs da rádio.
    CHAMADAS_BASE_PATH = os.getenv("CHAMADAS_BASE_PATH", r"J:\AZARASTUDIO\CHAMADAS")

    # Fuso horário local dos logs (os horários nos arquivos .log são horário local).
    # Deve corresponder à timezone do servidor de rádio.
    LOG_TIMEZONE = os.getenv("LOG_TIMEZONE", "America/Fortaleza")

    # Arquivo de persistência dos offsets de leitura dos logs.
    # Permite retomar do ponto onde parou após um restart, evitando duplicatas.
    OFFSETS_FILE = os.getenv("MONITOR_OFFSETS_FILE", "/tmp/radio_ads_monitor_offsets.json")

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

# Extrai o número entre parênteses no início do nome do arquivo
# Ex: "(20) MARTMAG (PADRÃO).mp3" → 20
_CODIGO_RE = re.compile(r"^\((\d+)\)\s")


class ZaraLogParser:
    """Parse dos arquivos de log do Zara Studio."""

    def __init__(self, config: Config):
        self.config = config
        self.log_pattern = re.compile(r"^\d{2}:\d{2}:\d{2}$")

    def _normalizar_path(self, valor: str) -> str:
        return valor.replace("/", "\\").strip().lower()

    def parse_file(self, filepath: str, date: datetime, frequencia: str) -> List[Dict]:
        propagandas = []
        try:
            with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
                for line_num, line in enumerate(f, 1):
                    try:
                        propaganda = self.parse_line(line, date, frequencia)
                        if propaganda:
                            propagandas.append(propaganda)
                    except Exception as e:
                        logger.warning(f"Erro ao processar linha {line_num}: {e}")
        except Exception as e:
            logger.error(f"Erro ao ler arquivo {filepath}: {e}")
        return propagandas

    def parse_line(self, line: str, date: datetime, frequencia: str) -> Optional[Dict]:
        linha = line.strip()
        if not linha or linha.startswith("LOG FILE") or linha.startswith("="):
            return None

        colunas = re.split(r"\t+", linha)
        if len(colunas) < 5:
            return None

        hora_str = colunas[0].strip()
        action = unicodedata.normalize("NFKD", colunas[1]).lower().strip()
        action = "".join(ch for ch in action if not unicodedata.combining(ch))
        caminho_tocado = colunas[-1].strip()

        if not self.log_pattern.match(hora_str):
            return None

        if action not in {"inicio", "in", "start"}:
            return None

        if not self.is_chamada(caminho_tocado):
            return None

        hora_parts = hora_str.split(":")
        tz = ZoneInfo(self.config.LOG_TIMEZONE)
        data_hora = date.replace(
            hour=int(hora_parts[0]),
            minute=int(hora_parts[1]),
            second=int(hora_parts[2]),
            microsecond=0,
            tzinfo=tz,
        )

        nome_arquivo = ntpath.basename(caminho_tocado)
        codigo_chamada = self._extrair_codigo(nome_arquivo)

        return {
            "nome_arquivo": nome_arquivo,
            "data_hora": data_hora,
            "frequencia": frequencia,
            "codigo_chamada": codigo_chamada,  # int ou None
        }

    def is_chamada(self, caminho_arquivo: str) -> bool:
        """Arquivo está dentro de CHAMADAS_BASE_PATH.
        Suporta tanto caminhos de unidade (J:\\...) quanto caminhos UNC (\\\\?\\UNC\\...).
        """
        caminho_normalizado = self._normalizar_path(caminho_arquivo)
        base_normalizada = self._normalizar_path(self.config.CHAMADAS_BASE_PATH)
        if not base_normalizada.endswith("\\"):
            base_normalizada = f"{base_normalizada}\\"
        # Correspondência direta (ex.: J:\AZARASTUDIO\CHAMADAS\)
        if caminho_normalizado.startswith(base_normalizada):
            return True
        # Correspondência via caminho UNC (ex.: \\?\UNC\server\share\AZARASTUDIO\CHAMADAS\)
        # Remove o prefixo de unidade (ex.: "j:") e verifica como subcaminho
        tail = base_normalizada.split("\\", 1)[-1]  # "azarastudio\chamadas\"
        return tail in caminho_normalizado

    @staticmethod
    def _extrair_codigo(nome_arquivo: str) -> Optional[int]:
        """Extrai o número entre parênteses no início do nome: (20) → 20."""
        m = _CODIGO_RE.match(nome_arquivo)
        if m:
            return int(m.group(1))
        return None


# ============================================
# CLASSE: Cliente da API
# ============================================

class APIClient:
    """Cliente para comunicação com a API do Radio Ads Manager."""

    def __init__(self, base_url: str, secret: Optional[str], timeout: float = 8.0, retries: int = 3):
        self.base_url = base_url
        self.timeout = timeout
        self.retries = max(1, retries)
        self.session = requests.Session()
        if secret:
            self.session.headers.update({"X-API-Key": secret})

    def _request_with_retry(self, method: str, url: str, **kwargs):
        last_exc: Optional[Exception] = None
        for attempt in range(1, self.retries + 1):
            try:
                response = self.session.request(
                    method, url,
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
        raise last_exc if last_exc else RuntimeError("Falha HTTP sem exceção registrada")

    def get_clientes_por_codigo(self, codigos: List[int]) -> Dict[int, int]:
        """
        Retorna um mapa {codigo_chamada: cliente_id} para os códigos informados.
        Só considera clientes ativos.
        """
        result: Dict[int, int] = {}
        for codigo in codigos:
            try:
                response = self._request_with_retry(
                    "GET",
                    f"{self.base_url}/clientes/",
                    params={"codigo_chamada": codigo, "status": "ativo", "limit": 1},
                )
                if response.status_code == 200:
                    clientes = response.json()
                    if clientes:
                        result[codigo] = clientes[0]["id"]
            except Exception as e:
                logger.error(f"Erro ao buscar cliente para código {codigo}: {e}")
        return result

    def create_veiculacoes_batch(self, payload: List[Dict]) -> Dict:
        """Cria várias veiculações em lote."""
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
            logger.warning("Erro na ingestão em lote: %s - %s", response.status_code, response.text[:200])
            return {"criadas": 0, "existentes": 0, "falhas": len(payload)}
        except Exception as e:
            logger.error(f"Falha no lote: {e}")
            return {"criadas": 0, "existentes": 0, "falhas": len(payload)}

    def check_health(self) -> bool:
        try:
            response = self._request_with_retry("GET", f"{self.base_url}/health", timeout=5)
            return response.status_code == 200
        except Exception:
            return False


# ============================================
# CLASSE: Monitor de Logs
# ============================================

class LogMonitor:
    """Monitor principal que coordena tudo."""

    def __init__(self, config: Config):
        self.config = config
        self.parser = ZaraLogParser(config)
        self.api_client = APIClient(
            config.API_BASE_URL,
            secret=config.MONITOR_SECRET,
            timeout=config.REQUEST_TIMEOUT,
            retries=config.REQUEST_RETRIES,
        )
        self.log_sources = config.parse_log_sources()
        self.veiculacoes_criadas = 0
        self.erros = 0
        self._dedupe_cache: set = set()
        self._codigo_para_cliente_cache: Dict[int, Optional[int]] = {}  # código → cliente_id ou None
        self._file_offsets: Dict[Tuple[str, str], int] = {}
        self._pending_events: Dict[Tuple[str, str], Dict] = {}
        self._load_offsets()

    def _load_offsets(self):
        """Carrega offsets persistidos do disco (sobrevive a restarts)."""
        try:
            with open(self.config.OFFSETS_FILE, "r", encoding="utf-8") as f:
                raw = json.load(f)
            # chave no JSON: "frequencia||filepath"
            for k, v in raw.items():
                partes = k.split("||", 1)
                if len(partes) == 2:
                    self._file_offsets[(partes[0], partes[1])] = int(v)
            logger.info(f"Offsets carregados: {len(self._file_offsets)} arquivo(s)")
        except FileNotFoundError:
            pass
        except Exception as e:
            logger.warning(f"Não foi possível carregar offsets: {e}")

    def _save_offsets(self):
        """Persiste offsets atuais no disco."""
        try:
            raw = {f"{k[0]}||{k[1]}": v for k, v in self._file_offsets.items()}
            with open(self.config.OFFSETS_FILE, "w", encoding="utf-8") as f:
                json.dump(raw, f)
        except Exception as e:
            logger.warning(f"Não foi possível salvar offsets: {e}")

    def _resolver_cliente(self, codigo: int) -> Optional[int]:
        """
        Resolve codigo_chamada → cliente_id usando cache.
        Retorna None se não houver cliente ativo com esse código.
        """
        if codigo in self._codigo_para_cliente_cache:
            return self._codigo_para_cliente_cache[codigo]

        mapa = self.api_client.get_clientes_por_codigo([codigo])
        cliente_id = mapa.get(codigo)
        self._codigo_para_cliente_cache[codigo] = cliente_id
        return cliente_id

    def process_log_file(self, filepath: str, date: datetime, frequencia: str, incremental: bool = False):
        logger.info(f"Processando arquivo: {filepath} (incremental={incremental})")
        key = (frequencia, filepath)
        propagandas: List[Dict] = []

        try:
            with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
                start_offset = self._file_offsets.get(key, 0) if incremental else 0
                if incremental:
                    tamanho_atual = os.path.getsize(filepath)
                    if start_offset > tamanho_atual:
                        start_offset = 0
                    f.seek(start_offset)

                for line in f:
                    propaganda = self.parser.parse_line(line, date, frequencia)
                    if propaganda:
                        propagandas.append(propaganda)

                self._file_offsets[key] = f.tell()
        except Exception as e:
            logger.error(f"Erro ao ler arquivo {filepath}: {e}")
            self.erros += 1
            return

        self._save_offsets()

        logger.info(f"Propagandas detectadas: {len(propagandas)}")
        if not propagandas:
            return

        self.create_veiculacoes_from_logs(propagandas)

    def create_veiculacoes_from_logs(self, propagandas: List[Dict]):
        """Cria veiculações em lote, determinando status_chamada e cliente_id."""
        payload: List[Dict] = []

        for propaganda in propagandas:
            nome_arquivo = propaganda["nome_arquivo"]
            codigo = propaganda.get("codigo_chamada")
            data_hora_iso = propaganda["data_hora"].isoformat()
            frequencia = propaganda.get("frequencia")

            # Dedupe por (nome_arquivo, data_hora, frequencia)
            dedupe_key = (nome_arquivo.lower(), data_hora_iso, frequencia)
            if dedupe_key in self._dedupe_cache:
                continue
            self._dedupe_cache.add(dedupe_key)

            item: Dict = {
                "data_hora": data_hora_iso,
                "frequencia": frequencia,
                "fonte": "zara_log",
                "nome_arquivo_raw": nome_arquivo,
            }

            if codigo is not None:
                item["codigo_chamada_raw"] = codigo
                cliente_id = self._resolver_cliente(codigo)
                if cliente_id is not None:
                    item["cliente_id"] = cliente_id
                    item["status_chamada"] = "verde"
                else:
                    item["status_chamada"] = "vermelho"
            else:
                item["status_chamada"] = "amarelo"

            payload.append(item)

        if not payload:
            return

        batch_size = max(1, self.config.INGEST_BATCH_SIZE)
        novas = 0
        for i in range(0, len(payload), batch_size):
            chunk = payload[i:i + batch_size]
            resultado = self.api_client.create_veiculacoes_batch(chunk)
            criadas = resultado.get("criadas", 0)
            self.veiculacoes_criadas += criadas
            novas += criadas
            self.erros += resultado.get("falhas", 0)

        if novas > 0:
            logger.info(f"{novas} veiculação(ões) nova(s) registrada(s).")

    def run_batch_mode(self):
        """Modo batch: Processa arquivos existentes e sai."""
        logger.info("Iniciando em modo BATCH")
        if not self.api_client.check_health():
            logger.error("API não está respondendo!")
            return
        logger.info("API online ✓")

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
                    date = datetime(
                        int(date_match.group(1)), int(date_match.group(2)), int(date_match.group(3))
                    ) if date_match else datetime.now()
                    self.process_log_file(str(log_file), date, frequencia)
                except Exception as e:
                    logger.error(f"Erro ao processar {log_file}: {e}")

        logger.info(f"BATCH concluído. Criadas: {self.veiculacoes_criadas} | Erros: {self.erros}")

    def run_watch_mode(self):
        """Modo watch: Monitora em tempo real."""
        logger.info("Iniciando em modo WATCH (monitoramento em tempo real)")
        if not self.api_client.check_health():
            logger.error("API não está respondendo!")
            return
        logger.info("API online ✓")

        # Scan inicial: processa arquivo de hoje antes de iniciar o watch
        hoje = datetime.now()
        nome_hoje = hoje.strftime("%Y-%m-%d.log")
        for frequencia, log_dir_raw in self.log_sources:
            log_path = Path(log_dir_raw) / nome_hoje
            if log_path.exists():
                logger.info(f"[scan inicial] {log_path} ({frequencia})")
                # incremental=True: se há offset salvo em disco, processa apenas conteúdo novo.
                # Se não há offset (primeiro run), start_offset=0 processa o arquivo completo.
                self.process_log_file(str(log_path), hoje, frequencia, incremental=True)
            else:
                logger.info(f"[scan inicial] Arquivo de hoje não encontrado: {log_path}")

        # Configurar watchdog
        observer = Observer()
        for frequencia, log_dir_raw in self.log_sources:
            if not Path(log_dir_raw).exists():
                logger.warning(f"Diretório não encontrado: {log_dir_raw}")
                continue
            event_handler = LogFileEventHandler(self, frequencia)
            observer.schedule(event_handler, log_dir_raw, recursive=False)
        observer.start()

        try:
            while True:
                time.sleep(1)
                self.flush_pending_file_events()
        except KeyboardInterrupt:
            logger.info("Parando monitor...")
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
                self.process_log_file(ev["filepath"], ev["date"], ev["frequencia"], incremental=True)
            except Exception as e:
                logger.error(f"Erro ao processar arquivo em debounce: {e}")


# ============================================
# CLASSE: Event Handler (Watchdog)
# ============================================

class LogFileEventHandler(FileSystemEventHandler):
    def __init__(self, monitor: LogMonitor, frequencia: str):
        self.monitor = monitor
        self.config = monitor.config
        self.frequencia = frequencia

    def on_modified(self, event):
        if event.is_directory:
            return
        if not re.match(self.config.LOG_FILE_PATTERN, os.path.basename(event.src_path)):
            return
        logger.info(f"Arquivo modificado: {event.src_path}")
        date_match = re.search(r"(\d{4})-(\d{2})-(\d{2})", event.src_path)
        date = datetime(
            int(date_match.group(1)), int(date_match.group(2)), int(date_match.group(3))
        ) if date_match else datetime.now()
        self.monitor.enqueue_file_event(event.src_path, date, self.frequencia)


# ============================================
# FUNÇÃO PRINCIPAL
# ============================================

def main():
    import argparse

    parser = argparse.ArgumentParser(description="Monitor de Logs do Zara Studio")
    parser.add_argument("mode", choices=["batch", "watch"])
    parser.add_argument("--log-sources", type=str)
    parser.add_argument("--api-url", type=str)
    args = parser.parse_args()

    config = Config()
    if args.log_sources:
        config.LOG_SOURCES = args.log_sources
    if args.api_url:
        config.API_BASE_URL = args.api_url

    if not config.MONITOR_SECRET:
        logger.warning("RADIO_ADS_MONITOR_SECRET não configurado — requisições à API podem falhar por falta de autenticação")

    monitor = LogMonitor(config)
    if args.mode == "batch":
        monitor.run_batch_mode()
    else:
        monitor.run_watch_mode()


if __name__ == "__main__":
    main()
