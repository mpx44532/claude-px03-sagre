"use strict";

const PROVINCE_NAMES = { GE: "Genova", SV: "Savona", SP: "La Spezia", IM: "Imperia" };

let allSagre = [];

function formatDate(iso) {
  if (!iso) return "";
  const [y, m, d] = iso.split("-");
  return `${d}/${m}/${y}`;
}

function formatDateRange(inizio, fine) {
  if (!inizio) return "Data non disponibile";
  if (!fine || inizio === fine) return formatDate(inizio);
  return `${formatDate(inizio)} – ${formatDate(fine)}`;
}

function badgeClass(stato) {
  if (stato === "in corso") return "badge-in-corso";
  if (stato === "futuro") return "badge-futuro";
  if (stato === "passato") return "badge-passato";
  return "badge-sconosciuto";
}

function badgeLabel(stato) {
  if (stato === "in corso") return "In corso";
  if (stato === "futuro") return "Prossima";
  if (stato === "passato") return "Passata";
  return "Sconosciuto";
}

function renderCard(s) {
  const prov = PROVINCE_NAMES[s.provincia] ? `${PROVINCE_NAMES[s.provincia]} (${s.provincia})` : s.provincia || "";
  const location = [s.comune, prov].filter(Boolean).join(" — ");
  const imgHtml = s.immagine
    ? `<img src="${escHtml(s.immagine)}" alt="${escHtml(s.nome)}" loading="lazy" onerror="this.parentNode.innerHTML='<div class=placeholder-img>🍽️</div>'">`
    : `<div class="placeholder-img">🍽️</div>`;

  return `
    <div class="card">
      ${imgHtml}
      <div class="card-body">
        <h2>${escHtml(s.nome)}</h2>
        <p class="card-meta">${escHtml(location)}</p>
        <p class="card-dates">📅 ${escHtml(formatDateRange(s.data_inizio, s.data_fine))}</p>
        ${s.descrizione ? `<p class="card-desc">${escHtml(s.descrizione)}</p>` : ""}
        <div class="card-footer">
          <span class="badge ${badgeClass(s.stato)}">${badgeLabel(s.stato)}</span>
          ${s.url ? `<a href="${escHtml(s.url)}" target="_blank" rel="noopener">Dettagli →</a>` : ""}
        </div>
      </div>
    </div>`;
}

function escHtml(str) {
  if (!str) return "";
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function applyFilters() {
  const q = document.getElementById("search").value.toLowerCase().trim();
  const prov = document.getElementById("filter-provincia").value;
  const stato = document.getElementById("filter-stato").value;

  const filtered = allSagre.filter(s => {
    if (q && !s.nome?.toLowerCase().includes(q) && !s.comune?.toLowerCase().includes(q)) return false;
    if (prov && s.provincia !== prov) return false;
    if (stato && s.stato !== stato) return false;
    return true;
  });

  const grid = document.getElementById("grid");
  const empty = document.getElementById("empty");
  const stats = document.getElementById("stats");

  if (filtered.length === 0) {
    grid.innerHTML = "";
    empty.style.display = "block";
    stats.textContent = "";
  } else {
    empty.style.display = "none";
    grid.innerHTML = filtered.map(renderCard).join("");
    stats.textContent = `${filtered.length} sagr${filtered.length === 1 ? "a" : "e"} trovat${filtered.length === 1 ? "a" : "e"}`;
  }
}

async function init() {
  try {
    // In GitHub Pages, sagre.json is at ../data/sagre.json relative to web/
    const resp = await fetch("/data/sagre.json");
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
    const data = await resp.json();
    allSagre = data.sagre || [];

    if (data.meta?.scraped_at) {
      const d = new Date(data.meta.scraped_at);
      document.getElementById("footer").textContent =
        `Ultimo aggiornamento: ${d.toLocaleDateString("it-IT", { day: "2-digit", month: "long", year: "numeric" })} — ${allSagre.length} sagre totali`;
    }

    applyFilters();
  } catch (err) {
    document.getElementById("grid").innerHTML =
      `<p style="color:#c0392b;padding:2rem">Errore nel caricamento dei dati: ${escHtml(err.message)}</p>`;
  }
}

document.getElementById("search").addEventListener("input", applyFilters);
document.getElementById("filter-provincia").addEventListener("change", applyFilters);
document.getElementById("filter-stato").addEventListener("change", applyFilters);

init();
