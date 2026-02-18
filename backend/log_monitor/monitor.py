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
import requests
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import logging

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
    
    # Pasta onde o Zara Studio grava os logs
    # AJUSTE ESTE CAMINHO PARA O SEU AMBIENTE!
    LOG_DIR = os.getenv("ZARA_LOG_DIR", "/caminho/para/logs/zara")
    
    # Padrão do nome dos arquivos de log
    # Exemplo: zara_2024-01-15.log
    LOG_FILE_PATTERN = r"zara_\d{4}-\d{2}-\d{2}\.log"
    
    # Intervalo para processar veiculações (em segundos)
    PROCESS_INTERVAL = 300  # 5 minutos
    
    # Padrão de linha de log do Zara Studio
    # AJUSTE CONFORME O FORMATO DOS SEUS LOGS!
    # Exemplo de linha: "14:30:25 | PLAY | supermercado_oferta_30s.mp3 | Musical"
    LOG_LINE_PATTERN = r"(\d{2}:\d{2}:\d{2})\s*\|\s*PLAY\s*\|\s*([^\|]+)\s*\|\s*([^\|]+)"
    
    # Palavras-chave que indicam que é uma propaganda
    # Arquivos que contenham essas palavras serão considerados propagandas
    PROPAGANDA_KEYWORDS = ["comercial", "anuncio", "propaganda", "spot", "ad_"]
    
    # Palavras-chave que indicam que NÃO é propaganda (vinhetas, músicas, etc.)
    IGNORE_KEYWORDS = ["vinheta", "musica", "trilha", "jingle", "abertura", "passagem"]


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
        self.log_pattern = re.compile(config.LOG_LINE_PATTERN)
    
    def parse_file(self, filepath: str, date: datetime) -> List[Dict]:
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
            with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                for line_num, line in enumerate(f, 1):
                    try:
                        propaganda = self.parse_line(line, date)
                        if propaganda:
                            propagandas.append(propaganda)
                    except Exception as e:
                        logger.warning(f"Erro ao processar linha {line_num}: {e}")
                        continue
        
        except Exception as e:
            logger.error(f"Erro ao ler arquivo {filepath}: {e}")
        
        return propagandas
    
    def parse_line(self, line: str, date: datetime) -> Optional[Dict]:
        """
        Faz parse de uma linha do log.
        
        Args:
            line: Linha do arquivo de log
            date: Data base para construir datetime
        
        Returns:
            Dicionário com informações da propaganda ou None
        """
        match = self.log_pattern.match(line.strip())
        
        if not match:
            return None
        
        hora_str = match.group(1)  # Ex: "14:30:25"
        nome_arquivo = match.group(2).strip()  # Ex: "supermercado_oferta_30s.mp3"
        tipo_programa = match.group(3).strip()  # Ex: "Musical"
        
        # Verificar se é propaganda
        if not self.is_propaganda(nome_arquivo):
            return None
        
        # Construir datetime completo
        hora_parts = hora_str.split(':')
        data_hora = date.replace(
            hour=int(hora_parts[0]),
            minute=int(hora_parts[1]),
            second=int(hora_parts[2])
        )
        
        return {
            'nome_arquivo': nome_arquivo,
            'data_hora': data_hora,
            'tipo_programa': tipo_programa.lower()
        }
    
    def is_propaganda(self, nome_arquivo: str) -> bool:
        """
        Verifica se o arquivo é uma propaganda baseado no nome.
        
        Lógica:
        1. Se contém palavra de IGNORE → não é propaganda
        2. Se contém palavra de PROPAGANDA → é propaganda
        3. Se não tem nenhuma das duas → considera como propaganda (conservador)
        """
        nome_lower = nome_arquivo.lower()
        
        # Verificar palavras de exclusão
        for keyword in self.config.IGNORE_KEYWORDS:
            if keyword in nome_lower:
                return False
        
        # Verificar palavras que indicam propaganda
        for keyword in self.config.PROPAGANDA_KEYWORDS:
            if keyword in nome_lower:
                return True
        
        # Por padrão, considera como propaganda
        # (você pode mudar para False se preferir ser mais conservador)
        return True


# ============================================
# CLASSE: Cliente da API
# ============================================

class APIClient:
    """
    Cliente para comunicação com a API do Radio Ads Manager.
    """
    
    def __init__(self, base_url: str):
        self.base_url = base_url
        self.session = requests.Session()
    
    def get_arquivo_by_nome(self, nome_arquivo: str) -> Optional[Dict]:
        """
        Busca um arquivo de áudio pelo nome.
        
        Returns:
            Dicionário com dados do arquivo ou None se não encontrado
        """
        try:
            response = self.session.get(
                f"{self.base_url}/arquivos",
                params={"busca": nome_arquivo, "limit": 100}
            )
            
            if response.status_code == 200:
                arquivos = response.json()
                if arquivos:
                    nome_normalizado = nome_arquivo.strip().lower()
                    for arquivo in arquivos:
                        if str(arquivo.get("nome_arquivo", "")).strip().lower() == nome_normalizado:
                            return arquivo
            
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
                json=veiculacao_data
            )
            
            if response.status_code == 201:
                return response.json()
            else:
                logger.warning(f"Erro ao criar veiculação: {response.status_code} - {response.text}")
                return None
        
        except Exception as e:
            logger.error(f"Erro ao criar veiculação: {e}")
            return None
    
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
                }
            )
            
            if response.status_code == 200:
                logger.info(f"Veiculações processadas: {response.json()}")
                return True
            else:
                logger.warning(f"Erro ao processar veiculações: {response.status_code}")
                return False
        
        except Exception as e:
            logger.error(f"Erro ao processar veiculações: {e}")
            return False
    
    def check_health(self) -> bool:
        """Verifica se a API está online"""
        try:
            response = self.session.get(f"{self.base_url}/health", timeout=5)
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
        self.api_client = APIClient(config.API_BASE_URL)
        self.veiculacoes_criadas = 0
        self.erros = 0
        self.last_process_time = None
    
    def process_log_file(self, filepath: str, date: datetime):
        """
        Processa um arquivo de log completo.
        
        Args:
            filepath: Caminho do arquivo
            date: Data do arquivo
        """
        logger.info(f"Processando arquivo: {filepath}")
        
        # Parse do arquivo
        propagandas = self.parser.parse_file(filepath, date)
        logger.info(f"Encontradas {len(propagandas)} propagandas no arquivo")
        
        # Criar veiculações
        for propaganda in propagandas:
            self.create_veiculacao_from_log(propaganda)
        
        logger.info(f"Processamento concluído. Criadas: {self.veiculacoes_criadas}, Erros: {self.erros}")
    
    def create_veiculacao_from_log(self, propaganda: Dict):
        """
        Cria uma veiculação a partir dos dados do log.
        
        Args:
            propaganda: Dados extraídos do log
        """
        nome_arquivo = propaganda['nome_arquivo']
        
        # Buscar arquivo cadastrado na API
        arquivo = self.api_client.get_arquivo_by_nome(nome_arquivo)
        
        if not arquivo:
            logger.debug(f"Arquivo '{nome_arquivo}' não encontrado no cadastro - ignorando")
            return
        
        # Preparar dados da veiculação
        veiculacao_data = {
            'arquivo_audio_id': arquivo['id'],
            'data_hora': propaganda['data_hora'].isoformat(),
            'tipo_programa': propaganda['tipo_programa'],
            'fonte': 'zara_log'
        }
        
        # Criar veiculação
        veiculacao = self.api_client.create_veiculacao(veiculacao_data)
        
        if veiculacao:
            self.veiculacoes_criadas += 1
            logger.debug(f"Veiculação criada: {nome_arquivo} às {propaganda['data_hora']}")
        else:
            self.erros += 1
    
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
        logger.info(f"Diretório de logs: {self.config.LOG_DIR}")
        
        # Verificar se API está online
        if not self.api_client.check_health():
            logger.error("API não está respondendo! Certifique-se de que está rodando.")
            return
        
        logger.info("API online ✓")
        
        # Listar arquivos de log
        log_dir = Path(self.config.LOG_DIR)
        if not log_dir.exists():
            logger.error(f"Diretório de logs não existe: {self.config.LOG_DIR}")
            return
        
        log_files = sorted(log_dir.glob("*.log"))
        logger.info(f"Encontrados {len(log_files)} arquivos de log")
        
        # Processar cada arquivo
        for log_file in log_files:
            try:
                # Extrair data do nome do arquivo
                # Exemplo: zara_2024-01-15.log
                date_match = re.search(r'(\d{4})-(\d{2})-(\d{2})', log_file.name)
                if date_match:
                    date = datetime(
                        int(date_match.group(1)),
                        int(date_match.group(2)),
                        int(date_match.group(3))
                    )
                else:
                    # Se não conseguir extrair data, usa hoje
                    date = datetime.now()
                
                self.process_log_file(str(log_file), date)
            
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
        logger.info(f"Monitorando: {self.config.LOG_DIR}")
        logger.info("Pressione Ctrl+C para parar")
        
        # Verificar se API está online
        if not self.api_client.check_health():
            logger.error("API não está respondendo! Certifique-se de que está rodando.")
            return
        
        logger.info("API online ✓")
        
        # Configurar watchdog
        event_handler = LogFileEventHandler(self)
        observer = Observer()
        observer.schedule(event_handler, self.config.LOG_DIR, recursive=False)
        observer.start()
        
        try:
            while True:
                time.sleep(1)
                
                # Processar veiculações periodicamente
                if self.should_process_veiculacoes():
                    self.process_pending_veiculacoes()
        
        except KeyboardInterrupt:
            logger.info("\nParando monitor...")
            observer.stop()
        
        observer.join()
        logger.info("Monitor parado")


# ============================================
# CLASSE: Event Handler (Watchdog)
# ============================================

class LogFileEventHandler(FileSystemEventHandler):
    """
    Handler de eventos do watchdog.
    Detecta quando arquivos de log são modificados.
    """
    
    def __init__(self, monitor: LogMonitor):
        self.monitor = monitor
        self.config = monitor.config
    
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
        
        # Processar arquivo
        try:
            self.monitor.process_log_file(event.src_path, date)
        except Exception as e:
            logger.error(f"Erro ao processar arquivo: {e}")


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
  python monitor.py batch --log-dir /caminho/para/logs

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
        '--log-dir',
        type=str,
        help='Diretório dos logs do Zara Studio'
    )
    
    parser.add_argument(
        '--api-url',
        type=str,
        help='URL da API (padrão: http://localhost:8000)'
    )
    
    args = parser.parse_args()
    
    # Configurar
    config = Config()
    
    if args.log_dir:
        config.LOG_DIR = args.log_dir
    
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
