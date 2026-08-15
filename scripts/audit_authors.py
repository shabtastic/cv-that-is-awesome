#!/usr/bin/env python3
"""
audit_authors.py — check bib author lists against the DOI registries.

Author lists drift silently. An entry can carry the right title, journal,
year and DOI while quietly omitting collaborators, and nothing in the build
will complain. The first run of this audit found four such entries:
Sumner2024personalizing was missing ten of seventeen authors,
Mosner2019neural three of fourteen, Sinclair2021imagining one of six, and
Tost2010acute one of seven. None were detectable without asking the
registry.

Two registries, chosen per DOI
------------------------------
  • arXiv DOIs (10.48550/arXiv.*) are registered with **DataCite**.
    Querying Crossref for them returns 404 — which looks like a broken
    audit rather than a routing problem, so the split is explicit here.
  • Everything else goes to **Crossref**, whose data is the publisher's
    own deposit.

What is NOT an error
--------------------
  • `usera` entries. Equal-contribution papers reorder authors on purpose
    (see CLAUDE.md § Own-name bolding); `usera` carries the display form
    with \\cvfnmark{equalcontrib}. Comparing `author` against the registry
    flags these as reordered when they are intentional, so entries with
    `usera` are reported as EXEMPT unless --include-usera is passed.
  • Deliberate abbreviation via `{others, including} ...`, used for the
    197-author NARPS consortium paper (Botvinik2020variability). Entries
    whose author list contains "others" are reported as ABBREVIATED.

Comparison is on family names only, accent- and case-insensitive, in
order. Given names and initials are not compared: registries and the bib
legitimately differ there (e.g. "Lucas Kempf" vs "Kempf, L. P.").

Exit status:
  0   no discrepancies (exemptions and abbreviations are not discrepancies)
  1   at least one discrepancy found

Run:
    python3 scripts/audit_authors.py                  # all refs/*.bib
    python3 scripts/audit_authors.py --file journals  # one file
    python3 scripts/audit_authors.py --key Tost2010acute
    python3 scripts/audit_authors.py --include-usera  # audit those too
    make audit-authors
"""

import argparse
import json
import re
import sys
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

REFS_DIR = Path(__file__).resolve().parent.parent / "refs"
ENTRY_RE = re.compile(r"@(\w+)\{([^,]+),(.*?)\n\}", re.S)
MAILTO = "shabnamhakimi@gmail.com"  # Crossref polite pool
USER_AGENT = f"cv-bib-audit/1.0 (mailto:{MAILTO})"


def norm(s: str) -> str:
    """Fold accents and punctuation so 'Galván' == 'Galvan'."""
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    return re.sub(r"[^a-z]", "", s.lower())


def family_of(author: str) -> str:
    """Family name from a BibTeX author. Handles braced compound surnames
    like {ul Haq}, B. and {Carter Carston}, R. M."""
    a = author.strip()
    if m := re.match(r"^\{(.+?)\}\s*,", a):
        return m.group(1)
    a = a.replace("{", "").replace("}", "")
    if "," in a:
        return a.split(",")[0].strip()
    parts = a.split()
    return parts[-1] if parts else a


def field(body: str, name: str) -> str | None:
    m = re.search(rf"^\s*{name}\s*=\s*\{{(.*?)\}}\s*,?\s*$", body, re.M | re.S)
    return " ".join(m.group(1).split()) if m else None


def parse_entries(paths):
    out = []
    for path in paths:
        for _typ, key, body in ENTRY_RE.findall(path.read_text()):
            doi = field(body, "doi")
            authors = field(body, "author")
            if not doi or not authors:
                continue
            out.append({
                "file": path.name,
                "key": key.strip(),
                "doi": doi,
                "authors": [" ".join(a.split()) for a in authors.split(" and ")],
                "usera": field(body, "usera") is not None,
            })
    return out


def fetch(doi: str):
    """Return (families, source) from whichever registry owns this DOI."""
    if "arxiv" in doi.lower():
        url = "https://api.datacite.org/dois/" + urllib.parse.quote(doi, safe="")
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        data = json.load(urllib.request.urlopen(req, timeout=30))
        creators = data["data"]["attributes"].get("creators", [])
        fams = [c.get("familyName") or c.get("name", "") for c in creators]
        return [f for f in fams if f], "datacite"

    url = ("https://api.crossref.org/works/" + urllib.parse.quote(doi, safe="")
           + f"?mailto={MAILTO}")
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    msg = json.load(urllib.request.urlopen(req, timeout=30))["message"]
    return [a["family"] for a in msg.get("author", []) if a.get("family")], "crossref"


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Check bib author lists against Crossref/DataCite.")
    ap.add_argument("--file", help="audit one refs/<name>.bib (name without .bib)")
    ap.add_argument("--key", help="audit a single cite key")
    ap.add_argument("--include-usera", action="store_true",
                    help="audit equal-contribution entries too (expect false positives)")
    ap.add_argument("--delay", type=float, default=0.4,
                    help="seconds between requests (default 0.4)")
    args = ap.parse_args()

    paths = ([REFS_DIR / f"{args.file}.bib"] if args.file
             else sorted(REFS_DIR.glob("*.bib")))
    for p in paths:
        if not p.exists():
            print(f"error: {p} not found", file=sys.stderr)
            return 1

    entries = parse_entries(paths)
    if args.key:
        entries = [e for e in entries if e["key"] == args.key]
        if not entries:
            print(f"error: no entry '{args.key}' with both author and doi",
                  file=sys.stderr)
            return 1

    print(f"auditing {len(entries)} entr{'y' if len(entries)==1 else 'ies'} with DOIs\n")
    discrepancies = exempt = abbreviated = failed = 0

    for e in entries:
        label = f"{e['key']:34} ({e['file']})"

        if any("others" in a for a in e["authors"]):
            abbreviated += 1
            print(f"  ABBREVIATED {label}  deliberate {{others}} form, skipped")
            continue

        if e["usera"] and not args.include_usera:
            exempt += 1
            print(f"  EXEMPT      {label}  usera / equal-contribution, skipped")
            continue

        try:
            reg_fams, source = fetch(e["doi"])
        except Exception as ex:  # noqa: BLE001 — report and keep going
            failed += 1
            print(f"  FAILED      {label}  {e['doi']}  {str(ex)[:60]}")
            continue

        if not reg_fams:
            failed += 1
            print(f"  FAILED      {label}  {source} lists no authors")
            continue

        bib_fams = [norm(family_of(a)) for a in e["authors"]]
        reg_norm = [norm(f) for f in reg_fams]

        if bib_fams == reg_norm:
            print(f"  ok          {label}  {len(bib_fams)} authors ({source})")
            continue

        discrepancies += 1
        missing = [f for f, n in zip(reg_fams, reg_norm) if n not in bib_fams]
        extra = [a for a, n in zip(e["authors"], bib_fams) if n not in reg_norm]
        kind = "ORDER" if not missing and not extra else "MEMBERSHIP"
        print(f"  {kind:11} {label}  bib {len(bib_fams)} vs {source} {len(reg_norm)}")
        if missing:
            print(f"              missing from bib : {missing}")
        if extra:
            print(f"              not in {source:9}: {extra}")
        if kind == "ORDER":
            print(f"              {source}: {reg_fams}")
            print(f"              bib     : {[family_of(a) for a in e['authors']]}")

        time.sleep(args.delay)

    print(f"\nSummary: {discrepancies} discrepanc{'y' if discrepancies==1 else 'ies'}, "
          f"{exempt} exempt, {abbreviated} abbreviated, {failed} lookup failure(s)")
    return 1 if discrepancies else 0


if __name__ == "__main__":
    sys.exit(main())
