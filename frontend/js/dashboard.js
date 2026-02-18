/**
 * dashboard.js - Carregamento do dashboard.
 */

async function loadDashboard() {
  try {
    showLoading()

    const [clientes, contratos, resumoHoje, recentes] = await Promise.all([
      api.getAllClientes({ status: "ativo" }),
      api.getAllContratos({ status_contrato: "ativo" }),
      api.getVeiculacoesHoje(),
      api.getVeiculacoesDetalhadas({ limit: 10 }),
    ])

    document.getElementById("stat-clientes").textContent = clientes.length
    document.getElementById("stat-contratos").textContent = contratos.length
    document.getElementById("stat-veiculacoes").textContent =
      resumoHoje.total_veiculacoes ?? 0
    document.getElementById("stat-nf-pendentes").textContent = contratos.filter(
      (c) => c.status_nf === "pendente",
    ).length

    renderChartTipoPrograma(resumoHoje.por_tipo_programa || {})
    renderChartTopClientes(resumoHoje.top_10_clientes?.slice(0, 5) || [])
    renderRecentes(recentes || [])
  } catch (error) {
    showToast(error.message || "Erro ao carregar dashboard", "error")
  } finally {
    hideLoading()
  }
}

function renderRecentes(items) {
  const tbody = document.querySelector("#table-recent-veiculacoes tbody")
  if (!tbody) return

  if (!items.length) {
    tbody.innerHTML = '<tr><td colspan="5" class="text-center">Sem dados</td></tr>'
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
        <td>${getStatusBadge(String(v.processado), "processado")}</td>
      </tr>
    `,
    )
    .join("")
}
