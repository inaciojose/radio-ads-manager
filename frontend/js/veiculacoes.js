/**
 * veiculacoes.js - Listagem e processamento.
 */

let _veiculacoesAll = []
let _activeFreq = null

// ============================================
// Abas da página de Veiculações
// ============================================

function switchVeiculacoesTab(tab) {
  document.querySelectorAll("#page-veiculacoes .vei-tab-btn").forEach((btn) => {
    btn.classList.toggle("active", btn.dataset.tab === tab)
  })
  document.querySelectorAll("#page-veiculacoes .vei-tab-panel").forEach((panel) => {
    panel.classList.toggle("active", panel.id === `vei-tab-${tab}`)
  })

  if (tab === "nao-contabilizadas") {
    loadNaoContabilizadas()
  }
}

// ============================================
// Aba: Veiculações do Dia
// ============================================

async function loadVeiculacoes() {
  const data = document.getElementById("filter-veiculacao-data")?.value || getTodayDate()
  if (document.getElementById("filter-veiculacao-data")) {
    document.getElementById("filter-veiculacao-data").value = data
  }

  try {
    showLoading()
    const items = await api.getVeiculacoesDetalhadas({ data, limit: 500 })
    _veiculacoesAll = items
    renderVeiculacoes(_veiculacoesAll)
  } catch (error) {
    showToast(error.message || "Erro ao carregar veiculacoes", "error")
  } finally {
    hideLoading()
  }
}

function setFreqTab(freq, btn) {
  _activeFreq = freq
  document.querySelectorAll(".freq-tab").forEach((b) => b.classList.remove("active"))
  btn.classList.add("active")
  renderVeiculacoes(_veiculacoesAll)
}

function _getVeiculacaoRowClass(v) {
  if (v.status_chamada === "verde") return ' class="row-verde"'
  if (v.status_chamada === "vermelho") return ' class="row-vermelho"'
  if (v.status_chamada === "amarelo") return ' class="row-amarelo"'
  // Fallback para veiculações antigas (sem status_chamada)
  if (!v.arquivo_nome) return ' class="row-nao-cadastrado"'
  return ""
}

function _getVeiculacaoClienteCell(v) {
  if (v.cliente_nome) return escapeHtml(v.cliente_nome)
  if (v.codigo_chamada_raw != null) {
    return `<span class="text-muted" title="Código (${v.codigo_chamada_raw}) sem cliente cadastrado">( ${v.codigo_chamada_raw} ) ?</span>`
  }
  return `<span class="text-muted">—</span>`
}

function _getVeiculacaoArquivoCell(v) {
  const nome = v.arquivo_nome || v.nome_arquivo_raw || "-"
  if (!v.arquivo_nome && v.nome_arquivo_raw) {
    return `<span class="text-muted" title="Arquivo não cadastrado no sistema">${escapeHtml(nome)}</span>`
  }
  return escapeHtml(nome)
}

function _getVeiculacaoStatusCell(v) {
  if (v.status_chamada === "verde") return '<span class="badge badge-success">Verde</span>'
  if (v.status_chamada === "vermelho") return '<span class="badge badge-danger">Vermelho</span>'
  if (v.status_chamada === "amarelo") return '<span class="badge badge-warning">Amarelo</span>'
  return '<span class="badge badge-secondary">—</span>'
}

function renderVeiculacoes(items) {
  const tbody = document.querySelector("#table-veiculacoes tbody")
  if (!tbody) return

  const filtered = _activeFreq ? items.filter((v) => v.frequencia === _activeFreq) : items

  if (!filtered.length) {
    tbody.innerHTML = '<tr><td colspan="6" class="text-center">Sem veiculacoes</td></tr>'
    return
  }

  tbody.innerHTML = filtered
    .map((v) => {
      const rowClass = _getVeiculacaoRowClass(v)
      return `
      <tr${rowClass}>
        <td>${formatTime(v.data_hora)}</td>
        <td>${escapeHtml(v.frequencia || "-")}</td>
        <td>${_getVeiculacaoClienteCell(v)}</td>
        <td>${_getVeiculacaoArquivoCell(v)}</td>
        <td>${escapeHtml(v.tipo_programa || "-")}</td>
        <td>${_getVeiculacaoStatusCell(v)}</td>
      </tr>
    `
    })
    .join("")
}

// ============================================
// Aba: Não Contabilizadas
// ============================================

async function loadNaoContabilizadas() {
  const dataInicio = document.getElementById("filter-nao-cont-inicio")?.value
  const dataFim = document.getElementById("filter-nao-cont-fim")?.value
  const frequencia = document.getElementById("filter-nao-cont-freq")?.value

  const params = {}
  if (dataInicio) params.data_inicio = dataInicio
  if (dataFim) params.data_fim = dataFim
  if (frequencia) params.frequencia = frequencia

  try {
    showLoading()
    const items = await api.getNaoContabilizadas(params)
    renderNaoContabilizadas(items || [])
  } catch (error) {
    showToast(error.message || "Erro ao carregar não contabilizadas", "error")
  } finally {
    hideLoading()
  }
}

function renderNaoContabilizadas(items) {
  const tbody = document.querySelector("#table-nao-contabilizadas tbody")
  if (!tbody) return

  if (!items.length) {
    tbody.innerHTML =
      '<tr><td colspan="5" class="text-center">Nenhuma veiculação não contabilizada no período</td></tr>'
    return
  }

  tbody.innerHTML = items
    .map((v) => {
      const nomeArquivo = v.arquivo_nome
        ? escapeHtml(v.arquivo_nome)
        : `<span class="text-muted" title="Nome original: ${escapeHtml(v.nome_arquivo_raw || "")}">${escapeHtml(v.nome_arquivo_raw || "-")} <small>(não cadastrado)</small></span>`

      const clienteCell = v.cliente_nome
        ? escapeHtml(v.cliente_nome)
        : `<span class="text-muted">—</span>`

      return `
      <tr>
        <td>${formatDateTime(v.data_hora)}</td>
        <td>${escapeHtml(v.frequencia || "-")}</td>
        <td>${nomeArquivo}</td>
        <td>${clienteCell}</td>
        <td><span class="badge badge-warning">${escapeHtml(v.motivo)}</span></td>
      </tr>
    `
    })
    .join("")
}

// ============================================
// Modal: Lançamento em Lote
// ============================================

async function showLoteVeiculacaoModal() {
  if (!requireWriteAccess()) return

  try {
    showLoading()
    await ensureProgramasLoaded()
    const loteSelect = document.getElementById("lote-tipo-programa")
    if (loteSelect) {
      loteSelect.innerHTML = `<option value="">Selecione um programa...</option>${getProgramaSelectOptions()}`
    }
    const arquivos = await api.getAllArquivos({ ativo: true })
    const select = document.getElementById("lote-arquivo")
    select.innerHTML = [
      '<option value="">Selecione...</option>',
      ...arquivos.map(
        (a) =>
          `<option value="${a.id}">${escapeHtml(a.nome_arquivo)} (cliente ${a.cliente_id})</option>`,
      ),
    ].join("")

    document.getElementById("lote-data").value =
      document.getElementById("filter-veiculacao-data")?.value || getTodayDate()
    document.getElementById("lote-frequencia").value = "102.7"
    document.getElementById("lote-horarios").value = ""
    openModal("modal-veiculacao-lote")
  } catch (error) {
    showToast(error.message || "Erro ao preparar lançamento em lote", "error")
  } finally {
    hideLoading()
  }
}

async function saveLoteVeiculacoes() {
  if (!requireWriteAccess()) return

  const arquivoId = Number(document.getElementById("lote-arquivo").value)
  const data = document.getElementById("lote-data").value
  const frequencia = document.getElementById("lote-frequencia").value
  const tipoPrograma = document.getElementById("lote-tipo-programa").value.trim()
  const horarios = document
    .getElementById("lote-horarios")
    .value.split(/\r?\n/)
    .map((h) => h.trim())
    .filter(Boolean)

  if (!arquivoId || !data || !frequencia || !horarios.length) {
    showToast("Arquivo, data, frequência e horários são obrigatórios", "warning")
    return
  }

  try {
    showLoading()
    const resp = await api.criarLoteVeiculacoes({
      arquivo_audio_id: arquivoId,
      data,
      horarios,
      frequencia,
      tipo_programa: tipoPrograma || null,
      fonte: "obs_manual",
    })

    const detalhes = resp?.detalhes || {}
    showToast(
      `Lote salvo: ${detalhes.criadas || 0} criadas, ${detalhes.existentes || 0} existentes`,
      "success",
    )
    if ((detalhes.horarios_invalidos || []).length) {
      showToast(
        `Horários inválidos: ${(detalhes.horarios_invalidos || []).join(", ")}`,
        "warning",
      )
    }

    closeModal()
    await loadVeiculacoes()
  } catch (error) {
    showToast(error.message || "Erro ao salvar lote", "error")
  } finally {
    hideLoading()
  }
}

function abrirRelatorioVeiculacoes() {
  const filtered = _activeFreq ? _veiculacoesAll.filter((v) => v.frequencia === _activeFreq) : _veiculacoesAll
  openRelatorioModal("Veiculações", filtered.length, exportarVeiculacoes)
}

async function exportarVeiculacoes(formato) {
  try {
    showLoading()
    const data = document.getElementById("filter-veiculacao-data")?.value || getTodayDate()
    const params = { data }
    if (_activeFreq) params.frequencia = _activeFreq
    if (formato === "excel") {
      await api.exportarVeiculacoesExcel(params)
    } else {
      await api.exportarVeiculacoesPdf(params)
    }
  } catch (error) {
    showToast(error.message || "Erro ao exportar", "error")
  } finally {
    hideLoading()
  }
}
