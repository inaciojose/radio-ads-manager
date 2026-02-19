/**
 * api.js - Cliente da API
 * Funções para comunicação com o backend
 */

class API {
  constructor(baseURL) {
    this.baseURL = baseURL
    this.token = window.localStorage.getItem("RADIO_ADS_ACCESS_TOKEN") || null
  }

  /**
   * Faz uma requisição HTTP
   */
  async request(endpoint, options = {}) {
    const url = `${this.baseURL}${endpoint}`
    const controller = new AbortController()
    const timeoutMs = CONFIG.REQUEST_TIMEOUT || 10000
    const timeoutId = setTimeout(() => controller.abort(), timeoutMs)

    const config = {
      ...options,
      signal: controller.signal,
      headers: {
        ...options.headers,
      },
    }
    if (options.body && !config.headers["Content-Type"]) {
      config.headers["Content-Type"] = "application/json"
    }
    if (this.token) {
      config.headers.Authorization = `Bearer ${this.token}`
    }

    try {
      const response = await fetch(url, config)

      if (!response.ok) {
        const error = await response.json().catch(() => ({
          detail: `HTTP ${response.status}: ${response.statusText}`,
        }))
        throw new Error(error.detail || error.message || "Erro na requisição")
      }

      if (response.status === 204) return null
      return await response.json()
    } catch (error) {
      if (error.name === "AbortError") {
        throw new Error(`Tempo limite excedido (${timeoutMs}ms)`)
      }
      console.error("API Error:", error)
      throw error
    } finally {
      clearTimeout(timeoutId)
    }
  }

  async fetchAllPages(fetchPage, baseParams = {}) {
    const pageSize = Math.min(CONFIG.DEFAULT_PAGE_SIZE || 200, 1000)
    let skip = 0
    const allItems = []

    while (true) {
      const page = await fetchPage({
        ...baseParams,
        skip,
        limit: pageSize,
      })
      allItems.push(...page)

      if (page.length < pageSize) break
      skip += pageSize
    }

    return allItems
  }

  // ============================================
  // Health Check
  // ============================================

  async checkHealth() {
    return this.request("/health")
  }

  setAuthToken(token) {
    this.token = token
    if (token) {
      window.localStorage.setItem("RADIO_ADS_ACCESS_TOKEN", token)
    } else {
      window.localStorage.removeItem("RADIO_ADS_ACCESS_TOKEN")
    }
  }

  // ============================================
  // Clientes
  // ============================================

  async getClientes(params = {}) {
    const query = new URLSearchParams(params).toString()
    return this.request(`/clientes/${query ? "?" + query : ""}`)
  }

  async getAllClientes(params = {}) {
    return this.fetchAllPages((pageParams) => this.getClientes(pageParams), params)
  }

  async getCliente(id) {
    return this.request(`/clientes/${id}`)
  }

  async createCliente(data) {
    return this.request("/clientes/", {
      method: "POST",
      body: JSON.stringify(data),
    })
  }

  async updateCliente(id, data) {
    return this.request(`/clientes/${id}`, {
      method: "PUT",
      body: JSON.stringify(data),
    })
  }

  async deleteCliente(id) {
    return this.request(`/clientes/${id}`, {
      method: "DELETE",
    })
  }

  async getClienteResumo(id) {
    return this.request(`/clientes/${id}/resumo`)
  }

  // ============================================
  // Auth / Usuários
  // ============================================

  async login(username, password) {
    return this.request("/auth/login", {
      method: "POST",
      body: JSON.stringify({ username, password }),
    })
  }

  async me() {
    return this.request("/auth/me")
  }

  async getUsuarios(params = {}) {
    const query = new URLSearchParams(params).toString()
    return this.request(`/usuarios/${query ? "?" + query : ""}`)
  }

  async createUsuario(data) {
    return this.request("/usuarios/", {
      method: "POST",
      body: JSON.stringify(data),
    })
  }

  async updateUsuario(id, data) {
    return this.request(`/usuarios/${id}`, {
      method: "PATCH",
      body: JSON.stringify(data),
    })
  }

  async deleteUsuario(id) {
    return this.request(`/usuarios/${id}`, {
      method: "DELETE",
    })
  }

  // ============================================
  // Contratos
  // ============================================

  async getContratos(params = {}) {
    const query = new URLSearchParams(params).toString()
    return this.request(`/contratos/${query ? "?" + query : ""}`)
  }

  async getAllContratos(params = {}) {
    return this.fetchAllPages((pageParams) => this.getContratos(pageParams), params)
  }

  async getContrato(id) {
    return this.request(`/contratos/${id}`)
  }

  async createContrato(data) {
    return this.request("/contratos/", {
      method: "POST",
      body: JSON.stringify(data),
    })
  }

  async updateContrato(id, data) {
    return this.request(`/contratos/${id}`, {
      method: "PUT",
      body: JSON.stringify(data),
    })
  }

  async updateContratoItem(contratoId, itemId, data) {
    return this.request(`/contratos/${contratoId}/itens/${itemId}`, {
      method: "PUT",
      body: JSON.stringify(data),
    })
  }

  async getContratoArquivosMetas(contratoId) {
    return this.request(`/contratos/${contratoId}/arquivos-metas`)
  }

  async createContratoArquivoMeta(contratoId, data) {
    return this.request(`/contratos/${contratoId}/arquivos-metas`, {
      method: "POST",
      body: JSON.stringify(data),
    })
  }

  async updateContratoArquivoMeta(contratoId, metaId, data) {
    return this.request(`/contratos/${contratoId}/arquivos-metas/${metaId}`, {
      method: "PUT",
      body: JSON.stringify(data),
    })
  }

  async deleteContratoArquivoMeta(contratoId, metaId) {
    return this.request(`/contratos/${contratoId}/arquivos-metas/${metaId}`, {
      method: "DELETE",
    })
  }

  async getContratoFaturamentosMensais(contratoId, params = {}) {
    const query = new URLSearchParams(params).toString()
    return this.request(
      `/contratos/${contratoId}/faturamentos${query ? "?" + query : ""}`,
    )
  }

  async createContratoFaturamentoMensal(contratoId, data) {
    return this.request(`/contratos/${contratoId}/faturamentos`, {
      method: "POST",
      body: JSON.stringify(data),
    })
  }

  async emitirNotaFiscalMensal(contratoId, competencia, data) {
    return this.request(`/contratos/${contratoId}/faturamentos/${competencia}/emitir`, {
      method: "POST",
      body: JSON.stringify(data),
    })
  }

  async updateFaturamentoMensal(faturamentoId, data) {
    return this.request(`/contratos/faturamentos/${faturamentoId}`, {
      method: "PATCH",
      body: JSON.stringify(data),
    })
  }

  async updateNotaFiscal(id, params) {
    const query = new URLSearchParams(params).toString()
    return this.request(`/contratos/${id}/nota-fiscal?${query}`, {
      method: "PATCH",
    })
  }

  async deleteContrato(id) {
    return this.request(`/contratos/${id}`, {
      method: "DELETE",
    })
  }

  async getEstatisticasContratos() {
    return this.request("/contratos/resumo/estatisticas")
  }

  async getResumoMetaDiariaHoje() {
    return this.request("/contratos/resumo/meta-diaria-hoje")
  }

  async getContratosCliente(clienteId) {
    return this.request(`/contratos/cliente/${clienteId}/resumo`)
  }

  // ============================================
  // Veiculações
  // ============================================

  async getVeiculacoes(params = {}) {
    const query = new URLSearchParams(params).toString()
    return this.request(`/veiculacoes/${query ? "?" + query : ""}`)
  }

  async getAllVeiculacoes(params = {}) {
    return this.fetchAllPages((pageParams) => this.getVeiculacoes(pageParams), params)
  }

  async getVeiculacao(id) {
    return this.request(`/veiculacoes/${id}`)
  }

  async createVeiculacao(data) {
    return this.request("/veiculacoes/", {
      method: "POST",
      body: JSON.stringify(data),
    })
  }

  async deleteVeiculacao(id) {
    return this.request(`/veiculacoes/${id}`, {
      method: "DELETE",
    })
  }

  async getVeiculacoesHoje() {
    return this.request("/veiculacoes/hoje/resumo")
  }

  async processarVeiculacoes(params = {}) {
    const query = new URLSearchParams(params).toString()
    return this.request(`/veiculacoes/processar${query ? "?" + query : ""}`, {
      method: "POST",
    })
  }

  async criarLoteVeiculacoes(data) {
    return this.request("/veiculacoes/lancamentos/lote", {
      method: "POST",
      body: JSON.stringify(data),
    })
  }

  async getEstatisticasVeiculacoes(dataInicio, dataFim) {
    return this.request(
      `/veiculacoes/estatisticas/periodo?data_inicio=${dataInicio}&data_fim=${dataFim}`,
    )
  }

  async getVeiculacoesDetalhadas(params = {}) {
    const query = new URLSearchParams(params).toString()
    return this.request(
      `/veiculacoes/detalhadas/lista${query ? "?" + query : ""}`,
    )
  }

  // ============================================
  // Arquivos
  // ============================================

  async getArquivos(params = {}) {
    const query = new URLSearchParams(params).toString()
    return this.request(`/arquivos/${query ? "?" + query : ""}`)
  }

  async getAllArquivos(params = {}) {
    return this.fetchAllPages((pageParams) => this.getArquivos(pageParams), params)
  }

  async getArquivo(id) {
    return this.request(`/arquivos/${id}`)
  }

  async createArquivo(data) {
    return this.request("/arquivos/", {
      method: "POST",
      body: JSON.stringify(data),
    })
  }

  async updateArquivo(id, data) {
    return this.request(`/arquivos/${id}`, {
      method: "PUT",
      body: JSON.stringify(data),
    })
  }

  async deleteArquivo(id) {
    return this.request(`/arquivos/${id}`, {
      method: "DELETE",
    })
  }

  async toggleArquivoAtivo(id) {
    return this.request(`/arquivos/${id}/toggle-ativo`, {
      method: "PATCH",
    })
  }

  async getEstatisticasArquivo(id) {
    return this.request(`/arquivos/${id}/estatisticas`)
  }

  async getArquivosNaoUtilizados(dias = 30) {
    return this.request(`/arquivos/relatorios/nao-utilizados?dias=${dias}`)
  }
}

// Instância global da API
const api = new API(CONFIG.API_BASE_URL)
