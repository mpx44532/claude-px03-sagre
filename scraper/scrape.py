"""
Orchestrator: auto-discovers sources/*.py plugins and calls scrape().
Usage: python scraper/scrape.py
"""

import importlib
import json
import pkgutil
import sys
from datetime import datetime, timezone
from pathlib import Path

# Ensure scraper package root is in path
SCRAPER_DIR = Path(__file__).parent
sys.path.insert(0, str(SCRAPER_DIR.parent))

from scraper.merge import merge
import scraper.sources as sources_pkg

OUTPUT_FILE = SCRAPER_DIR.parent / "data" / "sagre.json"


def discover_sources():
    """Yield module names for each non-private source plugin."""
    for info in pkgutil.iter_modules(sources_pkg.__path__, sources_pkg.__name__ + "."):
        module_name = info.name
        # Skip modules starting with underscore (disabled)
        leaf = module_name.rsplit(".", 1)[-1]
        if leaf.startswith("_"):
            continue
        yield module_name


def run():
    all_entries = []
    loaded_sources = []

    for module_name in discover_sources():
        try:
            mod = importlib.import_module(module_name)
            entries = mod.scrape()
            all_entries.extend(entries)
            loaded_sources.append(module_name)
            print(f"[scrape] {module_name}: {len(entries)} entries")
        except Exception as e:
            print(f"[scrape] ERROR in {module_name}: {e}", file=sys.stderr)
            import traceback
            traceback.print_exc()

    merged = merge(all_entries)
    print(f"[scrape] total after dedup: {len(merged)}")

    output = {
        "meta": {
            "scraped_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "total": len(merged),
            "sources": loaded_sources,
        },
        "sagre": merged,
    }

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_FILE.write_text(json.dumps(output, ensure_ascii=False, indent=2))
    print(f"[scrape] written to {OUTPUT_FILE}")


if __name__ == "__main__":
    run()
