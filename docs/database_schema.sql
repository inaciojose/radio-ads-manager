-- ============================================
-- SCHEMA DO BANCO DE DADOS - RADIO ADS MANAGER
-- ============================================

-- TABELA: clientes
-- Armazena informações dos anunciantes/clientes da rádio
CREATE TABLE clientes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,  -- ID único do cliente (gerado automaticamente)
    nome VARCHAR(200) NOT NULL,            -- Nome ou razão social
    cnpj_cpf VARCHAR(18) UNIQUE,           -- CNPJ ou CPF (único, não pode repetir)
    email VARCHAR(100),                     -- Email de contato
    telefone VARCHAR(20),                   -- Telefone
    endereco TEXT,                          -- Endereço completo
    status VARCHAR(20) DEFAULT 'ativo',     -- Status: 'ativo' ou 'inativo'
    observacoes TEXT,                       -- Campo livre para anotações
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,  -- Data de cadastro
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP   -- Última atualização
);

-- TABELA: contratos
-- Representa os pacotes/contratos fechados com os clientes
CREATE TABLE contratos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    cliente_id INTEGER NOT NULL,            -- Qual cliente pertence este contrato
    numero_contrato VARCHAR(50) UNIQUE,     -- Número do contrato (ex: "2024/001")
    data_inicio DATE NOT NULL,              -- Quando o contrato começa
    data_fim DATE NOT NULL,                 -- Quando o contrato termina
    valor_total DECIMAL(10, 2),             -- Valor total do contrato
    status_contrato VARCHAR(20) DEFAULT 'ativo',  -- 'ativo', 'concluído', 'cancelado'
    status_nf VARCHAR(20) DEFAULT 'pendente',     -- 'pendente', 'emitida', 'paga'
    numero_nf VARCHAR(50),                  -- Número da nota fiscal (quando emitida)
    data_emissao_nf DATE,                   -- Data de emissão da NF
    observacoes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- Relacionamento: um contrato pertence a um cliente
    FOREIGN KEY (cliente_id) REFERENCES clientes(id) ON DELETE CASCADE
);

-- TABELA: contrato_itens
-- Detalhamento do que foi contratado (quantas chamadas de cada tipo)
CREATE TABLE contrato_itens (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    contrato_id INTEGER NOT NULL,
    tipo_programa VARCHAR(50) NOT NULL,     -- 'musical', 'esporte', 'jornal', 'variedades', etc.
    quantidade_contratada INTEGER NOT NULL, -- Quantas chamadas foram contratadas
    quantidade_executada INTEGER DEFAULT 0, -- Quantas já foram tocadas (atualizado automaticamente)
    observacoes TEXT,
    
    FOREIGN KEY (contrato_id) REFERENCES contratos(id) ON DELETE CASCADE
);

-- TABELA: arquivos_audio
-- Mapeia os arquivos de áudio das propagandas aos clientes
CREATE TABLE arquivos_audio (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    cliente_id INTEGER NOT NULL,
    nome_arquivo VARCHAR(255) NOT NULL,     -- Nome do arquivo (ex: "cliente_produto_30s.mp3")
    titulo VARCHAR(200),                    -- Título/descrição da propaganda
    duracao_segundos INTEGER,               -- Duração em segundos
    caminho_completo TEXT,                  -- Caminho completo no servidor
    ativo BOOLEAN DEFAULT 1,                -- Se está ativo para veiculação (1=sim, 0=não)
    data_upload TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    observacoes TEXT,
    
    FOREIGN KEY (cliente_id) REFERENCES clientes(id) ON DELETE CASCADE,
    
    -- Um arquivo não pode ter o mesmo nome duas vezes
    UNIQUE(nome_arquivo)
);

-- TABELA: veiculacoes
-- Registra cada vez que uma propaganda foi ao ar
CREATE TABLE veiculacoes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    arquivo_audio_id INTEGER NOT NULL,
    contrato_id INTEGER,                    -- Pode ser NULL se não conseguir identificar
    data_hora TIMESTAMP NOT NULL,           -- Quando foi ao ar
    tipo_programa VARCHAR(50),              -- Em qual programa tocou
    fonte VARCHAR(50) DEFAULT 'zara_log',   -- De onde veio a informação
    processado BOOLEAN DEFAULT 0,           -- Se já foi contabilizado no contrato
    
    FOREIGN KEY (arquivo_audio_id) REFERENCES arquivos_audio(id) ON DELETE CASCADE,
    FOREIGN KEY (contrato_id) REFERENCES contratos(id) ON DELETE SET NULL
);

-- ============================================
-- ÍNDICES PARA MELHORAR PERFORMANCE
-- ============================================
-- Índices são como "atalhos" no banco que tornam buscas mais rápidas

-- Buscar contratos por cliente
CREATE INDEX idx_contratos_cliente ON contratos(cliente_id);

-- Buscar itens de um contrato
CREATE INDEX idx_contrato_itens_contrato ON contrato_itens(contrato_id);

-- Buscar arquivos de um cliente
CREATE INDEX idx_arquivos_cliente ON arquivos_audio(cliente_id);

-- Buscar veiculações por arquivo
CREATE INDEX idx_veiculacoes_arquivo ON veiculacoes(arquivo_audio_id);

-- Buscar veiculações por data (muito usado em relatórios)
CREATE INDEX idx_veiculacoes_data ON veiculacoes(data_hora);

-- Buscar veiculações não processadas
CREATE INDEX idx_veiculacoes_processado ON veiculacoes(processado);

-- ============================================
-- VIEWS ÚTEIS (Consultas pré-definidas)
-- ============================================

-- VIEW: Resumo dos contratos com informações do cliente
CREATE VIEW view_contratos_resumo AS
SELECT 
    c.id as contrato_id,
    c.numero_contrato,
    cl.nome as cliente_nome,
    c.data_inicio,
    c.data_fim,
    c.valor_total,
    c.status_contrato,
    c.status_nf,
    -- Soma total de chamadas contratadas
    COALESCE(SUM(ci.quantidade_contratada), 0) as total_contratado,
    -- Soma total de chamadas já executadas
    COALESCE(SUM(ci.quantidade_executada), 0) as total_executado,
    -- Percentual de conclusão
    CASE 
        WHEN SUM(ci.quantidade_contratada) > 0 
        THEN ROUND(CAST(SUM(ci.quantidade_executada) AS FLOAT) / SUM(ci.quantidade_contratada) * 100, 2)
        ELSE 0 
    END as percentual_conclusao
FROM contratos c
LEFT JOIN clientes cl ON c.cliente_id = cl.id
LEFT JOIN contrato_itens ci ON c.id = ci.contrato_id
GROUP BY c.id;

-- VIEW: Veiculações do dia com informações completas
CREATE VIEW view_veiculacoes_hoje AS
SELECT 
    v.id,
    v.data_hora,
    a.nome_arquivo,
    a.titulo,
    cl.nome as cliente_nome,
    v.tipo_programa,
    c.numero_contrato,
    v.processado
FROM veiculacoes v
JOIN arquivos_audio a ON v.arquivo_audio_id = a.id
JOIN clientes cl ON a.cliente_id = cl.id
LEFT JOIN contratos c ON v.contrato_id = c.id
WHERE DATE(v.data_hora) = DATE('now')
ORDER BY v.data_hora DESC;

-- ============================================
-- DADOS INICIAIS (SEED)
-- ============================================

-- Inserir tipos de programa padrão (você pode adicionar mais depois)
-- Esta não é uma tabela, mas podemos criar uma se quiser ter tipos pré-definidos
-- Por enquanto, os tipos serão strings livres