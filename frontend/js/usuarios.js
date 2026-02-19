/**
 * usuarios.js - Administração de usuários (admin).
 */

let usuariosCache = []
let usuariosSearchTimer = null

const usuariosState = {
  page: 1,
  pageSize: 20,
  hasNext: false,
}

async function loadUsuarios(page = 1) {
  if (!canManageUsers()) return

  const busca = (document.getElementById("search-usuarios")?.value || "").trim()
  const targetPage = Math.max(1, page)
  const skip = (targetPage - 1) * usuariosState.pageSize

  try {
    showLoading()
    const usuarios = await api.getUsuarios({
      skip,
      limit: usuariosState.pageSize,
      ...(busca ? { busca } : {}),
    })

    if (targetPage > 1 && usuarios.length === 0) {
      await loadUsuarios(targetPage - 1)
      return
    }

    usuariosCache = usuarios
    usuariosState.page = targetPage
    usuariosState.hasNext = usuarios.length === usuariosState.pageSize

    renderUsuarios(usuariosCache)
    updateUsuariosPagination()
  } catch (error) {
    showToast(error.message || "Erro ao carregar usuários", "error")
  } finally {
    hideLoading()
  }
}

function renderUsuarios(items) {
  const tbody = document.querySelector("#table-usuarios tbody")
  if (!tbody) return

  if (!items.length) {
    tbody.innerHTML = '<tr><td colspan="5" class="text-center">Sem usuários</td></tr>'
    return
  }

  tbody.innerHTML = items
    .map(
      (u) => `
      <tr>
        <td>${escapeHtml(u.username)}</td>
        <td>${escapeHtml(u.nome)}</td>
        <td>${getStatusBadge(u.role, "user_role")}</td>
        <td>${getStatusBadge(String(u.ativo), "arquivo")}</td>
        <td>
          <button class="btn btn-sm btn-secondary" onclick="showUsuarioModal(${u.id})">Editar</button>
          <button class="btn btn-sm btn-primary" onclick="toggleUsuarioAtivo(${u.id})">
            ${u.ativo ? "Inativar" : "Ativar"}
          </button>
          ${
            appState.user?.id === u.id
              ? '<span class="badge badge-secondary">Atual</span>'
              : `<button class="btn btn-sm btn-danger" onclick="removerUsuario(${u.id})">Excluir</button>`
          }
        </td>
      </tr>
    `,
    )
    .join("")
}

function updateUsuariosPagination() {
  const pageInfo = document.getElementById("usuarios-page-info")
  const prevBtn = document.getElementById("usuarios-prev")
  const nextBtn = document.getElementById("usuarios-next")

  if (pageInfo) {
    pageInfo.textContent = `Página ${usuariosState.page}`
  }
  if (prevBtn) {
    prevBtn.disabled = usuariosState.page <= 1
  }
  if (nextBtn) {
    nextBtn.disabled = !usuariosState.hasNext
  }
}

function changeUsuariosPage(delta) {
  if (!canManageUsers()) return
  if (delta > 0 && !usuariosState.hasNext) return
  const target = Math.max(1, usuariosState.page + delta)
  loadUsuarios(target)
}

function searchUsuarios() {
  clearTimeout(usuariosSearchTimer)
  usuariosSearchTimer = setTimeout(() => {
    loadUsuarios(1)
  }, 300)
}

function showUsuarioModal(usuarioId = null) {
  if (!canManageUsers()) return

  const usuario = usuarioId
    ? usuariosCache.find((u) => u.id === Number(usuarioId))
    : null
  const isEdit = Boolean(usuario)

  document.getElementById("usuario-modal-title").textContent = isEdit
    ? "Editar Usuário"
    : "Novo Usuário"

  document.getElementById("usuario-id").value = usuario?.id || ""
  document.getElementById("usuario-username").value = usuario?.username || ""
  document.getElementById("usuario-nome").value = usuario?.nome || ""
  document.getElementById("usuario-role").value = usuario?.role || "operador"
  document.getElementById("usuario-ativo").value = String(usuario?.ativo ?? true)
  document.getElementById("usuario-password").value = ""

  document.getElementById("usuario-username").disabled = false
  document.getElementById("usuario-senha-obrigatoria").textContent = isEdit ? "(opcional)" : "*"

  openModal("modal-usuario")
}

async function saveUsuario() {
  if (!canManageUsers()) return

  const id = document.getElementById("usuario-id").value
  const isEdit = Boolean(id)

  const payload = {
    username: document.getElementById("usuario-username").value.trim(),
    nome: document.getElementById("usuario-nome").value.trim(),
    role: document.getElementById("usuario-role").value,
    ativo: document.getElementById("usuario-ativo").value === "true",
  }
  const password = document.getElementById("usuario-password").value

  if (!payload.username || !payload.nome) {
    showToast("Username e nome são obrigatórios", "warning")
    return
  }

  if (!isEdit && !password) {
    showToast("Senha é obrigatória para novo usuário", "warning")
    return
  }

  try {
    showLoading()
    if (isEdit) {
      if (!canManageUsers()) return
      if (password) payload.password = password
      await api.updateUsuario(id, payload)
      showToast("Usuário atualizado", "success")
    } else {
      await api.createUsuario({
        ...payload,
        password,
      })
      showToast("Usuário criado", "success")
    }

    closeModal()
    await loadUsuarios(usuariosState.page)
  } catch (error) {
    showToast(error.message || "Erro ao salvar usuário", "error")
  } finally {
    hideLoading()
  }
}

async function toggleUsuarioAtivo(usuarioId) {
  if (!canManageUsers()) return

  const usuario = usuariosCache.find((u) => u.id === Number(usuarioId))
  if (!usuario) return

  try {
    showLoading()
    await api.updateUsuario(usuario.id, { ativo: !usuario.ativo })
    showToast("Status do usuário atualizado", "success")
    await loadUsuarios(usuariosState.page)
  } catch (error) {
    showToast(error.message || "Erro ao atualizar usuário", "error")
  } finally {
    hideLoading()
  }
}

async function removerUsuario(usuarioId) {
  if (!canManageUsers()) return
  if (!confirmAction("Deseja excluir este usuário?")) return

  try {
    showLoading()
    await api.deleteUsuario(usuarioId)
    showToast("Usuário removido", "success")
    await loadUsuarios(usuariosState.page)
  } catch (error) {
    showToast(error.message || "Erro ao excluir usuário", "error")
  } finally {
    hideLoading()
  }
}
