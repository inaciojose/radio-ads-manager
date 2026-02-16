/**
 * config.js - Configurações da Aplicação
 */

const CONFIG = {
  // URL da API
  API_BASE_URL: "http://localhost:8000",

  // Intervalo de atualização automática (em milissegundos)
  AUTO_REFRESH_INTERVAL: 30000, // 30 segundos

  // Timeout das requisições
  REQUEST_TIMEOUT: 10000, // 10 segundos

  // Paginação
  DEFAULT_PAGE_SIZE: 50,

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
