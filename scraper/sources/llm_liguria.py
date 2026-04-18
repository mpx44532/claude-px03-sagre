"""
LLM-based event discovery for Liguria using Claude API.

Sends the reference prompt for current month + next 2 months.
Requires: ANTHROPIC_API_KEY environment variable (GitHub Actions secret).
"""

import json
import os
import re
from datetime import date
from dateutil.relativedelta import relativedelta
import anthropic

REGIONE = "Liguria"

MONTH_IT = {
    1: "Gennaio",  2: "Febbraio", 3: "Marzo",    4: "Aprile",
    5: "Maggio",   6: "Giugno",   7: "Luglio",   8: "Agosto",
    9: "Settembre",10: "Ottobre", 11: "Novembre",12: "Dicembre",
}

PROV_NORM = {
    "genova": "GE", "ge": "GE",
    "savona": "SV", "sv": "SV",
    "la spezia": "SP", "spezia": "SP", "sp": "SP",
    "imperia": "IM", "im": "IM",
}

# ── Prompts ────────────────────────────────────────────────────────────────────

# User-facing prompt (the reference template)
USER_PROMPT = (
    "Ricerca eventi culinari, sagre e feste gastronomiche in {regione} "
    "per il mese/i di {mesi} {anno}. "
    "Per ogni evento includi: nome dell'evento, località e provincia, "
    "date precise, breve descrizione del piatto o prodotto tipico celebrato. "
    "Indica se si tratta di un Evento Autentico riconosciuto dalla Regione. "
    "Ordina i risultati cronologicamente"
)

# System prompt: steers Claude to return structured JSON
SYSTEM_PROMPT = """\
Sei un assistente esperto di sagre ed eventi gastronomici italiani.
Rispondi ESCLUSIVAMENTE con un array JSON valido — nessun testo prima o dopo.

Formato richiesto per ogni elemento:
{
  "nome": "Nome completo dell'evento",
  "comune": "Città o paese",
  "provincia": "XX",
  "data_inizio": "YYYY-MM-DD",
  "data_fine":   "YYYY-MM-DD",
  "descrizione": "Piatto/prodotto tipico celebrato (max 300 caratteri)",
  "autentico": false,
  "url": ""
}

Regole:
- Includi solo eventi gastronomici in Liguria (sagre, feste del cibo, degustazioni, mercati del gusto)
- Escludi concerti, mostre, sport, eventi non food
- Sigla provincia: GE, SV, SP, IM
- autentico: true solo se l'evento è registrato nel calendario degli Eventi Autentici di Regione Liguria
- Se non hai dati sufficienti per un periodo, restituisci []
- Non inventare eventi: includi solo quelli ricorrenti o di cui sei ragionevolmente certo\
"""


# ── Helpers ────────────────────────────────────────────────────────────────────

def _months_to_query() -> list[tuple[str, int]]:
    """Return (month_name_it, year) for current month + next 2 months."""
    today = date.today()
    return [
        (MONTH_IT[(today + relativedelta(months=i)).month],
         (today + relativedelta(months=i)).year)
        for i in range(3)
    ]


def _norm_prov(raw: str) -> str:
    if not raw:
        return ""
    key = raw.strip().lower()
    return PROV_NORM.get(key, raw.strip().upper()[:2])


def _stato(di: str, df: str) -> str:
    today = date.today().isoformat()
    if not di:
        return "sconosciuto"
    if today < di:
        return "futuro"
    if df and today > df:
        return "passato"
    return "in corso"


def _parse_response(raw: str) -> list[dict]:
    """Extract JSON array from Claude response (handles markdown fences)."""
    raw = raw.strip()
    # strip ```json ... ``` fences if present
    raw = re.sub(r"^```(?:json)?\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw)
    m = re.search(r"\[.*\]", raw, re.DOTALL)
    if not m:
        return []
    return json.loads(m.group())


# ── Main scrape() ──────────────────────────────────────────────────────────────

def scrape() -> list[dict]:
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("[llm_liguria] ANTHROPIC_API_KEY not set — skipping")
        return []

    client = anthropic.Anthropic(api_key=api_key)

    # Group months by year → one API call per year avoids redundant system-prompt tokens
    by_year: dict[int, list[str]] = {}
    for month_name, year in _months_to_query():
        by_year.setdefault(year, []).append(month_name)

    all_events: list[dict] = []

    for year, month_names in sorted(by_year.items()):
        mesi_str = "/".join(month_names)
        prompt   = USER_PROMPT.format(regione=REGIONE, mesi=mesi_str, anno=year)

        print(f"[llm_liguria] querying Claude for {mesi_str} {year}…")
        try:
            msg = client.messages.create(
                model      = "claude-haiku-4-5-20251001",
                max_tokens = 4096,
                system     = SYSTEM_PROMPT,
                messages   = [{"role": "user", "content": prompt}],
            )
            events = _parse_response(msg.content[0].text)
        except json.JSONDecodeError as e:
            print(f"[llm_liguria] JSON parse error for {mesi_str} {year}: {e}")
            continue
        except Exception as e:
            print(f"[llm_liguria] API error for {mesi_str} {year}: {e}")
            continue

        for ev in events:
            if not isinstance(ev, dict):
                continue
            di = (ev.get("data_inizio") or "").strip()
            df = (ev.get("data_fine")   or di).strip()
            if not ev.get("nome") or not di:
                continue
            all_events.append({
                "nome":        ev.get("nome", "").strip(),
                "comune":      ev.get("comune", "").strip(),
                "provincia":   _norm_prov(ev.get("provincia", "")),
                "regione":     REGIONE,
                "data_inizio": di,
                "data_fine":   df,
                "descrizione": (ev.get("descrizione") or "")[:300].strip(),
                "url":         ev.get("url") or "",
                "immagine":    "",
                "stato":       _stato(di, df),
                "fonte":       "llm_liguria",
                "autentico":   bool(ev.get("autentico")),
            })

    print(f"[llm_liguria] found {len(all_events)} events via LLM")
    return all_events
