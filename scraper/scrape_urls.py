"""
Step 2 — URL Scraper: fetch each URL from data/search_urls.json,
extract food-event details with Claude, and write data/sagre.json.

Run:  python scraper/scrape_urls.py
Env:  ANTHROPIC_API_KEY
"""

import json
import sys
from datetime import date, datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

import anthropic
import requests
from bs4 import BeautifulSoup

SCRAPER_DIR = Path(__file__).parent
sys.path.insert(0, str(SCRAPER_DIR.parent))

from scraper.merge import merge

SEARCH_URLS_FILE = SCRAPER_DIR.parent / "data" / "search_urls.json"
OUTPUT_FILE = SCRAPER_DIR.parent / "data" / "sagre.json"

MODEL = "claude-opus-4-7"
PAGE_CHAR_LIMIT = 12_000   # chars of page text sent to Claude per URL
HTTP_TIMEOUT = 15


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _today() -> str:
    return date.today().isoformat()


def _stato(di: str | None, df: str | None) -> str:
    today = _today()
    if not di:
        return "sconosciuto"
    if today < di:
        return "futuro"
    if df and today > df:
        return "passato"
    return "in corso"


def _fetch_text(url: str) -> str:
    """Return page body as plain text, limited to PAGE_CHAR_LIMIT chars."""
    headers = {"User-Agent": "Mozilla/5.0 (compatible; SagreScraper/2.0)"}
    resp = requests.get(url, headers=headers, timeout=HTTP_TIMEOUT)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "lxml")
    for tag in soup(["script", "style", "nav", "footer", "header"]):
        tag.decompose()
    text = soup.get_text(" ", strip=True)
    return text[:PAGE_CHAR_LIMIT]


def _extraction_prompt(url: str, page_text: str) -> str:
    return (
        f"Today is {_today()}. "
        f"The following is extracted text from the web page: {url}\n\n"
        f"--- PAGE TEXT START ---\n{page_text}\n--- PAGE TEXT END ---\n\n"
        f"Extract every food festival or food event (sagra, festa gastronomica, "
        f"evento enogastronomico) mentioned on this page. "
        f"For each event return a JSON object with EXACTLY these fields:\n"
        f"  nome         – event name (string, required)\n"
        f"  comune       – town/municipality (string, empty string if unknown)\n"
        f"  provincia    – 2-letter province code, e.g. GE SV SP IM (string, empty string if unknown)\n"
        f"  regione      – region name, e.g. Liguria (string)\n"
        f"  data_inizio  – start date YYYY-MM-DD (string, null if unknown)\n"
        f"  data_fine    – end date   YYYY-MM-DD (string, null if unknown)\n"
        f"  descrizione  – short description, max 300 chars (string)\n"
        f"  url          – direct URL for this event or the source page if no specific URL (string)\n"
        f"  immagine     – image URL if present (string, empty string if none)\n"
        f"  fonte        – domain of the source URL, e.g. example.com (string)\n\n"
        f"Return ONLY a JSON array of these objects. "
        f"If no food events are found return an empty array []. "
        f"Do not include any explanation outside the JSON."
    )


# ---------------------------------------------------------------------------
# Claude extraction
# ---------------------------------------------------------------------------

def _extract_events(url: str, page_text: str) -> list[dict]:
    """Call Claude to extract structured events from page text."""
    client = anthropic.Anthropic()

    response = client.messages.create(
        model=MODEL,
        max_tokens=4096,
        thinking={"type": "adaptive"},
        messages=[{"role": "user", "content": _extraction_prompt(url, page_text)}],
    )

    raw = " ".join(
        block.text for block in response.content
        if hasattr(block, "text")
    )

    # Parse JSON array from response
    start = raw.find("[")
    end = raw.rfind("]") + 1
    if start == -1 or end == 0:
        print(f"  [scrape_urls] no JSON array in response for {url}", file=sys.stderr)
        return []

    try:
        events = json.loads(raw[start:end])
    except json.JSONDecodeError as e:
        print(f"  [scrape_urls] JSON parse error for {url}: {e}", file=sys.stderr)
        return []

    if not isinstance(events, list):
        return []

    domain = urlparse(url).netloc
    normalised = []
    for ev in events:
        if not isinstance(ev, dict) or not ev.get("nome"):
            continue
        di = ev.get("data_inizio") or None
        df = ev.get("data_fine") or None
        normalised.append({
            "nome":        str(ev.get("nome", ""))[:120],
            "comune":      str(ev.get("comune", "")),
            "provincia":   str(ev.get("provincia", "")),
            "regione":     str(ev.get("regione", "Liguria")),
            "data_inizio": di,
            "data_fine":   df or di,
            "descrizione": str(ev.get("descrizione", ""))[:300],
            "url":         str(ev.get("url", url)),
            "immagine":    str(ev.get("immagine", "")),
            "stato":       _stato(di, df),
            "fonte":       str(ev.get("fonte", domain)),
        })

    return normalised


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------

def run():
    if not SEARCH_URLS_FILE.exists():
        print(f"[scrape_urls] {SEARCH_URLS_FILE} not found — run web_research.py first", file=sys.stderr)
        sys.exit(1)

    data = json.loads(SEARCH_URLS_FILE.read_text())
    urls: list[str] = data.get("urls", [])
    print(f"[scrape_urls] processing {len(urls)} URL(s)")

    all_entries: list[dict] = []

    for url in urls:
        print(f"[scrape_urls] fetching {url}")
        try:
            page_text = _fetch_text(url)
        except Exception as e:
            print(f"  [scrape_urls] fetch error: {e}", file=sys.stderr)
            continue

        try:
            events = _extract_events(url, page_text)
        except Exception as e:
            print(f"  [scrape_urls] extraction error: {e}", file=sys.stderr)
            continue

        print(f"  [scrape_urls] extracted {len(events)} event(s)")
        all_entries.extend(events)

    merged = merge(all_entries)
    print(f"[scrape_urls] total after dedup/filter: {len(merged)}")

    output = {
        "meta": {
            "scraped_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "total": len(merged),
            "sources": list({e["fonte"] for e in merged}),
            "pipeline": "web_research + scrape_urls",
        },
        "sagre": merged,
    }

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_FILE.write_text(json.dumps(output, ensure_ascii=False, indent=2))
    print(f"[scrape_urls] written to {OUTPUT_FILE}")


if __name__ == "__main__":
    run()
