/**
 * veiculacoes.js - Listagem e processamento.
 */

async function loadVeiculacoes() {
  const data = document.getElementById("filter-veiculacao-data")?.value || getTodayDate()
  if (document.getElementById("filter-veiculacao-data")) {
    document.getElementById("filter-veiculacao-data").value = data
  }

  try {
    showLoading()
    const items = await api.getVeiculacoesDetalhadas({ data, limit: 500 })
    renderVeiculacoes(items)
  } catch (error) {
    showToast(error.message || "Erro ao carregar veiculacoes", "error")
  } finally {
    hideLoading()
  }
}

function renderVeiculacoes(items) {
  const tbody = document.querySelector("#table-veiculacoes tbody")
  if (!tbody) return

  if (!items.length) {
    tbody.innerHTML = '<tr><td colspan="6" class="text-center">Sem veiculacoes</td></tr>'
    return
  }

  tbody.innerHTML = items
    .map(
      (v) => `
      <tr>
        <td>${formatTime(v.data_hora)}</td>
        <td>${escapeHtml(v.cliente_nome || "-")}</td>
        <td>${escapeHtml(v.arquivo_nome || "-")}</td>
        <td>${escapeHtml(v.tipo_programa || "-")}</td>
        <td>${escapeHtml(v.numero_contrato || "-")}</td>
        <td>${getStatusBadge(String(v.processado), "processado")}</td>
      </tr>
    `,
    )
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
