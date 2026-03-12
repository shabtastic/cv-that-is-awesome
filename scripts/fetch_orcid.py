#!/usr/bin/env python3
"""
fetch_orcid.py
==============
Fetch publications from ORCID and append new entries to refs/journals.bib.

Requirements: pip install requests bibtexparser
"""

import argparse
import re
import sys
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).parent))
from _shared import load_manual_fingerprints, fingerprint_matches  # noqa: E402

# ── CONFIG ────────────────────────────────────────────────────────────────────
ORCID_ID  = "0000-0003-4122-6041"   # ← replace with your ORCID iD
BIB_OUT   = Path("refs/journals.bib")
ORCID_API = "https://pub.orcid.org/v3.0"
HEADERS   = {"Accept": "application/json"}
# ─────────────────────────────────────────────────────────────────────────────


def fetch_works(orcid_id: str) -> list[dict]:
    url = f"{ORCID_API}/{orcid_id}/works"
    r   = requests.get(url, headers=HEADERS, timeout=15)
    r.raise_for_status()
    data   = r.json()
    groups = data.get("group", [])
    works  = []
    for g in groups:
        summaries = g.get("work-summary", [])
        if summaries:
            works.append(summaries[0])  # take the preferred/primary work
    return works


def work_to_bibtex(work: dict) -> str | None:
    """
    Convert an ORCID work summary dict to a BibTeX @article string.

    Note: the ORCID summary API does not return full author lists — only the
    work title, year, journal, and DOI are reliably available at this level.
    The generated entry omits the author field so it is clearly visible during
    review. fetch_pubmed.py will fill in complete author data for the same
    papers via PMID/DOI matching; run dedup afterward to merge them.
    """
    title_obj = work.get("title", {}).get("title", {})
    title     = title_obj.get("value", "") if title_obj else ""
    pub_date  = work.get("publication-date") or {}
    year      = pub_date.get("year", {}).get("value", "????") if pub_date else "????"

    journal_obj = work.get("journal-title") or {}
    journal     = journal_obj.get("value", "") if isinstance(journal_obj, dict) else ""

    # Extract DOI from external-ids
    doi = ""
    ext_ids = work.get("external-ids", {}).get("external-id", [])
    for eid in ext_ids:
        if eid.get("external-id-type") == "doi":
            doi = eid.get("external-id-value", "")
            break

    if not title:
        return None

    first_word = re.sub(r"[^a-zA-Z]", "", title.split()[0]) if title else "unknown"
    cite_key   = f"ORCID{year}{first_word}"

    lines = [f"@article{{{cite_key},"]
    lines.append(f"  title    = {{{title}}},")
    lines.append(f"  year     = {{{year}}},")
    if journal:
        lines.append(f"  journal  = {{{journal}}},")
    if doi:
        lines.append(f"  doi      = {{{doi}}},")
    lines.append(f"  note     = {{Fetched from ORCID {ORCID_ID}}},")
    lines.append(f"  keywords = {{}},")
    lines.append("}")
    return "\n".join(lines)


def load_existing_dois(bib_path: Path) -> set[str]:
    if not bib_path.exists():
        return set()
    text = bib_path.read_text(encoding="utf-8")
    return set(re.findall(r'doi\s*=\s*\{([^}]+)\}', text, re.IGNORECASE))


def main():
    parser = argparse.ArgumentParser(description="Fetch publications from ORCID")
    parser.add_argument("--dry-run", action="store_true",
                        help="Preview new entries without writing to disk")
    args = parser.parse_args()

    print(f"Fetching works for ORCID: {ORCID_ID}")
    try:
        works = fetch_works(ORCID_ID)
    except Exception as e:
        print(f"[error] ORCID fetch failed: {e}")
        sys.exit(1)

    print(f"  Found {len(works)} works on ORCID.")
    existing_dois    = load_existing_dois(BIB_OUT)
    manual_fp        = load_manual_fingerprints(BIB_OUT)
    new_entries      = []
    skipped_manual   = 0

    for w in works:
        entry = work_to_bibtex(w)
        if entry is None:
            continue
        doi_match = re.search(r'doi\s*=\s*\{([^}]+)\}', entry, re.IGNORECASE)
        doi = doi_match.group(1).lower() if doi_match else ""
        if doi and doi in {d.lower() for d in existing_dois}:
            continue
        # Build a minimal dict for fingerprint matching
        stub = {"ID": "", "doi": doi, "note": "", "title": ""}
        if fingerprint_matches(stub, manual_fp):
            skipped_manual += 1
            continue
        new_entries.append(entry)

    if skipped_manual:
        print(f"  Skipped {skipped_manual} entries that match "
              f"manual entries in {BIB_OUT}")

    if not new_entries:
        print("  No new entries to add.")
        return

    print(f"  {len(new_entries)} new entries found.")
    if not args.dry_run:
        with open(BIB_OUT, "a", encoding="utf-8") as f:
            f.write("\n\n% --- ORCID auto-fetched ---\n")
            f.write("\n\n".join(new_entries))
        print(f"  Appended to {BIB_OUT}")
    else:
        print("  [dry-run] Would append:\n")
        for e in new_entries:
            print(e, "\n")


if __name__ == "__main__":
    main()