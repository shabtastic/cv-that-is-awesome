#!/usr/bin/env python3
"""
_shared.py
==========
Shared utilities for fetch_orcid.py, fetch_pubmed.py, fetch_scholar.py.

Provides:
  - is_manual(entry)
  - load_manual_fingerprints(bib_path)
  - normalize_title(title)
  - load_all_titles(bib_paths)
  - fingerprint_matches(entry, fp)
  - display_entry(bibtex, index, total, source)
  - edit_in_editor(bibtex)
  - prompt_action(has_doi)
  - interactive_review(candidates, rejected_file)

These live here so each fetch script can use them both when run standalone
and when called in-process by update_refs.py.
"""

import json
import os
import re
import subprocess
import sys
import tempfile
import unicodedata
import webbrowser
from pathlib import Path


# ---------------------------------------------------------------------------
# ATOMIC WRITES
# ---------------------------------------------------------------------------
#
# Every script that mutates a .bib or .json file routes its final write
# through write_atomic(). The pattern: write to a temp file in the SAME
# directory (so os.replace is atomic on POSIX), fsync, then rename.
#
# Without this, an interrupted fetch (Ctrl+C, crash, power loss mid-write)
# can leave a .bib file with a half-written entry or a rejection JSON
# truncated to zero bytes -- silent data loss that is easy to miss until
# the next compile or fetch run.
#
# append_atomic() is the append-mode equivalent: read-modify-write, still
# atomic at the rename step. It's slightly more expensive than a plain
# append but the files involved are small (a few hundred KB max).

def write_atomic(path: Path, text: str, encoding: str = "utf-8") -> None:
    """Atomically replace `path` with `text`. Parent dir must exist."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    # delete=False so we control the rename; dir=path.parent so the rename
    # stays within one filesystem (cross-device rename is not atomic).
    fd, tmp_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent)
    )
    tmp = Path(tmp_name)
    try:
        with os.fdopen(fd, "w", encoding=encoding) as f:
            f.write(text)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    except BaseException:
        tmp.unlink(missing_ok=True)
        raise


def append_atomic(path: Path, text: str, encoding: str = "utf-8") -> None:
    """Atomically append `text` to `path` (create if missing)."""
    path = Path(path)
    existing = path.read_text(encoding=encoding) if path.exists() else ""
    write_atomic(path, existing + text, encoding=encoding)


# ---------------------------------------------------------------------------
# MANUAL ENTRY PROTECTION
# ---------------------------------------------------------------------------

def is_manual(entry: dict) -> bool:
    """Return True if a bibtexparser entry is flagged as manual."""
    return "manual" in entry.get("keywords", "").lower()


def load_manual_fingerprints(bib_path: Path) -> dict:
    """
    Parse a .bib file and return fingerprints of all manual entries.
    Returns dict with sets: {keys, dois, pmids, titles}
    """
    fp = {"keys": set(), "dois": set(), "pmids": set(), "titles": set()}
    if not bib_path.exists():
        return fp

    try:
        import bibtexparser
    except ImportError:
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
        pmid_match = re.search(r"PMID:\s*(\d+)",
                               entry.get("note", ""), re.IGNORECASE)
        if pmid_match:
            fp["pmids"].add(pmid_match.group(1))
        title = normalize_title(entry.get("title", ""))
        if title:
            fp["titles"].add(title)

    return fp


def _extract_braced_field(entry: str, field: str) -> str:
    """
    Return the raw content of ``field = {...}`` from a BibTeX entry with
    proper brace-balancing. Returns "" if not found. A plain
    ``[^}]+`` regex truncates at the first ``}`` and silently mangles
    titles like ``{{AI}-driven learning}`` into ``{AI``.
    """
    m = re.search(rf"\b{field}\s*=\s*\{{", entry, re.IGNORECASE)
    if not m:
        return ""
    i     = m.end()
    depth = 1
    out   = []
    while i < len(entry) and depth > 0:
        c = entry[i]
        if c == "{":
            depth += 1
            out.append(c)
        elif c == "}":
            depth -= 1
            if depth > 0:
                out.append(c)
        else:
            out.append(c)
        i += 1
    return "".join(out)


def _load_manual_fingerprints_regex(bib_path: Path) -> dict:
    """Regex fallback for load_manual_fingerprints (no bibtexparser)."""
    fp      = {"keys": set(), "dois": set(), "pmids": set(), "titles": set()}
    text    = bib_path.read_text(encoding="utf-8")
    entries = re.split(r"\n(?=@)", text)

    for entry in entries:
        kw_raw = _extract_braced_field(entry, "keywords")
        if "manual" not in kw_raw.lower():
            continue
        key_m   = re.search(r"@\w+\{(\S+),", entry)
        doi_raw = _extract_braced_field(entry, "doi").strip()
        pmid_m  = re.search(r"PMID:\s*(\d+)", entry, re.IGNORECASE)
        title_raw = _extract_braced_field(entry, "title")

        if key_m:   fp["keys"].add(key_m.group(1).lower())
        if doi_raw: fp["dois"].add(doi_raw.lower())
        if pmid_m:  fp["pmids"].add(pmid_m.group(1))
        if title_raw:
            title = normalize_title(title_raw)
            if title:
                fp["titles"].add(title)

    return fp


def normalize_title(title: str) -> str:
    """
    Canonical title fingerprint used for dedup across all code paths.
    Every site that compares titles for duplicate detection MUST route
    through this function so the two sides of the comparison agree.

    Steps:
      1. Strip LaTeX commands like \\emph{...} (keep the braced arg).
      2. Strip LaTeX braces (including nested, e.g. {{AI}}).
      3. Unicode-normalize (NFKD) and drop combining marks so
         "résumé" == "resume".
      4. Replace punctuation with spaces (not empty) so
         "Learning—Pt.1" != "learningpt1" -- it becomes
         "learning pt 1", which still matches "Learning Pt 1".
      5. Lowercase, collapse whitespace.
    """
    # Strip LaTeX commands like \emph{foo} -> foo, \textbf{bar} -> bar
    title = re.sub(r"\\[a-zA-Z]+\s*\{([^{}]*)\}", r"\1", title)
    # Strip remaining LaTeX braces (multiple passes handle nesting)
    for _ in range(4):
        new = re.sub(r"\{([^{}]*)\}", r"\1", title)
        if new == title:
            break
        title = new
    # Drop accents: NFKD decomposes "é" -> "e" + combining mark; filter marks
    title = unicodedata.normalize("NFKD", title)
    title = "".join(c for c in title if not unicodedata.combining(c))
    # Punctuation -> space (preserves word boundaries)
    title = re.sub(r"[^a-zA-Z0-9]+", " ", title)
    return re.sub(r"\s+", " ", title).strip().lower()


def load_all_titles(bib_paths: list) -> set:
    """
    Return a set of normalized titles from all entries in the given bib files.
    Used to detect duplicates regardless of whether DOI or PMID match.

    Uses the same brace-balanced extractor as the manual-fingerprint path
    so that e.g. ``{{AI}-driven learning}`` normalizes identically here and
    there.
    """
    titles = set()
    for path in bib_paths:
        p = Path(path)
        if not p.exists():
            continue
        text = p.read_text(encoding="utf-8")
        for entry in re.split(r"\n(?=@)", text):
            raw = _extract_braced_field(entry, "title")
            if raw:
                t = normalize_title(raw)
                if t:
                    titles.add(t)
    return titles


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
    pmid_match = re.search(r"PMID:\s*(\d+)",
                           entry.get("note", ""), re.IGNORECASE)
    if pmid_match and pmid_match.group(1) in fp["pmids"]:
        return True
    title = normalize_title(entry.get("title", ""))
    if title and title in fp["titles"]:
        return True
    return False


# ---------------------------------------------------------------------------
# INTERACTIVE REVIEW
# ---------------------------------------------------------------------------

def load_rejected(path: Path) -> dict:
    """
    Load persistent rejection list {key: title} from a JSON file.

    If the file exists but is unparseable, move it aside to
    ``<name>.corrupt.<timestamp>`` and loudly warn on stderr rather than
    silently returning {}. Silent failure here means every prior
    rejection reappears on the next fetch run, which is exactly the
    failure mode that produced this function in the first place.
    """
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError, UnicodeDecodeError) as exc:
        from datetime import datetime
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        bak   = path.with_suffix(path.suffix + f".corrupt.{stamp}")
        try:
            path.rename(bak)
        except OSError:
            bak = None
        print(
            f"\n  [error] Rejection list {path} is unreadable: {exc}",
            file=sys.stderr,
        )
        if bak:
            print(
                f"          Moved to {bak}; starting with an empty list.\n"
                f"          Restore manually if the old list is recoverable.",
                file=sys.stderr,
            )
        else:
            print(
                "          Could not move it aside; starting empty.",
                file=sys.stderr,
            )
        return {}
    if not isinstance(data, dict):
        print(
            f"\n  [error] Rejection list {path} is not a JSON object "
            f"(got {type(data).__name__}); ignoring.",
            file=sys.stderr,
        )
        return {}
    return data


def save_rejected(path: Path, rejected: dict) -> None:
    """Save rejection list to JSON atomically."""
    write_atomic(
        path,
        json.dumps(rejected, indent=2, ensure_ascii=False),
    )


def display_entry(bibtex: str, index: int, total: int, source: str) -> None:
    """Print a BibTeX entry with a header line for review."""
    W = 72
    print()
    print("-" * W)
    print(f"  Entry {index} of {total}  [{source}]")
    print("-" * W)
    for line in bibtex.splitlines():
        print("  " + line)
    print()


def edit_in_editor(bibtex: str) -> str:
    """Open bibtex in $EDITOR (fallback: nano) and return the edited result."""
    editor = os.environ.get("EDITOR") or os.environ.get("VISUAL") or "nano"
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".bib", delete=False, encoding="utf-8"
    ) as f:
        f.write(bibtex)
        tmp = Path(f.name)
    try:
        subprocess.run([editor, str(tmp)], check=True)
        return tmp.read_text(encoding="utf-8").strip()
    except Exception as exc:
        print(f"  [warn] Editor failed ({exc}); keeping original.")
        return bibtex
    finally:
        tmp.unlink(missing_ok=True)


def prompt_action(has_doi: bool, allow_unreject: bool = False) -> str:
    """
    Prompt for a review action. Returns one of:
      accept  edit  keyword  manual  reject  unreject  skip  open  quit
    unreject is only offered when allow_unreject=True (--review-rejected mode).
    """
    line = "  [a]ccept  [e]dit  [k]eywords  [m]anual  [r]eject+remember  [s]kip"
    if allow_unreject:
        line += "  [u]nreject"
    if has_doi:
        line += "  [o]pen DOI"
    line += " : "

    while True:
        try:
            ch = input(line).strip().lower()
        except (EOFError, KeyboardInterrupt):
            print("\n  Interrupted.")
            return "quit"

        if ch in ("a", "accept"):              return "accept"
        if ch in ("e", "edit"):                return "edit"
        if ch in ("k", "keywords", "keyword"):  return "keyword"
        if ch in ("m", "manual"):              return "manual"
        if ch in ("r", "reject"):              return "reject"
        if ch in ("u", "unreject") and allow_unreject: return "unreject"
        if ch in ("s", "skip"):                return "skip"
        if ch in ("o", "open") and has_doi:    return "open"
        valid = "a/e/k/m/r/s" + ("/u" if allow_unreject else "") + ("/o" if has_doi else "")
        print(f"  Please enter one of: {valid}")



def prompt_keywords(current: str = "") -> str:
    """
    Prompt for comma-separated keyword tags interactively.
    "manual" is always preserved when present. Returns the full keywords string.
    Leave blank to keep current tags. Enter "-" to clear all non-manual tags.
    Whatever you type REPLACES the current tags (manual is always kept).
    """
    existing = [k.strip() for k in current.split(",") if k.strip()]
    existing_display = ", ".join(existing) if existing else "(none)"
    print(f"  Current keywords: {existing_display}")
    print("  New tags (comma-separated) REPLACE current. Leave blank to keep. Enter - to clear.")
    try:
        raw = input("  Tags: ").strip()
    except (EOFError, KeyboardInterrupt):
        return current

    has_manual = "manual" in {k.lower() for k in existing}

    if raw == "-":
        return "manual" if has_manual else ""
    if not raw:
        return current

    new_tags = [t.strip() for t in raw.split(",") if t.strip()]
    if has_manual and "manual" not in {t.lower() for t in new_tags}:
        new_tags.append("manual")
    return ", ".join(sorted(new_tags))


def inject_keywords(bibtex: str, keywords: str) -> str:
    """Replace the keywords field value in a BibTeX entry string."""
    if re.search(r"keywords\s*=\s*\{[^}]*\}", bibtex, re.IGNORECASE):
        return re.sub(
            r"keywords\s*=\s*\{[^}]*\}",
            f"keywords = {{{keywords}}}",
            bibtex,
            flags=re.IGNORECASE,
        )
    # No keywords field present — insert before closing brace
    return bibtex.rstrip().rstrip("}") + f"  keywords = {{{keywords}}},\n}}"



def review_rejected(rejected_file: Path) -> tuple:
    """
    Load the rejection list for a source and interactively review each entry.
    Entries can be un-rejected (removed from the list) or kept.

    Returns (unrejected_keys, updated_rejected_dict).
    Callers should save the updated dict and optionally re-fetch un-rejected entries.
    """
    rejected = load_rejected(rejected_file)
    if not rejected:
        print(f"  No rejected entries in {rejected_file}.")
        return [], {}

    print(f"  Reviewing {len(rejected)} rejected entry/entries from {rejected_file}")
    print("  For each entry: [k]eep rejected  [u]nreject (remove from list)  [q]uit")

    unrejected  = []
    updated     = dict(rejected)
    items       = list(rejected.items())
    total       = len(items)

    for i, (key, title) in enumerate(items, 1):
        print()
        print(f"  [{i}/{total}]  key: {key}")
        print(f"         title: {title[:100]}")
        while True:
            try:
                ch = input("  [k]eep  [u]nreject  [q]uit : ").strip().lower()
            except (EOFError, KeyboardInterrupt):
                print("\n  Interrupted.")
                return unrejected, updated
            if ch in ("k", "keep", ""):
                print("  -> Kept rejected.")
                break
            if ch in ("u", "unreject"):
                del updated[key]
                unrejected.append(key)
                print("  -> Un-rejected.")
                break
            if ch in ("q", "quit"):
                print(f"  Stopped. {len(unrejected)} un-rejected so far.")
                return unrejected, updated
            print("  Please enter k, u, or q.")

    print()
    return unrejected, updated

def interactive_review(
    candidates: list,        # list of (bibtex_str, doi_or_empty, reject_key, source_label)
    rejected_file: Path,     # path to .json rejection list for this source
    allow_unreject: bool = False,  # True when called from --review-rejected
) -> tuple:
    """
    Walk through candidate BibTeX entries interactively.

    Each candidate is a tuple:
        (bibtex_str, doi, reject_key, source_label)

    where reject_key is any stable string identifying the entry for the
    rejection list (e.g. PMID, DOI, or cite key).

    Returns:
        (list_of_accepted_bibtex_strings, new_rejections_dict)

    Rejected entries are not written to disk here — the caller merges
    new_rejections into the existing list and saves it.
    """
    rejected  = load_rejected(rejected_file)
    accepted  = []
    to_reject = {}
    total     = len(candidates)

    for i, (bibtex, doi, reject_key, source) in enumerate(candidates, 1):
        # Skip anything already in the rejection list
        if reject_key in rejected:
            print(f"  [skip] Previously rejected: {reject_key}")
            continue

        has_doi = bool(doi)

        # Inner loop: open/edit re-display without advancing
        while True:
            display_entry(bibtex, i, total, source)
            action = prompt_action(has_doi, allow_unreject=allow_unreject)

            if action == "open":
                url = f"https://doi.org/{doi}"
                print(f"  Opening {url} ...")
                webbrowser.open(url)
                continue

            if action == "edit":
                bibtex = edit_in_editor(bibtex)
                continue

            if action == "keyword":
                kw_m    = re.search(r"keywords\s*=\s*\{([^}]*)\}", bibtex, re.IGNORECASE)
                current = kw_m.group(1) if kw_m else ""
                new_kw  = prompt_keywords(current)
                bibtex  = inject_keywords(bibtex, new_kw)
                continue

            break

        if action == "accept":
            accepted.append(bibtex)   # plain str
            print("  -> Accepted.")

        elif action == "manual":
            # Ensure "manual" is in keywords; preserve any tags already set via [k]
            kw_m    = re.search(r"keywords\s*=\s*\{([^}]*)\}", bibtex, re.IGNORECASE)
            current = kw_m.group(1) if kw_m else ""
            tags    = {"manual"} | {t.strip() for t in current.split(",") if t.strip()}
            bibtex  = inject_keywords(bibtex, ", ".join(sorted(tags)))
            accepted.append(bibtex)
            print("  -> Accepted as manual.")

        elif action == "reject":
            # Extract a short title for the rejection record if possible
            title_m = re.search(r"title\s*=\s*\{([^}]+)\}", bibtex, re.IGNORECASE)
            label   = title_m.group(1)[:120] if title_m else reject_key
            try:
                note = input("  Rejection note (optional, Enter to skip): ").strip()
            except (EOFError, KeyboardInterrupt):
                note = ""
            if note:
                label = f"{label} | {note}"
            to_reject[reject_key] = label
            print("  -> Rejected and remembered.")

        elif action == "skip":
            print("  -> Skipped (will appear again next run).")

        elif action == "unreject":
            # Will be removed from rejection list by caller
            accepted.append(("__unreject__", reject_key))
            print("  -> Un-rejected (removed from rejection list).")

        elif action == "quit":
            print(f"  Stopped at entry {i}. {len(accepted)} accepted so far.")
            break

    print()
    return accepted, to_reject