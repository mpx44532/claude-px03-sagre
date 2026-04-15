"use strict";

const DAY_L    = ["D","L","M","M","G","V","S"];
const DAY_FULL = ["Domenica","Lunedì","Martedì","Mercoledì","Giovedì","Venerdì","Sabato"];
const MON_S    = ["Gen","Feb","Mar","Apr","Mag","Giu","Lug","Ago","Set","Ott","Nov","Dic"];
const MON_F    = ["Gennaio","Febbraio","Marzo","Aprile","Maggio","Giugno","Luglio","Agosto","Settembre","Ottobre","Novembre","Dicembre"];
const PROV     = { GE:"Genova", SV:"Savona", SP:"La Spezia", IM:"Imperia" };

// ── State ──────────────────────────────────────────────
let allSagre   = [];
let sel        = today0();
let wkStart    = sundayOf(sel);
let allMode    = false;
let currentView = "home"; // "home" | "cal"

// Candidates persisted in localStorage
let candidates = new Set(
  JSON.parse(localStorage.getItem("sagre-candidates") || "[]")
);

// ── Date helpers ───────────────────────────────────────
function today0() {
  const d = new Date();
  d.setHours(0, 0, 0, 0);
  return d;
}

function sundayOf(d) {
  const day = new Date(d);
  day.setDate(day.getDate() - day.getDay());
  day.setHours(0, 0, 0, 0);
  return day;
}

// Use local date parts — toISOString() shifts to UTC which breaks Italian timezone
function iso(d) {
  const y  = d.getFullYear();
  const m  = String(d.getMonth() + 1).padStart(2, "0");
  const dd = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${dd}`;
}

function sameDay(a, b) { return iso(a) === iso(b); }

// ── Candidate helpers ──────────────────────────────────
function saveCands() {
  localStorage.setItem("sagre-candidates", JSON.stringify([...candidates]));
}

// Called from onclick attributes on cards — must be global
window.toggleCandidate = function(id) {
  if (candidates.has(id)) candidates.delete(id);
  else candidates.add(id);
  saveCands();
  renderBadge();
  if (currentView === "home") renderHome();
  else renderExplorer();
};

function renderBadge() {
  const badge = document.getElementById("cand-badge");
  const n = candidates.size;
  badge.textContent = n;
  badge.classList.toggle("show", n > 0);
}

// ── Event helpers ──────────────────────────────────────
function eventsOn(dateStr) {
  return allSagre.filter(s => {
    if (!s.data_inizio) return false;
    return dateStr >= s.data_inizio && dateStr <= (s.data_fine || s.data_inizio);
  });
}

function eventsWindow() {
  const startD = today0();
  const endD   = new Date(startD);
  endD.setMonth(endD.getMonth() + 2);
  const s0 = iso(startD), s1 = iso(endD);
  return allSagre
    .filter(ev => ev.data_inizio && (ev.data_fine || ev.data_inizio) >= s0 && ev.data_inizio <= s1)
    .sort((a, b) => a.data_inizio.localeCompare(b.data_inizio));
}

function eventDateSet() {
  const set = new Set();
  allSagre.forEach(ev => {
    if (!ev.data_inizio) return;
    const d = new Date(ev.data_inizio), end = new Date(ev.data_fine || ev.data_inizio);
    while (d <= end) { set.add(iso(d)); d.setDate(d.getDate() + 1); }
  });
  return set;
}

// ── Format helpers ─────────────────────────────────────
function fmtShort(isoStr) {
  if (!isoStr) return "";
  const [, m, d] = isoStr.split("-");
  return `${parseInt(d)} ${MON_S[parseInt(m) - 1]}`;
}

function fmtRange(start, end) {
  if (!start) return "Data n.d.";
  return (!end || end === start) ? fmtShort(start) : `${fmtShort(start)} – ${fmtShort(end)}`;
}

function esc(s) {
  return String(s || "")
    .replace(/&/g, "&amp;").replace(/</g, "&lt;")
    .replace(/>/g, "&gt;").replace(/"/g, "&quot;");
}

function locStr(s) {
  return [s.comune, s.provincia ? `(${s.provincia})` : ""].filter(Boolean).join(" ") || s.fonte || "–";
}

// ══════════════════════════════════════════════════════
// HOME VIEW — candidate list
// ══════════════════════════════════════════════════════
function renderHome() {
  const list = document.getElementById("cand-list");
  const candEvents = allSagre.filter(s => candidates.has(s.id))
    .sort((a, b) => (a.data_inizio || "").localeCompare(b.data_inizio || ""));

  if (!candEvents.length) {
    list.innerHTML = `
      <div class="empty">
        <div class="ei">🔖</div>
        <div class="et">Nessuna sagra selezionata</div>
        <div class="es">Esplora gli eventi e salva quelli a cui vuoi partecipare</div>
        <button class="btn-explore" id="btn-go-explore">Esplora eventi →</button>
      </div>`;
    document.getElementById("btn-go-explore")
      ?.addEventListener("click", () => showView("cal"));
    return;
  }

  list.innerHTML = candEvents.map(s => `
    <div class="cand-card">
      <div class="cand-top">
        <div class="cand-title">${esc(s.nome)}</div>
        <button class="btn-rm"
          onclick="toggleCandidate('${esc(s.id)}')"
          aria-label="Rimuovi">×</button>
      </div>
      ${s.descrizione ? `<div class="cand-sub">${esc(s.descrizione)}</div>` : ""}
      <div class="cand-rows">
        <div class="cand-row">
          <span class="cand-ico">📅</span>
          <span>${esc(fmtRange(s.data_inizio, s.data_fine))}</span>
        </div>
        <div class="cand-row">
          <span class="cand-ico">📍</span>
          <span>${esc(locStr(s))}</span>
        </div>
        ${s.url ? `<div class="cand-row">
          <span class="cand-ico">🔗</span>
          <a class="card-link" href="${esc(s.url)}" target="_blank" rel="noopener">Dettagli</a>
        </div>` : ""}
      </div>
    </div>`).join("");
}

// ══════════════════════════════════════════════════════
// CALENDAR / EXPLORER VIEW
// ══════════════════════════════════════════════════════
function renderHeader() {
  const d = allMode ? today0() : sel;
  document.getElementById("hdr-num").textContent = d.getDate();
  document.getElementById("hdr-day").textContent = DAY_FULL[d.getDay()];
  document.getElementById("hdr-my").textContent  = `${MON_F[d.getMonth()]} ${d.getFullYear()}`;
  document.getElementById("btn-all").classList.toggle("on", allMode);
  document.getElementById("week-nav").classList.toggle("dim", allMode);

  const lbl = document.getElementById("sec-lbl");
  if (allMode)                      lbl.textContent = "Prossimi 2 mesi";
  else if (sameDay(sel, today0()))  lbl.textContent = "Oggi";
  else lbl.textContent = `${sel.getDate()} ${MON_F[sel.getMonth()]}`;
}

function renderWeek() {
  const strip   = document.getElementById("week-strip");
  strip.innerHTML = "";
  const evDates = eventDateSet();
  const todayStr = iso(today0());

  for (let i = 0; i < 7; i++) {
    const d    = new Date(wkStart);
    d.setDate(wkStart.getDate() + i);
    const dStr = iso(d);

    const el = document.createElement("div");
    el.className = [
      "wk-day",
      sameDay(d, sel)   ? "is-sel"   : "",
      dStr === todayStr ? "is-today" : "",
      evDates.has(dStr) ? "has-ev"   : "",
    ].join(" ").trim();

    el.innerHTML =
      `<span class="wk-ltr">${DAY_L[d.getDay()]}</span>` +
      `<span class="wk-num">${d.getDate()}</span>`;

    el.addEventListener("click", () => {
      sel = new Date(d); allMode = false; renderCalView();
    });
    strip.appendChild(el);
  }
}

function renderExplorer() {
  const list   = document.getElementById("ev-list");
  const events = allMode ? eventsWindow() : eventsOn(iso(sel));

  if (!events.length) {
    list.innerHTML = `
      <div class="empty">
        <div class="ei">🍽️</div>
        <div class="et">${allMode ? "Nessun evento nei prossimi 2 mesi" : "Nessuna sagra"}</div>
        <div class="es">${allMode
          ? "I dati vengono aggiornati ogni notte."
          : "Nessun evento per questa data.<br>Prova un altro giorno o usa <b>All</b>."
        }</div>
      </div>`;
    return;
  }

  list.innerHTML = events.map((s, i) => {
    const active  = i === 0 && !allMode;
    const saved   = candidates.has(s.id);

    return `
      <div class="ev-row">
        <div class="ev-loc">
          <div class="city">${esc(s.comune || "–")}</div>
        </div>
        <div class="ev-card${active ? " active" : ""}">
          <div class="card-top">
            <div class="card-title">${esc(s.nome)}</div>
            <button class="card-bm${saved ? " saved" : ""}"
              onclick="toggleCandidate('${esc(s.id)}');event.stopPropagation()"
              aria-label="${saved ? "Rimuovi" : "Salva"}">
              ${saved ? "✓" : "+"}
            </button>
          </div>
          ${s.descrizione ? `<div class="card-sub">${esc(s.descrizione)}</div>` : ""}
          <div class="card-rows">
            <div class="card-row">
              <span class="card-ico">📅</span>
              <span>${esc(fmtRange(s.data_inizio, s.data_fine))}</span>
            </div>
            <div class="card-row">
              <span class="card-ico">📍</span>
              <span>${esc(locStr(s))}</span>
            </div>
            ${s.url ? `<div class="card-row">
              <span class="card-ico">🔗</span>
              <a class="card-link" href="${esc(s.url)}" target="_blank" rel="noopener"
                onclick="event.stopPropagation()">Dettagli</a>
            </div>` : ""}
          </div>
        </div>
      </div>`;
  }).join("");
}

function renderCalView() {
  renderHeader();
  renderWeek();
  renderExplorer();
}

// ── View switcher ──────────────────────────────────────
function showView(v) {
  currentView = v;
  document.getElementById("view-home").classList.toggle("active", v === "home");
  document.getElementById("view-cal").classList.toggle("active",  v === "cal");
  document.getElementById("nav-home").classList.toggle("active",  v === "home");
  document.getElementById("nav-cal").classList.toggle("active",   v === "cal");
  if (v === "home") renderHome();
  else renderCalView();
}

// ── Bottom nav ─────────────────────────────────────────
document.getElementById("nav-home").addEventListener("click", () => showView("home"));
document.getElementById("nav-cal").addEventListener("click",  () => showView("cal"));

// ── Explorer controls ──────────────────────────────────
document.getElementById("btn-today").addEventListener("click", () => {
  sel = today0(); wkStart = sundayOf(sel); allMode = false; renderCalView();
});
document.getElementById("btn-all").addEventListener("click", () => {
  allMode = !allMode; renderCalView();
});

function shiftWeek(delta) {
  const dow = sel.getDay();
  wkStart = new Date(wkStart);
  wkStart.setDate(wkStart.getDate() + delta * 7);
  sel = new Date(wkStart);
  sel.setDate(wkStart.getDate() + dow);
  allMode = false;
  renderCalView();
}
document.getElementById("btn-prev").addEventListener("click", () => shiftWeek(-1));
document.getElementById("btn-next").addEventListener("click", () => shiftWeek(+1));

// ── Init ───────────────────────────────────────────────
async function init() {
  renderBadge();
  try {
    const resp = await fetch("/data/sagre.json");
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
    const data = await resp.json();
    allSagre = data.sagre || [];
    if (data.meta?.scraped_at) {
      const d = new Date(data.meta.scraped_at);
      const dd  = String(d.getDate()).padStart(2, "0");
      const mon = MON_S[d.getMonth()];
      const hh  = String(d.getHours()).padStart(2, "0");
      const mm  = String(d.getMinutes()).padStart(2, "0");
      document.getElementById("last-update").textContent = `↻ ${dd} ${mon} ${hh}:${mm}`;
    }
    renderHome(); // home is the initial view
  } catch (err) {
    document.getElementById("cand-list").innerHTML = `
      <div class="empty">
        <div class="ei">⚠️</div>
        <div class="et">Errore caricamento dati</div>
        <div class="es">${esc(err.message)}</div>
      </div>`;
  }
}

init();
