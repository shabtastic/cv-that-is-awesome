#!/usr/bin/env python3
"""
fetch_scholar.py
================
Fetch publications from Google Scholar and append new entries to refs/.

Uses the Google Scholar author ID directly (more reliable than name search).
Your author ID is the `user=` parameter in your Scholar profile URL:
  https://scholar.google.com/citations?user=KVRrn40AAAAJ
                                              ^^^^^^^^^^^^ this part

Google Scholar blocks automated scraping from servers and cloud IPs.
Run this script from your own machine, not from a CI server.

If you are still getting blocked, set a ScraperAPI key below:
  1. Sign up at https://www.scraperapi.com (free tier available)
  2. Set SCRAPER_API_KEY = "your_key_here"

Requirements (optional):
    pip install scholarly

Usage:
    python scripts/fetch_scholar.py
    python scripts/fetch_scholar.py --dry-run
"""

import argparse
import re
import sys
import time
from pathlib import Path

# ── CONFIG ────────────────────────────────────────────────────────────────────
SCHOLAR_AUTHOR_ID = "KVRrn40AAAAJ"    # from your Scholar profile URL
BIB_OUT           = Path("refs/journals.bib")
SCRAPER_API_KEY   = ""                 # optional — set to use ScraperAPI proxy
# ─────────────────────────────────────────────────────────────────────────────

sys.path.insert(0, str(Path(__file__).parent))
from _shared import load_manual_fingerprints, fingerprint_matches  # noqa: E402


def load_existing_titles(bib_path: Path) -> set[str]:
    if not bib_path.exists():
        return set()
    text = bib_path.read_text(encoding="utf-8")
    titles = re.findall(r'title\s*=\s*\{([^}]+)\}', text, re.IGNORECASE)
    return {re.sub(r'\s+', ' ', t).lower().strip() for t in titles}


def fetch_full_bibtex(sc, pub: dict, delay: float = 1.5) -> str | None:
    """
    Fill a publication stub with full metadata and return its BibTeX string.
    Requires two Scholar requests per pub: one fill() for metadata, one bibtex().
    The delay between requests reduces the chance of rate-limiting.
    Returns None on failure (warnings are printed but the run continues).
    """
    time.sleep(delay)
    try:
        filled = sc.fill(pub)
        return sc.bibtex(filled)
    except Exception as e:
        title = pub.get("bib", {}).get("title", "?")
        print(f"    [warn] Could not fetch '{title[:60]}': {e}")
        return None


def main():
    parser = argparse.ArgumentParser(
        description="Fetch publications from Google Scholar"
    )
    parser.add_argument("--dry-run", action="store_true",
                        help="Preview new entries without writing to disk")
    args = parser.parse_args()

    try:
        from scholarly import scholarly as sc, ProxyGenerator
    except ImportError:
        print("  [skip] scholarly not installed — skipping Google Scholar fetch.")
        print("         To enable: pip install scholarly")
        sys.exit(0)

    # Optional: configure proxy to avoid Scholar bot-detection
    if SCRAPER_API_KEY:
        pg = ProxyGenerator()
        pg.ScraperAPI(SCRAPER_API_KEY)
        sc.use_proxy(pg)

    print(f"Fetching Google Scholar profile: {SCHOLAR_AUTHOR_ID}")

    try:
        author = sc.search_author_id(SCHOLAR_AUTHOR_ID)
        author = sc.fill(author, sections=["publications"])
    except Exception as e:
        print(f"  [warn] Google Scholar fetch failed: {e}")
        print()
        print("  Google Scholar blocks automated requests from server/cloud IPs.")
        print("  Run this script from your own machine (residential IP).")
        print("  Or set SCRAPER_API_KEY in fetch_scholar.py to use a proxy.")
        sys.exit(0)

    pubs = author.get("publications", [])
    print(f"  Found {len(pubs)} publications on Scholar.")

    existing_titles = load_existing_titles(BIB_OUT)
    manual_fp       = load_manual_fingerprints(BIB_OUT)
    new_pubs        = []
    skipped_manual  = 0

    for pub in pubs:
        title = pub.get("bib", {}).get("title", "")
        if not title:
            continue
        norm_title = re.sub(r'\s+', ' ', title).lower().strip()
        if norm_title in existing_titles:
            continue
        stub = {"ID": "", "doi": "", "note": "", "title": title}
        if fingerprint_matches(stub, manual_fp):
            skipped_manual += 1
            continue
        new_pubs.append(pub)

    if skipped_manual:
        print(f"  Skipped {skipped_manual} entries matching manual entries in {BIB_OUT}")

    if not new_pubs:
        print("  No new Scholar entries to add.")
        return

    # Fetch full metadata per pub — each requires its own Scholar request.
    # ~1.5s delay between requests to avoid rate-limiting.
    est = len(new_pubs) * 1.5
    print(f"  Fetching full BibTeX for {len(new_pubs)} new pubs (~{est:.0f}s)...")

    entries = []
    for i, pub in enumerate(new_pubs, 1):
        title = pub.get("bib", {}).get("title", "?")
        print(f"  [{i}/{len(new_pubs)}] {title[:70]}")
        bibtex = fetch_full_bibtex(sc, pub)
        if bibtex:
            entries.append(bibtex)

    if not entries:
        print("  No entries could be fetched.")
        return

    print(f"  Successfully fetched {len(entries)} of {len(new_pubs)} entries.")
    if not args.dry_run:
        with open(BIB_OUT, "a", encoding="utf-8") as f:
            f.write("\n\n% --- Google Scholar auto-fetched ---\n")
            f.write("\n\n".join(entries))
        print(f"  Appended to {BIB_OUT}")
    else:
        print("  [dry-run] Would append:\n")
        for e in entries:
            print(e, "\n")


if __name__ == "__main__":
    main()