#!/usr/bin/env python3
"""
update_refs.py — Master reference updater for Shabnam Hakimi's CV
=================================================================
Orchestrates fetching from ORCID, PubMed, and Google Scholar, then
merges new entries into the appropriate .bib files without duplicates.

MANUAL ENTRY PROTECTION
-----------------------
Any entry in any .bib file with  keywords = {manual}  (or any keyword
string containing "manual") is treated as protected:

  - The deduplicator will NEVER remove a manual entry, even if it
    appears to duplicate a fetched entry.
  - If a fetched entry would duplicate a manual one (matching DOI,
    PMID, or cite key), the fetched entry is silently skipped.
  - On dedup conflicts between a manual entry and a fetched entry,
    the manual entry is always kept and the fetched one removed.

To protect any entry you add by hand, simply add:
    keywords = {manual},
or combine with other keywords:
    keywords = {manual, selected},

NOTE: Patents are excluded from automated orchestration.
fetch_patents.py is interactive and must be run manually:

    python scripts/fetch_patents.py               # refresh from USPTO
    python scripts/fetch_patents.py --mode discover  # find new patents
    python scripts/fetch_patents.py --dry-run     # preview only

Usage:
    python update_refs.py [--sources orcid pubmed scholar] [--dry-run]
    python update_refs.py --dedup-only

Requirements:
    pip install bibtexparser requests scholarly habanero
"""

import argparse
import re
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

# ── Non-interactive fetch scripts ─────────────────────────────────────────────
SCRIPTS = {
    "orcid":   "fetch_orcid.py",
    "pubmed":  "fetch_pubmed.py",
    "scholar": "fetch_scholar.py",
}

# ── All .bib files to deduplicate (patents managed separately) ────────────────
BIB_FILES = {
    "journals":      Path("refs/journals.bib"),
    "preprints":     Path("refs/preprints.bib"),
    "conference":    Path("refs/conference.bib"),
    "presentations": Path("refs/presentations.bib"),
    "scicomm":       Path("refs/scicomm.bib"),
}


# ── MANUAL ENTRY UTILITIES ───────────────────────────────────────────────────

def is_manual(entry: dict) -> bool:
    """Return True if a bibtexparser entry is flagged as manual."""
    return "manual" in entry.get("keywords", "").lower()


def load_manual_fingerprints(bib_path: Path) -> dict:
    """
    Parse a .bib file and return fingerprints of all manual entries.
    Returns dict with sets: {keys, dois, pmids, titles}
    Used by fetch scripts to avoid appending duplicates of manual entries.
    """
    fp = {"keys": set(), "dois": set(), "pmids": set(), "titles": set()}
    if not bib_path.exists():
        return fp

    try:
        import bibtexparser
    except ImportError:
        # Fallback: regex-based extraction
        return _load_manual_fingerprints_regex(bib_path)

    with open(bib_path, encoding="utf-8") as f:
        db = bibtexparser.load(f)

    for entry in db.entries:
        if not is_manual(entry):
            continue
        fp["keys"].add(entry.get("ID", "").lower())
        doi = entry.get("doi", "").lower().strip()
        if doi:
            fp["dois"].add(doi)
        pmid_match = re.search(r'PMID:\s*(\d+)',
                               entry.get("note", ""), re.IGNORECASE)
        if pmid_match:
            fp["pmids"].add(pmid_match.group(1))
        title = re.sub(r'\s+', ' ', entry.get("title", "")).lower().strip()
        if title:
            fp["titles"].add(title)

    return fp


def _load_manual_fingerprints_regex(bib_path: Path) -> dict:
    """Regex fallback for load_manual_fingerprints."""
    fp      = {"keys": set(), "dois": set(), "pmids": set(), "titles": set()}
    text    = bib_path.read_text(encoding="utf-8")
    entries = re.split(r'\n(?=@)', text)

    for entry in entries:
        kw = re.search(r'keywords\s*=\s*\{([^}]*)\}', entry, re.IGNORECASE)
        if not kw or "manual" not in kw.group(1).lower():
            continue
        key_m   = re.search(r'@\w+\{(\S+),', entry)
        doi_m   = re.search(r'doi\s*=\s*\{([^}]+)\}', entry, re.IGNORECASE)
        pmid_m  = re.search(r'PMID:\s*(\d+)', entry, re.IGNORECASE)
        title_m = re.search(r'title\s*=\s*\{([^}]+)\}', entry, re.IGNORECASE)

        if key_m:
            fp["keys"].add(key_m.group(1).lower())
        if doi_m:
            fp["dois"].add(doi_m.group(1).lower().strip())
        if pmid_m:
            fp["pmids"].add(pmid_m.group(1))
        if title_m:
            title = re.sub(r'\s+', ' ', title_m.group(1)).lower().strip()
            fp["titles"].add(title)

    return fp


def fingerprint_matches(entry: dict, fp: dict) -> bool:
    """
    Return True if a fetched entry matches any manual fingerprint,
    meaning it would duplicate a protected manual entry.
    """
    if entry.get("ID", "").lower() in fp["keys"]:
        return True
    doi = entry.get("doi", "").lower().strip()
    if doi and doi in fp["dois"]:
        return True
    pmid_match = re.search(r'PMID:\s*(\d+)',
                           entry.get("note", ""), re.IGNORECASE)
    if pmid_match and pmid_match.group(1) in fp["pmids"]:
        return True
    title = re.sub(r'\s+', ' ',
                   entry.get("title", "")).lower().strip()
    if title and title in fp["titles"]:
        return True
    return False


# ── BACKUP ───────────────────────────────────────────────────────────────────

def backup_bib(bib_path: Path) -> Path:
    """Back up a .bib file, stamped with today's date. Returns backup path."""
    if not bib_path.exists():
        return None
    stamp    = datetime.now().strftime("%Y%m%d_%H%M%S")
    bak_path = bib_path.with_suffix(f".{stamp}.bak")
    shutil.copy2(bib_path, bak_path)
    return bak_path


# ── DEDUPLICATION ─────────────────────────────────────────────────────────────

def dedup_bib_file(bib_path: Path, dry_run: bool = False) -> int:
    """
    Remove duplicate entries from a .bib file.

    Rules:
      - Manual entries (keywords containing 'manual') are ALWAYS kept.
      - On a conflict between a manual entry and a fetched entry,
        the fetched entry is removed and a warning is printed.
      - On a conflict between two non-manual entries, the first
        occurrence (earlier in the file) is kept.

    Returns number of duplicates removed.
    """
    try:
        import bibtexparser
        from bibtexparser.bwriter import BibTexWriter
    except ImportError:
        print("  [warn] bibtexparser not installed; skipping dedup.")
        return 0

    if not bib_path.exists():
        return 0

    with open(bib_path, encoding="utf-8") as f:
        db = bibtexparser.load(f)

    # First pass: index manual entries by their fingerprints
    manual_keys  = set()
    manual_dois  = set()
    manual_pmids = set()

    for entry in db.entries:
        if not is_manual(entry):
            continue
        manual_keys.add(entry.get("ID", "").lower())
        doi = entry.get("doi", "").lower().strip()
        if doi:
            manual_dois.add(doi)
        pm = re.search(r'PMID:\s*(\d+)',
                       entry.get("note", ""), re.IGNORECASE)
        if pm:
            manual_pmids.add(pm.group(1))

    # Second pass: deduplicate, always preserving manual entries
    seen_keys    = set()
    seen_dois    = set()
    unique       = []
    removed      = 0
    warned_keys  = set()

    for entry in db.entries:
        key   = entry.get("ID", "")
        doi   = entry.get("doi", "").lower().strip()
        pm    = re.search(r'PMID:\s*(\d+)',
                          entry.get("note", ""), re.IGNORECASE)
        pmid  = pm.group(1) if pm else ""
        manual = is_manual(entry)

        is_dup = (
            key.lower() in seen_keys
            or (doi and doi in seen_dois)
        )

        if is_dup:
            # Check if the already-seen version is manual
            if key.lower() in manual_keys or doi in manual_dois:
                if key not in warned_keys:
                    print(f"  [warn] Fetched entry '{key}' duplicates a "
                          f"manual entry — removing fetched version.")
                    warned_keys.add(key)
                removed += 1
                continue
            elif manual:
                # Current entry is manual but earlier duplicate was not —
                # remove the earlier one and keep this manual entry
                unique   = [e for e in unique
                            if e.get("ID", "").lower() != key.lower()
                            and e.get("doi", "").lower() != doi]
                removed += 1
                print(f"  [info] Replaced non-manual entry '{key}' "
                      f"with manual version.")
            else:
                removed += 1
                continue

        seen_keys.add(key.lower())
        if doi:
            seen_dois.add(doi)
        unique.append(entry)

    if removed and not dry_run:
        bak = backup_bib(bib_path)
        print(f"  [backup] {bib_path.name} → {bak.name}")
        db.entries    = unique
        writer        = BibTexWriter()
        writer.indent = "  "
        with open(bib_path, "w", encoding="utf-8") as f:
            f.write(writer.write(db))
        print(f"  [dedup]  Removed {removed} duplicate(s) from {bib_path}")
    elif removed and dry_run:
        print(f"  [dry-run] Would remove {removed} duplicate(s) "
              f"from {bib_path}")
    else:
        print(f"  [ok]     No duplicates in {bib_path}")

    return removed


# ── SUBPROCESS RUNNER ─────────────────────────────────────────────────────────

def run_script(script_name: str, dry_run: bool) -> int:
    """Run a fetch sub-script and return its exit code."""
    cmd = [sys.executable, Path(__file__).parent / script_name]
    if dry_run:
        cmd.append("--dry-run")
    print(f"\n{'='*60}")
    print(f"  Running: {script_name}")
    print(f"{'='*60}")
    result = subprocess.run(cmd, check=False)
    return result.returncode


# ── PATENT REMINDER ───────────────────────────────────────────────────────────

def print_patent_reminder() -> None:
    print(
        "\n" + "="*60 + "\n"
        "  PATENTS — manual step required\n"
        "  fetch_patents.py is interactive and must be run separately:\n\n"
        "    python scripts/fetch_patents.py               # refresh\n"
        "    python scripts/fetch_patents.py --mode discover\n"
        "    python scripts/fetch_patents.py --dry-run     # preview\n"
        + "="*60
    )


# ── MAIN ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Master CV reference updater (excludes patents)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  python update_refs.py\n"
            "  python update_refs.py --sources orcid pubmed\n"
            "  python update_refs.py --dry-run\n"
            "  python update_refs.py --dedup-only\n"
        ),
    )
    parser.add_argument(
        "--sources", nargs="+",
        choices=list(SCRIPTS.keys()), default=list(SCRIPTS.keys()),
        help="Which sources to fetch from (default: all)"
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Preview without writing to disk"
    )
    parser.add_argument(
        "--dedup-only", action="store_true",
        help="Skip fetching; only deduplicate existing .bib files"
    )
    args = parser.parse_args()

    if not args.dedup_only:
        errors = []
        for source in args.sources:
            rc = run_script(SCRIPTS[source], args.dry_run)
            if rc != 0:
                errors.append(source)
        if errors:
            print(f"\n[warn] Sources with errors: {errors}")

    print("\n--- Deduplicating .bib files ---")
    total_removed = 0
    for label, path in BIB_FILES.items():
        total_removed += dedup_bib_file(path, dry_run=args.dry_run)

    print(f"\nDone. Total duplicates removed: {total_removed}")
    print_patent_reminder()


if __name__ == "__main__":
    main()