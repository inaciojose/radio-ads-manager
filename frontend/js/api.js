/**
 * api.js - Cliente da API
 * Funções para comunicação com o backend
 */

class API {
  constructor(baseURL) {
    this.baseURL = baseURL
    this.token = window.localStorage.getItem("RADIO_ADS_ACCESS_TOKEN") || null
  }

  getFieldLabel(path) {
    const labels = {
      username: "Username",
      nome: "Nome",
      password: "Senha",
      role: "Perfil",
      ativo: "Status",
      cnpj_cpf: "CNPJ/CPF",
      email: "Email",
      telefone: "Telefone",
      endereco: "Endereço",
      status: "Status",
      status_nf: "Status NF",
      status_contrato: "Status do contrato",
      data_inicio: "Data início",
      data_fim: "Data fim",
      data_emissao: "Data emissão",
      data_pagamento: "Data pagamento",
      competencia: "Competência",
      frequencia: "Frequência",
      valor: "Valor",
      valor_total: "Valor total",
      quantidade_contratada: "Quantidade contratada",
      quantidade_diaria_meta: "Meta diária",
      quantidade_meta: "Quantidade da meta",
      tipo_programa: "Tipo de programa",
      arquivo_audio_id: "Arquivo de áudio",
      cliente_id: "Cliente",
      numero_nf: "Número da NF",
      numero: "Número",
    }
    return labels[path] || path
  }

  normalizeValidationMessage(message = "") {
    const raw = String(message || "")
    const lower = raw.toLowerCase()

    if (lower.includes("field required")) return "Campo obrigatório."

    const minLen = raw.match(/at least (\d+) characters/i)
    if (minLen) return `Deve ter no mínimo ${minLen[1]} caracteres.`

    const maxLen = raw.match(/at most (\d+) characters/i)
    if (maxLen) return `Deve ter no máximo ${maxLen[1]} caracteres.`

    const greaterEq = raw.match(/greater than or equal to ([\d.-]+)/i)
    if (greaterEq) return `Deve ser maior ou igual a ${greaterEq[1]}.`

    const greater = raw.match(/greater than ([\d.-]+)/i)
    if (greater) return `Deve ser maior que ${greater[1]}.`

    const lowerEq = raw.match(/less than or equal to ([\d.-]+)/i)
    if (lowerEq) return `Deve ser menor ou igual a ${lowerEq[1]}.`

    if (lower.includes("valid date")) return "Data inválida."
    if (lower.includes("valid integer")) return "Número inteiro inválido."
    if (lower.includes("valid number")) return "Número inválido."
    if (lower.includes("valid boolean")) return "Valor inválido (esperado verdadeiro/falso)."
    if (lower.includes("valid string")) return "Texto inválido."

    return raw || "Valor inválido."
  }

  notifyAuthRequired(message) {
    if (typeof window === "undefined" || !window.dispatchEvent) return
    window.dispatchEvent(
      new CustomEvent("radio-ads-auth-required", {
        detail: { message },
      }),
    )
  }

  formatErrorMessage(status, payload) {
    const detail = payload?.detail
    const fallback = payload?.message || `HTTP ${status}: ${payload?.statusText || "Erro na requisição"}`
    const codeSuffix = payload?.code ? ` (Código: ${payload.code})` : ""

    if (status === 401) {
      return "Sessão expirada ou inválida. Faça login novamente."
    }
    if (status === 403) {
      return "Você não tem permissão para realizar esta ação."
    }
    if (status >= 500) {
      const errorId = payload?.error_id ? ` Código: ${payload.error_id}` : ""
      return `Erro interno do servidor.${errorId}`
    }

    if (!detail) return fallback

    if (typeof detail === "string") return detail + codeSuffix

    if (detail && typeof detail === "object" && detail.message) {
      return String(detail.message) + codeSuffix
    }

    if (Array.isArray(detail)) {
      const itens = detail
        .map((item) => {
          const locParts = Array.isArray(item?.loc) ? item.loc : []
          const cleanLoc = locParts.filter((p) => !["body", "query", "path"].includes(String(p)))
          const fieldName = cleanLoc.length ? this.getFieldLabel(String(cleanLoc[cleanLoc.length - 1])) : null
          const msg = this.normalizeValidationMessage(item?.msg || "")
          if (fieldName && msg) return `${fieldName}: ${msg}`
          return msg || null
        })
        .filter(Boolean)
      return itens.length ? itens.join(" | ") : fallback
    }

    if (typeof detail === "object") {
      try {
        return JSON.stringify(detail) + codeSuffix
      } catch {
        return fallback
      }
    }

    return String(detail)
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
        const errorPayload = await response.json().catch(() => ({
          message: `HTTP ${response.status}: ${response.statusText}`,
          statusText: response.statusText,
        }))
        const readableMessage = this.formatErrorMessage(response.status, errorPayload)
        if (response.status === 401) {
          this.setAuthToken(null)
          this.notifyAuthRequired(readableMessage)
        }
        throw new Error(readableMessage)
      }

      if (response.status === 204) return null
      return await response.json()
    } catch (error) {
      if (error.name === "AbortError") {
        throw new Error(`Tempo limite excedido (${timeoutMs}ms)`)
      }
      if (error instanceof TypeError) {
        throw new Error("Não foi possível conectar à API. Verifique sua conexão e tente novamente.")
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
    const notas = await this.getContratoNotasFiscais(contratoId, { ...params, tipo: "mensal" })
    return (notas || []).map((n) => ({
      ...n,
      status_nf: n.status,
      numero_nf: n.numero,
      data_emissao_nf: n.data_emissao,
      data_pagamento_nf: n.data_pagamento,
      valor_cobrado: n.valor,
    }))
  }

  async createContratoFaturamentoMensal(contratoId, data) {
    const nota = await this.createContratoNotaFiscal(contratoId, {
      tipo: "mensal",
      competencia: data.competencia,
      status: data.status_nf,
      numero: data.numero_nf,
      data_emissao: data.data_emissao_nf,
      data_pagamento: data.data_pagamento_nf,
      valor: data.valor_cobrado,
      observacoes: data.observacoes,
    })
    return {
      ...nota,
      status_nf: nota.status,
      numero_nf: nota.numero,
      data_emissao_nf: nota.data_emissao,
      data_pagamento_nf: nota.data_pagamento,
      valor_cobrado: nota.valor,
    }
  }

  async emitirNotaFiscalMensal(contratoId, competencia, data) {
    return this.request(`/contratos/${contratoId}/faturamentos/${competencia}/emitir`, {
      method: "POST",
      body: JSON.stringify(data),
    })
  }

  async updateFaturamentoMensal(faturamentoId, data) {
    return this.updateNotaFiscalRegistro(faturamentoId, data)
  }

  async getContratoNotasFiscais(contratoId, params = {}) {
    const query = new URLSearchParams(params).toString()
    return this.request(
      `/contratos/${contratoId}/notas-fiscais${query ? "?" + query : ""}`,
    )
  }

  async createContratoNotaFiscal(contratoId, data) {
    return this.request(`/contratos/${contratoId}/notas-fiscais`, {
      method: "POST",
      body: JSON.stringify(data),
    })
  }

  async updateNotaFiscalRegistro(notaId, data) {
    return this.request(`/contratos/notas-fiscais/${notaId}`, {
      method: "PATCH",
      body: JSON.stringify(data),
    })
  }

  async deleteNotaFiscalRegistro(notaId) {
    return this.request(`/contratos/notas-fiscais/${notaId}`, {
      method: "DELETE",
    })
  }

  async getNotasFiscais(params = {}) {
    const query = new URLSearchParams(params).toString()
    return this.request(`/notas-fiscais/${query ? "?" + query : ""}`)
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

  async getDashboardResumo() {
    return this.request("/contratos/resumo/dashboard")
  }

  async getContratosCliente(clienteId) {
    return this.request(`/contratos/cliente/${clienteId}/resumo`)
  }

  async getContratoResumoMonitoramento(contratoId, params = {}) {
    const query = new URLSearchParams(params).toString()
    return this.request(
      `/contratos/${contratoId}/resumo/monitoramento${query ? "?" + query : ""}`,
    )
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
