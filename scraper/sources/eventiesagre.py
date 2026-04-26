"""Scraper for eventiesagre.it — Liguria event listing."""

import re
import requests
from bs4 import BeautifulSoup
from dateutil import parser as dateparser
from datetime import date

BASE_URL = (
    "https://www.eventiesagre.it/Eventi_Vari/21150970_"
    "Eventi+E+Sagre+Regione+Liguria.html"
)

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

DATE_SHORT_RE = re.compile(
    r"(\d{1,2})[/\-\.](\d{1,2})[/\-\.](\d{2,4})"
    r"(?:\s*[-–]\s*(\d{1,2})[/\-\.](\d{1,2})[/\-\.](\d{2,4}))?",
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


def _numeric_date(d, m, y):
    y = int(y)
    if y < 100:
        y += 2000
    try:
        return date(y, int(m), int(d)).isoformat()
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


def _extract_dates(text):
    m = DATE_RE.search(text)
    if m:
        di = _it_date(m.group(1), m.group(2), m.group(3))
        df = _it_date(m.group(4), m.group(5), m.group(6)) if m.group(4) else di
        return di, df
    m2 = DATE_SHORT_RE.search(text)
    if m2:
        di = _numeric_date(m2.group(1), m2.group(2), m2.group(3))
        df = _numeric_date(m2.group(4), m2.group(5), m2.group(6)) if m2.group(4) else di
        return di, df
    return None, None


def scrape() -> list[dict]:
    headers = {"User-Agent": "Mozilla/5.0 (compatible; SagreScraper/1.0)"}
    try:
        resp = requests.get(BASE_URL, headers=headers, timeout=15)
        resp.raise_for_status()
    except Exception as e:
        print(f"[eventiesagre] fetch error: {e}")
        return []

    soup = BeautifulSoup(resp.text, "lxml")
    results = []

    # eventiesagre.it uses repeated div blocks per event
    for item in soup.find_all(["div", "article", "li"], class_=re.compile(
        r"event|sagra|result|item|row|card|listing|entry", re.I
    )):
        text = item.get_text(" ", strip=True)
        if not text or len(text) < 15:
            continue

        di, df = _extract_dates(text)
        if not di:
            continue

        heading = item.find(["h2", "h3", "h4", "strong", "b"])
        nome = heading.get_text(" ", strip=True)[:120] if heading else text[:80]

        mc = re.search(
            r"\b(?:a|ad|di|nel comune di)\s+([A-ZÀÈÌÒÙ][a-zàèìòùA-Z]+(?:\s[A-Z][a-z]+)?)",
            text,
        )
        comune = mc.group(1).strip() if mc else ""
        prov = _find_provincia(text)

        link = item.find("a", href=True)
        url_ev = link["href"] if link else BASE_URL
        if url_ev.startswith("/"):
            url_ev = "https://www.eventiesagre.it" + url_ev

        img_tag = item.find("img", src=True)
        immagine = img_tag["src"] if img_tag else ""

        results.append({
            "nome":        nome,
            "comune":      comune,
            "provincia":   prov,
            "regione":     "Liguria",
            "data_inizio": di,
            "data_fine":   df or di,
            "descrizione": text[:300].strip(),
            "url":         url_ev,
            "immagine":    immagine,
            "stato":       _stato(di, df),
            "fonte":       "eventiesagre",
        })

    # Fallback: scan all links with date-like anchor text
    if not results:
        for a in soup.find_all("a", href=True):
            parent_text = a.parent.get_text(" ", strip=True) if a.parent else ""
            combined = f"{a.get_text(' ', strip=True)} {parent_text}"
            di, df = _extract_dates(combined)
            if not di:
                continue
            nome = a.get_text(" ", strip=True)[:120]
            if not nome or len(nome) < 4:
                continue
            prov = _find_provincia(combined)
            url_ev = a["href"]
            if url_ev.startswith("/"):
                url_ev = "https://www.eventiesagre.it" + url_ev

            results.append({
                "nome":        nome,
                "comune":      "",
                "provincia":   prov,
                "regione":     "Liguria",
                "data_inizio": di,
                "data_fine":   df or di,
                "descrizione": combined[:300].strip(),
                "url":         url_ev,
                "immagine":    "",
                "stato":       _stato(di, df),
                "fonte":       "eventiesagre",
            })

    print(f"[eventiesagre] found {len(results)} sagre")
    return results
