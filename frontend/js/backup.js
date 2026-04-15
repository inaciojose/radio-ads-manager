/**
 * backup.js — Gerenciamento de backup e restauração do banco de dados.
 * Somente administradores têm acesso a esta página.
 */

let _backupArquivoSelecionado = null

// ============================================
// Inicialização da página
// ============================================

async function initBackupPage() {
  await Promise.all([backupCarregarConfig(), backupCarregarLista()])
}

// ============================================
// Configurações
// ============================================

async function backupCarregarConfig() {
  try {
    const cfg = await api.getBackupConfig()
    document.getElementById("backup-dir").value = cfg.backup_dir || ""
    document.getElementById("backup-keep-dias").value = cfg.backup_keep_dias ?? 30
    document.getElementById("backup-container").value = cfg.postgres_container || ""
    document.getElementById("backup-cron").textContent = cfg.cron_agendamento || "—"
  } catch (e) {
    showToast("Erro ao carregar configurações de backup", "error")
  }
}

async function backupSalvarConfig() {
  const backup_dir = document.getElementById("backup-dir").value.trim()
  const keep = parseInt(document.getElementById("backup-keep-dias").value, 10)
  const container = document.getElementById("backup-container").value.trim()

  if (!backup_dir) {
    showToast("Informe a pasta de destino dos backups.", "error")
    return
  }
  if (!keep || keep < 1) {
    showToast("Informe um período de retenção válido.", "error")
    return
  }

  try {
    showLoading()
    await api.putBackupConfig({ backup_dir, backup_keep_dias: keep, postgres_container: container })
    showToast("Configurações salvas com sucesso.", "success")
  } catch (e) {
    showToast(e.message || "Erro ao salvar configurações.", "error")
  } finally {
    hideLoading()
  }
}

// ============================================
// Executar backup imediato
// ============================================

async function backupExecutarAgora() {
  if (!confirm("Iniciar backup agora?")) return
  try {
    showLoading()
    const r = await api.postBackupExecutar()
    showToast(r.mensagem || "Backup concluído.", "success")
    await backupCarregarLista()
  } catch (e) {
    showToast(e.message || "Erro ao executar backup.", "error")
  } finally {
    hideLoading()
  }
}

// ============================================
// Lista de backups
// ============================================

async function backupCarregarLista() {
  const tbody = document.querySelector("#table-backups tbody")
  if (!tbody) return
  try {
    const lista = await api.getBackupListar()
    if (!lista.length) {
      tbody.innerHTML = '<tr><td colspan="4" class="text-center">Nenhum backup encontrado.</td></tr>'
      return
    }
    tbody.innerHTML = lista
      .map((b) => {
        const data = b.data_criacao
          ? new Date(b.data_criacao).toLocaleString("pt-BR")
          : "—"
        const size =
          b.tamanho_mb < 1
            ? `${Math.round(b.tamanho_mb * 1024)} KB`
            : `${b.tamanho_mb.toFixed(1)} MB`
        return `
          <tr>
            <td style="font-family:monospace;font-size:0.85rem">${escapeHtml(b.arquivo)}</td>
            <td>${size}</td>
            <td>${data}</td>
            <td>
              <button class="btn btn-danger btn-sm" onclick="backupIniciarRestauracao('${escapeHtml(b.arquivo)}')">
                <i class="fas fa-undo"></i> Restaurar
              </button>
            </td>
          </tr>`
      })
      .join("")
  } catch (e) {
    tbody.innerHTML = '<tr><td colspan="4" class="text-center text-danger">Erro ao carregar lista.</td></tr>'
  }
}

// ============================================
// Restauração
// ============================================

function backupIniciarRestauracao(arquivo) {
  _backupArquivoSelecionado = arquivo
  document.getElementById("restaurar-arquivo-nome").textContent = arquivo
  document.getElementById("restaurar-confirmacao").value = ""
  const modal = document.getElementById("modal-restaurar-backup")
  modal.style.display = "flex"
}

async function backupConfirmarRestauracao() {
  const confirmacao = document.getElementById("restaurar-confirmacao").value.trim()
  if (!_backupArquivoSelecionado) return

  try {
    showLoading()
    const r = await api.postBackupRestaurar({
      arquivo: _backupArquivoSelecionado,
      confirmacao,
    })
    closeModal()
    showToast(r.mensagem || "Banco restaurado com sucesso.", "success")
  } catch (e) {
    showToast(e.message || "Erro ao restaurar backup.", "error")
  } finally {
    hideLoading()
  }
}
