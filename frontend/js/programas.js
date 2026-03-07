/**
 * programas.js - CRUD de Programas de Rádio
 */

let programasCache = []

const DIAS_SEMANA = [
  { key: "seg", label: "Segunda" },
  { key: "ter", label: "Terça" },
  { key: "qua", label: "Quarta" },
  { key: "qui", label: "Quinta" },
  { key: "sex", label: "Sexta" },
  { key: "sab", label: "Sábado" },
  { key: "dom", label: "Domingo" },
]

const DIAS_CURTOS = {
  seg: "Seg", ter: "Ter", qua: "Qua", qui: "Qui", sex: "Sex", sab: "Sáb", dom: "Dom",
}

// ============================================
// Carregar e renderizar
// ============================================

async function loadProgramas() {
  const statusFiltro = document.getElementById("filter-programa-status")?.value
  try {
    showLoading()
    programasCache = await api.getProgramas(statusFiltro ? { status: statusFiltro } : {})
    renderProgramas(programasCache)
  } catch (error) {
    showToast(error.message || "Erro ao carregar programas", "error")
  } finally {
    hideLoading()
  }
}

function renderProgramas(items) {
  const tbody = document.querySelector("#table-programas tbody")
  if (!tbody) return

  if (!items.length) {
    tbody.innerHTML = '<tr><td colspan="5" class="text-center">Nenhum programa encontrado</td></tr>'
    return
  }

  tbody.innerHTML = items
    .map((p) => {
      const dias = (p.dias_semana || []).map((d) => DIAS_CURTOS[d] || d).join(", ")
      const horario = `${p.horario_inicio} – ${p.horario_fim}`
      const acoes = canWrite()
        ? `<button class="btn btn-sm btn-secondary" onclick="editarPrograma(${p.id})">Editar</button>
           ${
             p.status === "ativo"
               ? `<button class="btn btn-sm btn-warning" onclick="toggleStatusPrograma(${p.id}, 'inativo')">Inativar</button>`
               : `<button class="btn btn-sm btn-success" onclick="toggleStatusPrograma(${p.id}, 'ativo')">Ativar</button>`
           }
           <button class="btn btn-sm btn-danger" onclick="excluirPrograma(${p.id})">Excluir</button>`
        : '<span class="badge badge-secondary">Somente leitura</span>'

      return `
        <tr>
          <td>${escapeHtml(p.nome)}</td>
          <td>${escapeHtml(dias)}</td>
          <td>${escapeHtml(horario)}</td>
          <td>${getStatusBadge(p.status, "programa")}</td>
          <td>${acoes}</td>
        </tr>`
    })
    .join("")
}

function searchProgramas() {
  const termo = (document.getElementById("search-programas")?.value || "").trim().toLowerCase()
  if (!termo) {
    renderProgramas(programasCache)
    return
  }
  renderProgramas(
    programasCache.filter((p) => p.nome.toLowerCase().includes(termo))
  )
}

// ============================================
// Modal: criar / editar
// ============================================

function showProgramaModal(programa = null) {
  if (!requireWriteAccess()) return

  document.getElementById("programa-modal-title").textContent = programa
    ? "Editar Programa"
    : "Novo Programa"

  document.getElementById("programa-id").value = programa?.id || ""
  document.getElementById("programa-nome").value = programa?.nome || ""
  document.getElementById("programa-horario-inicio").value = programa?.horario_inicio || ""
  document.getElementById("programa-horario-fim").value = programa?.horario_fim || ""

  // Checkboxes de dias
  const dias = programa?.dias_semana || []
  DIAS_SEMANA.forEach(({ key }) => {
    const cb = document.getElementById(`dia-${key}`)
    if (cb) cb.checked = dias.includes(key)
  })

  // Campo status só visível ao editar
  const statusGroup = document.getElementById("programa-status-group")
  if (statusGroup) {
    statusGroup.style.display = programa ? "block" : "none"
  }
  if (programa) {
    document.getElementById("programa-status").value = programa.status || "ativo"
  }

  openModal("modal-programa")
}

async function savePrograma() {
  if (!requireWriteAccess()) return

  const id = document.getElementById("programa-id").value
  const nome = document.getElementById("programa-nome").value.trim()
  const horarioInicio = document.getElementById("programa-horario-inicio").value
  const horarioFim = document.getElementById("programa-horario-fim").value
  const dias = DIAS_SEMANA.map(({ key }) => key).filter(
    (key) => document.getElementById(`dia-${key}`)?.checked
  )

  if (!nome) { showToast("Nome é obrigatório", "warning"); return }
  if (!dias.length) { showToast("Selecione pelo menos um dia da semana", "warning"); return }
  if (!horarioInicio) { showToast("Horário de início é obrigatório", "warning"); return }
  if (!horarioFim) { showToast("Horário de fim é obrigatório", "warning"); return }

  const payload = { nome, dias_semana: dias, horario_inicio: horarioInicio, horario_fim: horarioFim }

  if (id) {
    payload.status = document.getElementById("programa-status").value
  }

  try {
    showLoading()
    if (id) {
      await api.updatePrograma(id, payload)
      showToast("Programa atualizado", "success")
    } else {
      await api.createPrograma(payload)
      showToast("Programa criado", "success")
    }
    closeModal()
    await loadProgramas()
  } catch (error) {
    showToast(error.message || "Erro ao salvar programa", "error")
  } finally {
    hideLoading()
  }
}

function editarPrograma(id) {
  const programa = programasCache.find((p) => p.id === id)
  if (!programa) return
  showProgramaModal(programa)
}

async function toggleStatusPrograma(id, novoStatus) {
  if (!requireWriteAccess()) return
  const acao = novoStatus === "inativo" ? "inativar" : "ativar"
  if (!confirmAction(`Deseja ${acao} este programa?`)) return

  try {
    showLoading()
    await api.updatePrograma(id, { status: novoStatus })
    showToast(`Programa ${novoStatus === "inativo" ? "inativado" : "ativado"}`, "success")
    await loadProgramas()
  } catch (error) {
    showToast(error.message || "Erro ao alterar status", "error")
  } finally {
    hideLoading()
  }
}

async function excluirPrograma(id) {
  if (!requireWriteAccess()) return
  if (!confirmAction("Deseja excluir este programa? Esta ação não pode ser desfeita.")) return

  try {
    showLoading()
    await api.deletePrograma(id)
    programasCache = programasCache.filter((p) => p.id !== id)
    showToast("Programa excluído", "success")
    renderProgramas(programasCache)
  } catch (error) {
    showToast(error.message || "Erro ao excluir programa", "error")
  } finally {
    hideLoading()
  }
}

// ============================================
// Integração com Contratos
// ============================================

/**
 * Retorna <option> tags dos programas ativos para uso em selects de tipo_programa.
 * @param {string} [selected] - valor atualmente selecionado
 */
function getProgramaSelectOptions(selected = "") {
  const ativos = programasCache.filter((p) => p.status === "ativo")
  return ativos
    .map((p) => `<option value="${escapeHtml(p.nome)}"${p.nome === selected ? " selected" : ""}>${escapeHtml(p.nome)}</option>`)
    .join("")
}

/**
 * Garante que o cache de programas está carregado (sem exibir loading global).
 */
async function ensureProgramasLoaded() {
  if (!programasCache.length) {
    try {
      programasCache = await api.getProgramas({ status: "ativo" })
    } catch {
      // falha silenciosa — o select ficará sem opções
    }
  }
}
