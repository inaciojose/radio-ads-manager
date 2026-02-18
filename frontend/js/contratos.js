/**
 * contratos.js - CRUD de contratos.
 */

let contratosCache = []
let clientesContratoCache = []

async function ensureClientesContratoCache() {
  clientesContratoCache = await api.getAllClientes()
  return clientesContratoCache
}

function fillClienteSelect(selectId, clientes, selectedId = "") {
  const select = document.getElementById(selectId)
  if (!select) return

  const options = ['<option value="">Selecione...</option>']
  for (const c of clientes) {
    options.push(`<option value="${c.id}">${escapeHtml(c.nome)}</option>`)
  }
  select.innerHTML = options.join("")
  select.value = selectedId ? String(selectedId) : ""
}

async function loadContratos() {
  const statusContrato = document.getElementById("filter-contrato-status")?.value
  const statusNf = document.getElementById("filter-contrato-nf")?.value

  try {
    showLoading()
    contratosCache = await api.getAllContratos({
      ...(statusContrato ? { status_contrato: statusContrato } : {}),
      ...(statusNf ? { status_nf: statusNf } : {}),
    })

    const clientes = await ensureClientesContratoCache()
    const clientesPorId = Object.fromEntries(clientes.map((c) => [c.id, c.nome]))

    renderContratos(contratosCache, clientesPorId)
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
    tbody.innerHTML = '<tr><td colspan="8" class="text-center">Sem contratos</td></tr>'
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
        <td>${escapeHtml(c.numero_contrato || "-")}</td>
        <td>${escapeHtml(clientesPorId[c.cliente_id] || String(c.cliente_id))}</td>
        <td>${formatDate(c.data_inicio)} a ${formatDate(c.data_fim)}</td>
        <td>${getProgressBar(totalExecutado, totalContratado)}</td>
        <td>${formatCurrency(c.valor_total)}</td>
        <td>${getStatusBadge(c.status_nf, "nf")}</td>
        <td>${getStatusBadge(c.status_contrato, "contrato")}</td>
        <td>
          <button class="btn btn-sm btn-secondary" onclick="showContratoModal(${c.id})">Editar</button>
          <button class="btn btn-sm btn-primary" onclick="atualizarNotaFiscalContrato(${c.id})">NF</button>
          <button class="btn btn-sm btn-danger" onclick="removerContrato(${c.id})">Excluir</button>
        </td>
      </tr>
      `
    })
    .join("")
}

async function showContratoModal(contratoId = null) {
  const modalTitle = document.getElementById("contrato-modal-title")
  const itemSection = document.getElementById("contrato-item-section")
  const clienteSelect = document.getElementById("contrato-cliente")

  let contrato = null
  if (contratoId) {
    contrato = contratosCache.find((c) => c.id === Number(contratoId))
    if (!contrato) {
      contrato = await api.getContrato(contratoId)
    }
  }

  const clientes = await ensureClientesContratoCache()
  fillClienteSelect("contrato-cliente", clientes, contrato?.cliente_id)

  const isEdit = Boolean(contrato)
  modalTitle.textContent = isEdit ? "Editar Contrato" : "Novo Contrato"
  clienteSelect.disabled = isEdit
  itemSection.style.display = isEdit ? "none" : "block"

  document.getElementById("contrato-id").value = contrato?.id || ""
  document.getElementById("contrato-data-inicio").value = contrato?.data_inicio || ""
  document.getElementById("contrato-data-fim").value = contrato?.data_fim || ""
  document.getElementById("contrato-frequencia").value = contrato?.frequencia || "ambas"
  document.getElementById("contrato-valor-total").value = contrato?.valor_total ?? ""
  document.getElementById("contrato-status-contrato").value =
    contrato?.status_contrato || "ativo"
  document.getElementById("contrato-status-nf").value = contrato?.status_nf || "pendente"
  document.getElementById("contrato-numero-nf").value = contrato?.numero_nf || ""
  document.getElementById("contrato-data-emissao-nf").value =
    contrato?.data_emissao_nf || ""
  document.getElementById("contrato-observacoes").value = contrato?.observacoes || ""

  document.getElementById("contrato-item-tipo").value = ""
  document.getElementById("contrato-item-quantidade").value = ""
  document.getElementById("contrato-item-observacoes").value = ""

  openModal("modal-contrato")
}

async function saveContrato() {
  const id = document.getElementById("contrato-id").value
  const isEdit = Boolean(id)

  const clienteId = Number(document.getElementById("contrato-cliente").value)
  const dataInicio = document.getElementById("contrato-data-inicio").value
  const dataFim = document.getElementById("contrato-data-fim").value

  if (!isEdit && !clienteId) {
    showToast("Selecione o cliente", "warning")
    return
  }
  if (!dataInicio || !dataFim) {
    showToast("Informe data de início e fim", "warning")
    return
  }

  const basePayload = {
    data_inicio: dataInicio,
    data_fim: dataFim,
    frequencia: document.getElementById("contrato-frequencia").value,
    valor_total:
      document.getElementById("contrato-valor-total").value === ""
        ? null
        : Number(document.getElementById("contrato-valor-total").value),
    status_contrato: document.getElementById("contrato-status-contrato").value,
    status_nf: document.getElementById("contrato-status-nf").value,
    numero_nf: document.getElementById("contrato-numero-nf").value.trim() || null,
    data_emissao_nf:
      document.getElementById("contrato-data-emissao-nf").value || null,
    observacoes: document.getElementById("contrato-observacoes").value.trim() || null,
  }

  try {
    showLoading()
    if (isEdit) {
      await api.updateContrato(id, basePayload)
      showToast("Contrato atualizado", "success")
    } else {
      const itemTipo = document.getElementById("contrato-item-tipo").value.trim()
      const itemQuantidade = Number(document.getElementById("contrato-item-quantidade").value)
      if (!itemTipo || !itemQuantidade || itemQuantidade < 1) {
        showToast("Informe item e quantidade do contrato", "warning")
        return
      }

      await api.createContrato({
        cliente_id: clienteId,
        ...basePayload,
        itens: [
          {
            tipo_programa: itemTipo,
            quantidade_contratada: itemQuantidade,
            observacoes:
              document.getElementById("contrato-item-observacoes").value.trim() || null,
          },
        ],
      })
      showToast("Contrato criado", "success")
    }

    closeModal()
    await loadContratos()
  } catch (error) {
    showToast(error.message || "Erro ao salvar contrato", "error")
  } finally {
    hideLoading()
  }
}

async function atualizarNotaFiscalContrato(id) {
  const contrato = contratosCache.find((c) => c.id === Number(id))
  if (!contrato) return

  const status = prompt("Status NF (pendente, emitida, paga)", contrato.status_nf || "pendente")
  if (!status) return

  const numero = prompt("Número NF (opcional)", contrato.numero_nf || "")
  const dataEmissao = prompt(
    "Data emissão (YYYY-MM-DD, opcional)",
    contrato.data_emissao_nf || "",
  )

  try {
    showLoading()
    await api.updateNotaFiscal(id, {
      status_nf: status,
      ...(numero ? { numero_nf: numero } : {}),
      ...(dataEmissao ? { data_emissao: dataEmissao } : {}),
    })
    showToast("Nota fiscal atualizada", "success")
    await loadContratos()
  } catch (error) {
    showToast(error.message || "Erro ao atualizar nota fiscal", "error")
  } finally {
    hideLoading()
  }
}

async function removerContrato(id) {
  if (!confirmAction("Deseja excluir este contrato?")) return

  try {
    showLoading()
    await api.deleteContrato(id)
    showToast("Contrato removido", "success")
    await loadContratos()
  } catch (error) {
    showToast(error.message || "Erro ao excluir contrato", "error")
  } finally {
    hideLoading()
  }
}
