#!/usr/bin/env python3
"""
add_ref.py
==========
Interactively add a new reference directly to any .bib file in refs/.

Three input modes:

  doi    -- fetch metadata from Crossref by DOI, open in editor to review
  pmid   -- fetch metadata from PubMed by PMID, open in editor to review
  manual -- open a blank BibTeX template in $EDITOR

After editing, keyword tags are assigned interactively. The entry is
always written with at least keywords = {manual} so it is protected
from deduplication by update_refs.py.

Usage:
    python scripts/add_ref.py
    python scripts/add_ref.py --bib refs/conference.bib
    python scripts/add_ref.py --doi 10.1038/s41562-021-01234-5
    python scripts/add_ref.py --pmid 34127854
    python scripts/add_ref.py --manual

Requirements: pip install requests
"""

import argparse
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).parent))
from _shared import (  # noqa: E402
    edit_in_editor, prompt_keywords, inject_keywords, append_atomic,
)

# ---------------------------------------------------------------------------
# CONFIG
# ---------------------------------------------------------------------------
CROSSREF_URL = "https://api.crossref.org/works"
EFETCH_URL   = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
TOOL_NAME    = "cv_updater"
ADMIN_EMAIL  = "shabnamhakimi@gmail.com"

BIB_CHOICES = {
    "1": ("refs/journals.bib",      "journals",       "article"),
    "2": ("refs/preprints.bib",     "preprints",      "article"),
    "3": ("refs/conference.bib",    "conference",     "inproceedings"),
    "4": ("refs/presentations.bib", "presentations",  "unpublished"),
    "5": ("refs/scicomm.bib",       "scicomm",        None),
    "6": ("refs/patents.bib",       "patents",        "patent"),
    "7": ("refs/chapters.bib",      "chapters",       None),
}
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# DOI LOOKUP (Crossref)
# ---------------------------------------------------------------------------

def fetch_by_doi(doi: str) -> str:
    """Fetch metadata from Crossref and return a BibTeX string."""
    url = f"{CROSSREF_URL}/{doi.strip()}"
    try:
        r = requests.get(url, headers={"User-Agent": f"{TOOL_NAME} ({ADMIN_EMAIL})"},
                         timeout=15)
        r.raise_for_status()
    except Exception as e:
        print(f"  [error] Crossref lookup failed: {e}")
        return _doi_template(doi)

    w = r.json().get("message", {})

    title   = " ".join(w.get("title", ["Unknown Title"]))
    year    = str(w.get("published", {}).get("date-parts", [[None]])[0][0] or "????")
    journal = (w.get("container-title") or [""])[0]
    volume  = w.get("volume", "")
    issue   = w.get("issue", "")
    pages   = w.get("page", "")

    authors = []
    for a in w.get("author", []):
        last  = a.get("family", "")
        first = a.get("given", "")
        if last:
            authors.append(f"{last}, {first}")
    author_str = " and ".join(authors)

    entry_type = "article"
    if w.get("type") in ("proceedings-article", "paper-conference"):
        entry_type = "inproceedings"

    first_author = authors[0].split(",")[0] if authors else "Unknown"
    first_word   = re.sub(r"[^a-zA-Z]", "", title.split()[0]) if title else "x"
    cite_key     = f"{first_author}{year}{first_word}"

    lines = [f"@{entry_type}{{{cite_key},"]
    if author_str: lines.append(f"  author   = {{{author_str}}},")
    lines.append(f"  title    = {{{title}}},")
    if journal:    lines.append(f"  journal  = {{{journal}}},")
    lines.append(f"  year     = {{{year}}},")
    if volume:     lines.append(f"  volume   = {{{volume}}},")
    if issue:      lines.append(f"  number   = {{{issue}}},")
    if pages:      lines.append(f"  pages    = {{{pages}}},")
    lines.append(f"  doi      = {{{doi.strip()}}},")
    lines.append(f"  keywords = {{}},")
    lines.append("}")
    return "\n".join(lines)


def _doi_template(doi: str) -> str:
    """Fallback blank template pre-filled with the DOI."""
    return (
        "@article{CiteKey,\n"
        "  author   = {},\n"
        "  title    = {},\n"
        "  journal  = {},\n"
        "  year     = {????},\n"
        f"  doi      = {{{doi.strip()}}},\n"
        "  keywords = {},\n"
        "}"
    )


# ---------------------------------------------------------------------------
# PMID LOOKUP (PubMed)
# ---------------------------------------------------------------------------

def fetch_by_pmid(pmid: str) -> str:
    """Fetch metadata from PubMed efetch and return a BibTeX string."""
    params = dict(db="pubmed", id=pmid.strip(), retmode="xml",
                  rettype="abstract", tool=TOOL_NAME, email=ADMIN_EMAIL)
    try:
        r = requests.get(EFETCH_URL, params=params, timeout=15)
        r.raise_for_status()
        root    = ET.fromstring(r.text)
        article = root.find(".//PubmedArticle")
        if article is None:
            raise ValueError("No PubmedArticle found")
    except Exception as e:
        print(f"  [error] PubMed lookup failed: {e}")
        return _pmid_template(pmid)

    def txt(path):
        node = article.find(path)
        return node.text.strip() if node is not None and node.text else ""

    title   = txt(".//ArticleTitle")
    journal = txt(".//Journal/Title")
    year    = txt(".//PubDate/Year") or txt(".//PubDate/MedlineDate")[:4]
    volume  = txt(".//Volume")
    issue   = txt(".//Issue")
    pages   = txt(".//MedlinePgn")

    doi = ""
    for eid in article.findall(".//ArticleId"):
        if eid.get("IdType") == "doi":
            doi = eid.text.strip() if eid.text else ""

    authors = []
    for a in article.findall(".//Author"):
        last  = a.findtext("LastName") or ""
        first = a.findtext("ForeName") or a.findtext("Initials") or ""
        if last:
            authors.append(f"{last}, {first}")
    author_str = " and ".join(authors)

    first_author = authors[0].split(",")[0] if authors else "Unknown"
    first_word   = re.sub(r"[^a-zA-Z]", "", title.split()[0]) if title else "x"
    cite_key     = f"{first_author}{year}{first_word}"

    lines = [f"@article{{{cite_key},"]
    if author_str: lines.append(f"  author   = {{{author_str}}},")
    lines.append(f"  title    = {{{title}}},")
    if journal:    lines.append(f"  journal  = {{{journal}}},")
    lines.append(f"  year     = {{{year}}},")
    if volume:     lines.append(f"  volume   = {{{volume}}},")
    if issue:      lines.append(f"  number   = {{{issue}}},")
    if pages:      lines.append(f"  pages    = {{{pages}}},")
    if doi:        lines.append(f"  doi      = {{{doi}}},")
    lines.append(f"  note     = {{PMID: {pmid.strip()}}},")
    lines.append(f"  keywords = {{}},")
    lines.append("}")
    return "\n".join(lines)


def _pmid_template(pmid: str) -> str:
    return (
        "@article{CiteKey,\n"
        "  author   = {},\n"
        "  title    = {},\n"
        "  journal  = {},\n"
        "  year     = {????},\n"
        f"  note     = {{PMID: {pmid.strip()}}},\n"
        "  keywords = {},\n"
        "}"
    )


# ---------------------------------------------------------------------------
# BLANK TEMPLATE
# ---------------------------------------------------------------------------

BLANK_TEMPLATES = {
    "article": (
        "@article{CiteKey,\n"
        "  author   = {},\n"
        "  title    = {},\n"
        "  journal  = {},\n"
        "  year     = {????},\n"
        "  volume   = {},\n"
        "  number   = {},\n"
        "  pages    = {},\n"
        "  doi      = {},\n"
        "  keywords = {},\n"
        "}"
    ),
    "inproceedings": (
        "@inproceedings{CiteKey,\n"
        "  author    = {},\n"
        "  title     = {},\n"
        "  booktitle = {},\n"
        "  year      = {????},\n"
        "  pages     = {},\n"
        "  doi       = {},\n"
        "  keywords  = {},\n"
        "}"
    ),
    "unpublished": (
        "@unpublished{CiteKey,\n"
        "  author   = {},\n"
        "  title    = {},\n"
        "  note     = {},\n"
        "  year     = {????},\n"
        "  month    = ,\n"
        "  type     = {Talk},\n"
        "  keywords = {presentation},\n"
        "}"
    ),
    "patent": (
        "@patent{CiteKey,\n"
        "  author      = {},\n"
        "  title       = {},\n"
        "  number      = {},\n"
        "  year        = {????},\n"
        "  month       = ,\n"
        "  assignee    = {Toyota Research Institute},\n"
        "  keywords    = {},\n"
        "}"
    ),
    "incollection": (
        "@incollection{CiteKey,\n"
        "  author    = {},\n"
        "  title     = {},\n"
        "  booktitle = {},\n"
        "  editor    = {},\n"
        "  publisher = {},\n"
        "  year      = {????},\n"
        "  pages     = {},\n"
        "  doi       = {},\n"
        "  keywords  = {bookchapter},\n"
        "}"
    ),
    "misc": (
        "@misc{CiteKey,\n"
        "  author   = {},\n"
        "  title    = {},\n"
        "  year     = {????},\n"
        "  howpublished = {},\n"
        "  note     = {},\n"
        "  keywords = {},\n"
        "}"
    ),
}

TEMPLATE_MENU = {
    "1": ("article",        "journal article"),
    "2": ("inproceedings",  "conference paper"),
    "3": ("unpublished",    "presentation / talk"),
    "4": ("incollection",   "book chapter"),
    "5": ("patent",         "patent"),
    "6": ("misc",           "other / preprint / scicomm"),
}


def choose_template(entry_type: str = None) -> str:
    """Return a blank BibTeX template. If entry_type is given, use it directly."""
    if entry_type and entry_type in BLANK_TEMPLATES:
        return BLANK_TEMPLATES[entry_type]
    print()
    print("  Entry type:")
    for k, (_, label) in TEMPLATE_MENU.items():
        print(f"    {k}  {label}")
    while True:
        try:
            ch = input(f"  Choose [1-{len(TEMPLATE_MENU)}]: ").strip()
        except (EOFError, KeyboardInterrupt):
            sys.exit(0)
        if ch in TEMPLATE_MENU:
            etype, _ = TEMPLATE_MENU[ch]
            return BLANK_TEMPLATES[etype]
        print(f"  Please enter 1-{len(TEMPLATE_MENU)}.")


# ---------------------------------------------------------------------------
# TARGET BIB FILE SELECTION
# ---------------------------------------------------------------------------

def choose_bib_file(default: str = None) -> tuple:
    """Prompt for target .bib file. Returns (Path, entry_type_or_None)."""
    if default:
        p = Path(default)
        if not p.parent.exists():
            p.parent.mkdir(parents=True, exist_ok=True)
        # Try to infer entry type from the known choices
        for path, _, entry_type in BIB_CHOICES.values():
            if Path(path) == p:
                return p, entry_type
        return p, None

    print()
    print("  Target .bib file:")
    for k, (path, label, _) in BIB_CHOICES.items():
        print(f"    {k}  {label:20s}  ({path})")
    while True:
        try:
            ch = input(f"  Choose [1-{len(BIB_CHOICES)}]: ").strip()
        except (EOFError, KeyboardInterrupt):
            sys.exit(0)
        if ch in BIB_CHOICES:
            path, _, entry_type = BIB_CHOICES[ch]
            return Path(path), entry_type
        print(f"  Please enter 1-{len(BIB_CHOICES)}.")


# ---------------------------------------------------------------------------
# VALIDATION
# ---------------------------------------------------------------------------

def looks_valid(bibtex: str) -> bool:
    """Basic sanity check: has an entry type, cite key, and title."""
    return bool(
        re.search(r"@\w+\{\S+,", bibtex)
        and re.search(r"title\s*=\s*\{[^}]+\}", bibtex, re.IGNORECASE)
    )


def coerce_entry_type(bibtex: str, entry_type: str) -> str:
    """Replace the @entrytype in a BibTeX string with the given type."""
    return re.sub(r"^@\w+", f"@{entry_type}", bibtex, count=1)


# ---------------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Interactively add a reference to a .bib file",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  python scripts/add_ref.py\n"
            "  python scripts/add_ref.py --doi 10.1038/s41562-021-01234-5\n"
            "  python scripts/add_ref.py --pmid 34127854\n"
            "  python scripts/add_ref.py --manual --bib refs/conference.bib\n"
        ),
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--doi",    metavar="DOI",  help="Fetch metadata by DOI")
    mode.add_argument("--pmid",   metavar="PMID", help="Fetch metadata by PubMed ID")
    mode.add_argument("--manual", action="store_true",
                      help="Open a blank template in $EDITOR")
    parser.add_argument("--bib",  metavar="PATH",
                        help="Target .bib file (default: prompt)")
    parser.add_argument("--dry-run", "-n", action="store_true",
                        help="Preview without writing to disk")
    args = parser.parse_args()

    print()
    print("=" * 60)
    print("  add_ref.py -- Add a reference to your CV bibliography")
    print("=" * 60)

    # -- Choose input mode if not specified via flags -------------------------
    if not any([args.doi, args.pmid, args.manual]):
        print()
        print("  Input mode:")
        print("    1  DOI lookup   (fetch from Crossref)")
        print("    2  PMID lookup  (fetch from PubMed)")
        print("    3  Manual entry (blank template in editor)")
        while True:
            try:
                ch = input("  Choose [1-3]: ").strip()
            except (EOFError, KeyboardInterrupt):
                sys.exit(0)
            if ch == "1":
                try:
                    args.doi = input("  DOI: ").strip()
                except (EOFError, KeyboardInterrupt):
                    sys.exit(0)
                break
            elif ch == "2":
                try:
                    args.pmid = input("  PMID: ").strip()
                except (EOFError, KeyboardInterrupt):
                    sys.exit(0)
                break
            elif ch == "3":
                args.manual = True
                break
            print("  Please enter 1, 2, or 3.")

    # -- Choose target bib file -----------------------------------------------
    bib_path, entry_type = choose_bib_file(args.bib)

    # -- Fetch / build initial bibtex ----------------------------------------
    if args.doi:
        print(f"\n  Looking up DOI: {args.doi} ...")
        bibtex = fetch_by_doi(args.doi)
        if entry_type:
            bibtex = coerce_entry_type(bibtex, entry_type)
        print("  Metadata fetched. Opening in editor...")
    elif args.pmid:
        print(f"\n  Looking up PMID: {args.pmid} ...")
        bibtex = fetch_by_pmid(args.pmid)
        if entry_type:
            bibtex = coerce_entry_type(bibtex, entry_type)
        print("  Metadata fetched. Opening in editor...")
    else:
        bibtex = choose_template(entry_type)
        print("\n  Opening blank template in editor...")

    # -- Edit in $EDITOR ------------------------------------------------------
    bibtex = edit_in_editor(bibtex)

    if not bibtex.strip():
        print("  Empty entry -- nothing to add.")
        return

    if not looks_valid(bibtex):
        print("  [warn] Entry looks incomplete (missing type, cite key, or title).")
        try:
            ch = input("  Add anyway? [y/N]: ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            ch = "n"
        if ch != "y":
            print("  Aborted.")
            return

    # -- Keyword tagging ------------------------------------------------------
    print()
    print("  Keyword tagging")
    print("  ---------------")
    kw_m    = re.search(r"keywords\s*=\s*\{([^}]*)\}", bibtex, re.IGNORECASE)
    current = kw_m.group(1) if kw_m else ""
    kw      = prompt_keywords(current)

    # Ensure manual is always set
    tags = {"manual"} | {t.strip() for t in kw.split(",") if t.strip()}
    kw   = ", ".join(sorted(tags))
    bibtex = inject_keywords(bibtex, kw)

    # -- Preview and confirm --------------------------------------------------
    print()
    print("  Final entry:")
    print("  " + "-" * 60)
    for line in bibtex.splitlines():
        print("  " + line)
    print("  " + "-" * 60)
    print(f"  Target: {bib_path}")
    print()

    if args.dry_run:
        print("  [dry-run] Would append the above entry.")
        return

    try:
        ch = input("  Write to file? [Y/n]: ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        ch = "n"
    if ch in ("", "y", "yes"):
        append_atomic(bib_path, f"\n\n% --- manually added ---\n{bibtex}\n")
        print(f"  Written to {bib_path}")
    else:
        print("  Aborted.")


if __name__ == "__main__":
    main()