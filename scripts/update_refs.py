#!/usr/bin/env python3
"""
update_refs.py -- Master reference updater for Shabnam Hakimi's CV
=================================================================
Orchestrates fetching from ORCID, PubMed, and Google Scholar, then
merges new entries into the appropriate .bib files without duplicates.

MANUAL ENTRY PROTECTION
-----------------------
Any entry with keywords = {manual} is protected:
  - The deduplicator will never remove it.
  - Fetched entries that duplicate a manual one are silently skipped.
To protect a hand-added entry: keywords = {manual},

INTERACTIVE REVIEW
------------------
When run in a terminal (stdin is a TTY), each fetch source pauses for
interactive review of candidate entries. For each entry you can:

  a  Accept               -- add to the relevant .bib file
  e  Edit                 -- open in $EDITOR, then re-display
  m  Mark as manual       -- add with keywords={manual}
  r  Reject + remember    -- skip and save to refs/.<source>_rejected.json
  s  Skip this run only   -- will appear again next run
  o  Open DOI in browser  -- then re-display and re-prompt

Use --no-interactive to suppress review (useful for CI or cron).
Rejection lists live in refs/.<source>_rejected.json.

NOTE: Patents are excluded from automated orchestration.
fetch_patents.py is interactive and must be run manually:

    python scripts/fetch_patents.py               # refresh from USPTO
    python scripts/fetch_patents.py --mode discover
    python scripts/fetch_patents.py --dry-run

Usage:
    python update_refs.py [--sources orcid pubmed scholar] [--dry-run]
    python update_refs.py --dedup-only
    python update_refs.py --no-interactive

Requirements:
    pip install bibtexparser requests scholarly habanero
"""

import argparse
import re
import shutil
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _shared import is_manual, load_manual_fingerprints, fingerprint_matches  # noqa: E402

BIB_FILES = {
    "journals":      Path("refs/journals.bib"),
    "preprints":     Path("refs/preprints.bib"),
    "conference":    Path("refs/conference.bib"),
    "presentations": Path("refs/presentations.bib"),
    "scicomm":       Path("refs/scicomm.bib"),
}


# -- BACKUP -------------------------------------------------------------------

def backup_bib(bib_path: Path) -> Path:
    if not bib_path.exists():
        return None
    stamp    = datetime.now().strftime("%Y%m%d_%H%M%S")
    bak_path = bib_path.with_suffix(f".{stamp}.bak")
    shutil.copy2(bib_path, bak_path)
    return bak_path


# -- DEDUPLICATION ------------------------------------------------------------

def dedup_bib_file(bib_path: Path, dry_run: bool = False) -> int:
    """
    Remove duplicate entries from a .bib file.
    Manual entries are always kept; fetched duplicates of manual entries
    are removed with a warning.
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

    manual_keys = set()
    manual_dois = set()

    for entry in db.entries:
        if not is_manual(entry):
            continue
        manual_keys.add(entry.get("ID", "").lower())
        doi = entry.get("doi", "").lower().strip()
        if doi:
            manual_dois.add(doi)

    seen_keys   = set()
    seen_dois   = set()
    unique      = []
    removed     = 0
    warned_keys = set()

    for entry in db.entries:
        key    = entry.get("ID", "")
        doi    = entry.get("doi", "").lower().strip()
        manual = is_manual(entry)

        is_dup = key.lower() in seen_keys or (doi and doi in seen_dois)

        if is_dup:
            if key.lower() in manual_keys or doi in manual_dois:
                if key not in warned_keys:
                    print(f"  [warn] '{key}' duplicates a manual entry -- "
                          f"removing fetched version.")
                    warned_keys.add(key)
                removed += 1
                continue
            elif manual:
                unique = [e for e in unique
                          if e.get("ID", "").lower() != key.lower()
                          and e.get("doi", "").lower() != doi]
                removed += 1
                print(f"  [info] Replaced non-manual '{key}' with manual version.")
            else:
                removed += 1
                continue

        seen_keys.add(key.lower())
        if doi:
            seen_dois.add(doi)
        unique.append(entry)

    if removed and not dry_run:
        bak = backup_bib(bib_path)
        print(f"  [backup] {bib_path.name} -> {bak.name}")
        db.entries    = unique
        writer        = BibTexWriter()
        writer.indent = "  "
        with open(bib_path, "w", encoding="utf-8") as f:
            f.write(writer.write(db))
        print(f"  [dedup]  Removed {removed} duplicate(s) from {bib_path}")
    elif removed and dry_run:
        print(f"  [dry-run] Would remove {removed} duplicate(s) from {bib_path}")
    else:
        print(f"  [ok]     No duplicates in {bib_path}")

    return removed


# -- IN-PROCESS FETCH RUNNERS -------------------------------------------------

def _run_module(module_name: str, dry_run: bool, interactive: bool, **kwargs) -> int:
    """
    Import a fetch module and call its main(), patching sys.argv so it
    receives the right flags. Running in-process preserves the TTY so
    interactive prompts work.
    """
    import importlib
    mod = importlib.import_module(module_name)

    old_argv  = sys.argv
    sys.argv  = [f"scripts/{module_name}.py"]
    if dry_run:
        sys.argv.append("--dry-run")
    if interactive:
        sys.argv.append("--interactive")
    if kwargs.get("show_skipped"):
        sys.argv.append("--show-skipped")
    if kwargs.get("review_rejected"):
        sys.argv.append("--review-rejected")

    try:
        mod.main()
        return 0
    except SystemExit as exc:
        return exc.code if isinstance(exc.code, int) else 0
    except Exception as exc:
        print(f"  [error] {module_name} raised: {exc}")
        return 1
    finally:
        sys.argv = old_argv


FETCH_MODULES = {
    "orcid":   "fetch_orcid",
    "pubmed":  "fetch_pubmed",
    "scholar": "fetch_scholar",
}


# -- PATENT REMINDER ----------------------------------------------------------

def print_patent_reminder() -> None:
    print(
        "\n" + "="*60 + "\n"
        "  PATENTS -- manual step required\n"
        "  fetch_patents.py must be run separately:\n\n"
        "    python scripts/fetch_patents.py               # refresh\n"
        "    python scripts/fetch_patents.py --mode discover\n"
        "    python scripts/fetch_patents.py --dry-run\n"
        + "="*60
    )


# -- MAIN ---------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Master CV reference updater (excludes patents)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  python update_refs.py\n"
            "  python update_refs.py --sources orcid pubmed\n"
            "  python update_refs.py --dry-run\n"
            "  python update_refs.py --no-interactive\n"
            "  python update_refs.py --dedup-only\n"
            "  python update_refs.py --show-skipped\n"
            "  python update_refs.py --review-rejected\n"
            "  python update_refs.py --review-rejected pubmed\n"
        ),
    )
    parser.add_argument(
        "--sources", nargs="+",
        choices=list(FETCH_MODULES.keys()), default=list(FETCH_MODULES.keys()),
        help="Which sources to fetch from (default: all)"
    )
    parser.add_argument("--dry-run", action="store_true",
                        help="Preview without writing to disk")
    parser.add_argument("--dedup-only", action="store_true",
                        help="Skip fetching; only deduplicate existing .bib files")
    parser.add_argument("--no-interactive", action="store_true",
                        help="Auto-accept all verified entries without prompting")
    parser.add_argument("--show-skipped", action="store_true",
                        help="List every filtered-out entry and why (all sources)")
    parser.add_argument("--review-rejected", metavar="SOURCE",
                        nargs="?", const="all",
                        help="Review rejection list: all | orcid | pubmed | scholar")
    args = parser.parse_args()

    # Interactive when stdin is a real terminal, unless explicitly suppressed
    interactive = sys.stdin.isatty() and not args.no_interactive

    if not args.dedup_only:
        errors = []
        for source in args.sources:
            # --review-rejected: skip sources not requested
            rr = args.review_rejected
            if rr and rr != "all" and source != rr:
                continue
            print(f"\n{'='*60}")
            label = "Reviewing rejections:" if rr else "Fetching:"
            print(f"  {label} {source}")
            print(f"{'='*60}")
            rc = _run_module(
                FETCH_MODULES[source], args.dry_run, interactive,
                show_skipped=args.show_skipped,
                review_rejected=bool(rr),
            )
            if rc != 0:
                errors.append(source)
        if errors:
            print(f"\n[warn] Sources with errors: {errors}")

    # Skip dedup if we only ran --review-rejected (no new entries were added)
    if args.review_rejected and args.dedup_only is False:
        print("\n(Skipping dedup — no new entries fetched in --review-rejected mode.)")
        print_patent_reminder()
        return

    print("\n--- Deduplicating .bib files ---")
    total_removed = 0
    for label, path in BIB_FILES.items():
        total_removed += dedup_bib_file(path, dry_run=args.dry_run)

    print(f"\nDone. Total duplicates removed: {total_removed}")
    print_patent_reminder()


if __name__ == "__main__":
    main()