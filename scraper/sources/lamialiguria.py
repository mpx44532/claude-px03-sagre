"""Scraper for lamialiguria.it — eventi autentici post."""

import re
import requests
from bs4 import BeautifulSoup
from dateutil import parser as dateparser
from datetime import date

BASE_URL = "https://lamialiguria.it/2026/03/eventi-autentici-liguria/"

MONTH_IT = {
    "gennaio": "January", "febbraio": "February", "marzo": "March",
    "aprile": "April", "maggio": "May", "giugno": "June",
    "luglio": "July", "agosto": "August", "settembre": "September",
    "ottobre": "October", "novembre": "November", "dicembre": "December",
}

DATE_RE = re.compile(
    r"(\d{1,2})\s+(" + "|".join(MONTH_IT) + r")\s+(\d{4})"
    r"(?:\s*[-–/al]+\s*(\d{1,2})\s+(" + "|".join(MONTH_IT) + r")\s+(\d{4}))?",
    re.IGNORECASE,
)

PROV_MAP = {
    "genova": "GE", "ge": "GE",
    "savona": "SV", "sv": "SV",
    "la spezia": "SP", "spezia": "SP", "sp": "SP",
    "imperia": "IM", "im": "IM",
}


def _it_date(day, month, year):
    raw = f"{day} {month.lower()} {year}"
    for it, en in MONTH_IT.items():
        raw = raw.replace(it, en)
    try:
        return dateparser.parse(raw, dayfirst=True).strftime("%Y-%m-%d")
    except Exception:
        return None


def _stato(di, df):
    today = date.today().isoformat()
    if not di:
        return "sconosciuto"
    if today < di:
        return "futuro"
    if df and today > df:
        return "passato"
    return "in corso"


def _find_provincia(text):
    t = text.lower()
    for name, code in PROV_MAP.items():
        if re.search(r"\b" + re.escape(name) + r"\b", t):
            return code
    return ""


def scrape() -> list[dict]:
    headers = {"User-Agent": "Mozilla/5.0 (compatible; SagreScraper/1.0)"}
    try:
        resp = requests.get(BASE_URL, headers=headers, timeout=15)
        resp.raise_for_status()
    except Exception as e:
        print(f"[lamialiguria] fetch error: {e}")
        return []

    soup = BeautifulSoup(resp.text, "lxml")

    # WordPress: main article content
    content = (
        soup.find("div", class_=re.compile(r"entry-content|post-content|article-content", re.I))
        or soup.find("article")
        or soup.body
    )

    results = []
    current_prov = ""

    # Walk headings and paragraphs
    for tag in content.find_all(["h1", "h2", "h3", "h4", "strong", "p"]):
        text = tag.get_text(" ", strip=True)
        if not text or len(text) < 4:
            continue

        # Province hint in section headings
        if tag.name in ("h2", "h3"):
            prov = _find_provincia(text)
            if prov:
                current_prov = prov

        # Event name: h3/h4 or bold paragraph
        is_heading = tag.name in ("h3", "h4") or (
            tag.name in ("p", "strong") and tag.find("strong") and len(text) < 120
        )
        if not is_heading:
            continue

        nome = text.strip()

        # Gather following siblings for dates/location/description
        di = df = None
        comune = ""
        url_ev = ""
        desc_parts = []

        for sib in tag.find_next_siblings():
            if sib.name in ("h2", "h3", "h4"):
                break
            stext = sib.get_text(" ", strip=True)
            if not stext:
                continue

            # Date extraction
            m = DATE_RE.search(stext)
            if m and not di:
                di = _it_date(m.group(1), m.group(2), m.group(3))
                if m.group(4):
                    df = _it_date(m.group(4), m.group(5), m.group(6))
                else:
                    df = di

            # Comune: "a Camogli", "a Genova", etc.
            mc = re.search(
                r"\b(?:a|ad|di|nel comune di)\s+([A-ZÀÈÌÒÙ][a-zàèìòùA-Z]+(?:\s[A-Z][a-z]+)?)",
                stext,
            )
            if mc and not comune:
                comune = mc.group(1).strip()

            if not current_prov:
                current_prov = _find_provincia(stext)

            link = sib.find("a", href=True)
            if link and not url_ev:
                url_ev = link["href"]

            desc_parts.append(stext)
            if len(desc_parts) >= 3:
                break

        if not di:
            continue

        results.append({
            "nome":        nome,
            "comune":      comune,
            "provincia":   current_prov,
            "regione":     "Liguria",
            "data_inizio": di,
            "data_fine":   df or di,
            "descrizione": " ".join(desc_parts)[:300].strip(),
            "url":         url_ev or BASE_URL,
            "immagine":    "",
            "stato":       _stato(di, df),
            "fonte":       "lamialiguria",
        })

    print(f"[lamialiguria] found {len(results)} sagre")
    return results
