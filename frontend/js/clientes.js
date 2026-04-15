/**
 * clientes.js - CRUD de clientes.
 */

let clientesCache = []

async function loadClientes() {
  const status = document.getElementById("filter-cliente-status")?.value
  try {
    showLoading()
    clientesCache = await api.getAllClientes({ ...(status ? { status } : {}) })
    renderClientes(clientesCache)
  } catch (error) {
    showToast(error.message || "Erro ao carregar clientes", "error")
  } finally {
    hideLoading()
  }
}

// Cache de progresso: { cliente_id: { veiculacoes_hoje, meta_diaria_total, tem_alerta } }
let _progressoCache = {}

async function _carregarProgressoClientes(clientes) {
  const ativos = clientes.filter((c) => c.status === "ativo" && c.codigo_chamada)
  if (!ativos.length) return
  await Promise.allSettled(
    ativos.map(async (c) => {
      try {
        const prog = await api.getClienteProgresso(c.id)
        _progressoCache[c.id] = prog
      } catch {
        // silencioso — progresso indisponível
      }
    }),
  )
}

function _renderProgressoCell(clienteId) {
  const prog = _progressoCache[clienteId]
  if (!prog) return '<span class="text-muted">—</span>'

  const hoje = prog.veiculacoes_hoje ?? 0
  if (prog.meta_diaria_total == null) {
    return `<span>${hoje} vei.</span>`
  }

  const alerta = prog.tem_alerta
  const cor = alerta ? "badge-warning" : "badge-success"
  return `<span class="badge ${cor}" title="Meta: ${prog.meta_diaria_total}/dia">${hoje} / ${prog.meta_diaria_total}</span>`
}

async function loadClientes() {
  const status = document.getElementById("filter-cliente-status")?.value
  try {
    showLoading()
    _progressoCache = {}
    clientesCache = await api.getAllClientes({ ...(status ? { status } : {}) })
    renderClientes(clientesCache)
    // Carrega progresso em background e atualiza a tabela
    _carregarProgressoClientes(clientesCache).then(() => renderClientes(clientesCache))
  } catch (error) {
    showToast(error.message || "Erro ao carregar clientes", "error")
  } finally {
    hideLoading()
  }
}

function renderClientes(items) {
  const tbody = document.querySelector("#table-clientes tbody")
  if (!tbody) return

  if (!items.length) {
    tbody.innerHTML = '<tr><td colspan="7" class="text-center">Sem clientes</td></tr>'
    return
  }

  tbody.innerHTML = items
    .map(
      (c) => `
      <tr>
        <td>${escapeHtml(c.nome)}</td>
        <td>${c.codigo_chamada != null ? `<code>(${c.codigo_chamada})</code>` : '<span class="text-muted">—</span>'}</td>
        <td>${escapeHtml(c.cnpj_cpf || "-")}</td>
        <td>${_renderProgressoCell(c.id)}</td>
        <td>${escapeHtml(c.telefone || "-")}</td>
        <td>${getStatusBadge(c.status, "cliente")}</td>
        <td>
          ${
            canWrite()
              ? `<button class="btn btn-sm btn-secondary" onclick="editarCliente(${c.id})">Editar</button>
                 <button class="btn btn-sm btn-danger" onclick="removerCliente(${c.id})">Excluir</button>`
              : '<span class="badge badge-secondary">Somente leitura</span>'
          }
        </td>
      </tr>
    `,
    )
    .join("")
}

function searchClientes() {
  const termo = (document.getElementById("search-clientes")?.value || "")
    .trim()
    .toLowerCase()

  if (!termo) {
    renderClientes(clientesCache)
    return
  }

  renderClientes(
    clientesCache.filter(
      (c) =>
        c.nome.toLowerCase().includes(termo) ||
        (c.cnpj_cpf || "").toLowerCase().includes(termo) ||
        String(c.codigo_chamada ?? "").includes(termo),
    ),
  )
}

function showClienteModal(cliente = null) {
  if (!requireWriteAccess()) return
  document.getElementById("cliente-modal-title").textContent = cliente
    ? "Editar Cliente"
    : "Novo Cliente"

  document.getElementById("cliente-id").value = cliente?.id || ""
  document.getElementById("cliente-nome").value = cliente?.nome || ""
  document.getElementById("cliente-cnpj").value = maskCnpjCpf(cliente?.cnpj_cpf || "")
  document.getElementById("cliente-codigo-chamada").value = cliente?.codigo_chamada ?? ""
  document.getElementById("cliente-telefone").value = maskTelefone(cliente?.telefone || "")
  document.getElementById("cliente-email").value = cliente?.email || ""
  document.getElementById("cliente-endereco").value = cliente?.endereco || ""
  document.getElementById("cliente-status").value = cliente?.status || "ativo"
  document.getElementById("cliente-observacoes").value = cliente?.observacoes || ""

  openModal("modal-cliente")
}

async function saveCliente() {
  if (!requireWriteAccess()) return
  const id = document.getElementById("cliente-id").value
  const codigoChamadaRaw = document.getElementById("cliente-codigo-chamada").value.trim()
  const payload = {
    nome: document.getElementById("cliente-nome").value.trim(),
    cnpj_cpf: document.getElementById("cliente-cnpj").value.trim() || null,
    codigo_chamada: codigoChamadaRaw ? Number(codigoChamadaRaw) : null,
    telefone: document.getElementById("cliente-telefone").value.trim() || null,
    email: document.getElementById("cliente-email").value.trim() || null,
    endereco: document.getElementById("cliente-endereco").value.trim() || null,
    status: document.getElementById("cliente-status").value,
    observacoes: document.getElementById("cliente-observacoes").value.trim() || null,
  }

  if (!payload.nome) {
    showToast("Nome e obrigatorio", "warning")
    return
  }

  try {
    showLoading()
    if (id) {
      await api.updateCliente(id, payload)
      showToast("Cliente atualizado", "success")
    } else {
      await api.createCliente(payload)
      showToast("Cliente criado", "success")
    }
    closeModal()
    await loadClientes()
  } catch (error) {
    showToast(error.message || "Erro ao salvar cliente", "error")
  } finally {
    hideLoading()
  }
}

function editarCliente(id) {
  const cliente = clientesCache.find((c) => c.id === id)
  if (!cliente) return
  showClienteModal(cliente)
}

async function removerCliente(id) {
  if (!requireWriteAccess()) return
  if (!confirmAction("Deseja excluir este cliente?")) return

  try {
    showLoading()
    await api.deleteCliente(id)
    showToast("Cliente removido", "success")
    await loadClientes()
  } catch (error) {
    showToast(error.message || "Erro ao excluir cliente", "error")
  } finally {
    hideLoading()
  }
}

function abrirRelatorioClientes() {
  openRelatorioModal("Clientes", clientesCache.length, exportarClientes)
}

async function exportarClientes(formato) {
  try {
    showLoading()
    const status = document.getElementById("filter-cliente-status")?.value || ""
    const busca = (document.getElementById("search-clientes")?.value || "").trim()
    const params = {}
    if (status) params.status = status
    if (busca) params.busca = busca
    if (formato === "excel") {
      await api.exportarClientesExcel(params)
    } else {
      await api.exportarClientesPdf(params)
    }
  } catch (error) {
    showToast(error.message || "Erro ao exportar", "error")
  } finally {
    hideLoading()
  }
}
