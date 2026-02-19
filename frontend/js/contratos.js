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

const contratoModalState = {
  arquivosCliente: [],
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
      const metas = c.arquivos_metas || []
      const usaMetas = metas.length > 0
      const totalContratado = usaMetas
        ? metas.reduce((acc, m) => acc + (m.quantidade_meta || 0), 0)
        : (c.itens || []).reduce((acc, i) => acc + (i.quantidade_contratada || 0), 0)
      const totalExecutado = usaMetas
        ? metas.reduce((acc, m) => acc + (m.quantidade_executada || 0), 0)
        : (c.itens || []).reduce((acc, i) => acc + (i.quantidade_executada || 0), 0)

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
          ${
            canWrite()
              ? `<button class="btn btn-sm btn-secondary" onclick="showContratoModal(${c.id})">Editar</button>
                 <button class="btn btn-sm btn-primary" onclick="showNotaFiscalModal(${c.id})">NF</button>
                 <button class="btn btn-sm btn-danger" onclick="removerContrato(${c.id})">Excluir</button>`
              : '<span class="badge badge-secondary">Somente leitura</span>'
          }
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

function buildArquivoOptions(arquivos, selectedId = "") {
  const options = ['<option value="">Selecione o arquivo...</option>']
  for (const a of arquivos) {
    options.push(
      `<option value="${a.id}" ${String(selectedId) === String(a.id) ? "selected" : ""}>${escapeHtml(a.nome_arquivo)}</option>`,
    )
  }
  return options.join("")
}

function renderContratoMetasCreate() {
  const container = document.getElementById("contrato-metas-create-list")
  if (!container) return
  container.innerHTML = ""
  addContratoMetaCreateRow()
}

function addContratoMetaCreateRow(meta = null) {
  const container = document.getElementById("contrato-metas-create-list")
  if (!container) return
  const row = document.createElement("div")
  row.className = "contrato-meta-row"
  row.innerHTML = `
    <div class="form-row contrato-meta-grid">
      <div class="form-group">
        <label>Arquivo</label>
        <select class="contrato-meta-arquivo">
          ${buildArquivoOptions(contratoModalState.arquivosCliente, meta?.arquivo_audio_id)}
        </select>
      </div>
      <div class="form-group">
        <label>Meta</label>
        <input type="number" min="1" class="contrato-meta-quantidade" value="${meta?.quantidade_meta || ""}" />
      </div>
      <div class="form-group">
        <label>Modo</label>
        <select class="contrato-meta-modo">
          <option value="fixo" ${meta?.modo_veiculacao === "fixo" ? "selected" : ""}>Fixo</option>
          <option value="rodizio" ${meta?.modo_veiculacao === "rodizio" ? "selected" : ""}>Rodízio</option>
        </select>
      </div>
      <div class="form-group">
        <label>Ativo</label>
        <select class="contrato-meta-ativo">
          <option value="true" ${meta?.ativo === false ? "" : "selected"}>Sim</option>
          <option value="false" ${meta?.ativo === false ? "selected" : ""}>Não</option>
        </select>
      </div>
    </div>
    <div class="form-row contrato-meta-grid-footer">
      <div class="form-group">
        <label>Observações</label>
        <input type="text" class="contrato-meta-observacoes" value="${escapeHtml(meta?.observacoes || "")}" />
      </div>
      <div class="form-group contrato-meta-actions">
        <button type="button" class="btn btn-danger btn-sm" onclick="removeContratoMetaCreateRow(this)">Remover</button>
      </div>
    </div>
  `
  container.appendChild(row)
}

function removeContratoMetaCreateRow(btn) {
  const row = btn?.closest(".contrato-meta-row")
  if (!row) return
  row.remove()
}

async function onContratoClienteChange() {
  const clienteId = Number(document.getElementById("contrato-cliente")?.value)
  if (!clienteId) {
    contratoModalState.arquivosCliente = []
    renderContratoMetasCreate()
    return
  }

  try {
    contratoModalState.arquivosCliente = await api.getAllArquivos({
      cliente_id: clienteId,
    })
    renderContratoMetasCreate()
  } catch (error) {
    showToast(error.message || "Erro ao carregar arquivos do cliente", "error")
  }
}

function renderContratoMetasEdit(metas) {
  const container = document.getElementById("contrato-metas-edit-list")
  if (!container) return

  if (!metas?.length) {
    container.innerHTML = '<p class="text-center">Sem metas por arquivo.</p>'
    return
  }

  container.innerHTML = metas
    .map(
      (meta) => `
      <div class="contrato-meta-row contrato-meta-edit-row" data-meta-id="${meta.id}" data-delete="0">
        <div class="form-row contrato-meta-grid">
          <div class="form-group">
            <label>Arquivo</label>
            <select class="contrato-meta-arquivo" disabled>
              ${buildArquivoOptions(contratoModalState.arquivosCliente, meta.arquivo_audio_id)}
            </select>
          </div>
          <div class="form-group">
            <label>Meta</label>
            <input type="number" min="1" class="contrato-meta-quantidade" value="${meta.quantidade_meta || ""}" />
          </div>
          <div class="form-group">
            <label>Modo</label>
            <select class="contrato-meta-modo">
              <option value="fixo" ${meta.modo_veiculacao === "fixo" ? "selected" : ""}>Fixo</option>
              <option value="rodizio" ${meta.modo_veiculacao === "rodizio" ? "selected" : ""}>Rodízio</option>
            </select>
          </div>
          <div class="form-group">
            <label>Ativo</label>
            <select class="contrato-meta-ativo">
              <option value="true" ${meta.ativo ? "selected" : ""}>Sim</option>
              <option value="false" ${meta.ativo ? "" : "selected"}>Não</option>
            </select>
          </div>
        </div>
        <div class="form-row contrato-meta-grid-footer">
          <div class="form-group">
            <label>Observações</label>
            <input type="text" class="contrato-meta-observacoes" value="${escapeHtml(meta.observacoes || "")}" />
          </div>
          <div class="form-group contrato-meta-actions">
            <button type="button" class="btn btn-danger btn-sm" onclick="toggleContratoMetaDelete(this)">Excluir</button>
          </div>
        </div>
        <small class="contrato-meta-hint">Executada: ${meta.quantidade_executada || 0}</small>
      </div>
    `,
    )
    .join("")
}

function addContratoMetaEditRow() {
  const container = document.getElementById("contrato-metas-edit-list")
  if (!container) return
  if (container.querySelector(".text-center")) {
    container.innerHTML = ""
  }
  const row = document.createElement("div")
  row.className = "contrato-meta-row contrato-meta-edit-row"
  row.dataset.metaId = ""
  row.dataset.delete = "0"
  row.innerHTML = `
    <div class="form-row contrato-meta-grid">
      <div class="form-group">
        <label>Arquivo</label>
        <select class="contrato-meta-arquivo">
          ${buildArquivoOptions(contratoModalState.arquivosCliente)}
        </select>
      </div>
      <div class="form-group">
        <label>Meta</label>
        <input type="number" min="1" class="contrato-meta-quantidade" value="" />
      </div>
      <div class="form-group">
        <label>Modo</label>
        <select class="contrato-meta-modo">
          <option value="fixo">Fixo</option>
          <option value="rodizio">Rodízio</option>
        </select>
      </div>
      <div class="form-group">
        <label>Ativo</label>
        <select class="contrato-meta-ativo">
          <option value="true" selected>Sim</option>
          <option value="false">Não</option>
        </select>
      </div>
    </div>
    <div class="form-row contrato-meta-grid-footer">
      <div class="form-group">
        <label>Observações</label>
        <input type="text" class="contrato-meta-observacoes" value="" />
      </div>
      <div class="form-group contrato-meta-actions">
        <button type="button" class="btn btn-danger btn-sm" onclick="toggleContratoMetaDelete(this)">Excluir</button>
      </div>
    </div>
  `
  container.appendChild(row)
}

function toggleContratoMetaDelete(btn) {
  const row = btn?.closest(".contrato-meta-edit-row")
  if (!row) return
  if (!row.dataset.metaId) {
    row.remove()
    return
  }
  const deleting = row.dataset.delete === "1"
  row.dataset.delete = deleting ? "0" : "1"
  row.classList.toggle("is-deleting", !deleting)
  btn.textContent = deleting ? "Excluir" : "Desfazer"
  btn.classList.toggle("btn-secondary", !deleting)
  btn.classList.toggle("btn-danger", deleting)
}

async function showContratoModal(contratoId = null) {
  if (!requireWriteAccess()) return
  const modalTitle = document.getElementById("contrato-modal-title")
  const createItemSection = document.getElementById("contrato-item-create-section")
  const editItemSection = document.getElementById("contrato-item-edit-section")
  const createMetaSection = document.getElementById("contrato-meta-create-section")
  const editMetaSection = document.getElementById("contrato-meta-edit-section")
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
    contratoModalState.arquivosCliente = await api.getAllArquivos({
      cliente_id: contrato.cliente_id,
    })
    const metas = contrato.arquivos_metas?.length
      ? contrato.arquivos_metas
      : await api.getContratoArquivosMetas(contrato.id)

    clienteSelect.innerHTML = `<option value="${contrato.cliente_id}">${escapeHtml(
      clientesPorIdCache[contrato.cliente_id] || `Cliente ${contrato.cliente_id}`,
    )}</option>`
    clienteSelect.value = String(contrato.cliente_id)
    clienteSelect.disabled = true
    createItemSection.style.display = "none"
    editItemSection.style.display = "block"
    createMetaSection.style.display = "none"
    editMetaSection.style.display = "block"
    renderContratoItensEdit(contrato.itens || [])
    renderContratoMetasEdit(metas || [])
  } else {
    const clientes = await api.getAllClientes()
    clienteSelect.innerHTML = [
      '<option value="">Selecione...</option>',
      ...clientes.map((c) => `<option value="${c.id}">${escapeHtml(c.nome)}</option>`),
    ].join("")
    clienteSelect.value = ""
    clienteSelect.disabled = false
    contratoModalState.arquivosCliente = []
    createItemSection.style.display = "block"
    editItemSection.style.display = "none"
    createMetaSection.style.display = "block"
    editMetaSection.style.display = "none"
    renderContratoMetasCreate()
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
  if (!requireWriteAccess()) return
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

      const metasRows = Array.from(
        document.querySelectorAll("#contrato-metas-edit-list .contrato-meta-edit-row"),
      )
      for (const row of metasRows) {
        const metaId = row.dataset.metaId
        const shouldDelete = row.dataset.delete === "1"

        if (shouldDelete) {
          if (metaId) {
            await api.deleteContratoArquivoMeta(id, metaId)
          }
          continue
        }

        const arquivoAudioId = Number(
          row.querySelector(".contrato-meta-arquivo")?.value,
        )
        const quantidadeMeta = Number(
          row.querySelector(".contrato-meta-quantidade")?.value,
        )
        const modoVeiculacao =
          row.querySelector(".contrato-meta-modo")?.value || "fixo"
        const ativo = row.querySelector(".contrato-meta-ativo")?.value === "true"
        const observacoes =
          row.querySelector(".contrato-meta-observacoes")?.value.trim() || null

        if (!arquivoAudioId || !quantidadeMeta || quantidadeMeta < 1) {
          throw new Error("Todas as metas precisam de arquivo e quantidade maior que 0")
        }

        if (metaId) {
          await api.updateContratoArquivoMeta(id, metaId, {
            quantidade_meta: quantidadeMeta,
            modo_veiculacao: modoVeiculacao,
            ativo,
            observacoes,
          })
        } else {
          await api.createContratoArquivoMeta(id, {
            arquivo_audio_id: arquivoAudioId,
            quantidade_meta: quantidadeMeta,
            modo_veiculacao: modoVeiculacao,
            ativo,
            observacoes,
          })
        }
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
        arquivos_metas: Array.from(
          document.querySelectorAll("#contrato-metas-create-list .contrato-meta-row"),
        )
          .map((row) => {
            const arquivoAudioId = Number(
              row.querySelector(".contrato-meta-arquivo")?.value,
            )
            const quantidadeMeta = Number(
              row.querySelector(".contrato-meta-quantidade")?.value,
            )
            const modoVeiculacao =
              row.querySelector(".contrato-meta-modo")?.value || "fixo"
            const ativo = row.querySelector(".contrato-meta-ativo")?.value === "true"
            const observacoes =
              row.querySelector(".contrato-meta-observacoes")?.value.trim() || null

            if (!arquivoAudioId && !quantidadeMeta) return null
            if (!arquivoAudioId || !quantidadeMeta || quantidadeMeta < 1) {
              throw new Error(
                "Metas por arquivo precisam de arquivo e quantidade maior que 0",
              )
            }

            return {
              arquivo_audio_id: arquivoAudioId,
              quantidade_meta: quantidadeMeta,
              modo_veiculacao: modoVeiculacao,
              ativo,
              observacoes,
            }
          })
          .filter(Boolean),
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
  if (!requireWriteAccess()) return
  const contrato = contratosCache.find((c) => c.id === Number(id))
  if (!contrato) return

  document.getElementById("nf-contrato-id").value = contrato.id
  document.getElementById("nf-status").value = contrato.status_nf || "pendente"
  document.getElementById("nf-numero").value = contrato.numero_nf || ""
  document.getElementById("nf-data-emissao").value = contrato.data_emissao_nf || ""

  openModal("modal-nota-fiscal")
}

async function saveNotaFiscal() {
  if (!requireWriteAccess()) return
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
  if (!requireWriteAccess()) return
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
