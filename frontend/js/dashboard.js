/**
 * dashboard.js - Carregamento do dashboard.
 */

function updateDashboardSensitiveMask() {
  const shouldBlur = !appState.user
  const blurTargets = [
    "stat-clientes-content",
    "stat-contratos-content",
    "stat-nf-pendentes-content",
  ]

  for (const id of blurTargets) {
    const el = document.getElementById(id)
    if (!el) continue
    el.classList.toggle("blur-unauth", shouldBlur)
  }

  const visibleTargets = ["stat-veiculacoes-content", "stat-meta-diaria-content"]
  for (const id of visibleTargets) {
    const el = document.getElementById(id)
    if (!el) continue
    el.classList.remove("blur-unauth")
  }
}

async function loadDashboard() {
  try {
    showLoading()
    const META_DIARIA_ALERT_THRESHOLD = 80

    const resumo = await api.getDashboardResumo()

    document.getElementById("stat-clientes").textContent = resumo.clientes_ativos ?? 0
    document.getElementById("stat-contratos").textContent = resumo.contratos_ativos ?? 0
    document.getElementById("stat-veiculacoes").textContent = resumo.total_veiculacoes ?? 0
    document.getElementById("stat-nf-pendentes").textContent = resumo.nf_pendentes ?? 0
    const metaDiaria = resumo.meta_diaria || {}
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

    renderChartTipoPrograma(resumo.por_tipo_programa || {})
    renderChartTopClientes(resumo.top_10_clientes?.slice(0, 5) || [])
    renderRecentes(resumo.recentes || [])
    updateDashboardSensitiveMask()
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
