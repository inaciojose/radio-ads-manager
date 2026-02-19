/**
 * app.js - Aplicação Principal
 */

// Estado da aplicação
const appState = {
  currentPage: "dashboard",
  apiOnline: false,
  user: null,
  role: "convidado",
}

function canWrite() {
  return appState.role === "admin" || appState.role === "operador"
}

function canManageUsers() {
  return appState.role === "admin"
}

function requireWriteAccess(message = "Esta ação exige login.") {
  if (canWrite()) return true
  showToast(message, "warning")
  showLoginModal()
  return false
}

function updateAuthUI() {
  const badge = document.getElementById("current-user-badge")
  const btnLogin = document.getElementById("btn-login")
  const btnLogout = document.getElementById("btn-logout")

  if (appState.user) {
    badge.textContent = `${appState.user.nome} (${appState.role})`
    badge.className = "badge badge-info"
    btnLogin.style.display = "none"
    btnLogout.style.display = "inline-flex"
  } else {
    badge.textContent = "Convidado"
    badge.className = "badge badge-secondary"
    btnLogin.style.display = "inline-flex"
    btnLogout.style.display = "none"
  }

  document.querySelectorAll("[data-requires-write='true']").forEach((el) => {
    el.style.display = canWrite() ? "inline-flex" : "none"
  })

  document.querySelectorAll("[data-admin-only='true']").forEach((el) => {
    el.style.display = canManageUsers() ? "inline-flex" : "none"
  })

  if (!canManageUsers() && appState.currentPage === "usuarios") {
    showPage("dashboard")
  }
}

async function restoreSession() {
  if (!api.token) {
    appState.user = null
    appState.role = "convidado"
    updateAuthUI()
    return
  }

  try {
    const me = await api.me()
    appState.user = me
    appState.role = me.role
  } catch {
    api.setAuthToken(null)
    appState.user = null
    appState.role = "convidado"
  }

  updateAuthUI()
}

function showLoginModal() {
  document.getElementById("login-username").value = ""
  document.getElementById("login-password").value = ""
  openModal("modal-login")
}

async function login() {
  const username = document.getElementById("login-username").value.trim()
  const password = document.getElementById("login-password").value

  if (!username || !password) {
    showToast("Informe usuário e senha", "warning")
    return
  }

  try {
    showLoading()
    const payload = await api.login(username, password)
    api.setAuthToken(payload.access_token)
    appState.user = payload.usuario
    appState.role = payload.usuario.role
    updateAuthUI()
    closeModal()
    showToast("Sessão iniciada", "success")
    await loadPageData(appState.currentPage)
  } catch (error) {
    showToast(error.message || "Erro ao autenticar", "error")
  } finally {
    hideLoading()
  }
}

function logout() {
  api.setAuthToken(null)
  appState.user = null
  appState.role = "convidado"
  updateAuthUI()
  showToast("Sessão finalizada", "info")
  loadPageData(appState.currentPage)
}

// Verificar status da API
async function checkAPIStatus() {
  try {
    await api.checkHealth()
    appState.apiOnline = true
    document.getElementById("api-status").classList.remove("offline")
    document.getElementById("api-status").classList.add("online")
    document.getElementById("api-status-text").textContent = "API Online"
  } catch (error) {
    appState.apiOnline = false
    document.getElementById("api-status").classList.remove("online")
    document.getElementById("api-status").classList.add("offline")
    document.getElementById("api-status-text").textContent = "API Offline"
  }
}

// Navegação entre páginas
function showPage(pageName, evt) {
  if (pageName === "usuarios" && !canManageUsers()) {
    showToast("Acesso restrito a administradores", "warning")
    return
  }

  // Atualizar estado
  appState.currentPage = pageName

  // Atualizar nav menu
  document.querySelectorAll(".nav-item").forEach((item) => {
    item.classList.remove("active")
  })
  if (evt?.target) {
    const navItem = evt.target.closest(".nav-item")
    if (navItem) navItem.classList.add("active")
  }

  // Atualizar título
  const titles = {
    dashboard: "Dashboard",
    clientes: "Clientes",
    contratos: "Contratos",
    veiculacoes: "Veiculações",
    arquivos: "Arquivos",
    usuarios: "Usuários",
  }
  document.getElementById("page-title").textContent = titles[pageName]

  // Mostrar página
  document.querySelectorAll(".page").forEach((page) => {
    page.classList.remove("active")
  })
  document.getElementById(`page-${pageName}`).classList.add("active")

  // Carregar dados da página
  loadPageData(pageName)
}

// Carregar dados da página
async function loadPageData(pageName) {
  switch (pageName) {
    case "dashboard":
      loadDashboard()
      break
    case "clientes":
      loadClientes()
      break
    case "contratos":
      loadContratos()
      break
    case "veiculacoes":
      loadVeiculacoes()
      break
    case "arquivos":
      loadArquivos()
      break
    case "usuarios":
      if (canManageUsers()) {
        loadUsuarios()
      } else {
        showToast("Acesso restrito a administradores", "warning")
      }
      break
  }
}

// Refresh página atual
function refreshCurrentPage(evt) {
  const btn = evt?.target?.closest(".btn-refresh")
  if (btn) {
    btn.querySelector("i").style.animation = "spin 1s linear"
    setTimeout(() => {
      btn.querySelector("i").style.animation = ""
    }, 1000)
  }

  loadPageData(appState.currentPage)
}

// Inicialização
document.addEventListener("DOMContentLoaded", async () => {
  console.log("🚀 Radio Ads Manager iniciando...")

  // Verificar API
  await checkAPIStatus()
  await restoreSession()

  // Carregar dashboard
  loadDashboard()

  // Auto-refresh a cada 30 segundos (se habilitado)
  if (CONFIG.AUTO_REFRESH_INTERVAL) {
    setInterval(() => {
      if (
        appState.currentPage === "dashboard" ||
        appState.currentPage === "veiculacoes"
      ) {
        loadPageData(appState.currentPage)
      }
    }, CONFIG.AUTO_REFRESH_INTERVAL)
  }

  console.log("✅ Aplicação carregada")
})

// Verificar API periodicamente
setInterval(checkAPIStatus, 30000)
