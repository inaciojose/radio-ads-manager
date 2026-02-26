/**
 * arquivos.js - CRUD de arquivos.
 */

let arquivosCache = []
let clientesArquivoCache = []

async function ensureClientesArquivoCache() {
  clientesArquivoCache = await api.getAllClientes({ status: "ativo" })
  return clientesArquivoCache
}

function fillArquivoClienteSelect(selectedId = "") {
  const select = document.getElementById("arquivo-cliente")
  if (!select) return

  const options = ['<option value="">Selecione...</option>']
  for (const c of clientesArquivoCache) {
    options.push(`<option value="${c.id}">${escapeHtml(c.nome)}</option>`)
  }
  select.innerHTML = options.join("")
  select.value = selectedId ? String(selectedId) : ""
}

async function loadArquivos() {
  const ativo = document.getElementById("filter-arquivo-status")?.value
  try {
    showLoading()
    const [arquivos, clientes] = await Promise.all([
      api.getAllArquivos({ ...(ativo ? { ativo } : {}) }),
      ensureClientesArquivoCache(),
    ])

    arquivosCache = arquivos
    const clientesPorId = Object.fromEntries(clientes.map((c) => [c.id, c.nome]))
    renderArquivos(arquivos, clientesPorId)
  } catch (error) {
    showToast(error.message || "Erro ao carregar arquivos", "error")
  } finally {
    hideLoading()
  }
}

function renderArquivos(items, clientesPorId) {
  const tbody = document.querySelector("#table-arquivos tbody")
  if (!tbody) return

  if (!items.length) {
    tbody.innerHTML = '<tr><td colspan="6" class="text-center">Sem arquivos</td></tr>'
    return
  }

  tbody.innerHTML = items
    .map(
      (a) => `
      <tr>
        <td>${escapeHtml(a.nome_arquivo)}</td>
        <td>${escapeHtml(a.titulo || "-")}</td>
        <td>${escapeHtml(clientesPorId[a.cliente_id] || String(a.cliente_id))}</td>
        <td>${a.duracao_segundos ? `${a.duracao_segundos}s` : "-"}</td>
        <td>${getStatusBadge(String(a.ativo), "arquivo")}</td>
        <td>
          ${
            canWrite()
              ? `<button class="btn btn-sm btn-secondary" onclick="showArquivoModal(${a.id})">Editar</button>
                 <button class="btn btn-sm btn-primary" onclick="toggleArquivo(${a.id})">Ativar/Inativar</button>
                 <button class="btn btn-sm btn-danger" onclick="removerArquivo(${a.id})">Excluir</button>`
              : '<span class="badge badge-secondary">Somente leitura</span>'
          }
        </td>
      </tr>
    `,
    )
    .join("")
}

async function showArquivoModal(arquivoId = null) {
  if (!requireWriteAccess()) return
  await ensureClientesArquivoCache()

  const arquivo = arquivoId
    ? arquivosCache.find((a) => a.id === Number(arquivoId))
    : null
  const isEdit = Boolean(arquivo)

  document.getElementById("arquivo-modal-title").textContent = isEdit
    ? "Editar Arquivo"
    : "Novo Arquivo"

  fillArquivoClienteSelect(arquivo?.cliente_id)

  document.getElementById("arquivo-id").value = arquivo?.id || ""
  document.getElementById("arquivo-nome").value = arquivo?.nome_arquivo || ""
  document.getElementById("arquivo-titulo").value = arquivo?.titulo || ""
  document.getElementById("arquivo-duracao").value = arquivo?.duracao_segundos ?? ""
  document.getElementById("arquivo-caminho").value = arquivo?.caminho_completo || ""
  document.getElementById("arquivo-ativo").value = String(arquivo?.ativo ?? true)
  document.getElementById("arquivo-observacoes").value = arquivo?.observacoes || ""

  document.getElementById("arquivo-cliente").disabled = isEdit
  document.getElementById("arquivo-nome").disabled = isEdit
  document.getElementById("arquivo-duracao").disabled = isEdit
  document.getElementById("arquivo-caminho").disabled = isEdit

  openModal("modal-arquivo")
}

async function saveArquivo() {
  if (!requireWriteAccess()) return
  const id = document.getElementById("arquivo-id").value
  const isEdit = Boolean(id)

  try {
    showLoading()

    if (isEdit) {
      await api.updateArquivo(id, {
        titulo: document.getElementById("arquivo-titulo").value.trim() || null,
        ativo: document.getElementById("arquivo-ativo").value === "true",
        observacoes:
          document.getElementById("arquivo-observacoes").value.trim() || null,
      })
      showToast("Arquivo atualizado", "success")
    } else {
      const clienteId = Number(document.getElementById("arquivo-cliente").value)
      const nomeArquivo = document.getElementById("arquivo-nome").value.trim()

      if (!clienteId || !nomeArquivo) {
        showToast("Cliente e nome do arquivo são obrigatórios", "warning")
        return
      }

      await api.createArquivo({
        cliente_id: clienteId,
        nome_arquivo: nomeArquivo,
        titulo: document.getElementById("arquivo-titulo").value.trim() || null,
        duracao_segundos:
          document.getElementById("arquivo-duracao").value === ""
            ? null
            : Number(document.getElementById("arquivo-duracao").value),
        caminho_completo:
          document.getElementById("arquivo-caminho").value.trim() || null,
        ativo: document.getElementById("arquivo-ativo").value === "true",
        observacoes:
          document.getElementById("arquivo-observacoes").value.trim() || null,
      })
      showToast("Arquivo criado", "success")
    }

    closeModal()
    await loadArquivos()
  } catch (error) {
    showToast(error.message || "Erro ao salvar arquivo", "error")
  } finally {
    hideLoading()
  }
}

async function toggleArquivo(id) {
  if (!requireWriteAccess()) return
  try {
    showLoading()
    await api.toggleArquivoAtivo(id)
    showToast("Status do arquivo atualizado", "success")
    await loadArquivos()
  } catch (error) {
    showToast(error.message || "Erro ao atualizar arquivo", "error")
  } finally {
    hideLoading()
  }
}

async function removerArquivo(id) {
  if (!requireWriteAccess()) return
  if (!confirmAction("Deseja excluir este arquivo?")) return

  try {
    showLoading()
    await api.deleteArquivo(id)
    showToast("Arquivo removido", "success")
    await loadArquivos()
  } catch (error) {
    showToast(error.message || "Erro ao excluir arquivo", "error")
  } finally {
    hideLoading()
  }
}
