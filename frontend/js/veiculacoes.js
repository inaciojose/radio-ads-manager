/**
 * veiculacoes.js - Listagem e processamento.
 */

let _veiculacoesAll = []
let _activeFreq = null

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
