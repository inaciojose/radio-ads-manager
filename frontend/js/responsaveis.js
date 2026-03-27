/**
 * responsaveis.js - CRUD de Responsáveis
 */

let responsaveisCache = []

// ============================================
// Carregar e renderizar
// ============================================

async function loadResponsaveis() {
  // Inicializa o filtro de mês de comissões com o mês atual, se ainda não definido
  const mesInput = document.getElementById("filter-comissoes-mes")
  if (mesInput && !mesInput.value) {
    const hoje = new Date()
    mesInput.value = `${hoje.getFullYear()}-${String(hoje.getMonth() + 1).padStart(2, "0")}`
    loadComissoes()
  }

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

// ============================================
// Comissões
// ============================================

let _comissaoDetalheAberto = null  // responsavel_id atualmente expandido

async function loadComissoes() {
  const mes = document.getElementById("filter-comissoes-mes")?.value
  const tbody = document.querySelector("#table-comissoes tbody")
  if (!tbody) return

  _comissaoDetalheAberto = null

  if (!mes) {
    tbody.innerHTML = '<tr><td colspan="3" class="text-center">Selecione um mês para ver as comissões</td></tr>'
    return
  }

  tbody.innerHTML = '<tr><td colspan="3" class="text-center">Carregando...</td></tr>'
  try {
    const items = await api.getComissoes(mes)
    if (!items.length) {
      tbody.innerHTML = '<tr><td colspan="3" class="text-center">Nenhuma comissão registrada neste mês</td></tr>'
      return
    }
    tbody.innerHTML = items
      .map(
        (item) => `
        <tr class="comissao-row" style="cursor:pointer;" onclick="toggleComissaoDetalhe(${item.responsavel_id}, '${escapeHtml(item.responsavel_nome)}')">
          <td>${escapeHtml(item.responsavel_nome)}</td>
          <td><strong>${formatCurrency(item.total_comissao)}</strong></td>
          <td style="text-align:center;"><i class="fas fa-chevron-down" id="comissao-icon-${item.responsavel_id}"></i></td>
        </tr>
        <tr id="comissao-detalhe-${item.responsavel_id}" style="display:none;">
          <td colspan="3" style="padding:0; background:#f8f9fa;"></td>
        </tr>`,
      )
      .join("")
  } catch (error) {
    tbody.innerHTML = `<tr><td colspan="3" class="text-center text-danger">${escapeHtml(error.message || "Erro ao carregar comissões")}</td></tr>`
  }
}

async function toggleComissaoDetalhe(responsavelId, responsavelNome) {
  const mes = document.getElementById("filter-comissoes-mes")?.value
  if (!mes) return

  const detalheRow = document.getElementById(`comissao-detalhe-${responsavelId}`)
  const icon = document.getElementById(`comissao-icon-${responsavelId}`)
  if (!detalheRow) return

  // Fechar o que estava aberto (se for diferente)
  if (_comissaoDetalheAberto !== null && _comissaoDetalheAberto !== responsavelId) {
    const anteriorRow = document.getElementById(`comissao-detalhe-${_comissaoDetalheAberto}`)
    const anteriorIcon = document.getElementById(`comissao-icon-${_comissaoDetalheAberto}`)
    if (anteriorRow) anteriorRow.style.display = "none"
    if (anteriorIcon) anteriorIcon.className = "fas fa-chevron-down"
    _comissaoDetalheAberto = null
  }

  // Toggle do atual
  if (detalheRow.style.display !== "none") {
    detalheRow.style.display = "none"
    if (icon) icon.className = "fas fa-chevron-down"
    _comissaoDetalheAberto = null
    return
  }

  // Abrir e carregar
  const td = detalheRow.querySelector("td")
  td.innerHTML = '<div style="padding:0.75rem; text-align:center;">Carregando...</div>'
  detalheRow.style.display = ""
  if (icon) icon.className = "fas fa-chevron-up"
  _comissaoDetalheAberto = responsavelId

  try {
    const detalhe = await api.getComissaoDetalhe(responsavelId, mes)
    td.innerHTML = _renderComissaoDetalhe(detalhe)
  } catch (error) {
    td.innerHTML = `<div style="padding:0.75rem; color:red;">${escapeHtml(error.message || "Erro ao carregar detalhe")}</div>`
  }
}

function _renderComissaoDetalhe(detalhe) {
  if (!detalhe.contratos.length) {
    return '<div style="padding:0.75rem;">Nenhum contrato encontrado.</div>'
  }

  const linhas = detalhe.contratos
    .map(
      (c) => `
      <tr>
        <td>${escapeHtml(c.cliente_nome)}</td>
        <td>${escapeHtml(c.numero_contrato || "-")}</td>
        <td>${formatCurrency(c.valor_liquido)}</td>
        <td>${c.percentagem != null ? c.percentagem + "%" : "-"}</td>
        <td><strong>${formatCurrency(c.valor_comissao)}</strong></td>
      </tr>`,
    )
    .join("")

  return `
    <div style="padding:0.75rem 1rem;">
      <table class="table" style="margin:0; font-size:0.9rem;">
        <thead>
          <tr>
            <th>Cliente</th>
            <th>Contrato</th>
            <th>Valor Líquido NF</th>
            <th>%</th>
            <th>Comissão</th>
          </tr>
        </thead>
        <tbody>${linhas}</tbody>
        <tfoot>
          <tr>
            <td colspan="4" style="text-align:right; font-weight:bold;">Total:</td>
            <td><strong>${formatCurrency(detalhe.total_comissao)}</strong></td>
          </tr>
        </tfoot>
      </table>
    </div>`
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

function abrirRelatorioComissoes() {
  const mes = document.getElementById("filter-comissoes-mes")?.value
  if (!mes) {
    showToast("Selecione um mês antes de exportar", "warning")
    return
  }
  openRelatorioModal("Comissões", null, exportarComissoes)
}

async function exportarComissoes(formato) {
  try {
    showLoading()
    const mes = document.getElementById("filter-comissoes-mes")?.value || ""
    if (!mes) {
      showToast("Selecione um mês para exportar as comissões", "warning")
      return
    }
    const params = { mes }
    if (formato === "excel") {
      await api.exportarComissoesExcel(params)
    } else {
      await api.exportarComissoesPdf(params)
    }
  } catch (error) {
    showToast(error.message || "Erro ao exportar", "error")
  } finally {
    hideLoading()
  }
}
