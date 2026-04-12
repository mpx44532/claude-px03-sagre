"use strict";

const DAY_L    = ["D","L","M","M","G","V","S"];
const DAY_FULL = ["Domenica","Lunedì","Martedì","Mercoledì","Giovedì","Venerdì","Sabato"];
const MON_S    = ["Gen","Feb","Mar","Apr","Mag","Giu","Lug","Ago","Set","Ott","Nov","Dic"];
const MON_F    = ["Gennaio","Febbraio","Marzo","Aprile","Maggio","Giugno","Luglio","Agosto","Settembre","Ottobre","Novembre","Dicembre"];
const PROV     = { GE:"Genova", SV:"Savona", SP:"La Spezia", IM:"Imperia" };

// ── State ──────────────────────────────────────────────
let allSagre = [];
let sel      = today0();      // selected date
let wkStart  = sundayOf(sel); // first day of displayed week
let allMode  = false;

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

// iso() uses LOCAL date parts — avoids UTC offset shifting the date backward
// (e.g. Italy UTC+2: midnight local = 22:00 UTC prev day → toISOString() wrong)
function iso(d) {
  const y  = d.getFullYear();
  const m  = String(d.getMonth() + 1).padStart(2, '0');
  const dd = String(d.getDate()).padStart(2, '0');
  return `${y}-${m}-${dd}`;
}
function sameDay(a, b) { return iso(a) === iso(b); }

// ── Event helpers ──────────────────────────────────────
function eventsOn(dateStr) {
  return allSagre.filter(s => {
    if (!s.data_inizio) return false;
    return dateStr >= s.data_inizio && dateStr <= (s.data_fine || s.data_inizio);
  });
}

// Events visible in "All" mode: ongoing or upcoming within next 2 months
function eventsWindow() {
  const startD = today0();
  const endD   = new Date(startD);
  endD.setMonth(endD.getMonth() + 2);
  const s0 = iso(startD);
  const s1 = iso(endD);
  return allSagre
    .filter(ev => {
      if (!ev.data_inizio) return false;
      return (ev.data_fine || ev.data_inizio) >= s0 && ev.data_inizio <= s1;
    })
    .sort((a, b) => a.data_inizio.localeCompare(b.data_inizio));
}

function eventDateSet() {
  const set = new Set();
  allSagre.forEach(ev => {
    if (!ev.data_inizio) return;
    const d   = new Date(ev.data_inizio);
    const end = new Date(ev.data_fine || ev.data_inizio);
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

// ── Render: header ─────────────────────────────────────
function renderHeader() {
  const d = allMode ? today0() : sel;
  document.getElementById("hdr-num").textContent = d.getDate();
  document.getElementById("hdr-day").textContent = DAY_FULL[d.getDay()];
  document.getElementById("hdr-my").textContent  = `${MON_F[d.getMonth()]} ${d.getFullYear()}`;

  document.getElementById("btn-all").classList.toggle("on", allMode);
  document.getElementById("week-nav").classList.toggle("dim", allMode);

  const lbl = document.getElementById("sec-lbl");
  if (allMode)                  lbl.textContent = "Tutti gli eventi";
  else if (sameDay(sel, today0())) lbl.textContent = "Oggi";
  else lbl.textContent = `${sel.getDate()} ${MON_F[sel.getMonth()]}`;
}

// ── Render: week strip ─────────────────────────────────
function renderWeek() {
  const strip    = document.getElementById("week-strip");
  strip.innerHTML = "";
  const evDates  = eventDateSet();
  const todayStr = iso(today0());

  for (let i = 0; i < 7; i++) {
    const d    = new Date(wkStart);
    d.setDate(wkStart.getDate() + i);
    const dStr = iso(d);

    const el = document.createElement("div");
    el.className = [
      "wk-day",
      sameDay(d, sel)     ? "is-sel"   : "",
      dStr === todayStr   ? "is-today" : "",
      evDates.has(dStr)   ? "has-ev"   : "",
    ].join(" ").trim();

    el.innerHTML =
      `<span class="wk-ltr">${DAY_L[d.getDay()]}</span>` +
      `<span class="wk-num">${d.getDate()}</span>`;

    el.addEventListener("click", () => {
      sel     = new Date(d);
      allMode = false;
      render();
    });
    strip.appendChild(el);
  }
}

// ── Render: events ─────────────────────────────────────
function renderEvents() {
  const list = document.getElementById("ev-list");

  const events = allMode ? eventsWindow() : eventsOn(iso(sel));

  if (!events.length) {
    list.innerHTML = `
      <div class="empty">
        <div class="ei">🍽️</div>
        <div class="et">${allMode ? "Nessun evento nei prossimi 2 mesi" : "Nessuna sagra"}</div>
        <div class="es">${allMode
          ? "I dati vengono aggiornati ogni notte dallo scraper."
          : "Nessun evento in questa data.<br>Prova un altro giorno o usa <b>All</b>."
        }</div>
      </div>`;
    return;
  }

  list.innerHTML = events.map((s, i) => {
    const active  = i === 0 && !allMode;
    const locFull = [s.comune, s.provincia ? `(${s.provincia})` : ""].filter(Boolean).join(" ");

    return `
      <div class="ev-row">
        <div class="ev-loc">
          <div class="city">${esc(s.comune || "–")}</div>
        </div>
        <div class="ev-card${active ? " active" : ""}">
          <div class="card-top">
            <div class="card-title">${esc(s.nome)}</div>
            ${s.url
              ? `<a class="card-menu" href="${esc(s.url)}" target="_blank" rel="noopener" onclick="event.stopPropagation()">⋮</a>`
              : ""}
          </div>
          ${s.descrizione ? `<div class="card-sub">${esc(s.descrizione)}</div>` : ""}
          <div class="card-rows">
            <div class="card-row">
              <span class="card-ico">📅</span>
              <span>${esc(fmtRange(s.data_inizio, s.data_fine))}</span>
            </div>
            <div class="card-row">
              <span class="card-ico">📍</span>
              <span>${esc(locFull || s.fonte || "–")}</span>
            </div>
          </div>
        </div>
      </div>`;
  }).join("");
}

// ── Render all ─────────────────────────────────────────
function render() {
  renderHeader();
  renderWeek();
  renderEvents();
}

// ── Nav listeners ──────────────────────────────────────
document.getElementById("nav-home").addEventListener("click", () => {
  document.getElementById("hero").scrollIntoView({ behavior: "smooth" });
  document.querySelectorAll(".nav-btn").forEach(b => b.classList.remove("active"));
  document.getElementById("nav-home").classList.add("active");
});

document.getElementById("nav-cal").addEventListener("click", () => {
  document.querySelector(".sticky-hdr").scrollIntoView({ behavior: "smooth" });
  document.querySelectorAll(".nav-btn").forEach(b => b.classList.remove("active"));
  document.getElementById("nav-cal").classList.add("active");
});

// ── Button listeners ───────────────────────────────────
document.getElementById("btn-today").addEventListener("click", () => {
  sel     = today0();
  wkStart = sundayOf(sel);
  allMode = false;
  render();
});

document.getElementById("btn-all").addEventListener("click", () => {
  allMode = !allMode;
  render();
});

function shiftWeek(delta) {
  // Move wkStart by ±7 days; keep sel on the same weekday in the new week
  const dow = sel.getDay();
  wkStart = new Date(wkStart);
  wkStart.setDate(wkStart.getDate() + delta * 7);
  sel = new Date(wkStart);
  sel.setDate(wkStart.getDate() + dow);
  allMode = false;
  render();
}

document.getElementById("btn-prev").addEventListener("click", () => shiftWeek(-1));
document.getElementById("btn-next").addEventListener("click", () => shiftWeek(+1));

// ── Init ───────────────────────────────────────────────
async function init() {
  try {
    const resp = await fetch("/data/sagre.json");
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
    const data = await resp.json();
    allSagre = data.sagre || [];
    render();
  } catch (err) {
    document.getElementById("ev-list").innerHTML = `
      <div class="empty">
        <div class="ei">⚠️</div>
        <div class="et">Errore caricamento</div>
        <div class="es">${esc(err.message)}</div>
      </div>`;
    renderHeader();
    renderWeek();
  }
}

init();
