/**
 * charts.js - Helpers para graficos do dashboard.
 */

let chartTipoPrograma = null
let chartTopClientes = null

function renderChartTipoPrograma(data = {}) {
  const canvas = document.getElementById("chart-tipo-programa")
  if (!canvas || typeof Chart === "undefined") return

  const labels = Object.keys(data)
  const values = Object.values(data)

  if (chartTipoPrograma) {
    chartTipoPrograma.data.labels = labels
    chartTipoPrograma.data.datasets[0].data = values
    chartTipoPrograma.update()
    return
  }

  chartTipoPrograma = new Chart(canvas, {
    type: "doughnut",
    data: {
      labels,
      datasets: [
        {
          data: values,
          backgroundColor: CONFIG.CHART_COLORS,
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
    },
  })
}

function renderChartTopClientes(items = []) {
  const canvas = document.getElementById("chart-top-clientes")
  if (!canvas || typeof Chart === "undefined") return

  const labels = items.map((item) => item.cliente_nome)
  const values = items.map((item) => item.total)

  if (chartTopClientes) {
    chartTopClientes.data.labels = labels
    chartTopClientes.data.datasets[0].data = values
    chartTopClientes.update()
    return
  }

  chartTopClientes = new Chart(canvas, {
    type: "bar",
    data: {
      labels,
      datasets: [
        {
          label: "Veiculacoes",
          data: values,
          backgroundColor: CONFIG.CHART_COLORS[0],
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: { legend: { display: false } },
    },
  })
}
