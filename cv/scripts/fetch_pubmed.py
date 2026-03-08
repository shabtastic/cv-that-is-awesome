#!/usr/bin/env python3
"""
fetch_pubmed.py
===============
Fetch publications by author name from the PubMed E-utilities API
and append new entries to refs/journals.bib.

Requirements: pip install requests bibtexparser
"""

import argparse
import re
import xml.etree.ElementTree as ET
from pathlib import Path

import requests

# ── CONFIG ────────────────────────────────────────────────────────────────────
PUBMED_AUTHOR = "Hakimi S"           # ← adjust if needed (LastName Initial)
BIB_OUT       = Path("refs/journals.bib")
ESEARCH_URL   = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
EFETCH_URL    = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
TOOL_NAME     = "cv_updater"
ADMIN_EMAIL   = "shabnam@tri.global"  # ← required by NCBI policy
# ─────────────────────────────────────────────────────────────────────────────


def search_pubmed(author: str, retmax: int = 200) -> list[str]:
    params = dict(db="pubmed", term=f"{author}[Author]",
                  retmax=retmax, retmode="json",
                  tool=TOOL_NAME, email=ADMIN_EMAIL)
    r = requests.get(ESEARCH_URL, params=params, timeout=15)
    r.raise_for_status()
    return r.json()["esearchresult"]["idlist"]


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
    if not bib_path.exists():
        return set()
    return set(re.findall(r'PMID:\s*(\d+)', bib_path.read_text()))


def main():
    parser = argparse.ArgumentParser(description="Fetch publications from PubMed")
    parser.add_argument("--dry-run", action="store_true",
                        help="Preview new entries without writing to disk")
    args = parser.parse_args()

    print(f"Searching PubMed for: {PUBMED_AUTHOR}")
    pmids = search_pubmed(PUBMED_AUTHOR)
    print(f"  Found {len(pmids)} PubMed IDs.")

    existing_pmids = load_existing_pmids(BIB_OUT)
    manual_fp      = load_manual_fingerprints(BIB_OUT)
    new_pmids      = []
    skipped_manual = 0

    for p in pmids:
        if p in existing_pmids:
            continue
        stub = {"ID": "", "doi": "", "note": f"PMID: {p}", "title": ""}
        if fingerprint_matches(stub, manual_fp):
            skipped_manual += 1
            continue
        new_pmids.append(p)

    if skipped_manual:
        print(f"  Skipped {skipped_manual} PubMed record(s) that match "
              f"manual entries in {BIB_OUT}")

    if not new_pmids:
        print("  No new PubMed records.")
        return

    print(f"  Fetching {len(new_pmids)} new records...")
    root     = fetch_pubmed_records(new_pmids)
    articles = root.findall(".//PubmedArticle")
    entries  = [record_to_bibtex(parse_article(a)) for a in articles]

    if not args.dry_run:
        with open(BIB_OUT, "a", encoding="utf-8") as f:
            f.write("\n\n% --- PubMed auto-fetched ---\n")
            f.write("\n\n".join(entries))
        print(f"  Appended {len(entries)} entries to {BIB_OUT}")
    else:
        print("  [dry-run] Would append:\n")
        for e in entries:
            print(e, "\n")


if __name__ == "__main__":
    main()