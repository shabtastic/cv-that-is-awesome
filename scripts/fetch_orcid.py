#!/usr/bin/env python3
"""
fetch_orcid.py
==============
Fetch publications from ORCID and append new entries to refs/journals.bib.

Note: the ORCID summary API does not return full author lists -- only the
title, year, journal, and DOI are reliably available. The generated entries
omit the author field so the gap is visible during review. fetch_pubmed.py
fills in complete author data for the same papers via DOI/PMID matching;
run dedup afterward to merge.

Rejected entries are saved to refs/.orcid_rejected.json.

Requirements: pip install requests
"""

import argparse
import re
import sys
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).parent))
from _shared import (  # noqa: E402
    load_manual_fingerprints, fingerprint_matches,
    load_rejected, save_rejected, interactive_review, review_rejected,
)

# ---------------------------------------------------------------------------
# CONFIG
# ---------------------------------------------------------------------------
ORCID_ID      = "0000-0003-4122-6041"
BIB_OUT       = Path("refs/journals.bib")
REJECTED_FILE = Path("refs/.orcid_rejected.json")
ORCID_API     = "https://pub.orcid.org/v3.0"
HEADERS       = {"Accept": "application/json"}
# ---------------------------------------------------------------------------


def fetch_works(orcid_id: str) -> list:
    url = f"{ORCID_API}/{orcid_id}/works"
    r   = requests.get(url, headers=HEADERS, timeout=15)
    r.raise_for_status()
    data   = r.json()
    groups = data.get("group", [])
    works  = []
    for g in groups:
        summaries = g.get("work-summary", [])
        if summaries:
            works.append(summaries[0])
    return works


def work_to_bibtex(work: dict) -> tuple:
    """
    Convert an ORCID work summary to a BibTeX string.
    Returns (bibtex_str, doi) or (None, None) if no title.
    """
    title_obj = work.get("title", {}).get("title", {})
    title     = title_obj.get("value", "") if title_obj else ""
    pub_date  = work.get("publication-date") or {}
    year      = pub_date.get("year", {}).get("value", "????") if pub_date else "????"

    journal_obj = work.get("journal-title") or {}
    journal     = journal_obj.get("value", "") if isinstance(journal_obj, dict) else ""

    doi = ""
    ext_ids = work.get("external-ids", {}).get("external-id", [])
    for eid in ext_ids:
        if eid.get("external-id-type") == "doi":
            doi = eid.get("external-id-value", "")
            break

    if not title:
        return None, None

    first_word = re.sub(r"[^a-zA-Z]", "", title.split()[0]) if title else "unknown"
    cite_key   = f"ORCID{year}{first_word}"

    lines = [f"@article{{{cite_key},"]
    lines.append(f"  title    = {{{title}}},")
    lines.append(f"  year     = {{{year}}},")
    if journal: lines.append(f"  journal  = {{{journal}}},")
    if doi:     lines.append(f"  doi      = {{{doi}}},")
    lines.append(f"  note     = {{Fetched from ORCID {ORCID_ID}}},")
    lines.append(f"  keywords = {{}},")
    lines.append("}")
    return "\n".join(lines), doi


def load_existing_dois(bib_path: Path) -> set:
    if not bib_path.exists():
        return set()
    text = bib_path.read_text(encoding="utf-8")
    return set(re.findall(r"doi\s*=\s*\{([^}]+)\}", text, re.IGNORECASE))


def main():
    parser = argparse.ArgumentParser(description="Fetch publications from ORCID")
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

    print(f"Fetching works for ORCID: {ORCID_ID}")
    try:
        works = fetch_works(ORCID_ID)
    except Exception as e:
        print(f"  [error] ORCID fetch failed: {e}")
        sys.exit(1)

    print(f"  Found {len(works)} works on ORCID.")
    existing_dois = load_existing_dois(BIB_OUT)
    manual_fp     = load_manual_fingerprints(BIB_OUT)
    rejected      = load_rejected(REJECTED_FILE)

    candidates     = []   # (bibtex, doi, reject_key, source_label)
    skipped_manual = 0
    skipped_exist  = 0
    skipped_reject = 0
    show           = args.show_skipped

    for w in works:
        bibtex, doi = work_to_bibtex(w)
        if bibtex is None:
            continue
        doi_norm = doi.lower().strip() if doi else ""
        reject_key = doi_norm or re.search(r"@\w+\{(\S+),", bibtex).group(1)
        if doi_norm and doi_norm in {d.lower() for d in existing_dois}:
            skipped_exist += 1
            if show: print(f"  [skip-exist]    DOI {doi_norm} already in {BIB_OUT}")
            continue
        if reject_key in rejected:
            skipped_reject += 1
            if show: print(f"  [skip-rejected] {reject_key}: {rejected[reject_key][:60]}")
            continue
        stub = {"ID": "", "doi": doi_norm, "note": "", "title": ""}
        if fingerprint_matches(stub, manual_fp):
            skipped_manual += 1
            if show: print(f"  [skip-manual]   {reject_key} matches a protected manual entry")
            continue
        candidates.append((bibtex, doi, reject_key, "ORCID"))

    if skipped_exist:   print(f"  Skipped {skipped_exist} already-present DOI(s)")
    if skipped_manual:  print(f"  Skipped {skipped_manual} matching manual entries")
    if skipped_reject:  print(f"  Skipped {skipped_reject} previously rejected")

    if not candidates:
        print("  No new entries to add.")
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
                f.write("\n\n% --- ORCID auto-fetched ---\n")
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