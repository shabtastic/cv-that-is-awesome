#!/usr/bin/env python3
"""
review_bib.py
=============
Interactively review the existing entries in any .bib file.

For each entry you can:

  e  Edit in $EDITOR          -- opens entry in your editor, saves on exit
  k  Keywords                 -- add/edit keyword tags interactively
  m  Toggle manual flag       -- add or remove "manual" from keywords
  d  Delete entry             -- mark for removal (confirmed at end)
  s  Skip                     -- leave unchanged, move to next entry
  q  Quit                     -- stop reviewing; write changes so far

Entries marked for deletion are shown in a confirmation summary before
anything is written to disk. Changes are written atomically (backup first).

Usage:
    python scripts/review_bib.py refs/journals.bib
    python scripts/review_bib.py refs/conference.bib --filter selected
    python scripts/review_bib.py refs/journals.bib --dry-run
    python scripts/review_bib.py refs/journals.bib --start 5

Options:
    --filter KEYWORD    Only show entries whose keywords contain KEYWORD
    --start N           Start at entry number N (1-indexed)
    --dry-run / -n      Preview changes without writing to disk

Requirements: pip install bibtexparser
"""

import argparse
import re
import shutil
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _shared import (  # noqa: E402
    display_entry, edit_in_editor, prompt_keywords, inject_keywords,
    write_atomic,
)

# ---------------------------------------------------------------------------
# BIB PARSING / WRITING (raw-text, preserving formatting)
# ---------------------------------------------------------------------------

def parse_entries(text: str) -> list:
    """
    Split a .bib file into (kind, text) chunks preserving order.
    kind is "entry" for @-entries and "comment" for everything else.
    Uses brace counting to handle nested braces correctly.
    Only matches @ signs that start a BibTeX entry (not those inside % comments).
    """
    chunks = []
    i      = 0
    n      = len(text)

    while i < n:
        # Find next @
        at = text.find("@", i)
        if at == -1:
            trailing = text[i:].strip()
            if trailing:
                chunks.append(("comment", trailing))
            break

        # Check if this @ is inside a % comment line
        # (scan back to the start of the line)
        line_start = text.rfind("\n", 0, at) + 1
        line_prefix = text[line_start:at].lstrip()
        if line_prefix.startswith("%"):
            # This @ is inside a comment — skip past it
            i = at + 1
            continue

        # Capture any comment/whitespace before the @
        pre = text[i:at].strip()
        if pre:
            chunks.append(("comment", pre))

        # Find the opening brace of the entry
        brace_start = text.find("{", at)
        if brace_start == -1:
            # Malformed — treat rest as comment
            chunks.append(("comment", text[at:].strip()))
            break

        # Brace-count to find the matching closing brace
        depth = 0
        j     = brace_start
        while j < n:
            if text[j] == "{":
                depth += 1
            elif text[j] == "}":
                depth -= 1
                if depth == 0:
                    break
            j += 1

        entry = text[at:j + 1].strip()
        chunks.append(("entry", entry))
        i = j + 1

    return chunks


def write_bib(path: Path, chunks: list, dry_run: bool = False) -> None:
    """Write kept entries back to the bib file (with backup)."""
    kept = [text for kind, text in chunks if kind != "deleted"]
    content = "\n\n".join(kept) + "\n"
    if dry_run:
        print(f"\n  [dry-run] Would write {len([c for c in chunks if c[0]=='entry' and c[0]!='deleted'])} entries to {path}")
        return
    stamp    = datetime.now().strftime("%Y%m%d_%H%M%S")
    bak_path = path.with_suffix(f".{stamp}.bak")
    shutil.copy2(path, bak_path)
    print(f"  [backup] {path.name} -> {bak_path.name}")
    write_atomic(path, content)
    print(f"  [written] {path}")


# ---------------------------------------------------------------------------
# ENTRY HELPERS
# ---------------------------------------------------------------------------

def get_cite_key(bibtex: str) -> str:
    m = re.search(r"@\w+\{(\S+),", bibtex)
    return m.group(1) if m else "?"


def get_keywords(bibtex: str) -> str:
    m = re.search(r"keywords\s*=\s*\{([^}]*)\}", bibtex, re.IGNORECASE)
    return m.group(1) if m else ""


def has_keyword(bibtex: str, kw: str) -> bool:
    tags = {t.strip().lower() for t in get_keywords(bibtex).split(",")}
    return kw.lower() in tags


def toggle_manual(bibtex: str) -> tuple:
    """
    Add or remove 'manual' from the keywords field.
    Returns (updated_bibtex, action_taken) where action_taken is 'added' or 'removed'.
    """
    kw_m = re.search(r"keywords\s*=\s*\{([^}]*)\}", bibtex, re.IGNORECASE)
    current = kw_m.group(1) if kw_m else ""
    tags = {t.strip() for t in current.split(",") if t.strip()}

    if "manual" in tags:
        tags.discard("manual")
        new_kw = ", ".join(sorted(tags))
        return inject_keywords(bibtex, new_kw), "removed"
    else:
        tags.add("manual")
        new_kw = ", ".join(sorted(tags))
        return inject_keywords(bibtex, new_kw), "added"


# ---------------------------------------------------------------------------
# PROMPT
# ---------------------------------------------------------------------------

def prompt_review_action(has_doi: bool) -> str:
    """
    Prompt for a review action on an existing bib entry. Returns one of:
      edit  keyword  manual  delete  skip  open  quit
    """
    line = "  [e]dit  [k]eywords  [m]anual toggle  [d]elete  [s]kip"
    if has_doi:
        line += "  [o]pen DOI"
    line += "  [q]uit : "

    while True:
        try:
            ch = input(line).strip().lower()
        except (EOFError, KeyboardInterrupt):
            print("\n  Interrupted.")
            return "quit"

        if ch in ("e", "edit"):               return "edit"
        if ch in ("k", "keywords", "keyword"): return "keyword"
        if ch in ("m", "manual"):             return "manual"
        if ch in ("d", "delete"):             return "delete"
        if ch in ("s", "skip", ""):           return "skip"
        if ch in ("o", "open") and has_doi:   return "open"
        if ch in ("q", "quit"):               return "quit"
        valid = "e/k/m/d/s" + ("/o" if has_doi else "") + "/q"
        print(f"  Please enter one of: {valid}")


# ---------------------------------------------------------------------------
# MAIN REVIEW LOOP
# ---------------------------------------------------------------------------

def review_entries(
    chunks: list,
    filter_kw: str = None,
    start: int = 1,
) -> tuple:
    """
    Walk through entry chunks interactively.

    Args:
        chunks:    list of ("entry"|"comment", text) from parse_entries()
        filter_kw: if set, only show entries containing this keyword
        start:     1-indexed entry number to start from

    Returns:
        (updated_chunks, changed, deleted_keys)
    """
    import webbrowser

    entries_only = [(i, text) for i, (kind, text) in enumerate(chunks) if kind == "entry"]

    if filter_kw:
        entries_only = [(i, text) for i, text in entries_only
                        if has_keyword(text, filter_kw)]
        print(f"  Filtered to {len(entries_only)} entries with keyword '{filter_kw}'.")

    if not entries_only:
        print("  No entries to review.")
        return chunks, 0, []

    # Apply --start offset
    if start > 1:
        entries_only = [(i, t) for i, t in entries_only
                        if entries_only.index((i, t)) >= start - 1]
        print(f"  Starting from entry {start}.")

    total       = len(entries_only)
    changed     = 0
    deleted_keys = []

    for seq, (chunk_idx, bibtex) in enumerate(entries_only, 1):
        doi_m   = re.search(r"doi\s*=\s*\{([^}]+)\}", bibtex, re.IGNORECASE)
        doi     = doi_m.group(1).strip() if doi_m else ""
        has_doi = bool(doi)
        key     = get_cite_key(bibtex)
        kws     = get_keywords(bibtex)
        source  = f"{key}  |  {kws}" if kws else key

        # Inner loop: edit/keyword re-display without advancing
        while True:
            display_entry(bibtex, seq, total, source)
            action = prompt_review_action(has_doi)

            if action == "open":
                import webbrowser
                url = f"https://doi.org/{doi}"
                print(f"  Opening {url} ...")
                webbrowser.open(url)
                continue

            if action == "edit":
                new_bibtex = edit_in_editor(bibtex)
                if new_bibtex != bibtex:
                    bibtex = new_bibtex
                    chunks[chunk_idx] = ("entry", bibtex)
                    changed += 1
                    source = f"{get_cite_key(bibtex)}  |  {get_keywords(bibtex)}"
                    print("  -> Saved.")
                continue  # re-display after edit

            if action == "keyword":
                current = get_keywords(bibtex)
                new_kw  = prompt_keywords(current)
                if new_kw != current:
                    bibtex = inject_keywords(bibtex, new_kw)
                    chunks[chunk_idx] = ("entry", bibtex)
                    changed += 1
                    source = f"{get_cite_key(bibtex)}  |  {get_keywords(bibtex)}"
                    print(f"  -> Keywords updated: {{{new_kw}}}")
                continue  # re-display

            if action == "manual":
                bibtex, result = toggle_manual(bibtex)
                chunks[chunk_idx] = ("entry", bibtex)
                changed += 1
                source = f"{get_cite_key(bibtex)}  |  {get_keywords(bibtex)}"
                print(f"  -> 'manual' {result}.")
                continue  # re-display so user sees updated keywords

            if action == "delete":
                try:
                    confirm = input(f"  Delete '{key}'? This cannot be undone. [y/N]: ").strip().lower()
                except (EOFError, KeyboardInterrupt):
                    confirm = "n"
                if confirm == "y":
                    chunks[chunk_idx] = ("deleted", bibtex)
                    deleted_keys.append(key)
                    changed += 1
                    print(f"  -> Marked for deletion: {key}")
                else:
                    print("  -> Cancelled.")
                break  # advance to next entry regardless

            if action == "skip":
                break  # advance without changes

            if action == "quit":
                print(f"\n  Stopped at entry {seq}/{total}. "
                      f"{changed} change(s) so far.")
                return chunks, changed, deleted_keys

    print(f"\n  Review complete. {changed} change(s) made.")
    return chunks, changed, deleted_keys


# ---------------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Interactively review entries in a .bib file",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  python scripts/review_bib.py refs/journals.bib\n"
            "  python scripts/review_bib.py refs/conference.bib --filter selected\n"
            "  python scripts/review_bib.py refs/journals.bib --start 10\n"
            "  python scripts/review_bib.py refs/preprints.bib --dry-run\n"
        ),
    )
    parser.add_argument("bib", metavar="BIB_FILE",
                        help="Path to the .bib file to review")
    parser.add_argument("--filter", metavar="KEYWORD", dest="filter_kw",
                        help="Only review entries containing this keyword")
    parser.add_argument("--start", metavar="N", type=int, default=1,
                        help="Start at entry number N (1-indexed, default: 1)")
    parser.add_argument("--dry-run", "-n", action="store_true",
                        help="Preview changes without writing to disk")
    args = parser.parse_args()

    bib_path = Path(args.bib)
    if not bib_path.exists():
        print(f"  [error] File not found: {bib_path}")
        sys.exit(1)

    text   = bib_path.read_text(encoding="utf-8")
    chunks = parse_entries(text)

    n_entries = sum(1 for kind, _ in chunks if kind == "entry")
    print()
    print("=" * 72)
    print(f"  review_bib.py  —  {bib_path}")
    print(f"  {n_entries} entries")
    if args.filter_kw:
        print(f"  filter: keywords contain '{args.filter_kw}'")
    if args.dry_run:
        print("  mode: dry-run (no changes will be written)")
    print("=" * 72)
    print()
    print("  Actions:  [e]dit  [k]eywords  [m]anual toggle  [d]elete  [s]kip  [q]uit")
    if any(re.search(r"doi\s*=", t, re.IGNORECASE) for _, t in chunks if _ == "entry"):
        print("            [o]pen DOI  (shown when entry has a DOI field)")

    chunks, changed, deleted_keys = review_entries(
        chunks,
        filter_kw=args.filter_kw,
        start=args.start,
    )

    if not changed:
        print("\n  No changes — nothing to write.")
        return

    # Deletion summary
    if deleted_keys:
        print(f"\n  Entries marked for deletion ({len(deleted_keys)}):")
        for k in deleted_keys:
            print(f"    - {k}")
        if not args.dry_run:
            try:
                confirm = input("\n  Write changes (including deletions) to disk? [Y/n]: ").strip().lower()
            except (EOFError, KeyboardInterrupt):
                confirm = "n"
            if confirm not in ("", "y", "yes"):
                print("  Aborted — no changes written.")
                return
    else:
        if not args.dry_run:
            try:
                confirm = input(f"\n  Write {changed} change(s) to {bib_path}? [Y/n]: ").strip().lower()
            except (EOFError, KeyboardInterrupt):
                confirm = "n"
            if confirm not in ("", "y", "yes"):
                print("  Aborted — no changes written.")
                return

    write_bib(bib_path, chunks, dry_run=args.dry_run)


if __name__ == "__main__":
    main()