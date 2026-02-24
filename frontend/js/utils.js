/**
 * utils.js - Funções Utilitárias
 */

// Formatação de Data e Hora
const formatDate = (dateString) => {
  if (!dateString) return "-"
  const date = new Date(dateString)
  return date.toLocaleDateString("pt-BR")
}

const formatDateTime = (dateString) => {
  if (!dateString) return "-"
  const date = new Date(dateString)
  return date.toLocaleString("pt-BR")
}

const formatTime = (dateString) => {
  if (!dateString) return "-"
  const date = new Date(dateString)
  return date.toLocaleTimeString("pt-BR")
}

// Formatação de Valores
const formatCurrency = (value) => {
  if (value === null || value === undefined) return "-"
  return new Intl.NumberFormat("pt-BR", {
    style: "currency",
    currency: "BRL",
  }).format(value)
}

const formatPercent = (value) => {
  if (value === null || value === undefined) return "-"
  return `${value.toFixed(1)}%`
}

// Loading
const showLoading = () => {
  document.getElementById("loading-overlay").classList.add("active")
}

const hideLoading = () => {
  document.getElementById("loading-overlay").classList.remove("active")
}

// Toast Notifications
const showToast = (message, type = "info") => {
  const container = document.getElementById("toast-container")
  const toast = document.createElement("div")
  toast.className = `toast ${type}`

  const icon = {
    success: "fa-check-circle",
    error: "fa-times-circle",
    warning: "fa-exclamation-triangle",
    info: "fa-info-circle",
  }[type]

  const iconElement = document.createElement("i")
  iconElement.className = `fas ${icon}`

  const messageElement = document.createElement("span")
  messageElement.textContent = String(message || "")

  toast.appendChild(iconElement)
  toast.appendChild(messageElement)

  container.appendChild(toast)

  setTimeout(() => {
    toast.remove()
  }, 5000)
}

// Escape de texto para uso seguro em templates HTML
const escapeHtml = (value) => {
  if (value === null || value === undefined) return ""
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;")
}

// Modal
const openModal = (modalId) => {
  document.getElementById("modal-backdrop").classList.add("active")
  document.getElementById(modalId).classList.add("active")
}

const closeModal = () => {
  document.getElementById("modal-backdrop").classList.remove("active")
  document.querySelectorAll(".modal").forEach((modal) => {
    modal.classList.remove("active")
  })
}

// Badges de Status
const getStatusBadge = (status, type = "cliente") => {
  const badges = {
    cliente: {
      ativo: '<span class="badge badge-success">Ativo</span>',
      inativo: '<span class="badge badge-secondary">Inativo</span>',
    },
    contrato: {
      ativo: '<span class="badge badge-success">Ativo</span>',
      concluído: '<span class="badge badge-info">Concluído</span>',
      cancelado: '<span class="badge badge-danger">Cancelado</span>',
    },
    nf: {
      pendente: '<span class="badge badge-warning">Pendente</span>',
      emitida: '<span class="badge badge-info">Emitida</span>',
      paga: '<span class="badge badge-success">Paga</span>',
    },
    processado: {
      true: '<span class="badge badge-success">Sim</span>',
      false: '<span class="badge badge-warning">Não</span>',
    },
    arquivo: {
      true: '<span class="badge badge-success">Ativo</span>',
      false: '<span class="badge badge-secondary">Inativo</span>',
    },
    user_role: {
      admin: '<span class="badge badge-admin">Administrador</span>',
      operador: '<span class="badge badge-operador">Operador</span>',
    },
  }

  return badges[type]?.[status] || status
}

// Barra de Progresso
const getProgressBar = (current, total) => {
  const percent = total > 0 ? (current / total) * 100 : 0
  return `
        <div class="progress-bar">
            <div class="progress-fill" style="width: ${percent}%"></div>
        </div>
        <small>${current}/${total} (${percent.toFixed(1)}%)</small>
    `
}

// Debounce para inputs de busca
const debounce = (func, wait) => {
  let timeout
  return function executedFunction(...args) {
    const later = () => {
      clearTimeout(timeout)
      func(...args)
    }
    clearTimeout(timeout)
    timeout = setTimeout(later, wait)
  }
}

// Confirmar ação
const confirmAction = (message) => {
  return confirm(message)
}

// Obter data de hoje no formato YYYY-MM-DD (horário local, não UTC)
const getTodayDate = () => {
  const today = new Date()
  const year = today.getFullYear()
  const month = String(today.getMonth() + 1).padStart(2, "0")
  const day = String(today.getDate()).padStart(2, "0")
  return `${year}-${month}-${day}`
}

// Atualizar data/hora no header
const updateDateTime = () => {
  const now = new Date()
  const formatted = now.toLocaleDateString("pt-BR", {
    weekday: "long",
    year: "numeric",
    month: "long",
    day: "numeric",
  })
  document.getElementById("current-date").textContent = formatted
}

// Executar a cada minuto
setInterval(updateDateTime, 60000)
updateDateTime()
