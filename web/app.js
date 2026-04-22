"use strict";

const MON_S = ["Gen","Feb","Mar","Apr","Mag","Giu","Lug","Ago","Set","Ott","Nov","Dic"];
const MON_F = ["Gennaio","Febbraio","Marzo","Aprile","Maggio","Giugno",
               "Luglio","Agosto","Settembre","Ottobre","Novembre","Dicembre"];
const WD_IT = ["L","M","M","G","V","S","D"]; // Mon-first display

// ── State ──────────────────────────────────────────────
let allSagre    = [];
let candidates  = new Set(JSON.parse(localStorage.getItem("sagre-candidates") || "[]"));
let diary       = JSON.parse(localStorage.getItem("sagre-diary") || "[]");
let newEventIds = new Set();

let currentView  = "agenda"; // agenda | cal | detail | diary
let prevView     = "agenda"; // for back-nav from detail
let detailId     = null;     // event id shown in detail
let openDiaryId  = null;     // diary entry id currently open

let calMonth   = (() => { const d = new Date(); d.setDate(1); d.setHours(0,0,0,0); return d; })();
let calSelDay  = null; // YYYY-MM-DD selected in month grid

// ── Date helpers ───────────────────────────────────────
function today0() { const d = new Date(); d.setHours(0,0,0,0); return d; }

function iso(d) {
  const y  = d.getFullYear();
  const m  = String(d.getMonth() + 1).padStart(2, "0");
  const dd = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${dd}`;
}

function fmtShort(s) {
  if (!s) return "";
  const [, m, d] = s.split("-");
  return `${parseInt(d)} ${MON_S[parseInt(m) - 1]}`;
}

function fmtRange(a, b) {
  if (!a) return "Data n.d.";
  return (!b || b === a) ? fmtShort(a) : `${fmtShort(a)} – ${fmtShort(b)}`;
}

function fmtMonthYear(d) {
  return `${MON_F[d.getMonth()]} ${d.getFullYear()}`;
}

function esc(s) {
  return String(s || "")
    .replace(/&/g, "&amp;").replace(/</g, "&lt;")
    .replace(/>/g, "&gt;").replace(/"/g, "&quot;");
}

function locStr(s) {
  return [s.comune, s.provincia ? `(${s.provincia})` : ""].filter(Boolean).join(" ") || "–";
}

function dayParts(isoStr) {
  const [, m, d] = isoStr.split("-");
  return { day: parseInt(d), mon: MON_S[parseInt(m) - 1] };
}

// ── Storage ─────────────────────────────────────────────
function saveCands() {
  localStorage.setItem("sagre-candidates", JSON.stringify([...candidates]));
}
function saveDiaryStore() {
  localStorage.setItem("sagre-diary", JSON.stringify(diary));
}

// ── Event helpers ──────────────────────────────────────
function eventsOn(dayStr) {
  return allSagre.filter(s =>
    s.data_inizio && dayStr >= s.data_inizio && dayStr <= (s.data_fine || s.data_inizio)
  );
}

function upcomingSaved() {
  const todayStr = iso(today0());
  return allSagre
    .filter(s => candidates.has(s.id) && s.data_inizio && (s.data_fine || s.data_inizio) >= todayStr)
    .sort((a, b) => (a.data_inizio || "").localeCompare(b.data_inizio || ""));
}

function upcomingNew() {
  const todayStr = iso(today0());
  const end = new Date(today0()); end.setMonth(end.getMonth() + 2);
  const endStr = iso(end);
  return allSagre
    .filter(s => !candidates.has(s.id) && s.data_inizio && s.data_inizio >= todayStr && s.data_inizio <= endStr)
    .sort((a, b) => (a.data_inizio || "").localeCompare(b.data_inizio || ""))
    .slice(0, 6);
}

// ── Emoji picker ───────────────────────────────────────
function pickEmoji(text) {
  const t = (text || "").toLowerCase();
  if (t.match(/pesce|acciug|baccal|polpo|calamari|gamberi|mare|frutti/)) return "🐟";
  if (t.match(/fungo|tartufo/))                return "🍄";
  if (t.match(/vino|verment|sciacchetra/))     return "🍷";
  if (t.match(/pesto|focaccia|farinata/))      return "🌿";
  if (t.match(/castagne/))                     return "🌰";
  if (t.match(/cinghiale|selvaggina/))         return "🐗";
  if (t.match(/prosciutto|salumi|porchetta|maiale/)) return "🥩";
  if (t.match(/olio|olive/))                   return "🫒";
  if (t.match(/dolci|torta|gelato|miele/))     return "🍰";
  if (t.match(/agnello|coniglio/))             return "🐑";
  return "🍽️";
}

// ── Candidate helpers ──────────────────────────────────
window.toggleCandidate = function(id) {
  if (candidates.has(id)) candidates.delete(id);
  else candidates.add(id);
  saveCands();
  renderBadge();
  if (currentView === "agenda") renderAgenda();
  else if (currentView === "cal") renderCal();
  else if (currentView === "detail") renderDetail();
};

function renderBadge() {
  const badge = document.getElementById("cand-badge");
  const n = candidates.size;
  badge.textContent = n;
  badge.classList.toggle("show", n > 0);
}

// ── Diary helpers ──────────────────────────────────────
function isDiaryEntry(eventId) {
  return diary.some(e => e.eventId === eventId);
}

function updateDiaryMeta() {
  const n = diary.length;
  const cnt = document.getElementById("diary-strip-cnt");
  const sub = document.getElementById("diary-hdr-sub");
  const txt = n ? `${n} ${n === 1 ? "ricordo" : "ricordi"}` : "Nessun ricordo ancora";
  if (cnt) cnt.textContent = txt;
  if (sub) sub.textContent = `${n} festival ricordati`;
}

window.addToDiary = function(eventId) {
  if (isDiaryEntry(eventId)) return;
  const ev = allSagre.find(s => s.id === eventId);
  if (!ev) return;
  diary.unshift({
    id: `d-${eventId}-${Date.now()}`,
    eventId,
    nome:        ev.nome,
    comune:      ev.comune || "",
    provincia:   ev.provincia || "",
    data_inizio: ev.data_inizio || "",
    rating:      0,
    notes:       "",
    added_at:    new Date().toISOString(),
  });
  saveDiaryStore();
  updateDiaryMeta();
  if (currentView === "detail") renderDetail();
};

window.setDiaryRating = function(entryId, rating) {
  const e = diary.find(x => x.id === entryId);
  if (!e) return;
  e.rating = e.rating === rating ? 0 : rating; // toggle off if same
  saveDiaryStore();
  renderDiaryOpen();
};

window.saveDiaryNotes = function(entryId, notes) {
  const e = diary.find(x => x.id === entryId);
  if (e) { e.notes = notes; saveDiaryStore(); }
};

// ════════════════════════════════════════════════════════
// AGENDA VIEW
// ════════════════════════════════════════════════════════
function renderAgenda() {
  const body   = document.getElementById("agenda-body");
  const saved  = upcomingSaved();
  const newEvs = upcomingNew();
  let html = "";

  if (saved.length) {
    html += `<div class="section-label">Salvati</div>`;
    html += saved.map(s => agendaItem(s, false)).join("");
  }

  if (newEvs.length) {
    html += `<div class="section-label red">Da scoprire</div>`;
    html += newEvs.map(s => agendaItem(s, true)).join("");
  }

  if (!saved.length && !newEvs.length) {
    html = `
      <div class="empty">
        <div class="empty-ico">🍽️</div>
        <div class="empty-title">Nessun evento in agenda</div>
        <div class="empty-sub">Esplora il calendario e salva le sagre a cui vuoi partecipare.</div>
        <button class="btn-go" onclick="showView('cal')">Vai al calendario →</button>
      </div>`;
  }

  body.innerHTML = html;
  updateDiaryMeta();
}

function agendaItem(s, isNew) {
  const { day, mon } = dayParts(s.data_inizio);
  const isNewItem = newEventIds.has(s.id);
  return `
    <div class="agenda-item${isNewItem ? " is-new-item" : ""}"
         onclick="window.showDetailGlobal('${esc(s.id)}','agenda')">
      <div class="date-badge${isNew ? " new-b" : " saved"}">
        <div class="db-day">${day}</div>
        <div class="db-mon">${mon}</div>
      </div>
      <div class="agenda-info">
        <div class="agenda-name">${esc(s.nome)}</div>
        <div class="agenda-loc">${esc(locStr(s))}</div>
      </div>
      <div class="agenda-dot" style="background:${isNew ? "var(--blue)" : "var(--amber)"}"></div>
    </div>`;
}

// ════════════════════════════════════════════════════════
// CALENDAR VIEW
// ════════════════════════════════════════════════════════
function renderCal() {
  renderMonthGrid();
  renderCalPopup();
  renderDayEvents();
}

function renderMonthGrid() {
  document.getElementById("cal-title").textContent = fmtMonthYear(calMonth);
  const todayStr = iso(today0());

  // Header row: Mon-first
  let cells = WD_IT.map(d => `<div class="cal-wd">${d}</div>`).join("");

  // Offset: JS getDay() 0=Sun; we want Mon=0
  const firstDay = new Date(calMonth.getFullYear(), calMonth.getMonth(), 1);
  let offset = firstDay.getDay() - 1;
  if (offset < 0) offset = 6;

  // Prev-month fill
  const prevDays = new Date(calMonth.getFullYear(), calMonth.getMonth(), 0).getDate();
  for (let i = offset - 1; i >= 0; i--) {
    cells += `<div class="cal-day other-month">${prevDays - i}</div>`;
  }

  // Current month
  const daysInMonth = new Date(calMonth.getFullYear(), calMonth.getMonth() + 1, 0).getDate();
  for (let d = 1; d <= daysInMonth; d++) {
    const ds = `${calMonth.getFullYear()}-${String(calMonth.getMonth() + 1).padStart(2, "0")}-${String(d).padStart(2, "0")}`;
    const evs     = eventsOn(ds);
    const hasSaved = evs.some(e => candidates.has(e.id));
    const hasNew   = evs.some(e => !candidates.has(e.id));
    const isToday  = ds === todayStr;
    const isSel    = ds === calSelDay;
    const isNewEv  = evs.some(e => newEventIds.has(e.id));

    let cls = "cal-day";
    if (isToday)       cls += " is-today";
    else if (hasSaved) cls += " ev-orange";
    else if (hasNew)   cls += " ev-blue";
    if (isSel && !isToday) cls += " is-sel";
    if (isNewEv && !isToday) cls += " is-new-cal";

    const click = evs.length ? `onclick="calDayClick('${ds}')"` : "";
    cells += `<div class="${cls}" ${click}>${d}</div>`;
  }

  // Next-month fill
  const total = offset + daysInMonth;
  const trailing = total % 7 === 0 ? 0 : 7 - (total % 7);
  for (let d = 1; d <= trailing; d++) {
    cells += `<div class="cal-day other-month">${d}</div>`;
  }

  document.getElementById("cal-grid").innerHTML = cells;
}

window.calDayClick = function(ds) {
  calSelDay = calSelDay === ds ? null : ds;
  renderCal();
};

function renderCalPopup() {
  const wrap = document.getElementById("cal-popup");
  if (!calSelDay) { wrap.innerHTML = ""; return; }
  const evs = eventsOn(calSelDay);
  if (!evs.length) { wrap.innerHTML = ""; return; }

  const ev    = evs[0];
  const saved = candidates.has(ev.id);
  wrap.innerHTML = `
    <div class="cal-popup">
      <div class="cal-popup-title">${esc(ev.nome)}</div>
      <div class="cal-popup-sub">${esc(locStr(ev))} · ${esc(fmtRange(ev.data_inizio, ev.data_fine))}</div>
      <div class="cal-popup-tags">
        ${ev.autentico ? `<div class="cal-popup-tag">★ Autentico</div>` : ""}
        <div class="cal-popup-tag${saved ? "" : " blue"}">${saved ? "Salvato ✓" : "Nuovo"}</div>
      </div>
      <div class="cal-popup-link" onclick="window.showDetailGlobal('${esc(ev.id)}','cal')">Vedi dettaglio →</div>
    </div>`;
}

function renderDayEvents() {
  const wrap = document.getElementById("cal-day-events");
  if (!calSelDay) { wrap.innerHTML = ""; return; }
  const evs = eventsOn(calSelDay);
  if (!evs.length) { wrap.innerHTML = ""; return; }

  wrap.innerHTML = evs.map(ev => {
    const saved = candidates.has(ev.id);
    return `
      <div class="cal-ev-card${saved ? "" : " new-ev"}"
           onclick="window.showDetailGlobal('${esc(ev.id)}','cal')">
        <div>
          <div class="cal-ev-name">${esc(ev.nome)}</div>
          <div class="cal-ev-loc">${esc(locStr(ev))}</div>
        </div>
        <div style="font-size:.7rem;color:${saved ? "var(--amber)" : "var(--blue)"}">●</div>
      </div>`;
  }).join("");
}

// ════════════════════════════════════════════════════════
// EVENT DETAIL VIEW
// ════════════════════════════════════════════════════════
window.showDetailGlobal = function(eventId, from) {
  prevView = from || currentView;
  detailId = eventId;
  showView("detail");
};

function renderDetail() {
  const ev = allSagre.find(s => s.id === detailId);
  if (!ev) { showView(prevView); return; }

  const saved   = candidates.has(ev.id);
  const inDiary = isDiaryEntry(ev.id);
  const emoji   = pickEmoji(`${ev.nome} ${ev.descrizione || ""}`);

  document.getElementById("detail-back").textContent =
    `← ${prevView === "cal" ? "Calendario" : "Agenda"}`;

  document.getElementById("detail-content").innerHTML = `
    <div class="detail-img">
      <div class="detail-img-emoji">${emoji}</div>
      <div class="detail-img-lbl">immagine evento</div>
    </div>
    <div class="detail-body">
      <div class="detail-title">${esc(ev.nome)}</div>
      <div class="detail-meta">
        📍 ${esc(locStr(ev))}<br>
        📅 ${esc(fmtRange(ev.data_inizio, ev.data_fine))}
        ${ev.url ? `<br>🔗 <a href="${esc(ev.url)}" target="_blank" rel="noopener">${esc(ev.url.replace(/^https?:\/\//, ""))}</a>` : ""}
      </div>
      ${ev.descrizione ? `<div class="detail-desc">${esc(ev.descrizione)}</div>` : ""}
      <div class="detail-tags">
        ${ev.autentico ? `<div class="detail-tag auth">★ Evento Autentico</div>` : ""}
        ${ev.provincia ? `<div class="detail-tag type">${esc(ev.provincia)}</div>` : ""}
        <div class="detail-tag food">${esc(ev.fonte || "")}</div>
      </div>
      <div class="detail-actions">
        <button class="btn-save${saved ? " saved" : ""}"
                onclick="toggleCandidate('${esc(ev.id)}')">
          ${saved ? "✓ In agenda" : "+ Salva in agenda"}
        </button>
        <button class="btn-diary-add${inDiary ? " in-diary" : ""}"
                onclick="${inDiary ? "" : `addToDiary('${esc(ev.id)}')`}">
          ${inDiary ? "📓 Aggiunto al diario" : "📓 Aggiungi al diario"}
        </button>
      </div>
    </div>`;
}

// ════════════════════════════════════════════════════════
// DIARY VIEW
// ════════════════════════════════════════════════════════
function renderDiary() {
  updateDiaryMeta();
  if (openDiaryId) { renderDiaryOpen(); return; }
  renderDiaryList();
}

function renderDiaryList() {
  // Restore normal header
  const hdrWrap = document.getElementById("diary-hdr-wrap");
  hdrWrap.innerHTML = `
    <div class="diary-hdr">
      <div class="diary-hdr-title">My Diary</div>
      <div class="diary-hdr-sub" id="diary-hdr-sub"></div>
    </div>`;
  updateDiaryMeta();

  const body = document.getElementById("diary-body");
  if (!diary.length) {
    body.innerHTML = `
      <div class="empty">
        <div class="empty-ico">📓</div>
        <div class="empty-title">Il tuo diario è vuoto</div>
        <div class="empty-sub">Apri un evento e aggiungi i tuoi ricordi dopo aver partecipato alla sagra.</div>
      </div>`;
    return;
  }

  body.innerHTML = diary.map(entry => {
    const emoji = pickEmoji(entry.nome);
    const stars = entry.rating
      ? "★".repeat(entry.rating) + "☆".repeat(5 - entry.rating)
      : "☆☆☆☆☆";
    return `
      <div class="diary-row" onclick="openDiaryEntry('${esc(entry.id)}')">
        <div class="diary-thumb">${emoji}</div>
        <div class="diary-row-info">
          <div class="diary-row-name">${esc(entry.nome)}</div>
          <div class="diary-row-date">${esc(fmtShort(entry.data_inizio))} · ${esc(entry.comune || "–")}</div>
          <div class="diary-row-stars">${stars}</div>
        </div>
      </div>`;
  }).join("");
}

function renderDiaryOpen() {
  const entry = diary.find(e => e.id === openDiaryId);
  if (!entry) { openDiaryId = null; renderDiaryList(); return; }

  // Replace header with dark back-bar
  const hdrWrap = document.getElementById("diary-hdr-wrap");
  hdrWrap.innerHTML = `
    <div class="diary-entry-back" onclick="closeDiaryEntry()">← ${esc(entry.nome)}</div>
    <div class="diary-entry-img">
      <div style="position:absolute;top:50%;left:50%;transform:translate(-50%,-65%);font-size:44px;opacity:.3">
        ${pickEmoji(entry.nome)}
      </div>
      <div class="diary-entry-img-lbl">${esc(entry.nome)} · ${esc(fmtShort(entry.data_inizio))}</div>
    </div>`;

  const stars = [1, 2, 3, 4, 5].map(n =>
    `<span class="star-btn${n <= entry.rating ? " on" : ""}"
           onclick="setDiaryRating('${esc(entry.id)}',${n})">★</span>`
  ).join("");

  document.getElementById("diary-body").innerHTML = `
    <div class="diary-entry-body">
      <div class="diary-stars-row">${stars}</div>
      <div class="field-label">Note</div>
      <textarea class="diary-textarea"
        oninput="saveDiaryNotes('${esc(entry.id)}',this.value)"
        placeholder="Le tue impressioni sulla sagra…">${esc(entry.notes)}</textarea>
      <div class="field-label">Foto</div>
      <div class="diary-photo-grid">
        <div class="diary-photo-cell">+</div>
        <div class="diary-photo-cell">+</div>
        <div class="diary-photo-cell">+</div>
        <div class="diary-photo-cell">+</div>
        <div class="diary-photo-cell">+</div>
        <div class="diary-photo-cell">+</div>
      </div>
    </div>`;
}

window.openDiaryEntry = function(entryId) {
  openDiaryId = entryId;
  renderDiary();
};

window.closeDiaryEntry = function() {
  openDiaryId = null;
  renderDiaryList();
};

// ════════════════════════════════════════════════════════
// VIEW SWITCHER
// ════════════════════════════════════════════════════════
const SWIPE_VIEWS = ["agenda", "cal", "diary"];

function showView(v) {
  currentView = v;
  ["agenda", "cal", "detail", "diary"].forEach(name => {
    const el = document.getElementById(`view-${name}`);
    const becoming = name === v;
    el.classList.toggle("active", becoming);
    if (becoming) { el.classList.add("fade-in"); setTimeout(() => el.classList.remove("fade-in"), 200); }
  });
  ["agenda", "cal", "diary"].forEach(name => {
    document.getElementById(`nav-${name}`)?.classList.toggle("active", name === v);
  });
  updateSwipeDots(v);

  if (v === "agenda")       renderAgenda();
  else if (v === "cal")     renderCal();
  else if (v === "detail")  renderDetail();
  else if (v === "diary")   renderDiary();
}
window.showView = showView;

function updateSwipeDots(v) {
  const idx = SWIPE_VIEWS.indexOf(v);
  if (idx === -1) return;
  // Update all three dot sets (one per view)
  ["", "b", "c"].forEach((sfx, vi) => {
    [0, 1, 2].forEach(di => {
      const el = document.getElementById(`dot-${di}${sfx}`);
      if (el) el.classList.toggle("active", di === idx);
    });
  });
}

// ════════════════════════════════════════════════════════
// SWIPE GESTURES
// ════════════════════════════════════════════════════════
(function initSwipe() {
  let sx = 0, sy = 0;

  document.addEventListener("touchstart", e => {
    sx = e.touches[0].clientX;
    sy = e.touches[0].clientY;
  }, { passive: true });

  document.addEventListener("touchend", e => {
    const dx = e.changedTouches[0].clientX - sx;
    const dy = e.changedTouches[0].clientY - sy;
    const absDx = Math.abs(dx), absDy = Math.abs(dy);
    if (Math.max(absDx, absDy) < 48) return; // threshold

    if (absDx > absDy) {
      // Horizontal swipe → navigate views
      if (currentView === "detail") return; // no swipe in detail
      const idx = SWIPE_VIEWS.indexOf(currentView);
      if (dx < 0 && idx < SWIPE_VIEWS.length - 1) showView(SWIPE_VIEWS[idx + 1]); // left
      if (dx > 0 && idx > 0)                       showView(SWIPE_VIEWS[idx - 1]); // right
    } else {
      // Vertical swipe → change month (calendar only)
      if (currentView !== "cal") return;
      if (dy < 0) { // swipe up → next month
        calMonth.setMonth(calMonth.getMonth() + 1);
        calSelDay = null; renderCal();
      } else {      // swipe down → prev month
        calMonth.setMonth(calMonth.getMonth() - 1);
        calSelDay = null; renderCal();
      }
    }
  }, { passive: true });
})();

// ── Nav buttons ────────────────────────────────────────
document.getElementById("nav-agenda").addEventListener("click", () => showView("agenda"));
document.getElementById("nav-cal").addEventListener("click",    () => showView("cal"));
document.getElementById("nav-diary").addEventListener("click",  () => showView("diary"));
document.getElementById("diary-strip-btn").addEventListener("click", () => showView("diary"));

document.getElementById("cal-prev").addEventListener("click", () => {
  calMonth.setMonth(calMonth.getMonth() - 1);
  calSelDay = null;
  renderCal();
});
document.getElementById("cal-next").addEventListener("click", () => {
  calMonth.setMonth(calMonth.getMonth() + 1);
  calSelDay = null;
  renderCal();
});

document.getElementById("detail-back").addEventListener("click", () => showView(prevView));

// ── Init ────────────────────────────────────────────────
async function init() {
  renderBadge();
  updateDiaryMeta();

  try {
    const resp = await fetch("/data/sagre.json");
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
    const data = await resp.json();
    allSagre = data.sagre || [];

    if (data.meta?.scraped_at) {
      const d   = new Date(data.meta.scraped_at);
      const dd  = String(d.getDate()).padStart(2, "0");
      const mon = MON_S[d.getMonth()];
      const hh  = String(d.getHours()).padStart(2, "0");
      const mm  = String(d.getMinutes()).padStart(2, "0");
      document.getElementById("last-update").textContent = `↻ ${dd} ${mon} ${hh}:${mm}`;
    }

    // LLM source indicator
    if (allSagre.some(ev => ev.fonte === "llm_liguria")) {
      document.documentElement.classList.add("theme-llm");
    }

    // New-event detection vs previous load
    const prevIds    = new Set(JSON.parse(localStorage.getItem("sagre-seen-ids") || "[]"));
    const currentIds = allSagre.map(ev => ev.id).filter(Boolean);
    if (prevIds.size > 0) {
      newEventIds = new Set(currentIds.filter(id => !prevIds.has(id)));
    }
    localStorage.setItem("sagre-seen-ids", JSON.stringify(currentIds));

    renderAgenda();
  } catch (err) {
    document.getElementById("agenda-body").innerHTML = `
      <div class="empty">
        <div class="empty-ico">⚠️</div>
        <div class="empty-title">Errore caricamento dati</div>
        <div class="empty-sub">${esc(err.message)}</div>
      </div>`;
  }
}

init();
