"""Scraper for sagreautentiche.it — Liguria section."""

import re
import requests
from bs4 import BeautifulSoup
from dateutil import parser as dateparser

BASE_URL = "https://sagreautentiche.it/ricerca-la-tua-sagra/?regione=Liguria"

PROVINCIA_MAP = {
    "Genova": "GE",
    "Savona": "SV",
    "La Spezia": "SP",
    "Imperia": "IM",
}

MONTH_IT = {
    "gennaio": "January", "febbraio": "February", "marzo": "March",
    "aprile": "April", "maggio": "May", "giugno": "June",
    "luglio": "July", "agosto": "August", "settembre": "September",
    "ottobre": "October", "novembre": "November", "dicembre": "December",
}


def _parse_date_it(text: str) -> str | None:
    """Convert Italian date string to YYYY-MM-DD."""
    if not text:
        return None
    text = text.strip().lower()
    for it, en in MONTH_IT.items():
        text = text.replace(it, en)
    try:
        return dateparser.parse(text, dayfirst=True).strftime("%Y-%m-%d")
    except Exception:
        return None


def _parse_dates(raw: str) -> tuple[str | None, str | None]:
    """
    Parse date strings like:
      "28 Marzo 2026"
      "28 Marzo 2026 - 26 Aprile 2026"
      "dal 28 marzo al 26 aprile 2026"
    Returns (data_inizio, data_fine).
    """
    raw = raw.strip()
    # try dash separator
    parts = re.split(r"\s*[-–]\s*", raw, maxsplit=1)
    if len(parts) == 2:
        d_start = _parse_date_it(parts[0])
        d_end = _parse_date_it(parts[1])
        return d_start, d_end or d_start
    d = _parse_date_it(raw)
    return d, d


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


def scrape() -> list[dict]:
    headers = {"User-Agent": "Mozilla/5.0 (compatible; SagreScraper/1.0)"}
    resp = requests.get(BASE_URL, headers=headers, timeout=15)
    resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "lxml")
    results = []

    for article in soup.find_all("article"):
        try:
            nome_tag = article.find(["h2", "h3"])
            nome = nome_tag.get_text(strip=True) if nome_tag else None
            if not nome:
                continue

            # Link
            link_tag = article.find("a", href=True)
            url = link_tag["href"] if link_tag else BASE_URL

            # Image
            img_tag = article.find("img")
            immagine = img_tag.get("src", "") if img_tag else ""

            # Date text — look for patterns like "28 Marzo 2026"
            date_text = ""
            for p in article.find_all(["p", "span", "div"]):
                t = p.get_text(strip=True)
                if re.search(r"\d{1,2}\s+\w+\s+\d{4}", t, re.IGNORECASE):
                    date_text = t
                    break

            data_inizio, data_fine = _parse_dates(date_text)

            # Location: look for "Comune | Regione" or "Comune (Provincia)"
            comune = ""
            provincia = ""
            for p in article.find_all(["p", "span", "div"]):
                t = p.get_text(strip=True)
                # "Comune | Liguria" pattern
                m = re.match(r"^([^|]+)\|\s*(Liguria)", t)
                if m:
                    loc = m.group(1).strip()
                    # try to extract province code from loc
                    for prov_name, prov_code in PROVINCIA_MAP.items():
                        if prov_name.lower() in loc.lower():
                            provincia = prov_code
                            comune = loc.replace(prov_name, "").strip(" ,-()")
                            break
                    if not comune:
                        comune = loc
                    break
                # "Comune (GE)" pattern
                m2 = re.match(r"^(.+?)\s*\(([A-Z]{2})\)", t)
                if m2:
                    comune = m2.group(1).strip()
                    provincia = m2.group(2)
                    break

            # Fallback: grab any paragraph text as descrizione
            descrizione = ""
            for p in article.find_all("p"):
                t = p.get_text(strip=True)
                if t and t != date_text and comune not in t and len(t) > 20:
                    descrizione = t
                    break

            entry = {
                "nome": nome,
                "comune": comune,
                "provincia": provincia,
                "regione": "Liguria",
                "data_inizio": data_inizio,
                "data_fine": data_fine,
                "descrizione": descrizione,
                "url": url,
                "immagine": immagine,
                "stato": _stato(data_inizio, data_fine),
                "fonte": "sagreautentiche",
            }
            results.append(entry)
        except Exception as e:
            print(f"[sagreautentiche] skipping article: {e}")
            continue

    print(f"[sagreautentiche] found {len(results)} sagre")
    return results
