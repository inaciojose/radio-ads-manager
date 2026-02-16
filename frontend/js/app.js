/**
 * app.js - Aplicação Principal
 */

// Estado da aplicação
const appState = {
  currentPage: "dashboard",
  apiOnline: false,
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
