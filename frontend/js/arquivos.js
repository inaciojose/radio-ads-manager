/**
 * arquivos.js - Listagem de arquivos.
 */

async function loadArquivos() {
  const ativo = document.getElementById("filter-arquivo-status")?.value
  try {
    showLoading()
    const arquivos = await api.getArquivos({
      limit: 1000,
      ...(ativo ? { ativo } : {}),
    })
    renderArquivos(arquivos)
  } catch (error) {
    showToast(error.message || "Erro ao carregar arquivos", "error")
  } finally {
    hideLoading()
  }
}

function renderArquivos(items) {
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
        <td>${a.nome_arquivo}</td>
        <td>${a.titulo || "-"}</td>
        <td>${a.cliente_id}</td>
        <td>${a.duracao_segundos ? `${a.duracao_segundos}s` : "-"}</td>
        <td>${getStatusBadge(String(a.ativo), "arquivo")}</td>
        <td>
          <button class="btn btn-sm btn-secondary" onclick="toggleArquivo(${a.id})">Ativar/Inativar</button>
        </td>
      </tr>
    `,
    )
    .join("")
}

async function toggleArquivo(id) {
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

function showArquivoModal() {
  showToast("Modal de arquivo ainda nao implementado.", "info")
}
