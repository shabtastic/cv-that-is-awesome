#!/usr/bin/env python3
"""
fetch_scholar.py
================
Fetch publications from Google Scholar and append new entries to refs/.

Uses your Google Scholar author ID (the `user=` parameter in your profile URL):
  https://scholar.google.com/citations?user=KVRrn40AAAAJ

Google Scholar blocks automated scraping from servers and cloud IPs.
Run this script from your own machine, not from a CI server.

If still blocked, set a ScraperAPI key below:
  1. Sign up at https://www.scraperapi.com (free tier available)
  2. Set SCRAPER_API_KEY = "your_key_here"

Rejected entries are saved to refs/.scholar_rejected.json.

Requirements: pip install scholarly
"""

import argparse
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _shared import (  # noqa: E402
    load_manual_fingerprints, fingerprint_matches,
    load_rejected, save_rejected, interactive_review, review_rejected,
)

# ---------------------------------------------------------------------------
# CONFIG
# ---------------------------------------------------------------------------
SCHOLAR_AUTHOR_ID = "KVRrn40AAAAJ"
BIB_OUT           = Path("refs/journals.bib")
REJECTED_FILE     = Path("refs/.scholar_rejected.json")
SCRAPER_API_KEY   = ""     # optional -- set to use ScraperAPI proxy
# ---------------------------------------------------------------------------


def load_existing_titles(bib_path: Path) -> set:
    if not bib_path.exists():
        return set()
    text   = bib_path.read_text(encoding="utf-8")
    titles = re.findall(r"title\s*=\s*\{([^}]+)\}", text, re.IGNORECASE)
    return {re.sub(r"\s+", " ", t).lower().strip() for t in titles}


def fetch_full_bibtex(sc, pub: dict, delay: float = 1.5) -> tuple:
    """
    Fill a Scholar stub with full metadata and return (bibtex_str, doi).
    Returns (None, None) on failure.
    """
    time.sleep(delay)
    try:
        filled = sc.fill(pub)
        bibtex = sc.bibtex(filled)
        doi_m  = re.search(r"doi\s*=\s*\{([^}]+)\}", bibtex, re.IGNORECASE)
        doi    = doi_m.group(1).strip() if doi_m else ""
        return bibtex, doi
    except Exception as e:
        title = pub.get("bib", {}).get("title", "?")
        print(f"    [warn] Could not fetch '{title[:60]}': {e}")
        return None, None


def main():
    parser = argparse.ArgumentParser(
        description="Fetch publications from Google Scholar"
    )
    parser.add_argument("--dry-run", "-n", action="store_true",
                        help="Preview without writing to disk")
    parser.add_argument("--interactive", "-i", action="store_true",
                        help="Review each entry before adding")
    parser.add_argument("--show-skipped", action="store_true",
                        help="List all filtered-out entries and why")
    parser.add_argument("--review-rejected", action="store_true",
                        help="Interactively review the rejection list")
    args = parser.parse_args()

    interactive = args.interactive or (
        not args.dry_run and sys.stdin.isatty() and sys.stdout.isatty()
    )

    if args.review_rejected:
        unrejected, updated = review_rejected(REJECTED_FILE)
        if unrejected and not args.dry_run:
            save_rejected(REJECTED_FILE, updated)
            print(f"  Removed {len(unrejected)} entry/entries from rejection list.")
            print("  Re-run without --review-rejected to fetch un-rejected entries.")
        elif unrejected and args.dry_run:
            print(f"  [dry-run] Would remove {len(unrejected)} entry/entries.")
        return

    try:
        from scholarly import scholarly as sc, ProxyGenerator
    except ImportError:
        print("  [skip] scholarly not installed -- skipping Google Scholar fetch.")
        print("         To enable: pip install scholarly")
        sys.exit(0)

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
        print("  Scholar blocks automated requests from server/cloud IPs.")
        print("  Run this script from your own machine (residential IP).")
        print("  Or set SCRAPER_API_KEY in fetch_scholar.py to use a proxy.")
        sys.exit(0)

    pubs = author.get("publications", [])
    print(f"  Found {len(pubs)} publications on Scholar.")

    existing_titles = load_existing_titles(BIB_OUT)
    manual_fp       = load_manual_fingerprints(BIB_OUT)
    rejected        = load_rejected(REJECTED_FILE)

    new_pubs       = []
    skipped_manual = 0
    skipped_exist  = 0
    skipped_reject = 0
    show           = args.show_skipped

    for pub in pubs:
        title = pub.get("bib", {}).get("title", "")
        if not title:
            continue
        norm_title = re.sub(r"\s+", " ", title).lower().strip()
        if norm_title in existing_titles:
            skipped_exist += 1
            if show: print(f"  [skip-exist]    {title[:70]}")
            continue
        if norm_title in rejected:
            skipped_reject += 1
            if show: print(f"  [skip-rejected] {title[:70]}")
            continue
        stub = {"ID": "", "doi": "", "note": "", "title": title}
        if fingerprint_matches(stub, manual_fp):
            skipped_manual += 1
            if show: print(f"  [skip-manual]   {title[:70]}")
            continue
        new_pubs.append(pub)

    if skipped_exist:   print(f"  Skipped {skipped_exist} already-present title(s)")
    if skipped_manual:  print(f"  Skipped {skipped_manual} matching manual entries")
    if skipped_reject:  print(f"  Skipped {skipped_reject} previously rejected")

    if not new_pubs:
        print("  No new Scholar entries to add.")
        return

    est = len(new_pubs) * 1.5
    print(f"  Fetching full BibTeX for {len(new_pubs)} new pubs (~{est:.0f}s)...")

    # Fetch full bibtex for each new pub before entering review
    candidates     = []   # (bibtex, doi, reject_key, source_label)
    fetch_failures = 0

    for i, pub in enumerate(new_pubs, 1):
        title = pub.get("bib", {}).get("title", "?")
        print(f"  [{i}/{len(new_pubs)}] {title[:70]}")
        bibtex, doi = fetch_full_bibtex(sc, pub)
        if bibtex is None:
            fetch_failures += 1
            continue
        norm_title = re.sub(r"\s+", " ", title).lower().strip()
        reject_key = norm_title   # use normalised title as stable key for Scholar
        candidates.append((bibtex, doi, reject_key, "Scholar"))

    if fetch_failures:
        print(f"  {fetch_failures} pub(s) could not be fetched and were skipped.")

    if not candidates:
        print("  No entries could be fetched.")
        return

    print(f"  {len(candidates)} candidate(s) to review.")

    new_rejected = {}
    if interactive:
        print()
        print("  Actions:  a=accept  e=edit  m=manual  r=reject+remember  s=skip  o=open DOI")
        entries, new_rejected = interactive_review(candidates, REJECTED_FILE)
    else:
        entries = [bibtex for bibtex, *_ in candidates]

    if not entries:
        print("  No entries accepted.")
    else:
        print(f"  {len(entries)} entry/entries accepted.")
        if not args.dry_run:
            with open(BIB_OUT, "a", encoding="utf-8") as f:
                f.write("\n\n% --- Google Scholar auto-fetched ---\n")
                f.write("\n\n".join(entries))
            print(f"  Appended to {BIB_OUT}")
        else:
            print("  [dry-run] Would append:\n")
            for e in entries:
                print(e, "\n")

    if new_rejected and not args.dry_run:
        existing = load_rejected(REJECTED_FILE)
        existing.update(new_rejected)
        save_rejected(REJECTED_FILE, existing)
        print(f"  Saved {len(new_rejected)} rejection(s) to {REJECTED_FILE}")
    elif new_rejected and args.dry_run:
        print(f"  [dry-run] Would remember {len(new_rejected)} rejection(s)")


if __name__ == "__main__":
    main()