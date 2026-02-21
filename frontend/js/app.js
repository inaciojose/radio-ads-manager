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

const pollingState = {
  healthTimerId: null,
  pageTimerId: null,
  healthRunning: false,
  pageRunning: false,
}

function canWrite() {
  return appState.role === "admin" || appState.role === "operador"
}

function canManageUsers() {
  return appState.role === "admin"
}

function isPublicPage(pageName) {
  return pageName === "dashboard" || pageName === "veiculacoes"
}

function canAccessPage(pageName) {
  if (isPublicPage(pageName)) return true
  if (pageName === "usuarios") return canManageUsers()
  return Boolean(appState.user)
}

function requirePageAccess(pageName) {
  if (canAccessPage(pageName)) return true

  if (!appState.user) {
    showToast("Faça login para acessar esta página.", "warning")
    showLoginModal()
    return false
  }

  if (pageName === "usuarios") {
    showToast("Acesso restrito a administradores", "warning")
    return false
  }

  return false
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

  document.querySelectorAll("[data-auth-only='true']").forEach((el) => {
    el.style.display = appState.user ? "inline-flex" : "none"
  })

  document.querySelectorAll("[data-admin-only='true']").forEach((el) => {
    el.style.display = canManageUsers() ? "inline-flex" : "none"
  })

  if (!canAccessPage(appState.currentPage)) {
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
    restartPolling()
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
  if (!canAccessPage(appState.currentPage)) {
    showPage("dashboard")
  } else {
    loadPageData(appState.currentPage)
  }
  restartPolling()
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
  if (!requirePageAccess(pageName)) {
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
    "notas-fiscais": "Notas Fiscais",
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
  restartPolling()
}

// Carregar dados da página
async function loadPageData(pageName) {
  if (!canAccessPage(pageName)) {
    return loadDashboard()
  }

  switch (pageName) {
    case "dashboard":
      return loadDashboard()
    case "clientes":
      return loadClientes()
    case "contratos":
      return loadContratos()
    case "notas-fiscais":
      return loadNotasFiscais()
    case "veiculacoes":
      return loadVeiculacoes()
    case "arquivos":
      return loadArquivos()
    case "usuarios":
      if (canManageUsers()) {
        return loadUsuarios()
      } else {
        showToast("Acesso restrito a administradores", "warning")
      }
      break
  }
}

function clearPollingTimers() {
  if (pollingState.healthTimerId) {
    clearTimeout(pollingState.healthTimerId)
    pollingState.healthTimerId = null
  }
  if (pollingState.pageTimerId) {
    clearTimeout(pollingState.pageTimerId)
    pollingState.pageTimerId = null
  }
}

function getHealthCheckInterval() {
  return appState.apiOnline
    ? CONFIG.HEALTH_CHECK_INTERVAL_ONLINE
    : CONFIG.HEALTH_CHECK_INTERVAL_OFFLINE
}

function getPageRefreshInterval(pageName) {
  return CONFIG.PAGE_REFRESH_INTERVALS?.[pageName] || null
}

function scheduleHealthPolling() {
  if (document.hidden) return

  const interval = getHealthCheckInterval()
  if (!interval) return

  pollingState.healthTimerId = setTimeout(async () => {
    if (!pollingState.healthRunning) {
      pollingState.healthRunning = true
      try {
        await checkAPIStatus()
      } finally {
        pollingState.healthRunning = false
      }
    }
    scheduleHealthPolling()
  }, interval)
}

function schedulePagePolling() {
  if (document.hidden) return

  const interval = getPageRefreshInterval(appState.currentPage)
  if (!interval) return

  pollingState.pageTimerId = setTimeout(async () => {
    if (!pollingState.pageRunning) {
      pollingState.pageRunning = true
      try {
        await loadPageData(appState.currentPage)
      } finally {
        pollingState.pageRunning = false
      }
    }
    schedulePagePolling()
  }, interval)
}

function restartPolling() {
  clearPollingTimers()
  if (document.hidden) return
  scheduleHealthPolling()
  schedulePagePolling()
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
  await loadDashboard()
  restartPolling()

  console.log("✅ Aplicação carregada")
})

document.addEventListener("visibilitychange", () => {
  if (document.hidden) {
    clearPollingTimers()
    return
  }

  checkAPIStatus()
  loadPageData(appState.currentPage)
  restartPolling()
})

window.addEventListener("radio-ads-auth-required", (event) => {
  if (appState.user) {
    appState.user = null
    appState.role = "convidado"
    updateAuthUI()
  }

  if (!isPublicPage(appState.currentPage)) {
    showPage("dashboard")
  }

  if (!document.getElementById("modal-login")?.classList.contains("active")) {
    showLoginModal()
  }
})
