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
    for (let hi = 0; hi < (blocos[bi].horarios || []).length; hi++) {
      if (blocos[bi].horarios[hi].horario <= agora) {
        blocoAtualIdx = bi
        horarioAtualIdx = hi
      }
    }
  }

  container.innerHTML = blocos
    .map((bloco, bi) => {
      const horarios = bloco.horarios || []
      const isAtual = bi === blocoAtualIdx

      let tbodyRows = ""
      horarios.forEach((h, hi) => {
        const isHorarioAtual = isAtual && hi === horarioAtualIdx
        const comerciais = h.comerciais || []

        if (!comerciais.length) {
          const cls = isHorarioAtual ? ' class="caixeta-horario--atual"' : ""
          tbodyRows += `<tr${cls}>
            <td class="caixeta-hora">${escapeHtml(h.horario)}</td>
            <td colspan="2" class="caixeta-sem-comerciais">—</td>
          </tr>`
        } else {
          comerciais.forEach((c, ci) => {
            const classes = []
            if (isHorarioAtual) classes.push("caixeta-horario--atual")
            if (c.destaque) classes.push("caixeta-comercial--destaque")
            const trAttr = classes.length ? ` class="${classes.join(" ")}"` : ""
            if (ci === 0) {
              tbodyRows += `<tr${trAttr}>
                <td class="caixeta-hora" rowspan="${comerciais.length}">${escapeHtml(h.horario)}</td>
                <td class="caixeta-comercial-nome">• ${escapeHtml(c.nome)}</td>
                <td class="caixeta-comercial-obs">${escapeHtml(c.observacao || "")}</td>
              </tr>`
            } else {
              tbodyRows += `<tr${trAttr}>
                <td class="caixeta-comercial-nome">• ${escapeHtml(c.nome)}</td>
                <td class="caixeta-comercial-obs">${escapeHtml(c.observacao || "")}</td>
              </tr>`
            }
          })
        }
      })

      if (!horarios.length) {
        tbodyRows = '<tr><td colspan="3" class="caixeta-sem-comerciais">Nenhum horário cadastrado.</td></tr>'
      }

      return `<div class="caixeta-bloco${isAtual ? " caixeta-bloco--atual" : ""}">
        <div class="caixeta-bloco-header">
          <span class="caixeta-programa">${escapeHtml(bloco.nome_programa)}</span>
        </div>
        <table class="caixeta-table">
          <colgroup>
            <col class="caixeta-col-hora">
            <col class="caixeta-col-comercial">
            <col class="caixeta-col-obs">
          </colgroup>
          <thead>
            <tr>
              <th>Horário</th>
              <th>Comercial</th>
              <th>Observação</th>
            </tr>
          </thead>
          <tbody>${tbodyRows}</tbody>
        </table>
      </div>`
    })
    .join("")

  // Scroll automático para o horário atual ao carregar/recarregar
  requestAnimationFrame(() => centralizarHorarioAtual(false))
}

function centralizarHorarioAtual(smooth = true) {
  const alvo =
    document.querySelector(".caixeta-horario--atual") ||
    document.querySelector(".caixeta-bloco--atual")
  if (!alvo) return
  const rect = alvo.getBoundingClientRect()
  const offset = rect.top + window.scrollY - window.innerHeight * 0.30
  window.scrollTo({ top: offset, behavior: smooth ? "smooth" : "instant" })
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
        horarios: (b.horarios || []).map((h) => ({
          horario: h.horario,
          comerciais: (h.comerciais || []).map((c) => ({
            nome: c.nome,
            observacao: c.observacao || "",
            destaque: c.destaque || false,
          })),
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
          <button class="btn btn-sm btn-danger" onclick="removeBlocoCaixeta(${bi})" title="Remover bloco">
            <i class="fas fa-trash"></i>
          </button>
        </div>
        <div id="caixeta-edit-horarios-${bi}">
          ${_renderCaixetaEditHorarios(bi, bloco.horarios)}
        </div>
        <div style="margin-top: 0.5rem;">
          <button class="btn btn-sm btn-secondary" onclick="addHorarioCaixeta(${bi})">
            <i class="fas fa-plus"></i> Adicionar Horário
          </button>
        </div>
      </div>`
    )
    .join("")
}

function _renderCaixetaEditHorarios(bi, horarios) {
  if (!horarios || !horarios.length) {
    return '<p style="color:#888; font-size:0.85rem; padding: 0.25rem 0.5rem;">Sem horários. Clique em "+ Adicionar Horário".</p>'
  }
  return horarios
    .map(
      (h, hi) => `
      <div class="caixeta-edit-horario-bloco">
        <div class="caixeta-edit-horario-header">
          <input
            type="time"
            class="form-control caixeta-time-input"
            value="${escapeHtml(h.horario)}"
            oninput="caixetaEditHorarioField(${bi}, ${hi}, 'horario', this.value)"
          />
          <button class="btn btn-sm btn-danger" onclick="removeHorarioCaixeta(${bi}, ${hi})" title="Remover horário">
            <i class="fas fa-trash"></i>
          </button>
        </div>
        <div class="caixeta-edit-comerciais-header">
          <span></span>
          <span class="caixeta-edit-col-label">Comercial</span>
          <span class="caixeta-edit-col-label">Observação</span>
          <span></span>
        </div>
        <div id="caixeta-edit-comerciais-${bi}-${hi}">
          ${_renderCaixetaEditComerciais(bi, hi, h.comerciais)}
        </div>
        <div style="margin-top: 0.25rem;">
          <button class="btn btn-sm btn-secondary" onclick="addComercialCaixeta(${bi}, ${hi})">
            <i class="fas fa-plus"></i> Comercial
          </button>
        </div>
      </div>`
    )
    .join("")
}

function _renderCaixetaEditComerciais(bi, hi, comerciais) {
  if (!comerciais || !comerciais.length) {
    return '<p style="color:#aaa; font-size:0.8rem; padding: 0.2rem 0;">Sem comerciais.</p>'
  }
  return comerciais
    .map(
      (c, ci) => `
      <div class="caixeta-edit-comercial-row">
        <input
          type="checkbox"
          class="caixeta-destaque-check"
          title="Destacar linha"
          ${c.destaque ? "checked" : ""}
          onchange="caixetaEditComercialField(${bi}, ${hi}, ${ci}, 'destaque', this.checked)"
        />
        <input
          type="text"
          class="form-control"
          placeholder="Nome do comercial"
          value="${escapeHtml(c.nome)}"
          oninput="caixetaEditComercialField(${bi}, ${hi}, ${ci}, 'nome', this.value)"
        />
        <input
          type="text"
          class="form-control"
          placeholder="Observação (opcional)"
          value="${escapeHtml(c.observacao)}"
          oninput="caixetaEditComercialField(${bi}, ${hi}, ${ci}, 'observacao', this.value)"
        />
        <button class="btn btn-sm btn-danger" onclick="removeComercialCaixeta(${bi}, ${hi}, ${ci})" title="Remover comercial">
          <i class="fas fa-trash"></i>
        </button>
      </div>`
    )
    .join("")
}

// Mutação de campos
function caixetaEditBlocoField(bi, field, value) {
  if (_caixetaEditBlocos[bi]) _caixetaEditBlocos[bi][field] = value
}

function caixetaEditHorarioField(bi, hi, field, value) {
  if (_caixetaEditBlocos[bi]?.horarios?.[hi]) _caixetaEditBlocos[bi].horarios[hi][field] = value
}

function caixetaEditComercialField(bi, hi, ci, field, value) {
  const com = _caixetaEditBlocos[bi]?.horarios?.[hi]?.comerciais?.[ci]
  if (com) com[field] = value
}

// Adicionar / remover blocos
function addBlocoCaixeta() {
  _caixetaEditBlocos.push({ nome_programa: "", horarios: [] })
  _renderCaixetaEditBlocos()
}

function removeBlocoCaixeta(bi) {
  _caixetaEditBlocos.splice(bi, 1)
  _renderCaixetaEditBlocos()
}

// Adicionar / remover horários
function addHorarioCaixeta(bi) {
  if (!_caixetaEditBlocos[bi]) return
  _caixetaEditBlocos[bi].horarios.push({ horario: "", comerciais: [] })
  const container = document.getElementById(`caixeta-edit-horarios-${bi}`)
  if (container) container.innerHTML = _renderCaixetaEditHorarios(bi, _caixetaEditBlocos[bi].horarios)
}

function removeHorarioCaixeta(bi, hi) {
  _caixetaEditBlocos[bi]?.horarios?.splice(hi, 1)
  const container = document.getElementById(`caixeta-edit-horarios-${bi}`)
  if (container) container.innerHTML = _renderCaixetaEditHorarios(bi, _caixetaEditBlocos[bi].horarios)
}

// Adicionar / remover comerciais
function addComercialCaixeta(bi, hi) {
  const h = _caixetaEditBlocos[bi]?.horarios?.[hi]
  if (!h) return
  h.comerciais.push({ nome: "", observacao: "", destaque: false })
  const container = document.getElementById(`caixeta-edit-comerciais-${bi}-${hi}`)
  if (container) container.innerHTML = _renderCaixetaEditComerciais(bi, hi, h.comerciais)
}

function removeComercialCaixeta(bi, hi, ci) {
  _caixetaEditBlocos[bi]?.horarios?.[hi]?.comerciais?.splice(ci, 1)
  const h = _caixetaEditBlocos[bi]?.horarios?.[hi]
  const container = document.getElementById(`caixeta-edit-comerciais-${bi}-${hi}`)
  if (container && h) container.innerHTML = _renderCaixetaEditComerciais(bi, hi, h.comerciais)
}

// ============================================
// Salvar
// ============================================

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
      for (let ci = 0; ci < b.horarios[hi].comerciais.length; ci++) {
        if (!b.horarios[hi].comerciais[ci].nome.trim()) {
          showToast(`Bloco ${bi + 1}, horário ${hi + 1}, comercial ${ci + 1}: Nome é obrigatório`, "warning")
          return
        }
      }
    }
  }

  const payload = {
    blocos: _caixetaEditBlocos.map((b, bi) => ({
      nome_programa: b.nome_programa.trim(),
      ordem: bi,
      horarios: b.horarios.map((h, hi) => ({
        horario: h.horario,
        ordem: hi,
        comerciais: h.comerciais.map((c, ci) => ({
          nome: c.nome.trim(),
          observacao: c.observacao.trim() || null,
          destaque: c.destaque || false,
          ordem: ci,
        })),
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
