#!/usr/bin/env python3
"""
validate_bib.py — static linter for the CV's BibTeX corpus.

Catches latent issues that would otherwise only surface at build time
or, worse, produce a silently-wrong PDF. The chapters.bib regression
this script was written to prevent is a perfect example: the file
existed, was well-formed, and was completely ignored because
cv.tex had no \\addbibresource line for it.

Checks
------
Per file:
  • Unbalanced braces in each entry
  • Per-type required fields (see REQUIRED_FIELDS)
  • Missing keyword tag on entries that the preamble routes by keyword
    (e.g. presentations, commentary, bookchapter, scicomm)
  • Malformed DOI (non-"10.x/..." prefix when present)

Across files:
  • Duplicate cite keys
  • Duplicate DOIs (excluding within-file which is a separate dedup concern)

Against cv.tex:
  • Every refs/*.bib on disk is loaded via \\addbibresource
  • Every \\addbibresource target exists on disk

Exit status:
  0   no errors (warnings may be present)
  1   at least one error found

Run:
    python3 scripts/validate_bib.py                 # all refs
    python3 scripts/validate_bib.py --no-cvtex      # skip cv.tex cross-ref
    make validate
"""

import argparse
import re
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _shared import _extract_braced_field, normalize_doi, normalize_title  # noqa: E402


# ---------------------------------------------------------------------------
# CONFIG
# ---------------------------------------------------------------------------

REFS_DIR = Path("refs")
CV_TEX   = Path("cv.tex")

# Required fields per entry type. These reflect the actual shape of this
# corpus, not BibTeX orthodoxy -- e.g. @unpublished presentation entries
# don't need a journal.
REQUIRED_FIELDS = {
    "article":       ["author", "title", "year", "journal"],
    "inproceedings": ["author", "title", "year", "booktitle"],
    "incollection":  ["author", "title", "year", "booktitle", "publisher"],
    "unpublished":   ["author", "title", "year"],
    "patent":        ["author", "title", "year", "number"],
    "misc":          ["author", "title", "year"],
}

# Which keyword tags carry semantics in cv.tex (or a downstream tool). An
# entry with no keywords field at all is fine; one with ``keywords = {}`` or
# a tag nothing recognizes is a warning.
KNOWN_KEYWORDS = {
    "selected", "manual", "presentation", "commentary",
    "bookchapter", "scicomm",
    # cv.tex source-mapping: drops the entry before biblatex sees it
    # (kept in the corpus, never compiled into any CV -- e.g. PhD thesis).
    "unlisted",
    # Personal tracking tags read by an external corpus tool, not by
    # cv.tex itself.
    "draft", "unpaywall-closed",
}

# Entry types that MUST carry at least one known keyword to render.
# These are routed in cv.tex via keyword= filters, so an untagged entry
# silently vanishes from the PDF.
KEYWORD_REQUIRED_TYPES = {
    # @unpublished is split into preprints (no keyword) vs. presentations
    # (keyword=presentation). We can't require a keyword on every
    # @unpublished, so this rule only applies to presentations via file.
}

# Files where every entry must carry a given keyword to render.
KEYWORD_REQUIRED_BY_FILE = {
    "presentations.bib": "presentation",
    "scicomm.bib":       "scicomm",
}


# ---------------------------------------------------------------------------
# RESULT COLLECTION
# ---------------------------------------------------------------------------

class Report:
    """Collects errors and warnings, prints a grouped summary."""

    def __init__(self):
        self.errors   = []
        self.warnings = []

    def error(self, where: str, msg: str) -> None:
        self.errors.append((where, msg))

    def warn(self, where: str, msg: str) -> None:
        self.warnings.append((where, msg))

    def print(self) -> int:
        for where, msg in self.errors:
            print(f"ERROR   {where}: {msg}")
        for where, msg in self.warnings:
            print(f"WARN    {where}: {msg}")
        n_err, n_warn = len(self.errors), len(self.warnings)
        print()
        if n_err == 0 and n_warn == 0:
            print("OK: all bibliographies validate.")
            return 0
        print(f"Summary: {n_err} error(s), {n_warn} warning(s)")
        return 0 if n_err == 0 else 1


# ---------------------------------------------------------------------------
# PARSING
# ---------------------------------------------------------------------------

ENTRY_RE = re.compile(r"@(\w+)\s*\{\s*([^,\s]+)\s*,", re.IGNORECASE)


def split_entries(text: str) -> list[str]:
    """Split a .bib file into raw entry strings starting with '@'."""
    chunks = re.split(r"\n(?=@)", text)
    return [c for c in chunks if ENTRY_RE.match(c.lstrip())]


def brace_balance(text: str) -> int:
    """Net brace count ignoring those preceded by a backslash (LaTeX escape)."""
    depth = 0
    prev  = ""
    for c in text:
        if prev != "\\":
            if c == "{":
                depth += 1
            elif c == "}":
                depth -= 1
        prev = c
    return depth


# ---------------------------------------------------------------------------
# CHECKS
# ---------------------------------------------------------------------------

def check_entry(entry: str, file_name: str, report: Report) -> dict:
    """Run per-entry checks. Returns metadata for cross-file checks."""
    m = ENTRY_RE.match(entry.lstrip())
    if not m:
        report.error(f"{file_name}", f"entry does not start with @type{{key,: "
                                     f"{entry[:60]!r}")
        return {}

    entry_type = m.group(1).lower()
    cite_key   = m.group(2)
    where      = f"{file_name}:{cite_key}"

    # 1. Brace balance
    bal = brace_balance(entry)
    if bal != 0:
        report.error(where, f"unbalanced braces (net {bal:+d})")

    # 2. Required fields per entry type
    required = REQUIRED_FIELDS.get(entry_type, [])
    for field in required:
        raw = _extract_braced_field(entry, field)
        if not raw.strip():
            report.error(where, f"missing required field '{field}' "
                                f"for @{entry_type}")

    # 3. DOI format sanity
    doi_raw = _extract_braced_field(entry, "doi").strip()
    doi = normalize_doi(doi_raw)
    if doi_raw and not doi:
        report.warn(where, f"DOI does not look like a valid '10.x/...' "
                           f"string: {doi_raw!r}")
    elif doi_raw and not re.match(r"^10\.\d{3,}/", doi):
        report.warn(where, f"DOI does not look like a valid '10.x/...' "
                           f"string: {doi_raw!r}")

    # 4. Keyword tagging
    kw_raw = _extract_braced_field(entry, "keywords").strip()
    kw_set = {k.strip().lower() for k in kw_raw.split(",") if k.strip()}
    required_kw = KEYWORD_REQUIRED_BY_FILE.get(file_name)
    if required_kw and required_kw not in kw_set:
        report.error(where,
                     f"entries in {file_name} must include "
                     f"keywords={{{required_kw}}} to render in the CV "
                     f"(got: {sorted(kw_set) or '(none)'})")

    if kw_set:
        unknown = kw_set - KNOWN_KEYWORDS
        if unknown:
            report.warn(where,
                        f"unknown keyword tag(s): {sorted(unknown)} "
                        f"(known: {sorted(KNOWN_KEYWORDS)})")

    # 5. Extract title for cross-file dedup
    title_raw = _extract_braced_field(entry, "title").strip()
    title = normalize_title(title_raw) if title_raw else None

    return {
        "cite_key":   cite_key,
        "entry_type": entry_type,
        "doi":        doi or None,
        "title":      title,
        "file":       file_name,
    }


def check_file(path: Path, report: Report) -> list[dict]:
    """Validate a single .bib file. Returns per-entry metadata."""
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        report.error(path.name, f"cannot read: {exc}")
        return []

    entries = split_entries(text)
    results = []
    for entry in entries:
        meta = check_entry(entry, path.name, report)
        if meta:
            results.append(meta)
    return results


def check_cross_file(all_meta: list[dict], report: Report) -> None:
    """Duplicate cite keys, DOIs, and titles across files."""
    by_key   = defaultdict(list)
    by_doi   = defaultdict(list)
    by_title = defaultdict(list)
    for m in all_meta:
        by_key[m["cite_key"].lower()].append(m["file"])
        if m["doi"]:
            by_doi[m["doi"]].append((m["file"], m["cite_key"]))
        if m["title"]:
            by_title[m["title"]].append((m["file"], m["cite_key"]))

    for key, files in by_key.items():
        if len(files) > 1:
            report.error("duplicate-key",
                         f"cite key '{key}' appears in: {', '.join(files)}")

    for doi, hits in by_doi.items():
        if len(hits) > 1:
            locs = ", ".join(f"{f}:{k}" for f, k in hits)
            report.error("duplicate-doi",
                         f"DOI '{doi}' appears in: {locs}")

    for title, hits in by_title.items():
        if len(hits) > 1:
            locs = ", ".join(f"{f}:{k}" for f, k in hits)
            report.warn("duplicate-title",
                        f"title '{title[:60]}' appears in: {locs}")


def check_cvtex_coverage(report: Report) -> None:
    """Every refs/*.bib on disk is loaded by cv.tex, and vice versa."""
    if not CV_TEX.exists():
        report.warn("cv.tex", f"{CV_TEX} not found; skipping cross-ref check")
        return

    cvtex    = CV_TEX.read_text(encoding="utf-8")
    resource = re.compile(r"\\addbibresource\{([^}]+)\}")
    declared = {Path(m.group(1)).resolve() for m in resource.finditer(cvtex)}

    on_disk = {p.resolve() for p in REFS_DIR.glob("*.bib")
               if ".bak" not in p.name}

    missing_from_cvtex = on_disk - declared
    missing_from_disk  = declared - on_disk

    for p in sorted(missing_from_cvtex, key=str):
        report.error("cv.tex",
                     f"{p.relative_to(Path.cwd())} exists on disk but is "
                     f"NOT loaded via \\addbibresource -- its entries will "
                     f"never render")

    for p in sorted(missing_from_disk, key=str):
        try:
            rel = p.relative_to(Path.cwd())
        except ValueError:
            rel = p
        report.error("cv.tex",
                     f"\\addbibresource{{{rel}}} in cv.tex points to a "
                     f"file that does not exist")


# ---------------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(
        description="Static linter for refs/*.bib",
    )
    parser.add_argument(
        "--no-cvtex", action="store_true",
        help="Skip cross-reference check against cv.tex \\addbibresource list",
    )
    parser.add_argument(
        "files", nargs="*", type=Path,
        help="Specific .bib files to check (default: all refs/*.bib)",
    )
    args = parser.parse_args()

    if args.files:
        bib_files = args.files
    else:
        bib_files = sorted(
            p for p in REFS_DIR.glob("*.bib") if ".bak" not in p.name
        )

    if not bib_files:
        print(f"No .bib files found in {REFS_DIR}/", file=sys.stderr)
        return 1

    report = Report()
    all_meta: list[dict] = []

    for path in bib_files:
        print(f"Checking {path}...")
        all_meta.extend(check_file(path, report))

    check_cross_file(all_meta, report)
    if not args.no_cvtex:
        check_cvtex_coverage(report)

    print()
    print(f"Scanned {len(bib_files)} file(s), {len(all_meta)} entry/entries.")
    return report.print()


if __name__ == "__main__":
    sys.exit(main())
