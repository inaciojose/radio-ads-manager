/**
 * dashboard.js - Carregamento do dashboard.
 */

async function loadDashboard() {
  try {
    showLoading()
    const META_DIARIA_ALERT_THRESHOLD = 80

    const [clientes, contratos, resumoHoje, recentes, metaDiaria] = await Promise.all([
      api.getAllClientes({ status: "ativo" }),
      api.getAllContratos({ status_contrato: "ativo" }),
      api.getVeiculacoesHoje(),
      api.getVeiculacoesDetalhadas({ limit: 10 }),
      api.getResumoMetaDiariaHoje(),
    ])

    document.getElementById("stat-clientes").textContent = clientes.length
    document.getElementById("stat-contratos").textContent = contratos.length
    document.getElementById("stat-veiculacoes").textContent =
      resumoHoje.total_veiculacoes ?? 0
    document.getElementById("stat-nf-pendentes").textContent = contratos.filter(
      (c) => c.status_nf === "pendente",
    ).length
    const metaTotal = metaDiaria?.meta_diaria_total ?? 0
    const executadasHoje = metaDiaria?.executadas_hoje ?? 0
    const percentual = metaTotal > 0 ? metaDiaria.percentual_cumprimento ?? 0 : 0

    document.getElementById("stat-meta-diaria").textContent =
      metaTotal > 0 ? `${percentual.toFixed(1)}%` : "-"
    document.getElementById("stat-meta-diaria-detail").textContent =
      metaTotal > 0
        ? `${executadasHoje}/${metaTotal} chamadas`
        : "Sem meta diária ativa"

    const metaCard = document.getElementById("stat-meta-diaria-card")
    if (metaCard) {
      metaCard.classList.remove("alert-low", "alert-ok")
      if (metaTotal > 0) {
        if (percentual < META_DIARIA_ALERT_THRESHOLD) {
          metaCard.classList.add("alert-low")
        } else {
          metaCard.classList.add("alert-ok")
        }
      }
    }

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
