"""Deduplication logic for scraped sagre entries."""

import re
import unicodedata


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
    Deduplicate entries by (nome, comune, data_inizio).
    When duplicates exist, prefer the entry with more filled fields.
    Returns list sorted by data_inizio ascending (nulls last).
    """
    seen: dict[str, dict] = {}

    for entry in entries:
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
