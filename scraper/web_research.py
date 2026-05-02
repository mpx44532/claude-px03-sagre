"""
Single-step pipeline: use Claude's built-in web_search tool to discover
food events (sagre) in configured Italian regions and extract structured
data in one pass. Claude fetches the pages server-side — no 403 issues.

Output: data/sagre.json  (same schema as before)
        data/search_urls.json  (URLs Claude visited, for the log view)

Run:  python scraper/web_research.py
Env:  ANTHROPIC_API_KEY
"""

import json
import re
import sys
from datetime import date, datetime, timezone
from pathlib import Path

import anthropic

SCRAPER_DIR = Path(__file__).parent
sys.path.insert(0, str(SCRAPER_DIR.parent))

from scraper.merge import merge

SEARCH_CONFIG = {
    "regions": [
        {
            "name": "Liguria",
            "provinces": ["Genova", "Savona", "La Spezia", "Imperia"],
        },
    ],
    "max_events": 30,
}

MODEL = "claude-opus-4-7"
SEARCH_URLS_FILE = SCRAPER_DIR.parent / "data" / "search_urls.json"
OUTPUT_FILE = SCRAPER_DIR.parent / "data" / "sagre.json"


# ---------------------------------------------------------------------------
# Prompt
# ---------------------------------------------------------------------------

def _build_prompt() -> str:
    today = date.today()
    regions_text = "; ".join(
        f"{r['name']} (province: {', '.join(r['provinces'])})"
        for r in SEARCH_CONFIG["regions"]
    )
    month_names = [
        "January", "February", "March", "April", "May", "June",
        "July", "August", "September", "October", "November", "December",
    ]
    window = [month_names[(today.month - 1 + i) % 12] for i in range(3)]
    window_str = ", ".join(window)

    return (
        f"Today is {today.isoformat()}. "
        f"Search the web for upcoming Italian food festivals (sagre, feste gastronomiche, "
        f"eventi enogastronomici) in these regions: {regions_text}. "
        f"Focus on events in {window_str} {today.year}. "
        f"For each food event you find, read the event page and extract:\n"
        f"  - nome: event name\n"
        f"  - comune: town/municipality\n"
        f"  - provincia: 2-letter province code (GE, SV, SP, IM)\n"
        f"  - regione: region name\n"
        f"  - data_inizio: start date as YYYY-MM-DD (null if unknown)\n"
        f"  - data_fine: end date as YYYY-MM-DD (null if unknown)\n"
        f"  - descrizione: short description max 300 chars\n"
        f"  - url: direct URL of the event page\n"
        f"  - immagine: image URL if available, else empty string\n"
        f"  - fonte: domain of the source site\n\n"
        f"Search multiple sources. Aim for up to {SEARCH_CONFIG['max_events']} distinct events. "
        f"When done, output ONLY a JSON array of event objects. No explanation outside the JSON."
    )


# ---------------------------------------------------------------------------
# Agentic loop
# ---------------------------------------------------------------------------

def _extract_events(text: str) -> list[dict]:
    start = text.find("[")
    end = text.rfind("]") + 1
    if start == -1 or end == 0:
        return []
    try:
        raw = json.loads(text[start:end])
    except json.JSONDecodeError:
        return []
    if not isinstance(raw, list):
        return []
    return [e for e in raw if isinstance(e, dict) and e.get("nome")]


def _collect_urls(content_blocks: list) -> list[str]:
    """Pull any URLs mentioned in tool_result or text blocks."""
    urls = []
    for block in content_blocks:
        text = getattr(block, "text", "") or ""
        found = re.findall(r"https?://[^\s\"'<>]+", text)
        urls.extend(found)
    return list(dict.fromkeys(urls))  # deduplicate, preserve order


def research() -> tuple[list[dict], list[str]]:
    client = anthropic.Anthropic()
    tools = [{"type": "web_search_20260209", "name": "web_search"}]
    user_query = _build_prompt()
    messages = [{"role": "user", "content": user_query}]

    print(f"[web_research] starting search for: {', '.join(r['name'] for r in SEARCH_CONFIG['regions'])}")

    visited_urls: list[str] = []
    response = None

    while True:
        response = client.messages.create(
            model=MODEL,
            max_tokens=16000,
            tools=tools,
            messages=messages,
        )

        stop = response.stop_reason
        visited_urls.extend(_collect_urls(response.content))
        print(f"[web_research] stop_reason={stop}, blocks={len(response.content)}")

        if stop == "end_turn":
            break

        if stop == "pause_turn":
            messages = [
                {"role": "user", "content": user_query},
                {"role": "assistant", "content": response.content},
            ]
            continue

        if stop == "max_tokens":
            # Response was cut off — ask Claude to continue the JSON
            messages.append({"role": "assistant", "content": response.content})
            messages.append({"role": "user", "content": "Continue from where you stopped. Output only the remaining JSON."})
            continue

        print(f"[web_research] unexpected stop_reason={stop!r}, stopping", file=sys.stderr)
        break

    final_text = " ".join(
        block.text for block in response.content
        if hasattr(block, "text")
    )
    events = _extract_events(final_text)
    visited_urls = list(dict.fromkeys(visited_urls))
    return events, visited_urls


# ---------------------------------------------------------------------------
# Normalise & state
# ---------------------------------------------------------------------------

def _stato(di, df):
    today = date.today().isoformat()
    if not di:
        return "sconosciuto"
    if today < di:
        return "futuro"
    if df and today > df:
        return "passato"
    return "in corso"


def _normalise(events: list[dict]) -> list[dict]:
    out = []
    for ev in events:
        di = ev.get("data_inizio") or None
        df = ev.get("data_fine") or None
        out.append({
            "nome":        str(ev.get("nome", ""))[:120],
            "comune":      str(ev.get("comune", "")),
            "provincia":   str(ev.get("provincia", "")),
            "regione":     str(ev.get("regione", "Liguria")),
            "data_inizio": di,
            "data_fine":   df or di,
            "descrizione": str(ev.get("descrizione", ""))[:300],
            "url":         str(ev.get("url", "")),
            "immagine":    str(ev.get("immagine", "")),
            "stato":       _stato(di, df),
            "fonte":       str(ev.get("fonte", "web_research")),
        })
    return out


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    raw_events, visited_urls = research()
    print(f"[web_research] Claude found {len(raw_events)} raw event(s) across {len(visited_urls)} URL(s)")

    normalised = _normalise(raw_events)
    merged = merge(normalised)
    print(f"[web_research] after dedup/filter: {len(merged)} event(s)")

    # Write search_urls.json (for the Log view)
    SEARCH_URLS_FILE.parent.mkdir(parents=True, exist_ok=True)
    SEARCH_URLS_FILE.write_text(json.dumps({
        "searched_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "query_regions": [r["name"] for r in SEARCH_CONFIG["regions"]],
        "urls": visited_urls,
    }, ensure_ascii=False, indent=2))

    # Write sagre.json
    output = {
        "meta": {
            "scraped_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "total": len(merged),
            "sources": list({e["fonte"] for e in merged}),
            "pipeline": "web_research (Claude web_search)",
        },
        "sagre": merged,
    }
    OUTPUT_FILE.write_text(json.dumps(output, ensure_ascii=False, indent=2))
    print(f"[web_research] written → {OUTPUT_FILE}")
    print()
    print("Events found:")
    for ev in merged:
        print(f"  [{ev.get('data_inizio','??')}] {ev['nome']} — {ev.get('comune','')} ({ev.get('provincia','')})")


if __name__ == "__main__":
    main()
