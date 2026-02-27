/**
 * notas_fiscais.js - Página de visão geral de notas fiscais
 */

const notasFiscaisState = {
  skip: 0,
  limit: 50,
  total: 0,
  sortBy: null,
  sortDir: "desc",
}

let notasFiscaisClientesCache = []
let _notasFiscaisItems = []

function _formatCompetenciaNota(competencia) {
  if (!competencia) return "-"
  const raw = String(competencia)
  const parts = raw.split("-")
  if (parts.length < 2) return raw
  return `${parts[1]}/${parts[0]}`
}

async function ensureNotasFiscaisClientesFiltro() {
  const select = document.getElementById("filter-nf-cliente")
  if (!select || notasFiscaisClientesCache.length) return

  try {
    const clientes = await api.getAllClientes({ status: "ativo" })
    notasFiscaisClientesCache = Array.isArray(clientes) ? clientes : []
    const options = notasFiscaisClientesCache
      .sort((a, b) => String(a.nome || "").localeCompare(String(b.nome || "")))
      .map((c) => `<option value="${c.id}">${escapeHtml(c.nome || `Cliente ${c.id}`)}</option>`)
      .join("")
    select.innerHTML = '<option value="">Todos os Clientes</option>' + options
  } catch (error) {
    console.error("Erro ao carregar clientes para filtro de NF:", error)
  }
}

function _buildNotasFiscaisParams() {
  const statusNf = document.getElementById("filter-nf-status")?.value || ""
  const clienteId = document.getElementById("filter-nf-cliente")?.value || ""
  const competenciaRaw = document.getElementById("filter-nf-competencia")?.value || ""

  return {
    skip: notasFiscaisState.skip,
    limit: notasFiscaisState.limit,
    ...(statusNf ? { status_nf: statusNf } : {}),
    ...(clienteId ? { cliente_id: clienteId } : {}),
    ...(competenciaRaw ? { competencia: competenciaRaw } : {}),
    ...(notasFiscaisState.sortBy
      ? { sort_by: notasFiscaisState.sortBy, sort_dir: notasFiscaisState.sortDir }
      : {}),
  }
}

function toggleNotasFiscaisSort(column) {
  if (notasFiscaisState.sortBy === column) {
    notasFiscaisState.sortDir = notasFiscaisState.sortDir === "asc" ? "desc" : "asc"
  } else {
    notasFiscaisState.sortBy = column
    notasFiscaisState.sortDir = "asc"
  }
  loadNotasFiscais()
}

function _updateNotasFiscaisSortHeaders() {
  document.querySelectorAll("#table-notas-fiscais th[data-sort-key]").forEach((th) => {
    const icon = th.querySelector("i")
    if (!icon) return
    if (th.dataset.sortKey === notasFiscaisState.sortBy) {
      icon.className = notasFiscaisState.sortDir === "asc" ? "fas fa-sort-up" : "fas fa-sort-down"
    } else {
      icon.className = "fas fa-sort"
    }
  })
}

function renderNotasFiscais(items) {
  _notasFiscaisItems = items
  _updateNotasFiscaisSortHeaders()
  const tbody = document.querySelector("#table-notas-fiscais tbody")
  if (!tbody) return

  if (!items.length) {
    tbody.innerHTML = '<tr><td colspan="7" class="text-center">Sem notas fiscais para os filtros atuais</td></tr>'
    return
  }

  tbody.innerHTML = items
    .map(
      (nf) => `
      <tr>
        <td>${escapeHtml(nf.cliente_nome || "-")}</td>
        <td>${escapeHtml(nf.contrato_numero || `#${nf.contrato_id}`)}</td>
        <td>${_formatCompetenciaNota(nf.competencia)}</td>
        <td>${formatCurrency(nf.valor_bruto)}</td>
        <td>${getStatusBadge(nf.status, "nf")}</td>
        <td>${escapeHtml(nf.numero || "-")}</td>
        <td>
          <button class="btn btn-sm btn-primary" onclick="editarNotaFiscalDireta(${nf.id})">
            <i class="fas fa-pen"></i> Editar
          </button>
          <button class="btn btn-sm btn-secondary" onclick="openContratoFromNotaFiscal(${nf.contrato_id})">
            Contrato
          </button>
        </td>
      </tr>
    `,
    )
    .join("")
}

function editarNotaFiscalDireta(notaId) {
  if (!requireWriteAccess()) return
  const nf = _notasFiscaisItems.find((n) => n.id === notaId)
  if (!nf) return

  document.getElementById("nf-contrato-id").value = nf.contrato_id
  document.getElementById("nf-nota-id").value = nf.id
  document.getElementById("nf-status").value = nf.status || "pendente"
  document.getElementById("nf-competencia").value = nf.competencia ? String(nf.competencia).slice(0, 7) : ""
  document.getElementById("nf-numero-recibo").value = nf.numero_recibo || ""
  document.getElementById("nf-numero").value = nf.numero || ""
  document.getElementById("nf-serie").value = nf.serie || ""
  document.getElementById("nf-data-emissao").value = nf.data_emissao || ""
  document.getElementById("nf-data-pagamento").value = nf.data_pagamento || ""
  document.getElementById("nf-valor-bruto").value = nf.valor_bruto ?? ""
  document.getElementById("nf-valor-liquido").value = nf.valor_liquido ?? ""
  document.getElementById("nf-valor-pago").value = nf.valor_pago ?? ""
  document.getElementById("nf-forma-pagamento").value = nf.forma_pagamento || ""
  document.getElementById("nf-campanha-agentes").value = nf.campanha_agentes || ""
  document.getElementById("nf-observacoes").value = nf.observacoes || ""

  // Após salvar, recarregar a listagem de NFs (não a de contratos)
  window._nfSaveCallback = () => loadNotasFiscais(false)

  openModal("modal-nota-fiscal")
}

function updateNotasFiscaisPagination() {
  const pageInfo = document.getElementById("notas-fiscais-page-info")
  const prevBtn = document.getElementById("notas-fiscais-prev")
  const nextBtn = document.getElementById("notas-fiscais-next")

  const paginaAtual = Math.floor(notasFiscaisState.skip / notasFiscaisState.limit) + 1
  const totalPaginas = Math.max(1, Math.ceil(notasFiscaisState.total / notasFiscaisState.limit))

  if (pageInfo) {
    pageInfo.textContent = `Página ${paginaAtual} de ${totalPaginas}`
  }

  if (prevBtn) prevBtn.disabled = notasFiscaisState.skip <= 0
  if (nextBtn) nextBtn.disabled = notasFiscaisState.skip + notasFiscaisState.limit >= notasFiscaisState.total
}

async function loadNotasFiscais(resetPagination = true) {
  if (!canWrite()) {
    showToast("Acesso restrito para visualizar notas fiscais.", "warning")
    showLoginModal()
    return
  }

  if (resetPagination) {
    notasFiscaisState.skip = 0
  }

  try {
    showLoading()
    await ensureNotasFiscaisClientesFiltro()
    const response = await api.getNotasFiscais(_buildNotasFiscaisParams())

    notasFiscaisState.total = Number(response?.total || 0)
    renderNotasFiscais(response?.items || [])
    updateNotasFiscaisPagination()
  } catch (error) {
    showToast(error.message || "Erro ao carregar notas fiscais", "error")
  } finally {
    hideLoading()
  }
}

function changeNotasFiscaisPage(direction) {
  const newSkip = notasFiscaisState.skip + direction * notasFiscaisState.limit
  if (newSkip < 0) return
  if (newSkip >= notasFiscaisState.total && direction > 0) return

  notasFiscaisState.skip = newSkip
  loadNotasFiscais(false)
}

async function openContratoFromNotaFiscal(contratoId) {
  showPage("contratos")
  await loadContratos(contratosState.page)
  await showContratoModal(contratoId)
}
