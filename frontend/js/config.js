/**
 * config.js - Configurações da Aplicação
 */

const isLocalhost =
  window.location.hostname === "localhost" ||
  window.location.hostname === "127.0.0.1"
const defaultApiBaseURL = isLocalhost
  ? `${window.location.protocol}//${window.location.hostname}:8000`
  : `${window.location.origin}/api`

const CONFIG = {
  // URL da API (permite override com localStorage.RADIO_ADS_API_BASE_URL)
  API_BASE_URL:
    window.localStorage.getItem("RADIO_ADS_API_BASE_URL") || defaultApiBaseURL,

  // Intervalo de atualização automática (em milissegundos)
  AUTO_REFRESH_INTERVAL: 30000, // 30 segundos

  // Polling adaptativo
  HEALTH_CHECK_INTERVAL_ONLINE: 60000, // 60 segundos
  HEALTH_CHECK_INTERVAL_OFFLINE: 30000, // 30 segundos
  PAGE_REFRESH_INTERVALS: {
    dashboard: 30000,
    veiculacoes: 30000,
  },

  // Timeout das requisições
  REQUEST_TIMEOUT: 10000, // 10 segundos

  // Paginação
  DEFAULT_PAGE_SIZE: 500,

  // Formatos
  DATE_FORMAT: "DD/MM/YYYY",
  DATETIME_FORMAT: "DD/MM/YYYY HH:mm:ss",
  TIME_FORMAT: "HH:mm:ss",

  // Status
  STATUS_CLIENTE: {
    ativo: "Ativo",
    inativo: "Inativo",
  },

  STATUS_CONTRATO: {
    ativo: "Ativo",
    concluído: "Concluído",
    cancelado: "Cancelado",
  },

  STATUS_NF: {
    pendente: "Pendente",
    emitida: "Emitida",
    paga: "Paga",
  },

  TIPOS_PROGRAMA: ["musical", "esporte", "jornal", "variedades"],

  // Cores dos gráficos
  CHART_COLORS: [
    "#2563eb", // blue
    "#10b981", // green
    "#f59e0b", // orange
    "#ef4444", // red
    "#8b5cf6", // purple
    "#ec4899", // pink
    "#14b8a6", // teal
    "#f97316", // orange-red
  ],
}
