"""
routers/veiculacoes.py - Endpoints para gerenciar veiculações

Este arquivo gerencia o registro de veiculações (quando propagandas vão ao ar).
As veiculações são geralmente criadas automaticamente pelo monitor de logs,
mas estes endpoints permitem consultar, corrigir e processar manualmente.
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, or_
from typing import List, Optional
from datetime import datetime, date, timedelta

from app.database import get_db
from app import models, schemas


router = APIRouter(
    prefix="/veiculacoes",
    tags=["Veiculações"]
)


# ============================================
# ENDPOINT: Listar veiculações
# ============================================

@router.get("/", response_model=List[schemas.VeiculacaoResponse])
def listar_veiculacoes(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    data_inicio: Optional[date] = Query(None, description="Filtrar por data início"),
    data_fim: Optional[date] = Query(None, description="Filtrar por data fim"),
    cliente_id: Optional[int] = Query(None, description="Filtrar por cliente"),
    arquivo_id: Optional[int] = Query(None, description="Filtrar por arquivo"),
    tipo_programa: Optional[str] = Query(None, description="Filtrar por tipo de programa"),
    processado: Optional[bool] = Query(None, description="Filtrar por status de processamento"),
    db: Session = Depends(get_db)
):
    """
    Lista veiculações com filtros opcionais.
    
    Filtros úteis:
    - data_inicio e data_fim: Período
    - cliente_id: Veiculações de um cliente específico
    - processado: true/false - se já foi contabilizado no contrato
    - tipo_programa: musical, esporte, jornal, etc.
    
    Exemplo:
    GET /veiculacoes?data_inicio=2024-01-01&data_fim=2024-01-31&processado=false
    """
    query = db.query(models.Veiculacao)
    
    # Aplicar filtros
    if data_inicio:
        query = query.filter(models.Veiculacao.data_hora >= datetime.combine(data_inicio, datetime.min.time()))
    
    if data_fim:
        query = query.filter(models.Veiculacao.data_hora <= datetime.combine(data_fim, datetime.max.time()))
    
    if arquivo_id:
        query = query.filter(models.Veiculacao.arquivo_audio_id == arquivo_id)
    
    if cliente_id:
        # Join com arquivo_audio para filtrar por cliente
        query = query.join(models.ArquivoAudio).filter(
            models.ArquivoAudio.cliente_id == cliente_id
        )
    
    if tipo_programa:
        query = query.filter(models.Veiculacao.tipo_programa == tipo_programa)
    
    if processado is not None:
        query = query.filter(models.Veiculacao.processado == processado)
    
    # Ordenar por data (mais recentes primeiro)
    veiculacoes = query.order_by(models.Veiculacao.data_hora.desc()).offset(skip).limit(limit).all()
    
    return veiculacoes


# ============================================
# ENDPOINT: Buscar veiculação específica
# ============================================

@router.get("/{veiculacao_id}", response_model=schemas.VeiculacaoResponse)
def buscar_veiculacao(
    veiculacao_id: int,
    db: Session = Depends(get_db)
):
    """
    Busca uma veiculação específica pelo ID.
    
    Exemplo:
    GET /veiculacoes/1
    """
    veiculacao = db.query(models.Veiculacao).filter(
        models.Veiculacao.id == veiculacao_id
    ).first()
    
    if not veiculacao:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Veiculação com ID {veiculacao_id} não encontrada"
        )
    
    return veiculacao


# ============================================
# ENDPOINT: Criar veiculação manualmente
# ============================================

@router.post("/", response_model=schemas.VeiculacaoResponse, status_code=status.HTTP_201_CREATED)
def criar_veiculacao(
    veiculacao: schemas.VeiculacaoCreate,
    db: Session = Depends(get_db)
):
    """
    Cria uma veiculação manualmente.
    
    Normalmente as veiculações são criadas automaticamente pelo monitor de logs,
    mas este endpoint permite registro manual (ex: correções).
    
    Exemplo:
    POST /veiculacoes
    Body: {
        "arquivo_audio_id": 1,
        "data_hora": "2024-01-15T14:30:00",
        "tipo_programa": "musical",
        "fonte": "manual"
    }
    """
    # Verificar se arquivo existe
    arquivo = db.query(models.ArquivoAudio).filter(
        models.ArquivoAudio.id == veiculacao.arquivo_audio_id
    ).first()
    
    if not arquivo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Arquivo com ID {veiculacao.arquivo_audio_id} não encontrado"
        )
    
    # Criar veiculação
    db_veiculacao = models.Veiculacao(**veiculacao.model_dump())
    db.add(db_veiculacao)
    db.commit()
    db.refresh(db_veiculacao)
    
    return db_veiculacao


# ============================================
# ENDPOINT: Deletar veiculação
# ============================================

@router.delete("/{veiculacao_id}", response_model=schemas.MessageResponse)
def deletar_veiculacao(
    veiculacao_id: int,
    db: Session = Depends(get_db)
):
    """
    Deleta uma veiculação.
    
    ATENÇÃO: Se a veiculação já foi processada (contabilizada no contrato),
    será necessário reprocessar para ajustar os contadores.
    
    Exemplo:
    DELETE /veiculacoes/1
    """
    veiculacao = db.query(models.Veiculacao).filter(
        models.Veiculacao.id == veiculacao_id
    ).first()
    
    if not veiculacao:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Veiculação com ID {veiculacao_id} não encontrada"
        )
    
    foi_processada = veiculacao.processado
    
    db.delete(veiculacao)
    db.commit()
    
    mensagem = "Veiculação deletada com sucesso"
    if foi_processada:
        mensagem += " (ATENÇÃO: Veiculação já estava processada - reprocesse os contratos se necessário)"
    
    return {
        "message": mensagem,
        "success": True
    }


# ============================================
# ENDPOINT: Veiculações do dia
# ============================================

@router.get("/hoje/resumo")
def veiculacoes_hoje(
    db: Session = Depends(get_db)
):
    """
    Retorna resumo das veiculações do dia atual.
    
    Útil para dashboard e monitoramento em tempo real.
    
    Exemplo:
    GET /veiculacoes/hoje/resumo
    """
    hoje = date.today()
    inicio_dia = datetime.combine(hoje, datetime.min.time())
    fim_dia = datetime.combine(hoje, datetime.max.time())
    
    # Total de veiculações do dia
    total_hoje = db.query(models.Veiculacao).filter(
        models.Veiculacao.data_hora.between(inicio_dia, fim_dia)
    ).count()
    
    # Por tipo de programa
    por_tipo = db.query(
        models.Veiculacao.tipo_programa,
        func.count(models.Veiculacao.id)
    ).filter(
        models.Veiculacao.data_hora.between(inicio_dia, fim_dia)
    ).group_by(models.Veiculacao.tipo_programa).all()
    
    tipos_dict = {tipo or "não definido": count for tipo, count in por_tipo}
    
    # Por cliente (top 10)
    por_cliente = db.query(
        models.ArquivoAudio.cliente_id,
        models.Cliente.nome,
        func.count(models.Veiculacao.id).label('total')
    ).join(
        models.ArquivoAudio, models.Veiculacao.arquivo_audio_id == models.ArquivoAudio.id
    ).join(
        models.Cliente, models.ArquivoAudio.cliente_id == models.Cliente.id
    ).filter(
        models.Veiculacao.data_hora.between(inicio_dia, fim_dia)
    ).group_by(
        models.ArquivoAudio.cliente_id, models.Cliente.nome
    ).order_by(
        func.count(models.Veiculacao.id).desc()
    ).limit(10).all()
    
    clientes_list = [
        {"cliente_id": c_id, "cliente_nome": nome, "total": total}
        for c_id, nome, total in por_cliente
    ]
    
    # Não processadas
    nao_processadas = db.query(models.Veiculacao).filter(
        models.Veiculacao.data_hora.between(inicio_dia, fim_dia),
        models.Veiculacao.processado == False
    ).count()
    
    return {
        "data": hoje,
        "total_veiculacoes": total_hoje,
        "por_tipo_programa": tipos_dict,
        "top_10_clientes": clientes_list,
        "nao_processadas": nao_processadas
    }


# ============================================
# ENDPOINT: Processar veiculações
# ============================================

@router.post("/processar", response_model=schemas.MessageResponse)
def processar_veiculacoes(
    data_inicio: Optional[date] = Query(None, description="Data início (padrão: hoje)"),
    data_fim: Optional[date] = Query(None, description="Data fim (padrão: hoje)"),
    force: bool = Query(False, description="Reprocessar mesmo se já processado"),
    db: Session = Depends(get_db)
):
    """
    Processa veiculações não processadas, contabilizando-as nos contratos.
    
    O processamento faz:
    1. Identifica o contrato ativo do cliente
    2. Encontra o item do contrato correspondente ao tipo de programa
    3. Incrementa a quantidade_executada
    4. Marca a veiculação como processada
    
    Parâmetros:
    - data_inicio e data_fim: Período a processar (padrão: hoje)
    - force: Se true, reprocessa mesmo veiculações já processadas
    
    Exemplo:
    POST /veiculacoes/processar?data_inicio=2024-01-01&data_fim=2024-01-31
    """
    # Definir período (padrão: hoje)
    if not data_inicio:
        data_inicio = date.today()
    if not data_fim:
        data_fim = data_inicio
    
    inicio_periodo = datetime.combine(data_inicio, datetime.min.time())
    fim_periodo = datetime.combine(data_fim, datetime.max.time())
    
    # Buscar veiculações a processar
    query = db.query(models.Veiculacao).filter(
        models.Veiculacao.data_hora.between(inicio_periodo, fim_periodo)
    )
    
    if not force:
        query = query.filter(models.Veiculacao.processado == False)
    
    veiculacoes = query.all()
    
    if not veiculacoes:
        return {
            "message": f"Nenhuma veiculação para processar no período {data_inicio} a {data_fim}",
            "success": True
        }
    
    # Processar cada veiculação
    processadas = 0
    erros = 0
    
    for veiculacao in veiculacoes:
        try:
            # Buscar arquivo e cliente
            arquivo = veiculacao.arquivo_audio
            if not arquivo:
                erros += 1
                continue
            
            cliente_id = arquivo.cliente_id
            
            # Buscar contrato ativo do cliente no período da veiculação
            contrato = db.query(models.Contrato).filter(
                models.Contrato.cliente_id == cliente_id,
                models.Contrato.status_contrato == 'ativo',
                models.Contrato.data_inicio <= veiculacao.data_hora.date(),
                models.Contrato.data_fim >= veiculacao.data_hora.date()
            ).first()
            
            if not contrato:
                # Não tem contrato ativo, mas marca como processada mesmo assim
                veiculacao.processado = True
                veiculacao.contrato_id = None
                processadas += 1
                continue
            
            # Buscar item do contrato correspondente ao tipo de programa
            item = None
            if veiculacao.tipo_programa:
                item = db.query(models.ContratoItem).filter(
                    models.ContratoItem.contrato_id == contrato.id,
                    models.ContratoItem.tipo_programa == veiculacao.tipo_programa
                ).first()
            
            # Se não encontrou por tipo específico, pega o primeiro item
            if not item and contrato.itens:
                item = contrato.itens[0]
            
            if item:
                # Incrementar quantidade executada
                item.quantidade_executada += 1
            
            # Marcar como processada e associar ao contrato
            veiculacao.processado = True
            veiculacao.contrato_id = contrato.id
            processadas += 1
            
        except Exception as e:
            print(f"Erro ao processar veiculação {veiculacao.id}: {e}")
            erros += 1
    
    # Commit de todas as mudanças
    db.commit()
    
    return {
        "message": f"Processamento concluído: {processadas} veiculações processadas, {erros} erros",
        "success": True,
        "detalhes": {
            "periodo": f"{data_inicio} a {data_fim}",
            "total_veiculacoes": len(veiculacoes),
            "processadas": processadas,
            "erros": erros
        }
    }


# ============================================
# ENDPOINT: Estatísticas de veiculações
# ============================================

@router.get("/estatisticas/periodo")
def estatisticas_periodo(
    data_inicio: date = Query(..., description="Data início"),
    data_fim: date = Query(..., description="Data fim"),
    db: Session = Depends(get_db)
):
    """
    Retorna estatísticas detalhadas de veiculações em um período.
    
    Exemplo:
    GET /veiculacoes/estatisticas/periodo?data_inicio=2024-01-01&data_fim=2024-01-31
    """
    inicio_periodo = datetime.combine(data_inicio, datetime.min.time())
    fim_periodo = datetime.combine(data_fim, datetime.max.time())
    
    # Total de veiculações
    total = db.query(models.Veiculacao).filter(
        models.Veiculacao.data_hora.between(inicio_periodo, fim_periodo)
    ).count()
    
    # Por dia
    por_dia = db.query(
        func.date(models.Veiculacao.data_hora).label('data'),
        func.count(models.Veiculacao.id).label('total')
    ).filter(
        models.Veiculacao.data_hora.between(inicio_periodo, fim_periodo)
    ).group_by(
        func.date(models.Veiculacao.data_hora)
    ).all()
    
    dia_dict = {str(data): total for data, total in por_dia}
    
    # Por tipo de programa
    por_tipo = db.query(
        models.Veiculacao.tipo_programa,
        func.count(models.Veiculacao.id)
    ).filter(
        models.Veiculacao.data_hora.between(inicio_periodo, fim_periodo)
    ).group_by(models.Veiculacao.tipo_programa).all()
    
    tipo_dict = {tipo or "não definido": count for tipo, count in por_tipo}
    
    # Por cliente
    por_cliente = db.query(
        models.Cliente.nome,
        func.count(models.Veiculacao.id).label('total')
    ).join(
        models.ArquivoAudio, models.Veiculacao.arquivo_audio_id == models.ArquivoAudio.id
    ).join(
        models.Cliente, models.ArquivoAudio.cliente_id == models.Cliente.id
    ).filter(
        models.Veiculacao.data_hora.between(inicio_periodo, fim_periodo)
    ).group_by(
        models.Cliente.nome
    ).order_by(
        func.count(models.Veiculacao.id).desc()
    ).all()
    
    cliente_dict = {nome: total for nome, total in por_cliente}
    
    return {
        "periodo": {
            "inicio": data_inicio,
            "fim": data_fim
        },
        "total_veiculacoes": total,
        "media_por_dia": round(total / ((data_fim - data_inicio).days + 1), 2),
        "por_dia": dia_dict,
        "por_tipo_programa": tipo_dict,
        "por_cliente": cliente_dict
    }


# ============================================
# ENDPOINT: Veiculações detalhadas (com info completa)
# ============================================

@router.get("/detalhadas/lista", response_model=List[schemas.VeiculacaoDetalhada])
def listar_veiculacoes_detalhadas(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=500),
    data: Optional[date] = Query(None, description="Data específica (padrão: hoje)"),
    db: Session = Depends(get_db)
):
    """
    Lista veiculações com todas as informações (arquivo, cliente, contrato).
    
    Útil para relatórios e visualizações.
    
    Exemplo:
    GET /veiculacoes/detalhadas/lista?data=2024-01-15
    """
    if not data:
        data = date.today()
    
    inicio_dia = datetime.combine(data, datetime.min.time())
    fim_dia = datetime.combine(data, datetime.max.time())
    
    # Query com joins para pegar todas as informações
    veiculacoes = db.query(
        models.Veiculacao.id,
        models.Veiculacao.data_hora,
        models.Veiculacao.tipo_programa,
        models.Veiculacao.processado,
        models.ArquivoAudio.nome_arquivo.label('arquivo_nome'),
        models.ArquivoAudio.titulo.label('arquivo_titulo'),
        models.Cliente.nome.label('cliente_nome'),
        models.Contrato.numero_contrato
    ).join(
        models.ArquivoAudio, models.Veiculacao.arquivo_audio_id == models.ArquivoAudio.id
    ).join(
        models.Cliente, models.ArquivoAudio.cliente_id == models.Cliente.id
    ).outerjoin(
        models.Contrato, models.Veiculacao.contrato_id == models.Contrato.id
    ).filter(
        models.Veiculacao.data_hora.between(inicio_dia, fim_dia)
    ).order_by(
        models.Veiculacao.data_hora.desc()
    ).offset(skip).limit(limit).all()
    
    # Converter para lista de dicts
    resultado = [
        {
            "id": v.id,
            "data_hora": v.data_hora,
            "tipo_programa": v.tipo_programa,
            "processado": v.processado,
            "arquivo_nome": v.arquivo_nome,
            "arquivo_titulo": v.arquivo_titulo,
            "cliente_nome": v.cliente_nome,
            "numero_contrato": v.numero_contrato
        }
        for v in veiculacoes
    ]
    
    return resultado