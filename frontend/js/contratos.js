/**
 * contratos.js - Listagem de contratos.
 */

async function loadContratos() {
  const statusContrato = document.getElementById("filter-contrato-status")?.value
  const statusNf = document.getElementById("filter-contrato-nf")?.value

  try {
    showLoading()
    const contratos = await api.getContratos({
      limit: 1000,
      ...(statusContrato ? { status_contrato: statusContrato } : {}),
      ...(statusNf ? { status_nf: statusNf } : {}),
    })

    const clientes = await api.getClientes({ limit: 1000 })
    const clientesPorId = Object.fromEntries(clientes.map((c) => [c.id, c.nome]))

    renderContratos(contratos, clientesPorId)
  } catch (error) {
    showToast(error.message || "Erro ao carregar contratos", "error")
  } finally {
    hideLoading()
  }
}

function renderContratos(items, clientesPorId) {
  const tbody = document.querySelector("#table-contratos tbody")
  if (!tbody) return

  if (!items.length) {
    tbody.innerHTML = '<tr><td colspan="7" class="text-center">Sem contratos</td></tr>'
    return
  }

  tbody.innerHTML = items
    .map((c) => {
      const totalContratado = (c.itens || []).reduce(
        (acc, i) => acc + (i.quantidade_contratada || 0),
        0,
      )
      const totalExecutado = (c.itens || []).reduce(
        (acc, i) => acc + (i.quantidade_executada || 0),
        0,
      )

      return `
      <tr>
        <td>${c.numero_contrato}</td>
        <td>${clientesPorId[c.cliente_id] || c.cliente_id}</td>
        <td>${formatDate(c.data_inicio)} a ${formatDate(c.data_fim)}</td>
        <td>${getProgressBar(totalExecutado, totalContratado)}</td>
        <td>${formatCurrency(c.valor_total)}</td>
        <td>${getStatusBadge(c.status_nf, "nf")}</td>
        <td>${getStatusBadge(c.status_contrato, "contrato")}</td>
      </tr>
      `
    })
    .join("")
}

function showContratoModal() {
  showToast("Modal de contrato ainda nao implementado.", "info")
}
