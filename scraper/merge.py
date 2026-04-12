"""Deduplication and food-event filtering for scraped sagre entries."""

import re
import unicodedata

# Keywords that confirm a food/drink event
_FOOD_KEYWORDS = re.compile(
    r"\b("
    r"sagra|gastronomic[ao]|enogastronomic[ao]|degustazion[ei]|assaggio|"
    r"cucina|ricett[ae]|piatt[oi]|sapor[ei]|gusto|"
    r"pesce|frutti? di mare|acciugh[ae]|baccala|polpo|calamari?|gamberi?|"
    r"focaccia|farinata|pesto|trofie|trenette|pasta|risotto|minestra|zuppa|"
    r"vino|birra|grappa|liquore|prosecco|sciacchetra|vermentino|"
    r"olio|olive|basilico|aglio|cipolla|pomodor[oi]|funghi|tartufo|"
    r"formaggio|salumi|prosciutto|cinghiale|agnello|coniglio|lumach[ae]|"
    r"castagne|farro|ceci|fagioli|lenticchie|"
    r"fritto|arrosto|grigliata|polenta|torta|dolci?|gelato|miele|"
    r"carne|maiale|vitello|pollo|selvaggina|"
    r"frutta|verdura|ortaggi|limone|arancio|ciliegia|fragola|fico|"
    r"street.?food|food.?festival|mercato.?contadin[oi]"
    r")\b",
    re.IGNORECASE,
)

# Keywords that signal clearly non-food events (only used when no food keyword found)
_NONFOOD_KEYWORDS = re.compile(
    r"\b("
    r"concerto|concerti|musica[le]*|band|orchestra|jazz|rock|pop|"
    r"teatro|spettacolo|rappresentazion[ei]|balletto|danza|coreografi[ae]|"
    r"mostra|esposizion[ei]|arte|pittura|scultura|fotografi[ae]|cinema|film|"
    r"maratona|corsa|gara|ciclismo|regata|torneo|campionato|sport|"
    r"processione|pellegrinaggio|preghiera|"
    r"mercatino.?natale|antiquariato|vintage.?market|collezionismo"
    r")\b",
    re.IGNORECASE,
)


def _is_food_event(entry: dict) -> bool:
    """Return True if the entry is a food/drink event."""
    text = " ".join([
        entry.get("nome", ""),
        entry.get("descrizione", ""),
    ])
    norm = _normalize(text)
    if _FOOD_KEYWORDS.search(norm):
        return True
    # If no food keyword found but clear non-food signals present → exclude
    if _NONFOOD_KEYWORDS.search(norm):
        return False
    # Default: keep (sources are food-focused, so unknown = likely food)
    return True


def _normalize(text: str) -> str:
    """Lowercase, strip accents, collapse spaces."""
    if not text:
        return ""
    text = unicodedata.normalize("NFD", text.lower())
    text = "".join(c for c in text if unicodedata.category(c) != "Mn")
    return re.sub(r"\s+", " ", text).strip()


def _dedup_key(entry: dict) -> str:
    return "|".join([
        _normalize(entry.get("nome", "")),
        _normalize(entry.get("comune", "")),
        entry.get("data_inizio", "") or "",
    ])


def _make_id(entry: dict) -> str:
    """Create a URL-friendly id."""
    parts = [
        entry.get("nome", ""),
        entry.get("comune", ""),
        entry.get("data_inizio", "") or "",
    ]
    slug = "-".join(parts)
    slug = unicodedata.normalize("NFD", slug.lower())
    slug = "".join(c for c in slug if unicodedata.category(c) != "Mn")
    slug = re.sub(r"[^a-z0-9]+", "-", slug).strip("-")
    return slug


def merge(entries: list[dict]) -> list[dict]:
    """
    Filter to food events, deduplicate by (nome, comune, data_inizio),
    and return sorted by data_inizio ascending (nulls last).
    """
    food_only = [e for e in entries if _is_food_event(e)]
    skipped = len(entries) - len(food_only)
    if skipped:
        print(f"[merge] filtered out {skipped} non-food event(s)")

    seen: dict[str, dict] = {}

    for entry in food_only:
        key = _dedup_key(entry)
        if key not in seen:
            seen[key] = entry
        else:
            # Keep whichever has more non-empty fields
            existing = seen[key]
            existing_score = sum(1 for v in existing.values() if v)
            new_score = sum(1 for v in entry.values() if v)
            if new_score > existing_score:
                seen[key] = entry

    result = list(seen.values())

    # Add id field
    for entry in result:
        entry["id"] = _make_id(entry)

    # Sort by data_inizio
    result.sort(key=lambda e: e.get("data_inizio") or "9999-99-99")

    return result
