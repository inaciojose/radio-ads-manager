/**
 * contratos.js - CRUD de contratos.
 */

let contratosCache = []
const clientesPorIdCache = {}

const contratosState = {
  page: 1,
  pageSize: 20,
  hasNext: false,
  searchTimer: null,
}

async function loadContratos(page = 1) {
  const statusContrato = document.getElementById("filter-contrato-status")?.value
  const statusNf = document.getElementById("filter-contrato-nf")?.value
  const frequencia = document.getElementById("filter-contrato-frequencia")?.value
  const busca = (document.getElementById("search-contratos")?.value || "").trim()

  const targetPage = Math.max(1, page)
  const skip = (targetPage - 1) * contratosState.pageSize

  try {
    showLoading()
    const contratos = await api.getContratos({
      skip,
      limit: contratosState.pageSize,
      ...(statusContrato ? { status_contrato: statusContrato } : {}),
      ...(statusNf ? { status_nf: statusNf } : {}),
      ...(frequencia ? { frequencia } : {}),
      ...(busca ? { busca } : {}),
    })

    if (targetPage > 1 && contratos.length === 0) {
      await loadContratos(targetPage - 1)
      return
    }

    contratosCache = contratos
    contratosState.page = targetPage
    contratosState.hasNext = contratos.length === contratosState.pageSize

    await hydrateClientesNomes(contratos)
    renderContratos(contratos, clientesPorIdCache)
    updateContratosPagination()
  } catch (error) {
    showToast(error.message || "Erro ao carregar contratos", "error")
  } finally {
    hideLoading()
  }
}

async function hydrateClientesNomes(contratos) {
  const clienteIds = [...new Set(contratos.map((c) => c.cliente_id))].filter(Boolean)
  const missingIds = clienteIds.filter((id) => !clientesPorIdCache[id])

  if (!missingIds.length) return

  const clientes = await Promise.all(missingIds.map((id) => api.getCliente(id)))
  for (const cliente of clientes) {
    clientesPorIdCache[cliente.id] = cliente.nome
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
          <button class="btn btn-sm btn-primary" onclick="showNotaFiscalModal(${c.id})">NF</button>
          <button class="btn btn-sm btn-danger" onclick="removerContrato(${c.id})">Excluir</button>
        </td>
      </tr>
      `
    })
    .join("")
}

function updateContratosPagination() {
  const pageInfo = document.getElementById("contratos-page-info")
  const prevBtn = document.getElementById("contratos-prev")
  const nextBtn = document.getElementById("contratos-next")

  if (pageInfo) {
    pageInfo.textContent = `Página ${contratosState.page}`
  }
  if (prevBtn) {
    prevBtn.disabled = contratosState.page <= 1
  }
  if (nextBtn) {
    nextBtn.disabled = !contratosState.hasNext
  }
}

function changeContratosPage(delta) {
  if (delta > 0 && !contratosState.hasNext) return
  const target = Math.max(1, contratosState.page + delta)
  loadContratos(target)
}

function searchContratos() {
  clearTimeout(contratosState.searchTimer)
  contratosState.searchTimer = setTimeout(() => {
    loadContratos(1)
  }, 300)
}

function renderContratoItensEdit(itens) {
  const container = document.getElementById("contrato-itens-edit-list")
  if (!container) return

  if (!itens || !itens.length) {
    container.innerHTML = '<p class="text-center">Este contrato não possui itens.</p>'
    return
  }

  container.innerHTML = itens
    .map(
      (item) => `
      <div class="contrato-item-edit-row" data-item-id="${item.id}">
        <div class="form-row">
          <div class="form-group">
            <label>Tipo de Programa</label>
            <input type="text" class="contrato-item-tipo" value="${escapeHtml(item.tipo_programa || "")}" />
          </div>
          <div class="form-group">
            <label>Qtd Contratada</label>
            <input type="number" min="1" class="contrato-item-quantidade" value="${item.quantidade_contratada || 1}" />
          </div>
        </div>
        <div class="form-group">
          <label>Observações</label>
          <input type="text" class="contrato-item-observacoes" value="${escapeHtml(item.observacoes || "")}" />
        </div>
        <small>Executada: ${item.quantidade_executada || 0}</small>
      </div>
    `,
    )
    .join("")
}

async function showContratoModal(contratoId = null) {
  const modalTitle = document.getElementById("contrato-modal-title")
  const createItemSection = document.getElementById("contrato-item-create-section")
  const editItemSection = document.getElementById("contrato-item-edit-section")
  const clienteSelect = document.getElementById("contrato-cliente")

  let contrato = null
  if (contratoId) {
    contrato = contratosCache.find((c) => c.id === Number(contratoId))
    if (!contrato) {
      contrato = await api.getContrato(contratoId)
    }
  }

  const isEdit = Boolean(contrato)
  modalTitle.textContent = isEdit ? "Editar Contrato" : "Novo Contrato"

  if (isEdit) {
    if (!contrato.itens?.length) {
      contrato = await api.getContrato(contrato.id)
    }
    clienteSelect.innerHTML = `<option value="${contrato.cliente_id}">${escapeHtml(
      clientesPorIdCache[contrato.cliente_id] || `Cliente ${contrato.cliente_id}`,
    )}</option>`
    clienteSelect.value = String(contrato.cliente_id)
    clienteSelect.disabled = true
    createItemSection.style.display = "none"
    editItemSection.style.display = "block"
    renderContratoItensEdit(contrato.itens || [])
  } else {
    const clientes = await api.getAllClientes()
    clienteSelect.innerHTML = [
      '<option value="">Selecione...</option>',
      ...clientes.map((c) => `<option value="${c.id}">${escapeHtml(c.nome)}</option>`),
    ].join("")
    clienteSelect.value = ""
    clienteSelect.disabled = false
    createItemSection.style.display = "block"
    editItemSection.style.display = "none"
  }

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
  if (new Date(dataFim) < new Date(dataInicio)) {
    showToast("Data fim não pode ser menor que data início", "warning")
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

      const itemRows = Array.from(document.querySelectorAll(".contrato-item-edit-row"))
      for (const row of itemRows) {
        const itemId = row.dataset.itemId
        const tipoPrograma = row.querySelector(".contrato-item-tipo")?.value.trim()
        const quantidade = Number(row.querySelector(".contrato-item-quantidade")?.value)

        if (!tipoPrograma || !quantidade || quantidade < 1) {
          throw new Error("Todos os itens devem ter tipo e quantidade maior que 0")
        }

        await api.updateContratoItem(id, itemId, {
          tipo_programa: tipoPrograma,
          quantidade_contratada: quantidade,
          observacoes:
            row.querySelector(".contrato-item-observacoes")?.value.trim() || null,
        })
      }

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
    await loadContratos(contratosState.page)
  } catch (error) {
    showToast(error.message || "Erro ao salvar contrato", "error")
  } finally {
    hideLoading()
  }
}

function showNotaFiscalModal(id) {
  const contrato = contratosCache.find((c) => c.id === Number(id))
  if (!contrato) return

  document.getElementById("nf-contrato-id").value = contrato.id
  document.getElementById("nf-status").value = contrato.status_nf || "pendente"
  document.getElementById("nf-numero").value = contrato.numero_nf || ""
  document.getElementById("nf-data-emissao").value = contrato.data_emissao_nf || ""

  openModal("modal-nota-fiscal")
}

async function saveNotaFiscal() {
  const id = document.getElementById("nf-contrato-id").value
  const status = document.getElementById("nf-status").value
  const numero = document.getElementById("nf-numero").value.trim()
  const dataEmissao = document.getElementById("nf-data-emissao").value

  try {
    showLoading()
    await api.updateNotaFiscal(id, {
      status_nf: status,
      ...(numero ? { numero_nf: numero } : {}),
      ...(dataEmissao ? { data_emissao: dataEmissao } : {}),
    })
    closeModal()
    showToast("Nota fiscal atualizada", "success")
    await loadContratos(contratosState.page)
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
    await loadContratos(contratosState.page)
  } catch (error) {
    showToast(error.message || "Erro ao excluir contrato", "error")
  } finally {
    hideLoading()
  }
}
