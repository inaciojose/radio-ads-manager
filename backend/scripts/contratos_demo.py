"""
contratos_demo.py - Script de Demonstração para Contratos

Este script demonstra como usar os endpoints de contratos.
Certifique-se de que o servidor está rodando e que você já criou alguns clientes!
"""

import requests
import json
from datetime import datetime, timedelta, date

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
        print(json.dumps(response.json(), indent=2, ensure_ascii=False, default=str))
    except:
        print(response.text)


def test_criar_contratos():
    """Cria contratos de exemplo"""
    print_section("1. Criando Contratos de Teste")
    
    # Primeiro, vamos buscar os clientes existentes
    print("\nBuscando clientes existentes...")
    response = requests.get(f"{BASE_URL}/clientes/")
    
    if response.status_code != 200 or not response.json():
        print("❌ Nenhum cliente encontrado! Execute api_demo.py primeiro.")
        return []
    
    clientes = response.json()
    print(f"✅ Encontrados {len(clientes)} clientes")
    
    # Criar contratos para os primeiros 3 clientes
    contratos_criados = []
    hoje = date.today()
    
    contratos_exemplo = [
        {
            "cliente_id": clientes[0]["id"] if len(clientes) > 0 else 1,
            "data_inicio": str(hoje),
            "data_fim": str(hoje + timedelta(days=30)),
            "valor_total": 3000.00,
            "observacoes": "Pacote básico mensal",
            "itens": [
                {
                    "tipo_programa": "musical",
                    "quantidade_contratada": 30,
                    "observacoes": "Horário comercial"
                },
                {
                    "tipo_programa": "esporte",
                    "quantidade_contratada": 20
                }
            ]
        },
        {
            "cliente_id": clientes[1]["id"] if len(clientes) > 1 else 1,
            "data_inicio": str(hoje),
            "data_fim": str(hoje + timedelta(days=90)),
            "valor_total": 8000.00,
            "observacoes": "Pacote trimestral premium",
            "itens": [
                {
                    "tipo_programa": "musical",
                    "quantidade_contratada": 90,
                    "observacoes": "Horário nobre"
                },
                {
                    "tipo_programa": "jornal",
                    "quantidade_contratada": 60
                },
                {
                    "tipo_programa": "esporte",
                    "quantidade_contratada": 30
                }
            ]
        },
        {
            "cliente_id": clientes[2]["id"] if len(clientes) > 2 else 1,
            "data_inicio": str(hoje - timedelta(days=15)),  # Já começou há 15 dias
            "data_fim": str(hoje + timedelta(days=15)),     # Termina em 15 dias
            "valor_total": 1500.00,
            "status_nf": "emitida",
            "numero_nf": "NF-001/2024",
            "observacoes": "Pacote teste",
            "itens": [
                {
                    "tipo_programa": "musical",
                    "quantidade_contratada": 15
                }
            ]
        }
    ]
    
    for i, contrato_data in enumerate(contratos_exemplo):
        if i < len(clientes):  # Só cria se tiver cliente
            print(f"\nCriando contrato para: {clientes[i]['nome']}")
            response = requests.post(f"{BASE_URL}/contratos/", json=contrato_data)
            
            if response.status_code == 201:
                contrato = response.json()
                contratos_criados.append(contrato)
                print(f"✅ Contrato criado: {contrato['numero_contrato']}")
                print(f"   - ID: {contrato['id']}")
                print(f"   - Valor: R$ {contrato['valor_total']:.2f}")
                print(f"   - Itens: {len(contrato['itens'])}")
            else:
                print(f"❌ Erro ao criar contrato")
                print_response(response)
    
    return contratos_criados


def test_listar_contratos():
    """Lista todos os contratos"""
    print_section("2. Listando Todos os Contratos")
    
    response = requests.get(f"{BASE_URL}/contratos/")
    print_response(response)
    
    if response.status_code == 200:
        contratos = response.json()
        print(f"\n✅ Total de contratos: {len(contratos)}")
        
        for c in contratos:
            print(f"\n📋 {c['numero_contrato']}")
            print(f"   Cliente ID: {c['cliente_id']}")
            print(f"   Período: {c['data_inicio']} a {c['data_fim']}")
            print(f"   Status: {c['status_contrato']} | NF: {c['status_nf']}")
            print(f"   Itens: {len(c['itens'])}")
    
    return contratos if response.status_code == 200 else []


def test_buscar_contrato(contrato_id):
    """Busca um contrato específico"""
    print_section(f"3. Buscando Contrato ID: {contrato_id}")
    
    response = requests.get(f"{BASE_URL}/contratos/{contrato_id}")
    print_response(response)
    
    if response.status_code == 200:
        contrato = response.json()
        print(f"\n✅ Contrato encontrado: {contrato['numero_contrato']}")
        print(f"\n📊 Detalhes dos Itens:")
        for item in contrato['itens']:
            print(f"   - {item['tipo_programa']}: {item['quantidade_executada']}/{item['quantidade_contratada']} chamadas")
            print(f"     Progresso: {item['percentual_execucao']:.1f}%")


def test_filtros():
    """Testa os filtros de contratos"""
    print_section("4. Testando Filtros")
    
    print("\n4.1. Contratos ativos:")
    response = requests.get(f"{BASE_URL}/contratos/?status_contrato=ativo")
    if response.status_code == 200:
        print(f"Encontrados: {len(response.json())} contratos ativos")
    
    print("\n4.2. Notas fiscais pendentes:")
    response = requests.get(f"{BASE_URL}/contratos/?status_nf=pendente")
    if response.status_code == 200:
        contratos = response.json()
        print(f"Encontrados: {len(contratos)} contratos com NF pendente")
        for c in contratos:
            print(f"   - {c['numero_contrato']} | Cliente ID: {c['cliente_id']}")


def test_atualizar_nota_fiscal(contrato_id):
    """Testa atualização de nota fiscal"""
    print_section(f"5. Atualizando Nota Fiscal do Contrato {contrato_id}")
    
    hoje = date.today()
    
    response = requests.patch(
        f"{BASE_URL}/contratos/{contrato_id}/nota-fiscal",
        params={
            "status_nf": "emitida",
            "numero_nf": f"NF-TEST-{contrato_id}",
            "data_emissao": str(hoje)
        }
    )
    
    print_response(response)
    
    if response.status_code == 200:
        print("\n✅ Nota fiscal atualizada!")


def test_adicionar_item(contrato_id):
    """Adiciona um item a um contrato"""
    print_section(f"6. Adicionando Item ao Contrato {contrato_id}")
    
    novo_item = {
        "tipo_programa": "variedades",
        "quantidade_contratada": 10,
        "observacoes": "Item adicionado via teste"
    }
    
    print(f"Item a adicionar: {json.dumps(novo_item, indent=2)}")
    
    response = requests.post(
        f"{BASE_URL}/contratos/{contrato_id}/itens",
        json=novo_item
    )
    
    print_response(response)
    
    if response.status_code == 201:
        item = response.json()
        print(f"\n✅ Item adicionado com ID: {item['id']}")


def test_estatisticas():
    """Testa o endpoint de estatísticas"""
    print_section("7. Estatísticas Gerais dos Contratos")
    
    response = requests.get(f"{BASE_URL}/contratos/resumo/estatisticas")
    print_response(response)
    
    if response.status_code == 200:
        stats = response.json()
        print("\n📊 Resumo:")
        print(f"   Total de contratos: {stats['total_contratos']}")
        print(f"   Contratos ativos: {stats['contratos_ativos']}")
        print(f"   NFs pendentes: {stats['notas_fiscais_pendentes']}")
        print(f"   Vencendo em 30 dias: {stats['vencendo_30_dias']}")
        print(f"   Valor total (ativos): R$ {stats['valor_total_ativos']:.2f}")


def test_resumo_cliente(cliente_id):
    """Testa resumo de contratos por cliente"""
    print_section(f"8. Resumo dos Contratos do Cliente {cliente_id}")
    
    response = requests.get(f"{BASE_URL}/contratos/cliente/{cliente_id}/resumo")
    print_response(response)
    
    if response.status_code == 200:
        resumo = response.json()
        print(f"\n✅ Cliente: {resumo['cliente_nome']}")
        print(f"   Total de contratos: {resumo['total_contratos']}")
        print(f"   Contratos ativos: {resumo['contratos_ativos']}")
        print(f"   Chamadas: {resumo['chamadas_executadas']}/{resumo['chamadas_contratadas']}")
        print(f"   Conclusão: {resumo['percentual_conclusao']:.1f}%")


def main():
    """Função principal"""
    print("""
    ╔══════════════════════════════════════════════════════════╗
    ║         TESTE DE CONTRATOS - RADIO ADS MANAGER           ║
    ║                                                          ║
    ║  Este script testa os endpoints de contratos            ║
    ╚══════════════════════════════════════════════════════════╝
    """)
    
    try:
        # 1. Criar contratos
        contratos = test_criar_contratos()
        
        if not contratos:
            print("\n⚠️  Nenhum contrato foi criado. Verifique se há clientes cadastrados.")
            print("   Execute 'python scripts/api_demo.py' primeiro para criar clientes.")
            return
        
        # 2. Listar contratos
        todos_contratos = test_listar_contratos()
        
        if todos_contratos and len(todos_contratos) > 0:
            primeiro_contrato_id = todos_contratos[0]['id']
            primeiro_cliente_id = todos_contratos[0]['cliente_id']
            
            # 3. Buscar contrato específico
            test_buscar_contrato(primeiro_contrato_id)
            
            # 4. Testar filtros
            test_filtros()
            
            # 5. Atualizar nota fiscal
            test_atualizar_nota_fiscal(primeiro_contrato_id)
            
            # 6. Adicionar item
            test_adicionar_item(primeiro_contrato_id)
            
            # 7. Estatísticas
            test_estatisticas()
            
            # 8. Resumo por cliente
            test_resumo_cliente(primeiro_cliente_id)
        
        print_section("TESTES CONCLUÍDOS!")
        print("""
        ✅ Todos os testes de contratos foram executados!
        
        Próximos passos:
        1. Acesse http://localhost:8000/docs
        2. Explore os endpoints de contratos
        3. Teste criar contratos com diferentes configurações
        4. Próxima fase: Veiculações e integração com Zara Studio
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
