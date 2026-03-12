#!/usr/bin/env python3
"""
_shared.py
==========
Shared utilities for fetch_orcid.py, fetch_pubmed.py, fetch_scholar.py.

Provides:
  - load_manual_fingerprints(bib_path)
  - fingerprint_matches(entry, fp)

These functions live here (not in update_refs.py) so each fetch script
can import them when run standalone as well as when invoked as a subprocess
by update_refs.py.
"""

import re
from pathlib import Path


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
    """Regex fallback for load_manual_fingerprints (no bibtexparser)."""
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