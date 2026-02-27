/**
 * contratos.js - CRUD de contratos.
 */

let contratosCache = []
const clientesPorIdCache = {}
const faturamentoResumoPorContrato = {}
const monitoramentoResumoPorContrato = {}

const contratosState = {
  page: 1,
  pageSize: 20,
  hasNext: false,
  searchTimer: null,
}

const contratoModalState = {
  arquivosCliente: [],
}

const faturamentoMensalState = {
  contratoId: null,
  contratoNumero: "",
}

async function loadContratos(page = 1) {
  const statusContrato = document.getElementById("filter-contrato-status")?.value
  const statusNf = document.getElementById("filter-contrato-nf")?.value
  const frequencia = document.getElementById("filter-contrato-frequencia")?.value
  const busca = (document.getElementById("search-contratos")?.value || "").trim()

  const targetPage = Math.max(1, page)
  const skip = (targetPage - 1) * contratosState.pageSize

  try {
    showLoading()
    const contratos = await api.getContratos({
      skip,
      limit: contratosState.pageSize,
      ...(statusContrato ? { status_contrato: statusContrato } : {}),
      ...(statusNf ? { status_nf: statusNf } : {}),
      ...(frequencia ? { frequencia } : {}),
      ...(busca ? { busca } : {}),
    })

    if (targetPage > 1 && contratos.length === 0) {
      await loadContratos(targetPage - 1)
      return
    }

    contratosCache = contratos
    contratosState.page = targetPage
    contratosState.hasNext = contratos.length === contratosState.pageSize

    await hydrateClientesNomes(contratos)
    await hydrateMonitoramentoResumo(contratos)
    await hydrateFaturamentoMensalResumo(contratos)
    renderContratos(contratos, clientesPorIdCache)
    updateContratosPagination()
  } catch (error) {
    showToast(error.message || "Erro ao carregar contratos", "error")
  } finally {
    hideLoading()
  }
}

async function hydrateMonitoramentoResumo(contratos) {
  const ids = [...new Set(contratos.map((c) => c.id))].filter(Boolean)
  if (!ids.length) return

  const resultados = await Promise.all(
    ids.map(async (contratoId) => {
      try {
        const resumo = await api.getContratoResumoMonitoramento(contratoId)
        return { contratoId, resumo }
      } catch {
        return { contratoId, resumo: null }
      }
    }),
  )

  for (const item of resultados) {
    monitoramentoResumoPorContrato[item.contratoId] = item.resumo
  }
}

function getProgressStack(resumo) {
  const totalMeta = resumo?.total?.meta || 0
  const totalExecutadas = resumo?.total?.executadas || 0
  const diariaMeta = resumo?.diario?.meta || 0
  const diariaExecutadas = resumo?.diario?.executadas || 0
  const blocos = []

  if (totalMeta > 0) {
    blocos.push(`<div>${getProgressBar(totalExecutadas, totalMeta)}</div>`)
  }
  if (diariaMeta > 0) {
    blocos.push(
      `<div class="contrato-progress-diario">
         <small>Hoje: ${diariaExecutadas}/${diariaMeta} (${(resumo.diario?.percentual || 0).toFixed(1)}%)</small>
       </div>`,
    )
  }

  if (!blocos.length) {
    return '<small class="text-muted">Sem metas definidas</small>'
  }

  return blocos.join("")
}

function getCompetenciaAtual() {
  const now = new Date()
  const mes = String(now.getMonth() + 1).padStart(2, "0")
  return `${now.getFullYear()}-${mes}`
}

async function hydrateFaturamentoMensalResumo(contratos) {
  const competenciaAtual = getCompetenciaAtual()
  const ids = [...new Set(
    contratos
      .filter((c) => c.nf_dinamica === "mensal")
      .map((c) => c.id),
  )].filter(Boolean)
  if (!ids.length) return

  const pendentes = ids.filter(
    (id) => !faturamentoResumoPorContrato[id] || faturamentoResumoPorContrato[id].competencia !== competenciaAtual,
  )
  if (!pendentes.length) return

  const resultados = await Promise.all(
    pendentes.map(async (contratoId) => {
      try {
        const itens = await api.getContratoFaturamentosMensais(contratoId, {
          competencia: competenciaAtual,
        })
        const atual = Array.isArray(itens) && itens.length ? itens[0] : null
        return { contratoId, atual, competencia: competenciaAtual }
      } catch {
        return { contratoId, atual: null, competencia: competenciaAtual }
      }
    }),
  )

  for (const item of resultados) {
    faturamentoResumoPorContrato[item.contratoId] = {
      competencia: item.competencia,
      atual: item.atual,
    }
  }
}

async function hydrateClientesNomes(contratos) {
  const clienteIds = [...new Set(contratos.map((c) => c.cliente_id))].filter(Boolean)
  const missingIds = clienteIds.filter((id) => !clientesPorIdCache[id])

  if (!missingIds.length) return

  const clientes = await Promise.all(missingIds.map((id) => api.getCliente(id)))
  for (const cliente of clientes) {
    clientesPorIdCache[cliente.id] = cliente.nome
  }
}

function renderContratos(items, clientesPorId) {
  const tbody = document.querySelector("#table-contratos tbody")
  if (!tbody) return
  const isUnauthenticated = !appState.user

  if (!items.length) {
    tbody.innerHTML = '<tr><td colspan="8" class="text-center">Sem contratos</td></tr>'
    return
  }

  tbody.innerHTML = items
    .map((c) => {
      const resumoMensal = faturamentoResumoPorContrato[c.id]
      const faturamentoAtual = resumoMensal?.atual || null
      const competenciaAtual = getCompetenciaAtual()
      const resumoMensalHtml = c.nf_dinamica === "mensal" && faturamentoAtual
        ? `<div class="contrato-nf-mensal">
             <small>Mês ${competenciaAtual}: ${getStatusBadge(faturamentoAtual.status_nf, "nf")}</small>
           </div>`
        : c.nf_dinamica === "mensal"
          ? `<div class="contrato-nf-mensal">
               <small>Mês ${competenciaAtual}: <span class="badge badge-secondary">Sem lançamento</span></small>
             </div>`
          : ""

      const monitoramentoResumo = monitoramentoResumoPorContrato[c.id]
      const sensitiveClass = isUnauthenticated ? "blur-unauth" : ""

      return `
      <tr>
        <td>${escapeHtml(c.numero_contrato || "-")}</td>
        <td>${escapeHtml(clientesPorId[c.cliente_id] || String(c.cliente_id))}</td>
        <td>
          ${formatDate(c.data_inicio)} a ${c.data_fim ? formatDate(c.data_fim) : "Sem prazo"}
          ${!c.data_fim ? '<div><span class="badge badge-info">Recorrente</span></div>' : ""}
        </td>
        <td>${getProgressStack(monitoramentoResumo)}</td>
        <td><span class="${sensitiveClass}">${formatCurrency(c.valor_total)}</span></td>
        <td>
          <div class="${sensitiveClass}">
            ${getStatusBadge(c.status_nf, "nf")}
            <div><small>Dinâmica: ${c.nf_dinamica === "mensal" ? "Mensal" : "Única"}</small></div>
            ${resumoMensalHtml}
          </div>
        </td>
        <td>${getStatusBadge(c.status_contrato, "contrato")}</td>
        <td>
          ${
            canWrite()
              ? `<button class="btn btn-sm btn-secondary" onclick="showContratoModal(${c.id})">Editar</button>
                 ${
                   c.nf_dinamica === "mensal"
                     ? `<button class="btn btn-sm btn-warning" onclick="showFaturamentoMensalModal(${c.id})">NFs</button>`
                     : `<button class="btn btn-sm btn-primary" onclick="showNotaFiscalModal(${c.id})">NF</button>`
                 }
                 <button class="btn btn-sm btn-danger" onclick="removerContrato(${c.id})">Excluir</button>`
              : '<span class="badge badge-secondary">Somente leitura</span>'
          }
        </td>
      </tr>
      `
    })
    .join("")
}

function updateContratosPagination() {
  const pageInfo = document.getElementById("contratos-page-info")
  const prevBtn = document.getElementById("contratos-prev")
  const nextBtn = document.getElementById("contratos-next")

  if (pageInfo) {
    pageInfo.textContent = `Página ${contratosState.page}`
  }
  if (prevBtn) {
    prevBtn.disabled = contratosState.page <= 1
  }
  if (nextBtn) {
    nextBtn.disabled = !contratosState.hasNext
  }
}

function changeContratosPage(delta) {
  if (delta > 0 && !contratosState.hasNext) return
  const target = Math.max(1, contratosState.page + delta)
  loadContratos(target)
}

function searchContratos() {
  clearTimeout(contratosState.searchTimer)
  contratosState.searchTimer = setTimeout(() => {
    loadContratos(1)
  }, 300)
}

function renderContratoItensEdit(itens) {
  const container = document.getElementById("contrato-itens-edit-list")
  if (!container) return

  if (!itens || !itens.length) {
    container.innerHTML = '<p class="text-center">Este contrato não possui itens.</p>'
    return
  }

  container.innerHTML = itens
    .map(
      (item) => `
      <div class="contrato-item-edit-row" data-item-id="${item.id}">
        <div class="form-row">
          <div class="form-group">
            <label>Tipo de Programa</label>
            <input type="text" class="contrato-item-tipo" value="${escapeHtml(item.tipo_programa || "")}" />
          </div>
          <div class="form-group">
            <label>Qtd Contratada</label>
            <input type="number" min="1" class="contrato-item-quantidade" value="${item.quantidade_contratada || ""}" />
          </div>
          <div class="form-group">
            <label>Meta Diária</label>
            <input type="number" min="1" class="contrato-item-meta-diaria" value="${item.quantidade_diaria_meta || ""}" />
          </div>
        </div>
        <div class="form-group">
          <label>Observações</label>
          <input type="text" class="contrato-item-observacoes" value="${escapeHtml(item.observacoes || "")}" />
        </div>
        <small>Executada: ${item.quantidade_executada || 0}</small>
      </div>
    `,
    )
    .join("")
}

function buildArquivoOptions(arquivos, selectedId = "") {
  const options = ['<option value="">Selecione o arquivo...</option>']
  for (const a of arquivos) {
    options.push(
      `<option value="${a.id}" ${String(selectedId) === String(a.id) ? "selected" : ""}>${escapeHtml(a.nome_arquivo)}</option>`,
    )
  }
  return options.join("")
}

function renderContratoMetasCreate() {
  const container = document.getElementById("contrato-metas-create-list")
  if (!container) return
  container.innerHTML = ""
  addContratoMetaCreateRow()
}

function addContratoMetaCreateRow(meta = null) {
  const container = document.getElementById("contrato-metas-create-list")
  if (!container) return
  const row = document.createElement("div")
  row.className = "contrato-meta-row"
  row.innerHTML = `
    <div class="form-row contrato-meta-grid">
      <div class="form-group">
        <label>Arquivo</label>
        <select class="contrato-meta-arquivo">
          ${buildArquivoOptions(contratoModalState.arquivosCliente, meta?.arquivo_audio_id)}
        </select>
      </div>
      <div class="form-group">
        <label>Meta</label>
        <input type="number" min="1" class="contrato-meta-quantidade" value="${meta?.quantidade_meta || ""}" />
      </div>
      <div class="form-group">
        <label>Modo</label>
        <select class="contrato-meta-modo">
          <option value="fixo" ${meta?.modo_veiculacao === "fixo" ? "selected" : ""}>Fixo</option>
          <option value="rodizio" ${meta?.modo_veiculacao === "rodizio" ? "selected" : ""}>Rodízio</option>
        </select>
      </div>
      <div class="form-group">
        <label>Ativo</label>
        <select class="contrato-meta-ativo">
          <option value="true" ${meta?.ativo === false ? "" : "selected"}>Sim</option>
          <option value="false" ${meta?.ativo === false ? "selected" : ""}>Não</option>
        </select>
      </div>
    </div>
    <div class="form-row contrato-meta-grid-footer">
      <div class="form-group">
        <label>Observações</label>
        <input type="text" class="contrato-meta-observacoes" value="${escapeHtml(meta?.observacoes || "")}" />
      </div>
      <div class="form-group contrato-meta-actions">
        <button type="button" class="btn btn-danger btn-sm" onclick="removeContratoMetaCreateRow(this)">Remover</button>
      </div>
    </div>
  `
  container.appendChild(row)
}

function removeContratoMetaCreateRow(btn) {
  const row = btn?.closest(".contrato-meta-row")
  if (!row) return
  row.remove()
}

async function onContratoClienteChange() {
  const clienteId = Number(document.getElementById("contrato-cliente")?.value)
  if (!clienteId) {
    contratoModalState.arquivosCliente = []
    renderContratoMetasCreate()
    return
  }

  try {
    contratoModalState.arquivosCliente = await api.getAllArquivos({
      cliente_id: clienteId,
    })
    renderContratoMetasCreate()
  } catch (error) {
    showToast(error.message || "Erro ao carregar arquivos do cliente", "error")
  }
}

function renderContratoMetasEdit(metas) {
  const container = document.getElementById("contrato-metas-edit-list")
  if (!container) return

  if (!metas?.length) {
    container.innerHTML = '<p class="text-center">Sem metas por arquivo.</p>'
    return
  }

  container.innerHTML = metas
    .map(
      (meta) => `
      <div class="contrato-meta-row contrato-meta-edit-row" data-meta-id="${meta.id}" data-delete="0">
        <div class="form-row contrato-meta-grid">
          <div class="form-group">
            <label>Arquivo</label>
            <select class="contrato-meta-arquivo" disabled>
              ${buildArquivoOptions(contratoModalState.arquivosCliente, meta.arquivo_audio_id)}
            </select>
          </div>
          <div class="form-group">
            <label>Meta</label>
            <input type="number" min="1" class="contrato-meta-quantidade" value="${meta.quantidade_meta || ""}" />
          </div>
          <div class="form-group">
            <label>Modo</label>
            <select class="contrato-meta-modo">
              <option value="fixo" ${meta.modo_veiculacao === "fixo" ? "selected" : ""}>Fixo</option>
              <option value="rodizio" ${meta.modo_veiculacao === "rodizio" ? "selected" : ""}>Rodízio</option>
            </select>
          </div>
          <div class="form-group">
            <label>Ativo</label>
            <select class="contrato-meta-ativo">
              <option value="true" ${meta.ativo ? "selected" : ""}>Sim</option>
              <option value="false" ${meta.ativo ? "" : "selected"}>Não</option>
            </select>
          </div>
        </div>
        <div class="form-row contrato-meta-grid-footer">
          <div class="form-group">
            <label>Observações</label>
            <input type="text" class="contrato-meta-observacoes" value="${escapeHtml(meta.observacoes || "")}" />
          </div>
          <div class="form-group contrato-meta-actions">
            <button type="button" class="btn btn-danger btn-sm" onclick="toggleContratoMetaDelete(this)">Excluir</button>
          </div>
        </div>
        <small class="contrato-meta-hint">Executada: ${meta.quantidade_executada || 0}</small>
      </div>
    `,
    )
    .join("")
}

function addContratoMetaEditRow() {
  const container = document.getElementById("contrato-metas-edit-list")
  if (!container) return
  if (container.querySelector(".text-center")) {
    container.innerHTML = ""
  }
  const row = document.createElement("div")
  row.className = "contrato-meta-row contrato-meta-edit-row"
  row.dataset.metaId = ""
  row.dataset.delete = "0"
  row.innerHTML = `
    <div class="form-row contrato-meta-grid">
      <div class="form-group">
        <label>Arquivo</label>
        <select class="contrato-meta-arquivo">
          ${buildArquivoOptions(contratoModalState.arquivosCliente)}
        </select>
      </div>
      <div class="form-group">
        <label>Meta</label>
        <input type="number" min="1" class="contrato-meta-quantidade" value="" />
      </div>
      <div class="form-group">
        <label>Modo</label>
        <select class="contrato-meta-modo">
          <option value="fixo">Fixo</option>
          <option value="rodizio">Rodízio</option>
        </select>
      </div>
      <div class="form-group">
        <label>Ativo</label>
        <select class="contrato-meta-ativo">
          <option value="true" selected>Sim</option>
          <option value="false">Não</option>
        </select>
      </div>
    </div>
    <div class="form-row contrato-meta-grid-footer">
      <div class="form-group">
        <label>Observações</label>
        <input type="text" class="contrato-meta-observacoes" value="" />
      </div>
      <div class="form-group contrato-meta-actions">
        <button type="button" class="btn btn-danger btn-sm" onclick="toggleContratoMetaDelete(this)">Excluir</button>
      </div>
    </div>
  `
  container.appendChild(row)
}

function toggleContratoMetaDelete(btn) {
  const row = btn?.closest(".contrato-meta-edit-row")
  if (!row) return
  if (!row.dataset.metaId) {
    row.remove()
    return
  }
  const deleting = row.dataset.delete === "1"
  row.dataset.delete = deleting ? "0" : "1"
  row.classList.toggle("is-deleting", !deleting)
  btn.textContent = deleting ? "Excluir" : "Desfazer"
  btn.classList.toggle("btn-secondary", !deleting)
  btn.classList.toggle("btn-danger", deleting)
}

async function showContratoModal(contratoId = null) {
  if (!requireWriteAccess()) return
  const modalTitle = document.getElementById("contrato-modal-title")
  const createItemSection = document.getElementById("contrato-item-create-section")
  const editItemSection = document.getElementById("contrato-item-edit-section")
  const createMetaSection = document.getElementById("contrato-meta-create-section")
  const editMetaSection = document.getElementById("contrato-meta-edit-section")
  const clienteSelect = document.getElementById("contrato-cliente")

  let contrato = null
  if (contratoId) {
    contrato = contratosCache.find((c) => c.id === Number(contratoId))
    if (!contrato) {
      contrato = await api.getContrato(contratoId)
    }
  }

  const isEdit = Boolean(contrato)
  modalTitle.textContent = isEdit ? "Editar Contrato" : "Novo Contrato"

  if (isEdit) {
    if (!contrato.itens?.length) {
      contrato = await api.getContrato(contrato.id)
    }
    contratoModalState.arquivosCliente = await api.getAllArquivos({
      cliente_id: contrato.cliente_id,
    })
    const metas = contrato.arquivos_metas?.length
      ? contrato.arquivos_metas
      : await api.getContratoArquivosMetas(contrato.id)

    clienteSelect.innerHTML = `<option value="${contrato.cliente_id}">${escapeHtml(
      clientesPorIdCache[contrato.cliente_id] || `Cliente ${contrato.cliente_id}`,
    )}</option>`
    clienteSelect.value = String(contrato.cliente_id)
    clienteSelect.disabled = true
    createItemSection.style.display = "none"
    editItemSection.style.display = "block"
    createMetaSection.style.display = "none"
    editMetaSection.style.display = "block"
    document.getElementById("contrato-nf-resumo-section").style.display = ""
    renderContratoItensEdit(contrato.itens || [])
    renderContratoMetasEdit(metas || [])
  } else {
    const clientes = await api.getAllClientes({ status: "ativo" })
    clienteSelect.innerHTML = [
      '<option value="">Selecione...</option>',
      ...clientes.map((c) => `<option value="${c.id}">${escapeHtml(c.nome)}</option>`),
    ].join("")
    clienteSelect.value = ""
    clienteSelect.disabled = false
    contratoModalState.arquivosCliente = []
    createItemSection.style.display = "block"
    editItemSection.style.display = "none"
    createMetaSection.style.display = "block"
    editMetaSection.style.display = "none"
    document.getElementById("contrato-nf-resumo-section").style.display = "none"
    renderContratoMetasCreate()
  }

  document.getElementById("contrato-id").value = contrato?.id || ""
  document.getElementById("contrato-data-inicio").value = contrato?.data_inicio || ""
  document.getElementById("contrato-data-fim").value = contrato?.data_fim || ""
  document.getElementById("contrato-frequencia").value = contrato?.frequencia || "ambas"
  document.getElementById("contrato-nf-dinamica").value = contrato?.nf_dinamica || "unica"
  document.getElementById("contrato-valor-total").value = contrato?.valor_total ?? ""
  document.getElementById("contrato-status-contrato").value =
    contrato?.status_contrato || "ativo"
  document.getElementById("contrato-status-nf").value = contrato?.status_nf || "pendente"
  document.getElementById("contrato-numero-nf").value = contrato?.numero_nf || ""
  document.getElementById("contrato-data-emissao-nf").value =
    contrato?.data_emissao_nf || ""
  document.getElementById("contrato-observacoes").value = contrato?.observacoes || ""

  document.getElementById("contrato-item-tipo").value = ""
  document.getElementById("contrato-item-quantidade").value = ""
  document.getElementById("contrato-item-meta-diaria").value = ""
  document.getElementById("contrato-item-observacoes").value = ""

  openModal("modal-contrato")
}

async function saveContrato() {
  if (!requireWriteAccess()) return
  const id = document.getElementById("contrato-id").value
  const isEdit = Boolean(id)

  const clienteId = Number(document.getElementById("contrato-cliente").value)
  const dataInicio = document.getElementById("contrato-data-inicio").value
  const dataFim = document.getElementById("contrato-data-fim").value
  const contratoFechado = Boolean(dataFim)

  if (!isEdit && !clienteId) {
    showToast("Selecione o cliente", "warning")
    return
  }
  if (!dataInicio) {
    showToast("Informe data de início", "warning")
    return
  }
  if (dataFim && new Date(dataFim) < new Date(dataInicio)) {
    showToast("Data fim não pode ser menor que data início", "warning")
    return
  }

  const basePayload = {
    data_inicio: dataInicio,
    data_fim: dataFim || null,
    frequencia: document.getElementById("contrato-frequencia").value,
    nf_dinamica: document.getElementById("contrato-nf-dinamica").value,
    valor_total:
      document.getElementById("contrato-valor-total").value === ""
        ? null
        : Number(document.getElementById("contrato-valor-total").value),
    status_contrato: document.getElementById("contrato-status-contrato").value,
    status_nf: isEdit ? document.getElementById("contrato-status-nf").value : "pendente",
    numero_nf: isEdit ? (document.getElementById("contrato-numero-nf").value.trim() || null) : null,
    data_emissao_nf: isEdit ? (document.getElementById("contrato-data-emissao-nf").value || null) : null,
    observacoes: document.getElementById("contrato-observacoes").value.trim() || null,
  }

  try {
    showLoading()
    if (isEdit) {
      const itemRows = Array.from(document.querySelectorAll(".contrato-item-edit-row"))
      const itensPayload = []
      for (const row of itemRows) {
        const itemId = row.dataset.itemId
        const tipoPrograma = row.querySelector(".contrato-item-tipo")?.value.trim()
        const quantidadeRaw = row.querySelector(".contrato-item-quantidade")?.value
        const metaDiariaRaw = row.querySelector(".contrato-item-meta-diaria")?.value
        const quantidade = quantidadeRaw ? Number(quantidadeRaw) : null
        const metaDiaria = metaDiariaRaw ? Number(metaDiariaRaw) : null

        if (!tipoPrograma) {
          throw new Error("Todos os itens devem ter tipo de programa")
        }
        if ((quantidade !== null && quantidade < 1) || (metaDiaria !== null && metaDiaria < 1)) {
          throw new Error("Metas de item devem ser maiores que 0")
        }
        if (quantidade === null && metaDiaria === null) {
          throw new Error("Cada item precisa de meta total, diária ou ambas")
        }
        if (contratoFechado && quantidade === null) {
          throw new Error("Contrato com data fim exige meta total em todos os itens")
        }
        if (!contratoFechado && metaDiaria === null) {
          throw new Error("Contrato sem data fim exige meta diária em todos os itens")
        }

        itensPayload.push({
          itemId,
          tipo_programa: tipoPrograma,
          quantidade_contratada: quantidade,
          quantidade_diaria_meta: metaDiaria,
          observacoes:
            row.querySelector(".contrato-item-observacoes")?.value.trim() || null,
        })
      }

      await api.updateContrato(id, basePayload)

      for (const item of itensPayload) {
        await api.updateContratoItem(id, item.itemId, {
          tipo_programa: item.tipo_programa,
          quantidade_contratada: item.quantidade_contratada,
          quantidade_diaria_meta: item.quantidade_diaria_meta,
          observacoes: item.observacoes,
        })
      }

      const metasRows = Array.from(
        document.querySelectorAll("#contrato-metas-edit-list .contrato-meta-edit-row"),
      )
      for (const row of metasRows) {
        const metaId = row.dataset.metaId
        const shouldDelete = row.dataset.delete === "1"

        if (shouldDelete) {
          if (metaId) {
            await api.deleteContratoArquivoMeta(id, metaId)
          }
          continue
        }

        const arquivoAudioId = Number(
          row.querySelector(".contrato-meta-arquivo")?.value,
        )
        const quantidadeMeta = Number(
          row.querySelector(".contrato-meta-quantidade")?.value,
        )
        const modoVeiculacao =
          row.querySelector(".contrato-meta-modo")?.value || "fixo"
        const ativo = row.querySelector(".contrato-meta-ativo")?.value === "true"
        const observacoes =
          row.querySelector(".contrato-meta-observacoes")?.value.trim() || null

        if (!arquivoAudioId || !quantidadeMeta || quantidadeMeta < 1) {
          throw new Error("Todas as metas precisam de arquivo e quantidade maior que 0")
        }

        if (metaId) {
          await api.updateContratoArquivoMeta(id, metaId, {
            quantidade_meta: quantidadeMeta,
            modo_veiculacao: modoVeiculacao,
            ativo,
            observacoes,
          })
        } else {
          await api.createContratoArquivoMeta(id, {
            arquivo_audio_id: arquivoAudioId,
            quantidade_meta: quantidadeMeta,
            modo_veiculacao: modoVeiculacao,
            ativo,
            observacoes,
          })
        }
      }

      showToast("Contrato atualizado", "success")
    } else {
      const itemTipo = document.getElementById("contrato-item-tipo").value.trim()
      const itemQuantidadeRaw = document.getElementById("contrato-item-quantidade").value
      const itemMetaDiariaRaw = document.getElementById("contrato-item-meta-diaria").value
      const itemQuantidade = itemQuantidadeRaw ? Number(itemQuantidadeRaw) : null
      const itemMetaDiaria = itemMetaDiariaRaw ? Number(itemMetaDiariaRaw) : null
      if (!itemTipo) {
        showToast("Informe o tipo de programa do item", "warning")
        return
      }
      if ((itemQuantidade !== null && itemQuantidade < 1) || (itemMetaDiaria !== null && itemMetaDiaria < 1)) {
        showToast("Metas do item devem ser maiores que 0", "warning")
        return
      }
      if (itemQuantidade === null && itemMetaDiaria === null) {
        showToast("Informe meta total, diária ou ambas no item", "warning")
        return
      }
      if (contratoFechado && itemQuantidade === null) {
        showToast("Contrato com data fim exige meta total", "warning")
        return
      }
      if (!contratoFechado && itemMetaDiaria === null) {
        showToast("Contrato sem data fim exige meta diária", "warning")
        return
      }

      await api.createContrato({
        cliente_id: clienteId,
        ...basePayload,
        itens: [
          {
            tipo_programa: itemTipo,
            quantidade_contratada: itemQuantidade,
            quantidade_diaria_meta: itemMetaDiaria,
            observacoes:
            document.getElementById("contrato-item-observacoes").value.trim() || null,
          },
        ],
        arquivos_metas: Array.from(
          document.querySelectorAll("#contrato-metas-create-list .contrato-meta-row"),
        )
          .map((row) => {
            const arquivoAudioId = Number(
              row.querySelector(".contrato-meta-arquivo")?.value,
            )
            const quantidadeMeta = Number(
              row.querySelector(".contrato-meta-quantidade")?.value,
            )
            const modoVeiculacao =
              row.querySelector(".contrato-meta-modo")?.value || "fixo"
            const ativo = row.querySelector(".contrato-meta-ativo")?.value === "true"
            const observacoes =
              row.querySelector(".contrato-meta-observacoes")?.value.trim() || null

            if (!arquivoAudioId && !quantidadeMeta) return null
            if (!arquivoAudioId || !quantidadeMeta || quantidadeMeta < 1) {
              throw new Error(
                "Metas por arquivo precisam de arquivo e quantidade maior que 0",
              )
            }

            return {
              arquivo_audio_id: arquivoAudioId,
              quantidade_meta: quantidadeMeta,
              modo_veiculacao: modoVeiculacao,
              ativo,
              observacoes,
            }
          })
          .filter(Boolean),
      })
      showToast("Contrato criado", "success")
    }

    closeModal()
    await loadContratos(contratosState.page)
  } catch (error) {
    showToast(error.message || "Erro ao salvar contrato", "error")
  } finally {
    hideLoading()
  }
}

async function showNotaFiscalModal(id) {
  if (!requireWriteAccess()) return
  const contrato = contratosCache.find((c) => c.id === Number(id)) || (await api.getContrato(id))
  if (!contrato) return
  if (contrato.nf_dinamica === "mensal") {
    await showFaturamentoMensalModal(contrato.id)
    return
  }

  const notas = await api.getContratoNotasFiscais(contrato.id, { tipo: "unica" })
  // Usa apenas a NF ativa; NFs canceladas ficam preservadas no banco mas não pré-preenchem o form
  const nota = Array.isArray(notas)
    ? (notas.find((n) => n.status !== "cancelada") ?? null)
    : null

  document.getElementById("nf-contrato-id").value = contrato.id
  document.getElementById("nf-nota-id").value = nota?.id || ""
  document.getElementById("nf-status").value = nota?.status || "pendente"
  // competencia vem como "YYYY-MM-DD"; input[type=month] espera "YYYY-MM"
  document.getElementById("nf-competencia").value = nota?.competencia ? nota.competencia.slice(0, 7) : ""
  document.getElementById("nf-numero-recibo").value = nota?.numero_recibo || ""
  document.getElementById("nf-numero").value = nota?.numero || contrato.numero_nf || ""
  document.getElementById("nf-serie").value = nota?.serie || ""
  document.getElementById("nf-data-emissao").value = nota?.data_emissao || contrato.data_emissao_nf || ""
  document.getElementById("nf-data-pagamento").value = nota?.data_pagamento || ""
  document.getElementById("nf-valor-bruto").value = nota?.valor_bruto ?? ""
  document.getElementById("nf-valor-liquido").value = nota?.valor_liquido ?? ""
  document.getElementById("nf-valor-pago").value = nota?.valor_pago ?? ""
  document.getElementById("nf-forma-pagamento").value = nota?.forma_pagamento || ""
  document.getElementById("nf-campanha-agentes").value = nota?.campanha_agentes || ""
  document.getElementById("nf-observacoes").value = nota?.observacoes || ""

  openModal("modal-nota-fiscal")
}

async function saveNotaFiscal() {
  if (!requireWriteAccess()) return
  const contratoId = Number(document.getElementById("nf-contrato-id").value)
  const notaId = Number(document.getElementById("nf-nota-id").value || 0)
  const status = document.getElementById("nf-status").value
  const competenciaMonth = document.getElementById("nf-competencia").value
  const numeroRecibo = document.getElementById("nf-numero-recibo").value.trim()
  const numero = document.getElementById("nf-numero").value.trim()
  const serie = document.getElementById("nf-serie").value.trim()
  const dataEmissao = document.getElementById("nf-data-emissao").value
  const dataPagamento = document.getElementById("nf-data-pagamento").value
  const valorBrutoRaw = document.getElementById("nf-valor-bruto").value
  const valorLiquidoRaw = document.getElementById("nf-valor-liquido").value
  const valorPagoRaw = document.getElementById("nf-valor-pago").value
  const formaPagamento = document.getElementById("nf-forma-pagamento").value
  const campanhaAgentes = document.getElementById("nf-campanha-agentes").value.trim()
  const observacoes = document.getElementById("nf-observacoes").value.trim()

  const payload = {
    status,
    competencia: competenciaMonth ? `${competenciaMonth}-01` : null,
    numero_recibo: numeroRecibo || null,
    numero: numero || null,
    serie: serie || null,
    data_emissao: dataEmissao || null,
    data_pagamento: dataPagamento || null,
    valor_bruto: valorBrutoRaw === "" ? null : Number(valorBrutoRaw),
    valor_liquido: valorLiquidoRaw === "" ? null : Number(valorLiquidoRaw),
    valor_pago: valorPagoRaw === "" ? null : Number(valorPagoRaw),
    forma_pagamento: formaPagamento || null,
    campanha_agentes: campanhaAgentes || null,
    observacoes: observacoes || null,
  }

  try {
    showLoading()
    if (notaId) {
      await api.updateNotaFiscalRegistro(notaId, payload)
    } else {
      await api.createContratoNotaFiscal(contratoId, { tipo: "unica", ...payload })
    }
    closeModal()
    showToast("Nota fiscal salva", "success")
    if (window._nfSaveCallback) {
      const cb = window._nfSaveCallback
      window._nfSaveCallback = null
      await cb()
    } else {
      await loadContratos(contratosState.page)
    }
  } catch (error) {
    showToast(error.message || "Erro ao salvar nota fiscal", "error")
  } finally {
    hideLoading()
  }
}

async function removerContrato(id) {
  if (!requireWriteAccess()) return
  if (!confirmAction("Deseja excluir este contrato?")) return

  try {
    showLoading()
    await api.deleteContrato(id)
    showToast("Contrato removido", "success")
    await loadContratos(contratosState.page)
  } catch (error) {
    showToast(error.message || "Erro ao excluir contrato", "error")
  } finally {
    hideLoading()
  }
}

function _getCompetenciaInputOrCurrent() {
  const input = document.getElementById("faturamento-competencia")
  const raw = (input?.value || "").trim()
  if (raw) return raw
  const now = new Date()
  const mes = String(now.getMonth() + 1).padStart(2, "0")
  const atual = `${now.getFullYear()}-${mes}`
  if (input) input.value = atual
  return atual
}

function _competenciaMonthToDateString(competenciaMonth) {
  return `${competenciaMonth}-01`
}

function _formatCompetencia(competenciaDate) {
  if (!competenciaDate) return "-"
  const raw = String(competenciaDate)
  const parts = raw.split("-")
  if (parts.length < 2) return raw
  return `${parts[1]}/${parts[0]}`
}

function _getStatusNfMensalBadge(status) {
  const map = {
    pendente: '<span class="badge badge-warning">Pendente</span>',
    emitida: '<span class="badge badge-info">Emitida</span>',
    paga: '<span class="badge badge-success">Paga</span>',
    cancelada: '<span class="badge badge-danger">Cancelada</span>',
  }
  return map[status] || escapeHtml(status || "-")
}

function _buildStatusMensalOptions(selected) {
  const opts = ["pendente", "emitida", "paga", "cancelada"]
  return opts
    .map(
      (status) =>
        `<option value="${status}" ${status === selected ? "selected" : ""}>${escapeHtml(status)}</option>`,
    )
    .join("")
}

async function showFaturamentoMensalModal(contratoId) {
  if (!requireWriteAccess()) return
  const contrato = contratosCache.find((c) => c.id === Number(contratoId)) || (await api.getContrato(contratoId))
  if (!contrato) {
    showToast("Contrato não encontrado", "error")
    return
  }
  if (contrato.nf_dinamica !== "mensal") {
    showToast("Este contrato usa NF única. Altere a dinâmica para mensal para usar histórico.", "warning")
    return
  }

  faturamentoMensalState.contratoId = contrato.id
  faturamentoMensalState.contratoNumero = contrato.numero_contrato || `#${contrato.id}`

  document.getElementById("faturamento-contrato-id").value = String(contrato.id)
  document.getElementById("faturamento-contrato-label").textContent = `Contrato ${faturamentoMensalState.contratoNumero}`
  document.getElementById("faturamento-filtro-status").value = ""
  _getCompetenciaInputOrCurrent()
  document.getElementById("faturamento-status-inicial").value = "pendente"
  document.getElementById("faturamento-numero-recibo").value = ""
  document.getElementById("faturamento-numero-nf").value = ""
  document.getElementById("faturamento-data-emissao").value = ""
  document.getElementById("faturamento-data-pagamento").value = ""
  document.getElementById("faturamento-valor-bruto").value = ""
  document.getElementById("faturamento-valor-liquido").value = ""
  document.getElementById("faturamento-valor-pago").value = ""
  document.getElementById("faturamento-forma-pagamento").value = ""
  document.getElementById("faturamento-campanha-agentes").value = ""
  document.getElementById("faturamento-observacoes").value = ""

  openModal("modal-faturamento-mensal")
  await loadFaturamentosMensais()
}

async function loadFaturamentosMensais() {
  const contratoId = Number(document.getElementById("faturamento-contrato-id")?.value)
  if (!contratoId) return

  const competencia = (document.getElementById("faturamento-competencia")?.value || "").trim()
  const statusNf = document.getElementById("faturamento-filtro-status")?.value

  try {
    showLoading()
    const items = await api.getContratoFaturamentosMensais(contratoId, {
      ...(competencia ? { competencia } : {}),
      ...(statusNf ? { status_nf: statusNf } : {}),
    })
    renderFaturamentosMensais(items || [])
  } catch (error) {
    showToast(error.message || "Erro ao carregar faturamentos mensais", "error")
  } finally {
    hideLoading()
  }
}

function renderFaturamentosMensais(items) {
  const tbody = document.querySelector("#table-faturamentos-mensais tbody")
  if (!tbody) return

  if (!items.length) {
    tbody.innerHTML = '<tr><td colspan="13" class="text-center">Sem faturamentos mensais</td></tr>'
    return
  }

  tbody.innerHTML = items
    .map(
      (f) => `
      <tr data-faturamento-id="${f.id}">
        <td>${_formatCompetencia(f.competencia)}</td>
        <td>${_getStatusNfMensalBadge(f.status)}</td>
        <td><input type="text" class="faturamento-numero-recibo" value="${escapeHtml(f.numero_recibo || "")}" placeholder="Recibo" /></td>
        <td><input type="text" class="faturamento-numero-nf" value="${escapeHtml(f.numero || "")}" /></td>
        <td><input type="date" class="faturamento-data-emissao" value="${f.data_emissao || ""}" /></td>
        <td><input type="date" class="faturamento-data-pagamento" value="${f.data_pagamento || ""}" /></td>
        <td><input type="number" min="0" step="0.01" class="faturamento-valor-bruto" value="${f.valor_bruto ?? ""}" /></td>
        <td><input type="number" min="0" step="0.01" class="faturamento-valor-liquido" value="${f.valor_liquido ?? ""}" /></td>
        <td><input type="number" min="0" step="0.01" class="faturamento-valor-pago" value="${f.valor_pago ?? ""}" /></td>
        <td>
          <select class="faturamento-forma-pagamento">
            <option value="">—</option>
            <option value="Caixa Seara" ${f.forma_pagamento === "Caixa Seara" ? "selected" : ""}>Caixa Seara</option>
            <option value="CC Banco do Brasil" ${f.forma_pagamento === "CC Banco do Brasil" ? "selected" : ""}>CC Banco do Brasil</option>
            <option value="CC Bradesco" ${f.forma_pagamento === "CC Bradesco" ? "selected" : ""}>CC Bradesco</option>
            <option value="Gerência Net" ${f.forma_pagamento === "Gerência Net" ? "selected" : ""}>Gerência Net</option>
          </select>
        </td>
        <td><input type="text" class="faturamento-campanha-agentes" value="${escapeHtml(f.campanha_agentes || "")}" placeholder="Campanha/Ag." /></td>
        <td>
          <select class="faturamento-status-nf">
            ${_buildStatusMensalOptions(f.status)}
          </select>
          <input type="text" class="faturamento-observacoes" value="${escapeHtml(f.observacoes || "")}" placeholder="Observações" />
        </td>
        <td>
          <button class="btn btn-sm btn-secondary" onclick="salvarFaturamentoMensal(${f.id})">Salvar</button>
          <button class="btn btn-sm btn-danger" onclick="excluirFaturamentoMensal(${f.id})">Excluir</button>
        </td>
      </tr>
    `,
    )
    .join("")
}

async function criarFaturamentoMensalManual() {
  if (!requireWriteAccess()) return
  const contratoId = Number(document.getElementById("faturamento-contrato-id")?.value)
  if (!contratoId) return

  const competencia = _getCompetenciaInputOrCurrent()
  const status = document.getElementById("faturamento-status-inicial")?.value || "pendente"
  const numeroRecibo = document.getElementById("faturamento-numero-recibo")?.value.trim() || null
  const numero = document.getElementById("faturamento-numero-nf")?.value.trim() || null
  const dataEmissao = document.getElementById("faturamento-data-emissao")?.value || null
  const dataPagamento = document.getElementById("faturamento-data-pagamento")?.value || null
  const valorBrutoRaw = document.getElementById("faturamento-valor-bruto")?.value
  const valorLiquidoRaw = document.getElementById("faturamento-valor-liquido")?.value
  const valorPagoRaw = document.getElementById("faturamento-valor-pago")?.value
  const formaPagamento = document.getElementById("faturamento-forma-pagamento")?.value || null
  const campanhaAgentes = document.getElementById("faturamento-campanha-agentes")?.value.trim() || null
  const observacoes = document.getElementById("faturamento-observacoes")?.value.trim() || null

  try {
    showLoading()
    await api.createContratoFaturamentoMensal(contratoId, {
      competencia: _competenciaMonthToDateString(competencia),
      status,
      numero_recibo: numeroRecibo,
      numero,
      data_emissao: dataEmissao,
      data_pagamento: dataPagamento,
      valor_bruto: valorBrutoRaw === "" ? null : Number(valorBrutoRaw),
      valor_liquido: valorLiquidoRaw === "" ? null : Number(valorLiquidoRaw),
      valor_pago: valorPagoRaw === "" ? null : Number(valorPagoRaw),
      forma_pagamento: formaPagamento,
      campanha_agentes: campanhaAgentes,
      observacoes,
    })
    showToast("Faturamento mensal criado", "success")
    await loadFaturamentosMensais()
  } catch (error) {
    showToast(error.message || "Erro ao criar faturamento mensal", "error")
  } finally {
    hideLoading()
  }
}

async function emitirNotaFiscalMensalAtual() {
  if (!requireWriteAccess()) return
  const contratoId = Number(document.getElementById("faturamento-contrato-id")?.value)
  if (!contratoId) return

  const competencia = _getCompetenciaInputOrCurrent()
  const numeroNf = document.getElementById("faturamento-numero-nf")?.value.trim()
  const dataEmissao = document.getElementById("faturamento-data-emissao")?.value || null
  const valorBrutoRaw = document.getElementById("faturamento-valor-bruto")?.value
  const observacoes = document.getElementById("faturamento-observacoes")?.value.trim() || null

  if (!numeroNf) {
    showToast("Informe o número da NF para emitir", "warning")
    return
  }

  try {
    showLoading()
    await api.emitirNotaFiscalMensal(contratoId, competencia, {
      numero_nf: numeroNf,
      data_emissao_nf: dataEmissao,
      valor_bruto: valorBrutoRaw === "" ? null : Number(valorBrutoRaw),
      observacoes,
    })
    showToast("NF mensal emitida", "success")
    await loadFaturamentosMensais()
  } catch (error) {
    showToast(error.message || "Erro ao emitir NF mensal", "error")
  } finally {
    hideLoading()
  }
}

async function salvarFaturamentoMensal(faturamentoId) {
  if (!requireWriteAccess()) return
  const row = document.querySelector(`tr[data-faturamento-id="${faturamentoId}"]`)
  if (!row) return

  const status = row.querySelector(".faturamento-status-nf")?.value || "pendente"
  const numeroRecibo = row.querySelector(".faturamento-numero-recibo")?.value.trim() || null
  const numero = row.querySelector(".faturamento-numero-nf")?.value.trim() || null
  const dataEmissao = row.querySelector(".faturamento-data-emissao")?.value || null
  const dataPagamento = row.querySelector(".faturamento-data-pagamento")?.value || null
  const valorBrutoRaw = row.querySelector(".faturamento-valor-bruto")?.value
  const valorLiquidoRaw = row.querySelector(".faturamento-valor-liquido")?.value
  const valorPagoRaw = row.querySelector(".faturamento-valor-pago")?.value
  const formaPagamento = row.querySelector(".faturamento-forma-pagamento")?.value || null
  const campanhaAgentes = row.querySelector(".faturamento-campanha-agentes")?.value.trim() || null
  const observacoes = row.querySelector(".faturamento-observacoes")?.value.trim() || null

  try {
    showLoading()
    await api.updateFaturamentoMensal(faturamentoId, {
      status,
      numero_recibo: numeroRecibo,
      numero,
      data_emissao: dataEmissao,
      data_pagamento: dataPagamento,
      valor_bruto: valorBrutoRaw === "" ? null : Number(valorBrutoRaw),
      valor_liquido: valorLiquidoRaw === "" ? null : Number(valorLiquidoRaw),
      valor_pago: valorPagoRaw === "" ? null : Number(valorPagoRaw),
      forma_pagamento: formaPagamento,
      campanha_agentes: campanhaAgentes,
      observacoes,
    })
    showToast("Faturamento mensal atualizado", "success")
    await loadFaturamentosMensais()
  } catch (error) {
    showToast(error.message || "Erro ao atualizar faturamento mensal", "error")
  } finally {
    hideLoading()
  }
}

async function excluirFaturamentoMensal(faturamentoId) {
  if (!requireWriteAccess()) return
  if (!confirmAction("Deseja excluir esta nota fiscal mensal?")) return
  try {
    showLoading()
    await api.deleteNotaFiscalRegistro(faturamentoId)
    showToast("Nota fiscal removida", "success")
    await loadFaturamentosMensais()
    await loadContratos(contratosState.page)
  } catch (error) {
    showToast(error.message || "Erro ao remover nota fiscal", "error")
  } finally {
    hideLoading()
  }
}
