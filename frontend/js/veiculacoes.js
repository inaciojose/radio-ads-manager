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

function renderVeiculacoes(items) {
  const tbody = document.querySelector("#table-veiculacoes tbody")
  if (!tbody) return

  const filtered = _activeFreq ? items.filter((v) => v.frequencia === _activeFreq) : items

  if (!filtered.length) {
    tbody.innerHTML = '<tr><td colspan="7" class="text-center">Sem veiculacoes</td></tr>'
    return
  }

  tbody.innerHTML = filtered
    .map((v) => {
      const naoCadastrado = !v.arquivo_nome  // arquivo não está no sistema
      const semContrato = !naoCadastrado && v.processado && !v.contabilizada

      let rowClass = ""
      if (naoCadastrado) rowClass = ' class="row-nao-cadastrado"'
      else if (semContrato) rowClass = ' class="row-sem-contrato"'

      const arquivoCell = naoCadastrado
        ? `<span title="Arquivo não cadastrado no sistema">${escapeHtml(v.nome_arquivo_raw || "-")}</span>`
        : escapeHtml(v.arquivo_nome || "-")

      const clienteCell = naoCadastrado
        ? `<span class="text-muted">Não cadastrado</span>`
        : escapeHtml(v.cliente_nome || "-")

      let contratoCell
      if (naoCadastrado) {
        contratoCell = `<span class="badge badge-danger">Não identificado</span>`
      } else if (semContrato) {
        contratoCell = `<span class="badge badge-warning">Sem contrato</span>`
      } else {
        contratoCell = escapeHtml(v.numero_contrato || "-")
      }

      return `
      <tr${rowClass}>
        <td>${formatTime(v.data_hora)}</td>
        <td>${escapeHtml(v.frequencia || "-")}</td>
        <td>${clienteCell}</td>
        <td>${arquivoCell}</td>
        <td>${escapeHtml(v.tipo_programa || "-")}</td>
        <td>${contratoCell}</td>
        <td>${getStatusBadge(String(v.processado), "processado")}</td>
      </tr>
    `
    })
    .join("")
}

async function processarVeiculacoes() {
  if (!requireWriteAccess()) return
  const data = document.getElementById("filter-veiculacao-data")?.value || getTodayDate()
  try {
    showLoading()
    const response = await api.processarVeiculacoes({
      data_inicio: data,
      data_fim: data,
    })
    showToast(response.message || "Processamento concluido", "success")
    await loadVeiculacoes()
  } catch (error) {
    showToast(error.message || "Erro ao processar veiculacoes", "error")
  } finally {
    hideLoading()
  }
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
    document.getElementById("lote-tipo-programa").value = ""
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
