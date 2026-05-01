"""
Step 1 — Web Research: use Claude's built-in web_search tool to discover
URLs for food events (sagre) in configured Italian regions.

Output: data/search_urls.json
  {
    "searched_at": "2026-05-01T02:00:00Z",
    "query_regions": [...],
    "urls": ["https://...", ...]
  }

Run:  python scraper/web_research.py
Env:  ANTHROPIC_API_KEY
"""

import json
import re
import sys
from datetime import date, datetime, timezone
from pathlib import Path

import anthropic

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

SEARCH_CONFIG = {
    "regions": [
        {
            "name": "Liguria",
            "provinces": ["Genova", "Savona", "La Spezia", "Imperia"],
        },
    ],
    "max_urls": 10,
}

MODEL = "claude-opus-4-7"
OUTPUT_FILE = Path(__file__).parent.parent / "data" / "search_urls.json"


# ---------------------------------------------------------------------------
# Prompt builder
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
    window = [
        month_names[(today.month - 1 + i) % 12]
        for i in range(3)
    ]
    window_str = ", ".join(window)

    return (
        f"Today is {today.isoformat()}. "
        f"Search the web for upcoming Italian food festivals (sagre, feste, "
        f"eventi gastronomici) taking place in the following regions: {regions_text}. "
        f"Focus on events happening in {window_str} {today.year}. "
        f"Return up to {SEARCH_CONFIG['max_urls']} URLs of web pages that list or "
        f"describe individual food events — event listing pages, local news articles, "
        f"or official event sites. "
        f"Exclude generic tourism sites, social-media home pages, or pages unrelated "
        f"to food festivals. "
        f"When you are done searching, output ONLY a JSON array of URLs, nothing else. "
        f"Example: [\"https://example.com/sagra-del-pesce\", ...]"
    )


# ---------------------------------------------------------------------------
# Agentic loop with server-side web_search tool
# ---------------------------------------------------------------------------

def _extract_urls(text: str) -> list[str]:
    """Pull a JSON URL array from the model's final text response."""
    # Try strict JSON array first
    match = re.search(r"\[[\s\S]*?\]", text)
    if match:
        try:
            urls = json.loads(match.group())
            if isinstance(urls, list):
                return [u for u in urls if isinstance(u, str) and u.startswith("http")]
        except json.JSONDecodeError:
            pass

    # Fall back: collect bare URLs
    return re.findall(r"https?://[^\s\"\]>]+", text)


def research() -> list[str]:
    client = anthropic.Anthropic()

    tools = [{"type": "web_search_20260209", "name": "web_search"}]
    user_query = _build_prompt()
    messages = [{"role": "user", "content": user_query}]

    print(f"[web_research] prompt:\n{user_query}\n")

    while True:
        response = client.messages.create(
            model=MODEL,
            max_tokens=4096,
            thinking={"type": "adaptive"},
            tools=tools,
            messages=messages,
        )

        stop = response.stop_reason
        print(f"[web_research] stop_reason={stop}")

        if stop == "end_turn":
            break

        if stop == "pause_turn":
            # Server-side tool loop hit its iteration limit; continue
            messages = [
                {"role": "user", "content": user_query},
                {"role": "assistant", "content": response.content},
            ]
            continue

        # Unexpected stop — break to avoid infinite loop
        print(f"[web_research] unexpected stop_reason={stop!r}, stopping", file=sys.stderr)
        break

    # Extract text from the final response
    final_text = " ".join(
        block.text for block in response.content
        if hasattr(block, "text")
    )
    urls = _extract_urls(final_text)
    print(f"[web_research] extracted {len(urls)} URLs")
    return urls


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    urls = research()

    output = {
        "searched_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "query_regions": [r["name"] for r in SEARCH_CONFIG["regions"]],
        "urls": urls,
    }

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_FILE.write_text(json.dumps(output, ensure_ascii=False, indent=2))
    print(f"[web_research] written to {OUTPUT_FILE}")

    for u in urls:
        print(f"  {u}")


if __name__ == "__main__":
    main()
