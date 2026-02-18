"""
api_demo.py - Script de Demonstração da API

Este script demonstra como usar a API do Radio Ads Manager.
Execute este arquivo para criar dados de teste e ver como tudo funciona.

ATENÇÃO: Certifique-se de que o servidor está rodando antes de executar!
"""

import requests
import json
from datetime import datetime, timedelta

# URL base da API
BASE_URL = "http://localhost:8000"


def print_section(title):
    """Imprime um separador visual"""
    print("\n" + "=" * 60)
    print(f"  {title}")
    print("=" * 60)


def print_response(response):
    """Imprime a resposta da API de forma bonita"""
    print(f"Status: {response.status_code}")
    try:
        print(json.dumps(response.json(), indent=2, ensure_ascii=False))
    except:
        print(response.text)


def test_health():
    """Testa se a API está online"""
    print_section("1. Testando Health Check")
    
    response = requests.get(f"{BASE_URL}/health")
    print_response(response)
    
    if response.status_code == 200:
        print("✅ API está online e funcionando!")
    else:
        print("❌ API não está respondendo. Certifique-se de que está rodando.")
        exit(1)


def test_criar_clientes():
    """Cria alguns clientes de exemplo"""
    print_section("2. Criando Clientes de Teste")
    
    clientes = [
        {
            "nome": "Supermercado Bom Preço",
            "cnpj_cpf": "12.345.678/0001-90",
            "email": "contato@bompreco.com",
            "telefone": "(88) 3333-1111",
            "endereco": "Rua Principal, 100 - Centro",
            "status": "ativo"
        },
        {
            "nome": "Auto Peças Rápidas",
            "cnpj_cpf": "98.765.432/0001-10",
            "email": "vendas@autopecas.com",
            "telefone": "(88) 3333-2222",
            "status": "ativo"
        },
        {
            "nome": "Farmácia Saúde Total",
            "cnpj_cpf": "11.222.333/0001-44",
            "email": "contato@farmacia.com",
            "telefone": "(88) 3333-3333",
            "status": "ativo"
        }
    ]
    
    clientes_criados = []
    
    for cliente_data in clientes:
        print(f"\nCriando: {cliente_data['nome']}")
        response = requests.post(f"{BASE_URL}/clientes/", json=cliente_data)
        
        if response.status_code == 201:
            cliente = response.json()
            clientes_criados.append(cliente)
            print(f"✅ Cliente criado com ID: {cliente['id']}")
        elif response.status_code == 400:
            print(f"⚠️  Cliente já existe (provavelmente)")
        else:
            print(f"❌ Erro ao criar cliente: {response.status_code}")
            print_response(response)
    
    return clientes_criados


def test_listar_clientes():
    """Lista todos os clientes"""
    print_section("3. Listando Todos os Clientes")
    
    response = requests.get(f"{BASE_URL}/clientes/")
    print_response(response)
    
    if response.status_code == 200:
        clientes = response.json()
        print(f"\n✅ Total de clientes cadastrados: {len(clientes)}")
    
    return clientes if response.status_code == 200 else []


def test_buscar_cliente(cliente_id):
    """Busca um cliente específico"""
    print_section(f"4. Buscando Cliente ID: {cliente_id}")
    
    response = requests.get(f"{BASE_URL}/clientes/{cliente_id}")
    print_response(response)
    
    if response.status_code == 200:
        print("✅ Cliente encontrado!")
    elif response.status_code == 404:
        print("❌ Cliente não encontrado")


def test_atualizar_cliente(cliente_id):
    """Atualiza dados de um cliente"""
    print_section(f"5. Atualizando Cliente ID: {cliente_id}")
    
    update_data = {
        "telefone": "(88) 99999-9999",
        "observacoes": "Cliente VIP - atualizado pelo teste"
    }
    
    print(f"Dados a atualizar: {json.dumps(update_data, indent=2)}")
    
    response = requests.put(f"{BASE_URL}/clientes/{cliente_id}", json=update_data)
    print_response(response)
    
    if response.status_code == 200:
        print("✅ Cliente atualizado com sucesso!")


def test_filtros():
    """Testa os filtros de busca"""
    print_section("6. Testando Filtros de Busca")
    
    # Filtrar por status
    print("\n6.1. Filtrando clientes ativos:")
    response = requests.get(f"{BASE_URL}/clientes/?status=ativo")
    if response.status_code == 200:
        clientes = response.json()
        print(f"Encontrados: {len(clientes)} clientes ativos")
    
    # Buscar por nome
    print("\n6.2. Buscando 'Farmácia':")
    response = requests.get(f"{BASE_URL}/clientes/?busca=Farmácia")
    if response.status_code == 200:
        clientes = response.json()
        print(f"Encontrados: {len(clientes)} resultados")
        print_response(response)
    
    # Paginação
    print("\n6.3. Paginação (primeiros 2 registros):")
    response = requests.get(f"{BASE_URL}/clientes/?skip=0&limit=2")
    if response.status_code == 200:
        clientes = response.json()
        print(f"Retornados: {len(clientes)} clientes")


def test_resumo_cliente(cliente_id):
    """Testa o endpoint de resumo do cliente"""
    print_section(f"7. Resumo do Cliente ID: {cliente_id}")
    
    response = requests.get(f"{BASE_URL}/clientes/{cliente_id}/resumo")
    print_response(response)
    
    if response.status_code == 200:
        print("✅ Resumo gerado com sucesso!")


def test_deletar_cliente():
    """
    CUIDADO: Isso deleta um cliente!
    Vamos criar um cliente temporário só para deletar
    """
    print_section("8. Testando Deleção (Cliente Temporário)")
    
    # Criar cliente temporário
    cliente_temp = {
        "nome": "Cliente Temporário - PODE DELETAR",
        "cnpj_cpf": "99.999.999/0001-99",
        "email": "temp@temp.com"
    }
    
    print("Criando cliente temporário...")
    response = requests.post(f"{BASE_URL}/clientes/", json=cliente_temp)
    
    if response.status_code == 201:
        cliente = response.json()
        cliente_id = cliente['id']
        print(f"✅ Cliente temporário criado com ID: {cliente_id}")
        
        # Agora deletar
        print(f"\nDeletando cliente ID: {cliente_id}...")
        response = requests.delete(f"{BASE_URL}/clientes/{cliente_id}")
        print_response(response)
        
        if response.status_code == 200:
            print("✅ Cliente deletado com sucesso!")
    else:
        print("❌ Não foi possível criar cliente temporário")


def main():
    """Função principal que executa todos os testes"""
    print("""
    ╔══════════════════════════════════════════════════════════╗
    ║         TESTE DA API - RADIO ADS MANAGER                 ║
    ║                                                          ║
    ║  Este script vai testar todos os endpoints de clientes  ║
    ║  e criar alguns dados de exemplo.                       ║
    ╚══════════════════════════════════════════════════════════╝
    """)
    
    try:
        # 1. Verificar se API está online
        test_health()
        
        # 2. Criar clientes de teste
        clientes_criados = test_criar_clientes()
        
        # 3. Listar todos os clientes
        todos_clientes = test_listar_clientes()
        
        if todos_clientes and len(todos_clientes) > 0:
            primeiro_cliente_id = todos_clientes[0]['id']
            
            # 4. Buscar cliente específico
            test_buscar_cliente(primeiro_cliente_id)
            
            # 5. Atualizar cliente
            test_atualizar_cliente(primeiro_cliente_id)
            
            # 6. Testar filtros
            test_filtros()
            
            # 7. Resumo do cliente
            test_resumo_cliente(primeiro_cliente_id)
        
        # 8. Testar deleção
        test_deletar_cliente()
        
        print_section("TESTES CONCLUÍDOS!")
        print("""
        ✅ Todos os testes foram executados!
        
        Próximos passos:
        1. Acesse http://localhost:8000/docs para ver a documentação interativa
        2. Explore os clientes criados através da API
        3. Continue o desenvolvimento adicionando contratos e veiculações
        """)
        
    except requests.exceptions.ConnectionError:
        print("\n❌ ERRO: Não foi possível conectar à API!")
        print("Certifique-se de que o servidor está rodando:")
        print("  cd backend")
        print("  python -m app.main")
    except Exception as e:
        print(f"\n❌ ERRO: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
