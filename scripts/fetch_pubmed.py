#!/usr/bin/env python3
"""
fetch_pubmed.py
===============
Fetch publications from the PubMed E-utilities API and append new entries
to refs/journals.bib.

STRATEGY — two complementary queries are combined:

  1. ORCID query  [auid]   — exact match, works for papers published since ~2012
                             where the journal/author linked an ORCID.
  2. Name query   [Author] — broad match, catches older papers and any papers
                             where ORCID metadata is missing.

Results from both queries are unioned. Any PMID found *only* by the name query
(i.e. not confirmed by ORCID) is passed through a name-verification step that
checks the author list for a recognizable form of the target author's name.
Records where a Hakimi with a clearly different first name is the matching
author are rejected.

CONFIG — edit the block below to match your identity:
  ORCID_ID            — your ORCID (used for the exact query)
  PUBMED_AUTHOR       — "LastName Initial" for the name query
  AUTHOR_LAST         — last name to match (case-insensitive)
  AUTHOR_FIRSTS       — accepted first names / initials (all lowercase,
                        no punctuation). Include every form that might appear
                        in PubMed: full first name, given initial, etc.
  AUTHOR_MAX_INITIALS — max tokens in the first-name field; set to 1 since
                        Shabnam has no middle name (rejects "S A", "S M", etc.)

Requirements: pip install requests bibtexparser
"""

import argparse
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).parent))
from _shared import load_manual_fingerprints, fingerprint_matches  # noqa: E402

# ── CONFIG ────────────────────────────────────────────────────────────────────
ORCID_ID            = "0000-0003-4122-6041"   # your ORCID iD
PUBMED_AUTHOR       = "Hakimi S"              # LastName Initial for name query
AUTHOR_LAST         = "Hakimi"               # last name to match
AUTHOR_FIRSTS       = {"shabnam", "s"}        # accepted first-name forms
AUTHOR_MAX_INITIALS = 1                       # no middle name → max 1 token
BIB_OUT             = Path("refs/journals.bib")
ESEARCH_URL         = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
EFETCH_URL          = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
TOOL_NAME           = "cv_updater"
ADMIN_EMAIL         = "shabnam@tri.global"    # required by NCBI policy
# ─────────────────────────────────────────────────────────────────────────────


def esearch(term: str, retmax: int = 200) -> set[str]:
    """Run a PubMed esearch query and return the set of matching PMIDs."""
    params = dict(db="pubmed", term=term, retmax=retmax,
                  retmode="json", tool=TOOL_NAME, email=ADMIN_EMAIL)
    r = requests.get(ESEARCH_URL, params=params, timeout=15)
    r.raise_for_status()
    return set(r.json()["esearchresult"]["idlist"])


def fetch_pubmed_records(pmids: list[str]) -> ET.Element:
    params = dict(db="pubmed", id=",".join(pmids),
                  retmode="xml", rettype="abstract",
                  tool=TOOL_NAME, email=ADMIN_EMAIL)
    r = requests.get(EFETCH_URL, params=params, timeout=30)
    r.raise_for_status()
    return ET.fromstring(r.text)


def parse_article(article: ET.Element) -> dict:
    """Extract key fields from a PubmedArticle XML element."""
    def txt(el, path):
        node = el.find(path)
        return node.text.strip() if node is not None and node.text else ""

    title   = txt(article, ".//ArticleTitle")
    journal = txt(article, ".//Journal/Title")
    year    = (txt(article, ".//PubDate/Year") or
               txt(article, ".//PubDate/MedlineDate")[:4])
    volume  = txt(article, ".//Volume")
    issue   = txt(article, ".//Issue")
    pages   = txt(article, ".//MedlinePgn")
    pmid    = txt(article, ".//PMID")

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

    return dict(title=title, journal=journal, year=year, volume=volume,
                issue=issue, pages=pages, pmid=pmid, doi=doi, authors=authors)


def author_matches(rec: dict) -> bool:
    """
    Return True if the article contains an author matching AUTHOR_LAST whose
    first-name field is consistent with the target author's identity:

      - First name or initial must be in AUTHOR_FIRSTS
      - The first-name field must have no more than AUTHOR_MAX_INITIALS tokens
        (no middle name or second initial — Shabnam has none)

    Examples:
      "Hakimi, Shabnam"  → accept  (full first name matches)
      "Hakimi, S"        → accept  (single initial, could be ours)
      "Hakimi, Sophie"   → reject  (first name not in AUTHOR_FIRSTS)
      "Hakimi, S A"      → reject  (second initial — different person)
    """
    last_lower = AUTHOR_LAST.lower()
    for author in rec["authors"]:
        parts = [p.strip() for p in author.split(",", 1)]
        if len(parts) < 2:
            continue
        last, first = parts
        if last.lower() != last_lower:
            continue
        tokens = first.strip().split()
        if len(tokens) > AUTHOR_MAX_INITIALS:
            continue
        first_norm = re.sub(r"[^a-z]", "", tokens[0].lower()) if tokens else ""
        if first_norm in AUTHOR_FIRSTS:
            return True
    return False


def record_to_bibtex(rec: dict) -> str:
    first_author = rec["authors"][0].split(",")[0] if rec["authors"] else "Unknown"
    first_word   = re.sub(r"[^a-zA-Z]", "", rec["title"].split()[0]) if rec["title"] else "x"
    cite_key     = f"{first_author}{rec['year']}{first_word}"
    author_str   = " and ".join(rec["authors"])

    lines = [f"@article{{{cite_key},"]
    lines.append(f"  author   = {{{author_str}}},")
    lines.append(f"  title    = {{{rec['title']}}},")
    lines.append(f"  journal  = {{{rec['journal']}}},")
    lines.append(f"  year     = {{{rec['year']}}},")
    if rec["volume"]:  lines.append(f"  volume   = {{{rec['volume']}}},")
    if rec["issue"]:   lines.append(f"  number   = {{{rec['issue']}}},")
    if rec["pages"]:   lines.append(f"  pages    = {{{rec['pages']}}},")
    if rec["doi"]:     lines.append(f"  doi      = {{{rec['doi']}}},")
    lines.append(f"  note     = {{PMID: {rec['pmid']}}},")
    lines.append(f"  keywords = {{}},")
    lines.append("}")
    return "\n".join(lines)


def load_existing_pmids(bib_path: Path) -> set[str]:
    if not bib_path.exists():\
        return set()
    return set(re.findall(r'PMID:\s*(\d+)', bib_path.read_text()))


def main():
    parser = argparse.ArgumentParser(description="Fetch publications from PubMed")
    parser.add_argument("--dry-run", action="store_true",
                        help="Preview new entries without writing to disk")
    args = parser.parse_args()

    # ── Query 1: ORCID (exact) ────────────────────────────────────────────────
    print(f"Searching PubMed by ORCID: {ORCID_ID}")
    orcid_pmids = esearch(f"{ORCID_ID}[auid]")
    print(f"  [auid]   {len(orcid_pmids)} results")

    # ── Query 2: Author name (broad) ──────────────────────────────────────────
    print(f"Searching PubMed by name:  {PUBMED_AUTHOR}")
    name_pmids = esearch(f"{PUBMED_AUTHOR}[Author]")
    print(f"  [Author] {len(name_pmids)} results (before name verification)")

    # PMIDs confirmed by ORCID need no further verification.
    # PMIDs only from the name search will be verified after fetching.
    name_only_pmids = name_pmids - orcid_pmids
    all_pmids       = orcid_pmids | name_pmids
    print(f"  Combined {len(all_pmids)} unique PMIDs "
          f"({len(orcid_pmids)} ORCID-confirmed, "
          f"{len(name_only_pmids)} name-only pending verification)")

    # ── Filter against existing bib and manual entries ────────────────────────
    existing_pmids = load_existing_pmids(BIB_OUT)
    manual_fp      = load_manual_fingerprints(BIB_OUT)
    new_pmids      = []
    skipped_manual = 0

    for p in sorted(all_pmids):
        if p in existing_pmids:
            continue
        stub = {"ID": "", "doi": "", "note": f"PMID: {p}", "title": ""}
        if fingerprint_matches(stub, manual_fp):
            skipped_manual += 1
            continue
        new_pmids.append(p)

    if skipped_manual:
        print(f"  Skipped {skipped_manual} record(s) matching manual entries")

    if not new_pmids:
        print("  No new PubMed records.")
        return

    # ── Fetch and verify ──────────────────────────────────────────────────────
    print(f"  Fetching {len(new_pmids)} new records...")
    root     = fetch_pubmed_records(new_pmids)
    articles = root.findall(".//PubmedArticle")

    entries        = []
    rejected_names = []

    for article in articles:
        rec  = parse_article(article)
        pmid = rec["pmid"]

        # Name-only PMIDs must pass author verification
        if pmid in name_only_pmids and pmid not in orcid_pmids:
            if not author_matches(rec):
                rejected_names.append((pmid, rec["title"][:70]))
                continue

        entries.append(record_to_bibtex(rec))

    if rejected_names:
        print(f"  Rejected {len(rejected_names)} name-search result(s) "
              f"(author name mismatch):")
        for pmid, title in rejected_names:
            print(f"    PMID {pmid}: {title}")

    if not entries:
        print("  No new entries after verification.")
        return

    print(f"  {len(entries)} entries passed verification.")
    if not args.dry_run:
        with open(BIB_OUT, "a", encoding="utf-8") as f:
            f.write("\n\n% --- PubMed auto-fetched ---\n")
            f.write("\n\n".join(entries))
        print(f"  Appended to {BIB_OUT}")
    else:
        print("  [dry-run] Would append:\n")
        for e in entries:
            print(e, "\n")


if __name__ == "__main__":
    main()