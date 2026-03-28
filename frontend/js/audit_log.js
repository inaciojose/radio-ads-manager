/**
 * audit_log.js - Página de Audit Log
 */

let _auditLogTotal = 0

// ============================================
// Carregar e renderizar
// ============================================

async function loadAuditLog() {
  try {
    showLoading()
    const params = _buildAuditParams()
    const data = await api.getAuditLog(params)
    _auditLogTotal = data.total
    _renderAuditLogTable(data.items)
    _renderAuditLogSummary(data.items.length, data.total)
  } catch (error) {
    showToast(error.message || "Erro ao carregar audit log", "error")
  } finally {
    hideLoading()
  }
}

function filtrarAuditLog() {
  loadAuditLog()
}

function limparFiltrosAuditLog() {
  document.getElementById("audit-filtro-data-inicio").value = ""
  document.getElementById("audit-filtro-data-fim").value = ""
  document.getElementById("audit-filtro-area").value = ""
  document.getElementById("audit-filtro-acao").value = ""
  loadAuditLog()
}

function _buildAuditParams() {
  const params = {}
  const dataInicio = document.getElementById("audit-filtro-data-inicio")?.value
  const dataFim = document.getElementById("audit-filtro-data-fim")?.value
  const area = document.getElementById("audit-filtro-area")?.value
  const acao = document.getElementById("audit-filtro-acao")?.value

  if (dataInicio) params.data_inicio = dataInicio
  if (dataFim) params.data_fim = dataFim
  if (area) params.area = area
  if (acao) params.acao = acao

  return params
}

function _renderAuditLogSummary(shown, total) {
  const el = document.getElementById("audit-log-summary")
  if (!el) return
  if (total === 0) {
    el.textContent = "Nenhum registro encontrado."
  } else if (shown < total) {
    el.textContent = `Exibindo ${shown.toLocaleString("pt-BR")} de ${total.toLocaleString("pt-BR")} registros (limite de 1.000 por consulta).`
  } else {
    el.textContent = `${total.toLocaleString("pt-BR")} registro${total !== 1 ? "s" : ""} encontrado${total !== 1 ? "s" : ""}.`
  }
}

const _ACAO_CLASS = {
  criado: "audit-badge--criado",
  editado: "audit-badge--editado",
  excluído: "audit-badge--excluido",
  inativado: "audit-badge--inativado",
  cancelado: "audit-badge--cancelado",
}

function _renderAuditLogTable(items) {
  const tbody = document.getElementById("audit-log-tbody")
  if (!tbody) return

  if (!items.length) {
    tbody.innerHTML = '<tr><td colspan="6" class="text-center" style="color:#888; padding: 2rem;">Nenhum registro encontrado.</td></tr>'
    return
  }

  tbody.innerHTML = items
    .map((item) => {
      const dataHora = item.data_hora
        ? new Date(item.data_hora).toLocaleString("pt-BR")
        : "—"
      const acao = item.acao || "—"
      const badgeClass = _ACAO_CLASS[acao] || ""
      const registro = escapeHtml(item.registro_descricao || item.registro_id || "—")
      const detalhe = item.detalhe ? `<span class="audit-detalhe">${escapeHtml(item.detalhe)}</span>` : "—"

      return `<tr>
        <td class="audit-col-data">${escapeHtml(dataHora)}</td>
        <td>${escapeHtml(item.usuario_nome || "—")}</td>
        <td><span class="audit-area-badge">${escapeHtml(item.area || "—")}</span></td>
        <td><span class="audit-acao-badge ${badgeClass}">${escapeHtml(acao)}</span></td>
        <td>${registro}</td>
        <td>${detalhe}</td>
      </tr>`
    })
    .join("")
}

// ============================================
// Relatório (PDF / Excel)
// ============================================

function abrirRelatorioAuditLog() {
  openRelatorioModal("Audit Log", _auditLogTotal, exportarAuditLog)
}

async function exportarAuditLog(formato) {
  try {
    showLoading()
    const params = _buildAuditParams()
    if (formato === "excel") {
      await api.exportarAuditLogExcel(params)
    } else {
      await api.exportarAuditLogPdf(params)
    }
  } catch (error) {
    showToast(error.message || "Erro ao exportar relatório", "error")
  } finally {
    hideLoading()
  }
}
