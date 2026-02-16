/**
 * clientes.js - CRUD de clientes.
 */

let clientesCache = []

async function loadClientes() {
  try {
    showLoading()
    clientesCache = await api.getClientes({ limit: 1000 })
    renderClientes(clientesCache)
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
    tbody.innerHTML = '<tr><td colspan="6" class="text-center">Sem clientes</td></tr>'
    return
  }

  tbody.innerHTML = items
    .map(
      (c) => `
      <tr>
        <td>${c.nome}</td>
        <td>${c.cnpj_cpf || "-"}</td>
        <td>${c.email || "-"}</td>
        <td>${c.telefone || "-"}</td>
        <td>${getStatusBadge(c.status, "cliente")}</td>
        <td>
          <button class="btn btn-sm btn-secondary" onclick="editarCliente(${c.id})">Editar</button>
          <button class="btn btn-sm btn-danger" onclick="removerCliente(${c.id})">Excluir</button>
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
        (c.cnpj_cpf || "").toLowerCase().includes(termo),
    ),
  )
}

function showClienteModal(cliente = null) {
  document.getElementById("cliente-modal-title").textContent = cliente
    ? "Editar Cliente"
    : "Novo Cliente"

  document.getElementById("cliente-id").value = cliente?.id || ""
  document.getElementById("cliente-nome").value = cliente?.nome || ""
  document.getElementById("cliente-cnpj").value = cliente?.cnpj_cpf || ""
  document.getElementById("cliente-telefone").value = cliente?.telefone || ""
  document.getElementById("cliente-email").value = cliente?.email || ""
  document.getElementById("cliente-endereco").value = cliente?.endereco || ""
  document.getElementById("cliente-status").value = cliente?.status || "ativo"
  document.getElementById("cliente-observacoes").value = cliente?.observacoes || ""

  openModal("modal-cliente")
}

async function saveCliente() {
  const id = document.getElementById("cliente-id").value
  const payload = {
    nome: document.getElementById("cliente-nome").value.trim(),
    cnpj_cpf: document.getElementById("cliente-cnpj").value.trim() || null,
    telefone: document.getElementById("cliente-telefone").value.trim() || null,
    email: document.getElementById("cliente-email").value.trim() || null,
    endereco: document.getElementById("cliente-endereco").value.trim() || null,
    status: document.getElementById("cliente-status").value,
    observacoes:
      document.getElementById("cliente-observacoes").value.trim() || null,
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
