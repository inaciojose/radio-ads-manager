/**
 * responsaveis.js - CRUD de Responsáveis
 */

let responsaveisCache = []

// ============================================
// Carregar e renderizar
// ============================================

async function loadResponsaveis() {
  const statusFiltro = document.getElementById("filter-responsavel-status")?.value
  try {
    showLoading()
    responsaveisCache = await api.getResponsaveis(statusFiltro ? { status: statusFiltro } : {})
    renderResponsaveis(responsaveisCache)
  } catch (error) {
    showToast(error.message || "Erro ao carregar responsáveis", "error")
  } finally {
    hideLoading()
  }
}

function renderResponsaveis(items) {
  const tbody = document.querySelector("#table-responsaveis tbody")
  if (!tbody) return

  if (!items.length) {
    tbody.innerHTML = '<tr><td colspan="4" class="text-center">Nenhum responsável encontrado</td></tr>'
    return
  }

  tbody.innerHTML = items
    .map((r) => {
      const acoes = canWrite()
        ? `<button class="btn btn-sm btn-secondary" onclick="editarResponsavel(${r.id})">Editar</button>
           ${
             r.status === "ativo"
               ? `<button class="btn btn-sm btn-warning" onclick="toggleStatusResponsavel(${r.id}, 'inativo')">Inativar</button>`
               : `<button class="btn btn-sm btn-success" onclick="toggleStatusResponsavel(${r.id}, 'ativo')">Ativar</button>`
           }`
        : '<span class="badge badge-secondary">Somente leitura</span>'

      return `
        <tr>
          <td>${escapeHtml(r.nome)}</td>
          <td>${escapeHtml(r.telefone || "-")}</td>
          <td>${getStatusBadge(r.status, "responsavel")}</td>
          <td>${acoes}</td>
        </tr>`
    })
    .join("")
}

function searchResponsaveis() {
  const termo = (document.getElementById("search-responsaveis")?.value || "").trim().toLowerCase()
  if (!termo) {
    renderResponsaveis(responsaveisCache)
    return
  }
  renderResponsaveis(
    responsaveisCache.filter((r) => r.nome.toLowerCase().includes(termo))
  )
}

// ============================================
// Modal: criar / editar
// ============================================

function showResponsavelModal(responsavel = null) {
  if (!requireWriteAccess()) return

  document.getElementById("responsavel-modal-title").textContent = responsavel
    ? "Editar Responsável"
    : "Novo Responsável"

  document.getElementById("responsavel-id").value = responsavel?.id || ""
  document.getElementById("responsavel-nome").value = responsavel?.nome || ""
  document.getElementById("responsavel-telefone").value = maskTelefone(responsavel?.telefone || "")

  const statusGroup = document.getElementById("responsavel-status-group")
  if (statusGroup) {
    statusGroup.style.display = responsavel ? "block" : "none"
  }
  if (responsavel) {
    document.getElementById("responsavel-status").value = responsavel.status || "ativo"
  }

  openModal("modal-responsavel")
}

async function saveResponsavel() {
  if (!requireWriteAccess()) return

  const id = document.getElementById("responsavel-id").value
  const nome = document.getElementById("responsavel-nome").value.trim()
  const telefone = document.getElementById("responsavel-telefone").value.trim() || null

  if (!nome) {
    showToast("Nome é obrigatório", "warning")
    return
  }

  const payload = { nome, telefone }
  if (id) {
    payload.status = document.getElementById("responsavel-status").value
  }

  try {
    showLoading()
    if (id) {
      await api.updateResponsavel(id, payload)
      showToast("Responsável atualizado", "success")
    } else {
      await api.createResponsavel(payload)
      showToast("Responsável criado", "success")
    }
    closeModal()
    await loadResponsaveis()
  } catch (error) {
    showToast(error.message || "Erro ao salvar responsável", "error")
  } finally {
    hideLoading()
  }
}

function editarResponsavel(id) {
  const responsavel = responsaveisCache.find((r) => r.id === id)
  if (!responsavel) return
  showResponsavelModal(responsavel)
}

async function toggleStatusResponsavel(id, novoStatus) {
  if (!requireWriteAccess()) return
  const acao = novoStatus === "inativo" ? "inativar" : "ativar"
  if (!confirmAction(`Deseja ${acao} este responsável?`)) return

  try {
    showLoading()
    await api.updateResponsavel(id, { status: novoStatus })
    showToast(`Responsável ${novoStatus === "inativo" ? "inativado" : "ativado"}`, "success")
    await loadResponsaveis()
  } catch (error) {
    showToast(error.message || "Erro ao alterar status", "error")
  } finally {
    hideLoading()
  }
}

// ============================================
// Integração com Contratos (uso futuro)
// ============================================

/**
 * Retorna <option> tags dos responsáveis ativos para selects de contratos.
 * @param {string|number} [selected] - id atualmente selecionado
 */
function getResponsavelSelectOptions(selected = "") {
  const ativos = responsaveisCache.filter((r) => r.status === "ativo")
  return ativos
    .map(
      (r) =>
        `<option value="${r.id}"${String(r.id) === String(selected) ? " selected" : ""}>${escapeHtml(r.nome)}</option>`,
    )
    .join("")
}

/**
 * Garante que o cache de responsáveis está carregado (sem exibir loading global).
 */
async function ensureResponsaveisLoaded() {
  if (!responsaveisCache.length) {
    try {
      responsaveisCache = await api.getResponsaveis({ status: "ativo" })
    } catch {
      // falha silenciosa
    }
  }
}
