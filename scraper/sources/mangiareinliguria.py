"""Scraper for mangiareinliguria.it — sagre/eventi page."""

import re
import requests
from bs4 import BeautifulSoup
from dateutil import parser as dateparser

BASE_URL = "https://www.mangiareinliguria.it/eventi-sagre-liguri/sagre-eventi-in-liguria"

PROVINCIA_MAP = {
    "genova": "GE",
    "savona": "SV",
    "la spezia": "SP",
    "spezia": "SP",
    "imperia": "IM",
}

MONTH_IT = {
    "gennaio": "January", "febbraio": "February", "marzo": "March",
    "aprile": "April", "maggio": "May", "giugno": "June",
    "luglio": "July", "agosto": "August", "settembre": "September",
    "ottobre": "October", "novembre": "November", "dicembre": "December",
}

# Patterns to extract dates from Italian text
DATE_PATTERN = re.compile(
    r"(\d{1,2})\s+(\w+)\s+(\d{4})"
    r"(?:\s*[-–al]+\s*(\d{1,2})\s+(\w+)\s+(\d{4}))?",
    re.IGNORECASE,
)


def _it_to_en(text: str) -> str:
    text = text.lower()
    for it, en in MONTH_IT.items():
        text = text.replace(it, en)
    return text


def _parse_date(day: str, month: str, year: str) -> str | None:
    raw = f"{day} {month} {year}"
    raw = _it_to_en(raw)
    try:
        return dateparser.parse(raw, dayfirst=True).strftime("%Y-%m-%d")
    except Exception:
        return None


def _stato(data_inizio: str | None, data_fine: str | None) -> str:
    from datetime import date
    today = date.today().isoformat()
    if not data_inizio:
        return "sconosciuto"
    if today < data_inizio:
        return "futuro"
    if data_fine and today > data_fine:
        return "passato"
    return "in corso"


def _extract_province_from_section(heading_text: str) -> str:
    """Detect province from section heading like 'Appuntamenti a Genova e Provincia'."""
    h = heading_text.lower()
    for name, code in PROVINCIA_MAP.items():
        if name in h:
            return code
    return ""


def scrape() -> list[dict]:
    headers = {"User-Agent": "Mozilla/5.0 (compatible; SagreScraper/1.0)"}
    resp = requests.get(BASE_URL, headers=headers, timeout=15)
    resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "lxml")

    # Find main content area
    content = soup.find("article") or soup.find("div", class_=re.compile(r"entry|content|post", re.I))
    if not content:
        content = soup.body

    results = []
    current_provincia = ""

    for tag in content.find_all(["h2", "h3", "h4", "p"]):
        tag_name = tag.name
        text = tag.get_text(strip=True)
        if not text:
            continue

        # Detect province section headings
        if tag_name in ("h2", "h3") and re.search(r"appuntamenti|sagre|eventi", text, re.I):
            prov = _extract_province_from_section(text)
            if prov:
                current_provincia = prov
            continue

        # Detect event headings: H3/H4 with quoted name or obvious event name
        if tag_name in ("h3", "h4"):
            # Strip quotes if present
            nome = re.sub(r'^["\u201c\u201d\u2018\u2019«»]+|["\u201c\u201d\u2018\u2019«»]+$', "", text).strip()
            if not nome or len(nome) < 4:
                continue

            # Look at the next siblings for date/location info
            descrizione_parts = []
            data_inizio = data_fine = None
            comune = ""
            url = ""

            # Gather following paragraphs until next heading
            sibling = tag.find_next_sibling()
            while sibling and sibling.name not in ("h2", "h3", "h4"):
                stext = sibling.get_text(strip=True)
                if stext:
                    # Try to extract dates
                    m = DATE_PATTERN.search(stext)
                    if m and not data_inizio:
                        d1, mo1, y1 = m.group(1), m.group(2), m.group(3)
                        data_inizio = _parse_date(d1, mo1, y1)
                        if m.group(4):
                            data_fine = _parse_date(m.group(4), m.group(5), m.group(6))
                        else:
                            data_fine = data_inizio

                    # Extract comune: look for patterns like "a Camogli" or "di Sestri Levante"
                    mc = re.search(r"\b(?:a|ad|di|nel comune di)\s+([A-ZÀÈÌÒÙ][a-zàèìòùA-Z\s]+?)(?:\s*[,.(]|$)", stext)
                    if mc and not comune:
                        comune = mc.group(1).strip()

                    # Extract URL
                    link = sibling.find("a", href=True)
                    if link and not url:
                        url = link["href"]

                    descrizione_parts.append(stext)
                sibling = sibling.find_next_sibling()

            if not data_inizio:
                # Skip entries with no parseable date
                sibling = None
                continue

            entry = {
                "nome": nome,
                "comune": comune,
                "provincia": current_provincia,
                "regione": "Liguria",
                "data_inizio": data_inizio,
                "data_fine": data_fine,
                "descrizione": " ".join(descrizione_parts[:2]),
                "url": url or BASE_URL,
                "immagine": "",
                "stato": _stato(data_inizio, data_fine),
                "fonte": "mangiareinliguria",
            }
            results.append(entry)

    print(f"[mangiareinliguria] found {len(results)} sagre")
    return results
