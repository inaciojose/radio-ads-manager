/**
 * caixeta.js - Grade de Comerciais (Caixeta)
 */

let _caixetaTipo = _detectarTipoPorDia()
let _caixetaData = { semana: null, sabado: null }
let _caixetaEditBlocos = []

function _detectarTipoPorDia() {
  return new Date().getDay() === 6 ? "sabado" : "semana"
}

function _horaAtual() {
  const now = new Date()
  return String(now.getHours()).padStart(2, "0") + ":" + String(now.getMinutes()).padStart(2, "0")
}

// ============================================
// Carregar e renderizar
// ============================================

async function loadCaixeta() {
  _caixetaTipo = _detectarTipoPorDia()
  _updateCaixetaTabButtons()
  await _fetchAndRenderCaixeta(_caixetaTipo)
}

async function switchCaixetaTipo(tipo) {
  _caixetaTipo = tipo
  _updateCaixetaTabButtons()
  await _fetchAndRenderCaixeta(tipo)
}

function _updateCaixetaTabButtons() {
  document.getElementById("btn-caixeta-semana")?.classList.toggle("active", _caixetaTipo === "semana")
  document.getElementById("btn-caixeta-sabado")?.classList.toggle("active", _caixetaTipo === "sabado")
}

async function _fetchAndRenderCaixeta(tipo) {
  try {
    showLoading()
    const data = await api.getCaixeta(tipo)
    _caixetaData[tipo] = data
    _renderCaixetaView(data)
  } catch (error) {
    showToast(error.message || "Erro ao carregar grade", "error")
  } finally {
    hideLoading()
  }
}

function _renderCaixetaView(data) {
  document.getElementById("caixeta-view").style.display = ""
  document.getElementById("caixeta-edit").style.display = "none"

  const metaEl = document.getElementById("caixeta-meta")
  if (data.updated_at || data.updated_by) {
    const ts = data.updated_at ? new Date(data.updated_at).toLocaleString("pt-BR") : ""
    const by = data.updated_by ? ` por ${escapeHtml(data.updated_by)}` : ""
    metaEl.innerHTML = `<p class="caixeta-meta-text">Última atualização: ${ts}${by}</p>`
  } else {
    metaEl.innerHTML = ""
  }

  const blocos = data.blocos || []
  const container = document.getElementById("caixeta-blocos")

  if (!blocos.length) {
    container.innerHTML = '<p class="caixeta-vazia">Nenhuma grade cadastrada para este tipo.</p>'
    return
  }

  const agora = _horaAtual()
  let blocoAtualIdx = -1
  let horarioAtualIdx = -1

  for (let bi = 0; bi < blocos.length; bi++) {
    const b = blocos[bi]
    for (let hi = 0; hi < (b.horarios || []).length; hi++) {
      if (b.horarios[hi].horario <= agora) {
        blocoAtualIdx = bi
        horarioAtualIdx = hi
      }
    }
  }

  container.innerHTML = blocos
    .map((bloco, bi) => {
      const horarios = bloco.horarios || []
      const isAtual = bi === blocoAtualIdx

      const horariosHtml = horarios
        .map((h, hi) => {
          const isHorarioAtual = isAtual && hi === horarioAtualIdx
          const comerciais = (h.comerciais || "").split("\n").filter(Boolean)
          const comHtml = comerciais.length
            ? `<ul class="caixeta-comerciais">${comerciais.map((c) => `<li>${escapeHtml(c)}</li>`).join("")}</ul>`
            : ""
          return `<div class="caixeta-horario${isHorarioAtual ? " caixeta-horario--atual" : ""}">
            <span class="caixeta-hora">${escapeHtml(h.horario)}</span>
            ${comHtml}
          </div>`
        })
        .join("")

      const obsHtml = bloco.observacao
        ? `<div class="caixeta-obs">${escapeHtml(bloco.observacao)}</div>`
        : ""

      return `<div class="caixeta-bloco${isAtual ? " caixeta-bloco--atual" : ""}">
        <div class="caixeta-bloco-header">
          <span class="caixeta-programa">${escapeHtml(bloco.nome_programa)}</span>
        </div>
        <div class="caixeta-horarios">${horariosHtml}</div>
        ${obsHtml}
      </div>`
    })
    .join("")
}

// ============================================
// PDF
// ============================================

async function baixarCaixetaPdf() {
  try {
    showLoading()
    await api.downloadCaixetaPdf(_caixetaTipo)
  } catch (error) {
    showToast(error.message || "Erro ao gerar PDF", "error")
  } finally {
    hideLoading()
  }
}

// ============================================
// Modo edição
// ============================================

function entrarEdicaoCaixeta() {
  if (!requireWriteAccess()) return

  const data = _caixetaData[_caixetaTipo]
  _caixetaEditBlocos = JSON.parse(
    JSON.stringify(
      (data?.blocos || []).map((b) => ({
        nome_programa: b.nome_programa,
        observacao: b.observacao || "",
        horarios: (b.horarios || []).map((h) => ({
          horario: h.horario,
          comerciais: h.comerciais || "",
        })),
      }))
    )
  )

  document.getElementById("caixeta-view").style.display = "none"
  document.getElementById("caixeta-edit").style.display = ""
  _renderCaixetaEditBlocos()
}

function cancelarEdicaoCaixeta() {
  document.getElementById("caixeta-view").style.display = ""
  document.getElementById("caixeta-edit").style.display = "none"
}

function _renderCaixetaEditBlocos() {
  const container = document.getElementById("caixeta-edit-blocos")
  container.innerHTML = _caixetaEditBlocos
    .map(
      (bloco, bi) => `
      <div class="caixeta-edit-bloco" data-bloco="${bi}">
        <div class="caixeta-edit-bloco-header">
          <span class="caixeta-edit-bloco-num">Bloco ${bi + 1}</span>
          <input
            type="text"
            class="form-control"
            placeholder="Nome do programa"
            value="${escapeHtml(bloco.nome_programa)}"
            oninput="caixetaEditBlocoField(${bi}, 'nome_programa', this.value)"
          />
          <button class="btn btn-sm btn-danger" onclick="removeBlocoCaixeta(${bi})">
            <i class="fas fa-trash"></i>
          </button>
        </div>
        <div class="caixeta-edit-horarios" id="caixeta-edit-horarios-${bi}">
          ${_renderCaixetaEditHorarios(bi, bloco.horarios)}
        </div>
        <div style="margin-top: 0.5rem;">
          <button class="btn btn-sm btn-secondary" onclick="addHorarioCaixeta(${bi})">
            <i class="fas fa-plus"></i> Adicionar Horário
          </button>
        </div>
        <div class="form-group" style="margin-top: 0.75rem;">
          <label>Observação</label>
          <textarea
            class="form-control"
            rows="2"
            placeholder="Observação (opcional)"
            oninput="caixetaEditBlocoField(${bi}, 'observacao', this.value)"
          >${escapeHtml(bloco.observacao)}</textarea>
        </div>
      </div>`
    )
    .join("")
}

function _renderCaixetaEditHorarios(bi, horarios) {
  if (!horarios || !horarios.length) {
    return '<p style="color:#888; font-size:0.85rem; padding: 0.25rem 0;">Nenhum horário. Clique em "+ Adicionar Horário".</p>'
  }
  return horarios
    .map(
      (h, hi) => `
      <div class="caixeta-edit-horario-row">
        <input
          type="time"
          class="form-control caixeta-time-input"
          value="${escapeHtml(h.horario)}"
          oninput="caixetaEditHorarioField(${bi}, ${hi}, 'horario', this.value)"
        />
        <textarea
          class="form-control"
          rows="2"
          placeholder="Comerciais (um por linha)"
          oninput="caixetaEditHorarioField(${bi}, ${hi}, 'comerciais', this.value)"
        >${escapeHtml(h.comerciais)}</textarea>
        <button class="btn btn-sm btn-danger" onclick="removeHorarioCaixeta(${bi}, ${hi})">
          <i class="fas fa-trash"></i>
        </button>
      </div>`
    )
    .join("")
}

function caixetaEditBlocoField(bi, field, value) {
  if (_caixetaEditBlocos[bi]) _caixetaEditBlocos[bi][field] = value
}

function caixetaEditHorarioField(bi, hi, field, value) {
  if (_caixetaEditBlocos[bi]?.horarios?.[hi]) _caixetaEditBlocos[bi].horarios[hi][field] = value
}

function addBlocoCaixeta() {
  _caixetaEditBlocos.push({ nome_programa: "", observacao: "", horarios: [] })
  _renderCaixetaEditBlocos()
}

function removeBlocoCaixeta(bi) {
  _caixetaEditBlocos.splice(bi, 1)
  _renderCaixetaEditBlocos()
}

function addHorarioCaixeta(bi) {
  if (!_caixetaEditBlocos[bi]) return
  _caixetaEditBlocos[bi].horarios.push({ horario: "", comerciais: "" })
  const container = document.getElementById(`caixeta-edit-horarios-${bi}`)
  if (container) {
    container.innerHTML = _renderCaixetaEditHorarios(bi, _caixetaEditBlocos[bi].horarios)
  }
}

function removeHorarioCaixeta(bi, hi) {
  _caixetaEditBlocos[bi]?.horarios?.splice(hi, 1)
  const container = document.getElementById(`caixeta-edit-horarios-${bi}`)
  if (container) {
    container.innerHTML = _renderCaixetaEditHorarios(bi, _caixetaEditBlocos[bi].horarios)
  }
}

async function salvarCaixeta() {
  if (!requireWriteAccess()) return

  for (let bi = 0; bi < _caixetaEditBlocos.length; bi++) {
    const b = _caixetaEditBlocos[bi]
    if (!b.nome_programa.trim()) {
      showToast(`Bloco ${bi + 1}: Nome do programa é obrigatório`, "warning")
      return
    }
    for (let hi = 0; hi < b.horarios.length; hi++) {
      if (!b.horarios[hi].horario) {
        showToast(`Bloco ${bi + 1}, horário ${hi + 1}: Informe o horário`, "warning")
        return
      }
    }
  }

  const payload = {
    blocos: _caixetaEditBlocos.map((b, bi) => ({
      nome_programa: b.nome_programa.trim(),
      observacao: b.observacao.trim() || null,
      ordem: bi,
      horarios: b.horarios.map((h, hi) => ({
        horario: h.horario,
        comerciais: h.comerciais.trim() || null,
        ordem: hi,
      })),
    })),
  }

  try {
    showLoading()
    const saved = await api.saveCaixeta(_caixetaTipo, payload)
    _caixetaData[_caixetaTipo] = saved
    showToast("Grade salva com sucesso!", "success")
    _renderCaixetaView(saved)
    await api.downloadCaixetaPdf(_caixetaTipo)
  } catch (error) {
    showToast(error.message || "Erro ao salvar grade", "error")
  } finally {
    hideLoading()
  }
}
