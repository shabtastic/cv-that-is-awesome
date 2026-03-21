#!/usr/bin/env python3
"""
fetch_pubmed.py
===============
Fetch publications from the PubMed E-utilities API and append new entries
to refs/journals.bib.

STRATEGY
--------
Two complementary queries are combined:

  1. ORCID query  [auid]   -- exact match, works for papers since ~2012
                              where the journal/author linked an ORCID.
  2. Name query   [Author] -- broad match, catches older papers and journals
                              that do not deposit ORCID metadata.

Results are unioned. PMIDs found only by the name query pass through an
automatic author-name check, then through interactive review (if enabled).

Rejected entries are saved to refs/.pubmed_rejected.json.

CONFIG
------
Edit the CONFIG block below to match your identity.

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
    load_manual_fingerprints, fingerprint_matches,
    load_rejected, save_rejected, interactive_review, review_rejected,
    normalize_title, load_all_titles,
)

# ---------------------------------------------------------------------------
# CONFIG
# ---------------------------------------------------------------------------
ORCID_ID            = "0000-0003-4122-6041"
PUBMED_AUTHOR       = "Hakimi S"
AUTHOR_LAST         = "Hakimi"
AUTHOR_FIRSTS       = {"shabnam", "s"}
AUTHOR_MAX_INITIALS = 1                  # no middle name -> reject "S A", "S M"
BIB_OUT             = Path("refs/journals.bib")
REJECTED_FILE       = Path("refs/.pubmed_rejected.json")
ESEARCH_URL         = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
EFETCH_URL          = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
TOOL_NAME           = "cv_updater"
ADMIN_EMAIL         = "shabnamhakimi@gmail.com"
# ---------------------------------------------------------------------------


def esearch(term: str, retmax: int = 200) -> set:
    """Run a PubMed esearch and return the set of matching PMIDs."""
    params = dict(db="pubmed", term=term, retmax=retmax,
                  retmode="json", tool=TOOL_NAME, email=ADMIN_EMAIL)
    r = requests.get(ESEARCH_URL, params=params, timeout=15)
    r.raise_for_status()
    return set(r.json()["esearchresult"]["idlist"])


def fetch_pubmed_records(pmids: list) -> ET.Element:
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
    Return True if the record contains a Hakimi whose first-name field is
    consistent with the target author.

      "Hakimi, Shabnam" -> accept
      "Hakimi, S"       -> accept (single initial)
      "Hakimi, Sophie"  -> reject (wrong first name)
      "Hakimi, S A"     -> reject (second initial -- different person)
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


def record_to_bibtex(rec: dict, keywords: str = "") -> str:
    authors      = rec.get("authors", [])
    title        = rec.get("title", "")
    first_author = authors[0].split(",")[0] if authors else "Unknown"
    first_word   = re.sub(r"[^a-zA-Z]", "", title.split()[0]) if title else "x"
    cite_key     = f"{first_author}{rec.get('year', '????')}{first_word}"
    author_str   = " and ".join(authors)

    lines = [f"@article{{{cite_key},"]
    lines.append(f"  author   = {{{author_str}}},")
    lines.append(f"  title    = {{{title}}},")
    lines.append(f"  journal  = {{{rec.get('journal', '')}}},")
    lines.append(f"  year     = {{{rec.get('year', '????')}}},")
    if rec.get("volume"): lines.append(f"  volume   = {{{rec['volume']}}},")
    if rec.get("issue"):  lines.append(f"  number   = {{{rec['issue']}}},")
    if rec.get("pages"):  lines.append(f"  pages    = {{{rec['pages']}}},")
    if rec.get("doi"):    lines.append(f"  doi      = {{{rec['doi']}}},")
    lines.append(f"  note     = {{PMID: {rec.get('pmid', '')}}},")
    lines.append(f"  keywords = {{{keywords}}},")
    lines.append("}")
    return "\n".join(lines)


def load_existing_pmids(bib_path: Path) -> set:
    if not bib_path.exists():
        return set()
    return set(re.findall(r"PMID:\s*(\d+)", bib_path.read_text()))


def load_existing_dois(bib_path: Path) -> set:
    if not bib_path.exists():
        return set()
    text = bib_path.read_text(encoding="utf-8")
    return {d.lower().strip() for d in re.findall(r"doi\s*=\s*\{([^}]+)\}", text, re.IGNORECASE)}


def main():
    parser = argparse.ArgumentParser(description="Fetch publications from PubMed")
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
            print(f"  Removed {len(unrejected)} PMID(s) from rejection list.")
            print("  Re-run without --review-rejected to fetch un-rejected entries.")
        elif unrejected and args.dry_run:
            print(f"  [dry-run] Would remove {len(unrejected)} PMID(s) from rejection list.")
        return

    # -- Query 1: ORCID -------------------------------------------------------
    print(f"Searching PubMed by ORCID: {ORCID_ID}")
    orcid_pmids = esearch(f"{ORCID_ID}[auid]")
    print(f"  [auid]   {len(orcid_pmids)} results")

    # -- Query 2: Author name -------------------------------------------------
    print(f"Searching PubMed by name:  {PUBMED_AUTHOR}")
    name_pmids = esearch(f"{PUBMED_AUTHOR}[Author]")
    print(f"  [Author] {len(name_pmids)} results (before filtering)")

    name_only_pmids = name_pmids - orcid_pmids
    all_pmids       = orcid_pmids | name_pmids
    print(f"  Combined {len(all_pmids)} unique PMIDs "
          f"({len(orcid_pmids)} ORCID-confirmed, "
          f"{len(name_only_pmids)} name-only)")

    # -- Filter ---------------------------------------------------------------
    all_bib_files = [
        BIB_OUT,
        Path("refs/preprints.bib"),
        Path("refs/conference.bib"),
        Path("refs/chapters.bib"),
        Path("refs/presentations.bib"),
        Path("refs/scicomm.bib"),
        Path("refs/patents.bib"),
    ]
    existing_pmids = set()
    existing_dois  = set()
    for bib in all_bib_files:
        existing_pmids |= load_existing_pmids(bib)
        existing_dois  |= load_existing_dois(bib)
    existing_titles = load_all_titles(all_bib_files)
    manual_fp      = load_manual_fingerprints(BIB_OUT)
    rejected       = load_rejected(REJECTED_FILE)

    new_pmids       = []
    skipped_manual  = 0
    skipped_reject  = 0
    skipped_exist   = 0
    show            = args.show_skipped

    for p in sorted(all_pmids):
        if p in existing_pmids:
            skipped_exist += 1
            if show: print(f"  [skip-exist]   PMID {p} already in {BIB_OUT}")
            continue
        if p in rejected:
            skipped_reject += 1
            if show: print(f"  [skip-rejected] PMID {p}: {rejected[p][:60]}")
            continue
        stub = {"ID": "", "doi": "", "note": f"PMID: {p}", "title": ""}
        if fingerprint_matches(stub, manual_fp):
            skipped_manual += 1
            if show: print(f"  [skip-manual]  PMID {p} matches a protected manual entry")
            continue
        new_pmids.append(p)

    if skipped_exist:   print(f"  Skipped {skipped_exist} already-present PMID(s)")
    if skipped_manual:  print(f"  Skipped {skipped_manual} matching manual entries")
    if skipped_reject:  print(f"  Skipped {skipped_reject} previously rejected PMID(s)")

    if not new_pmids:
        print("  No new PubMed records.")
        return

    # -- Fetch ----------------------------------------------------------------
    print(f"  Fetching {len(new_pmids)} new records...")
    root     = fetch_pubmed_records(new_pmids)
    articles = root.findall(".//PubmedArticle")

    # -- Auto name-filter + build candidate list ------------------------------
    candidates    = []   # (bibtex, doi, reject_key, source_label)
    auto_rejected = []

    for article in articles:
        rec  = parse_article(article)
        pmid = rec["pmid"]
        doi  = rec.get("doi", "").lower().strip()

        # Skip if DOI already present in any bib file (catches conference papers
        # that live in conference.bib rather than journals.bib)
        if doi and doi in existing_dois:
            skipped_exist += 1
            if show: print(f"  [skip-exist]   DOI {doi} already in a .bib file")
            continue

        # Skip if title already present in any bib file (catches entries where
        # PubMed returns a wrong/mismatched DOI that wouldn't match on DOI alone)
        norm_title = normalize_title(rec.get("title", ""))
        if norm_title and norm_title in existing_titles:
            skipped_exist += 1
            if show: print(f"  [skip-exist]   title already in a .bib file: {rec['title'][:60]}")
            continue

        if pmid in name_only_pmids and pmid not in orcid_pmids:
            if not author_matches(rec):
                auto_rejected.append((pmid, rec["title"][:70]))
                continue
            source = "name-search, verified"
        else:
            source = "ORCID-confirmed"

        bibtex = record_to_bibtex(rec)
        candidates.append((bibtex, rec["doi"], pmid, source))

    if auto_rejected:
        print(f"  Auto-rejected {len(auto_rejected)} record(s) "
              f"(author name mismatch):")
        for pmid, title in auto_rejected:
            print(f"    PMID {pmid}: {title}")

    if not candidates:
        print("  No candidates remaining after filtering.")
        return

    print(f"  {len(candidates)} candidate(s) to review.")

    # -- Interactive review or auto-accept ------------------------------------
    new_rejected = {}
    if interactive:
        print()
        print("  Actions:  a=accept  e=edit  m=manual  r=reject+remember  s=skip  o=open DOI")
        entries, new_rejected = interactive_review(candidates, REJECTED_FILE)
    else:
        entries = [bibtex for bibtex, *_ in candidates]

    # -- Write ----------------------------------------------------------------
    if not entries:
        print("  No entries accepted.")
    else:
        print(f"  {len(entries)} entry/entries accepted.")
        if not args.dry_run:
            with open(BIB_OUT, "a", encoding="utf-8") as f:
                f.write("\n\n% --- PubMed auto-fetched ---\n")
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
        print(f"  [dry-run] Would remember {len(new_rejected)} rejection(s):")
        for pmid, title in new_rejected.items():
            print(f"    PMID {pmid}: {title}")


if __name__ == "__main__":
    main()