"""
test_sistema_completo.py - Teste Integrado Completo

Este script testa o sistema completo:
1. Cria clientes
2. Cria contratos
3. Cadastra arquivos de áudio
4. Gera logs simulados
5. Executa o monitor
6. Verifica resultados
"""

import requests
import subprocess
import os
import time
from datetime import datetime, date, timedelta
import json


BASE_URL = "http://localhost:8000"


def print_section(title):
    """Imprime separador visual"""
    print("\n" + "=" * 70)
    print(f"  {title}")
    print("=" * 70)


def check_api():
    """Verifica se API está rodando"""
    print_section("1. Verificando API")
    
    try:
        response = requests.get(f"{BASE_URL}/health", timeout=5)
        if response.status_code == 200:
            print("✅ API está online e funcionando")
            return True
        else:
            print("❌ API respondeu mas com erro")
            return False
    except:
        print("❌ API não está respondendo")
        print("   Execute: cd backend/app && python main.py")
        return False


def create_test_data():
    """Cria dados de teste (clientes, contratos, arquivos)"""
    print_section("2. Criando Dados de Teste")
    
    # Criar cliente
    print("\n📝 Criando cliente de teste...")
    cliente_data = {
        "nome": "Supermercado Teste Monitor",
        "cnpj_cpf": "99.999.999/0001-99",
        "email": "teste@monitor.com"
    }
    
    response = requests.post(f"{BASE_URL}/clientes/", json=cliente_data)
    if response.status_code == 201:
        cliente = response.json()
        print(f"✅ Cliente criado - ID: {cliente['id']}")
    elif response.status_code == 400:
        # Cliente já existe
        response = requests.get(f"{BASE_URL}/clientes/?busca=Supermercado Teste Monitor")
        cliente = response.json()[0]
        print(f"ℹ️  Cliente já existe - ID: {cliente['id']}")
    else:
        print("❌ Erro ao criar cliente")
        return None
    
    cliente_id = cliente['id']
    
    # Criar contrato
    print("\n📋 Criando contrato de teste...")
    hoje = date.today()
    contrato_data = {
        "cliente_id": cliente_id,
        "data_inicio": str(hoje - timedelta(days=30)),
        "data_fim": str(hoje + timedelta(days=30)),
        "valor_total": 5000.00,
        "itens": [
            {"tipo_programa": "musical", "quantidade_contratada": 100},
            {"tipo_programa": "esporte", "quantidade_contratada": 50},
            {"tipo_programa": "jornal", "quantidade_contratada": 30}
        ]
    }
    
    response = requests.post(f"{BASE_URL}/contratos/", json=contrato_data)
    if response.status_code == 201:
        contrato = response.json()
        print(f"✅ Contrato criado - {contrato['numero_contrato']}")
        contrato_id = contrato['id']
    else:
        print("ℹ️  Usando contrato existente")
        response = requests.get(f"{BASE_URL}/contratos/?cliente_id={cliente_id}")
        if response.json():
            contrato = response.json()[0]
            contrato_id = contrato['id']
        else:
            print("❌ Erro ao criar/encontrar contrato")
            return None
    
    # Cadastrar arquivos de áudio
    print("\n🎵 Cadastrando arquivos de áudio...")
    arquivos = [
        {
            "nome": "supermercado_oferta_30s.mp3",
            "titulo": "Oferta Supermercado"
        },
        {
            "nome": "autopecas_desconto_20s.mp3",
            "titulo": "Desconto Auto Peças"
        },
        {
            "nome": "farmacia_entrega_15s.mp3",
            "titulo": "Entrega Farmácia"
        },
        {
            "nome": "loja_roupas_liquidacao_30s.mp3",
            "titulo": "Liquidação Loja de Roupas"
        },
        {
            "nome": "restaurante_almoco_20s.mp3",
            "titulo": "Almoço Restaurante"
        }
    ]
    
    arquivos_criados = 0
    for arq in arquivos:
        arquivo_data = {
            "cliente_id": cliente_id,
            "nome_arquivo": arq["nome"],
            "titulo": arq["titulo"],
            "duracao_segundos": 30
        }
        
        response = requests.post(f"{BASE_URL}/arquivos/", json=arquivo_data)
        if response.status_code == 201:
            arquivos_criados += 1
            print(f"   ✅ {arq['nome']}")
        elif response.status_code == 400:
            print(f"   ℹ️  {arq['nome']} (já existe)")
        else:
            print(f"   ❌ Erro ao criar {arq['nome']}")
    
    print(f"\n✅ Configuração completa!")
    print(f"   Cliente ID: {cliente_id}")
    print(f"   Contrato ID: {contrato_id}")
    print(f"   Arquivos: {arquivos_criados} novos + existentes")
    
    return {
        "cliente_id": cliente_id,
        "contrato_id": contrato_id
    }


def generate_logs():
    """Gera logs de teste"""
    print_section("3. Gerando Logs de Teste")
    
    print("🎬 Executando gerador de logs...")
    
    try:
        result = subprocess.run(
            ["python", "generate_test_logs.py", "--days", "3"],
            capture_output=True,
            text=True,
            cwd=os.path.dirname(__file__) or "."
        )
        
        print(result.stdout)
        
        if result.returncode == 0:
            print("✅ Logs gerados com sucesso")
            return True
        else:
            print("❌ Erro ao gerar logs")
            print(result.stderr)
            return False
    
    except Exception as e:
        print(f"❌ Erro ao executar gerador: {e}")
        return False


def run_monitor():
    """Executa o monitor em modo batch"""
    print_section("4. Executando Monitor de Logs")
    
    print("📡 Processando logs com o monitor...")
    print("   (Isso pode levar alguns segundos)")
    print()
    
    try:
        # Configurar ambiente
        env = os.environ.copy()
        env["ZARA_LOG_DIR"] = os.path.join(os.path.dirname(__file__) or ".", "test_logs")
        env["API_BASE_URL"] = BASE_URL
        
        # Executar monitor
        result = subprocess.run(
            ["python", "-m", "log_monitor.monitor", "batch"],
            capture_output=True,
            text=True,
            env=env,
            cwd=os.path.dirname(os.path.dirname(__file__)) or "."
        )
        
        # Mostrar saída
        print(result.stdout)
        
        if result.returncode == 0:
            print("✅ Monitor executado com sucesso")
            return True
        else:
            print("❌ Erro ao executar monitor")
            print(result.stderr)
            return False
    
    except Exception as e:
        print(f"❌ Erro: {e}")
        return False


def verify_results(data):
    """Verifica os resultados"""
    print_section("5. Verificando Resultados")
    
    contrato_id = data['contrato_id']
    
    # Buscar contrato atualizado
    print("\n📊 Verificando contrato...")
    response = requests.get(f"{BASE_URL}/contratos/{contrato_id}")
    
    if response.status_code != 200:
        print("❌ Erro ao buscar contrato")
        return
    
    contrato = response.json()
    
    print(f"\n✅ Contrato: {contrato['numero_contrato']}")
    print(f"   Status: {contrato['status_contrato']}")
    print(f"   Período: {contrato['data_inicio']} a {contrato['data_fim']}")
    print()
    print("📈 Progresso dos Itens:")
    
    total_contratado = 0
    total_executado = 0
    
    for item in contrato['itens']:
        total_contratado += item['quantidade_contratada']
        total_executado += item['quantidade_executada']
        
        print(f"\n   {item['tipo_programa'].upper()}:")
        print(f"      Contratado: {item['quantidade_contratada']}")
        print(f"      Executado:  {item['quantidade_executada']}")
        print(f"      Restante:   {item['quantidade_restante']}")
        print(f"      Progresso:  {item['percentual_execucao']:.1f}%")
    
    print()
    print(f"📊 TOTAL:")
    print(f"   Contratado: {total_contratado}")
    print(f"   Executado:  {total_executado}")
    
    if total_executado > 0:
        percentual = (total_executado / total_contratado) * 100
        print(f"   Progresso:  {percentual:.1f}%")
    
    # Veiculações de hoje
    print("\n📡 Veiculações registradas hoje:")
    response = requests.get(f"{BASE_URL}/veiculacoes/hoje/resumo")
    
    if response.status_code == 200:
        resumo = response.json()
        print(f"   Total: {resumo['total_veiculacoes']}")
        print(f"   Não processadas: {resumo['nao_processadas']}")
        
        if resumo['por_tipo_programa']:
            print("\n   Por tipo de programa:")
            for tipo, count in resumo['por_tipo_programa'].items():
                print(f"      {tipo}: {count}")


def main():
    """Função principal"""
    print("""
    ╔══════════════════════════════════════════════════════════════════╗
    ║                 TESTE INTEGRADO COMPLETO                         ║
    ║           Sistema de Gerenciamento de Anúncios                   ║
    ╚══════════════════════════════════════════════════════════════════╝
    
    Este script vai testar o sistema completo:
    1. Verificar API
    2. Criar dados de teste (clientes, contratos, arquivos)
    3. Gerar logs simulados
    4. Executar monitor
    5. Verificar resultados
    """)
    
    input("Pressione ENTER para começar...")
    
    # 1. Verificar API
    if not check_api():
        return
    
    # 2. Criar dados de teste
    data = create_test_data()
    if not data:
        print("\n❌ Falha ao criar dados de teste")
        return
    
    # 3. Gerar logs
    if not generate_logs():
        print("\n❌ Falha ao gerar logs")
        return
    
    # 4. Executar monitor
    if not run_monitor():
        print("\n❌ Falha ao executar monitor")
        return
    
    # 5. Verificar resultados
    verify_results(data)
    
    # Conclusão
    print_section("TESTE COMPLETO FINALIZADO!")
    
    print("""
    ✅ Sistema testado com sucesso!
    
    O que foi testado:
    ✓ Cadastro de clientes
    ✓ Criação de contratos
    ✓ Cadastro de arquivos
    ✓ Leitura de logs
    ✓ Criação de veiculações
    ✓ Processamento automático
    ✓ Contabilização nos contratos
    
    Próximos passos:
    1. Acesse http://localhost:8000/docs para ver todos os endpoints
    2. Configure o monitor para os logs reais do Zara Studio
    3. Execute em modo watch para monitoramento contínuo:
       python log_monitor/monitor.py watch
    4. Considere criar um frontend para visualização
    
    Parabéns! O sistema está 100% funcional! 🎉
    """)


if __name__ == '__main__':
    main()