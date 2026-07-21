#!/usr/bin/env python3
"""
fetch_patents.py
================
Fetch patent data from the USPTO Patent Center API by exact patent number
and write authoritative entries to refs/patents.bib.

Three modes:
  --mode refresh      Re-fetch all known patent numbers from USPTO, preserve any
                      manually-added entries (keyword=manual), back up the old
                      file first, then write a clean merged patents.bib. (default)
  --mode discover     Search USPTO by inventor name for NEW patents not yet in
                      the known list, and append them as stubs for review.
  --mode check-status Scan patents.bib for Filed entries, query USPTO by
                      application number, and update any that have been granted
                      (status, number, note) in-place. Also adds newly granted
                      numbers to KNOWN_PATENT_NUMBERS.

Manual entry protection:
  Any @patent entry in patents.bib with  keywords = {manual}  (or any value
  containing "manual") will be detected before the refresh, preserved in full,
  and re-inserted at the end of the rebuilt file under a clearly marked section.
  The old file is always backed up to patents.bib.bak before any write.

Requirements:
    pip install requests bibtexparser

USPTO API docs:
    https://developer.uspto.gov/api-catalog/patentcenteropen
"""

# `from __future__ import annotations` lets us use PEP 604 syntax
# ("dict | None") on Python 3.9, where without it the annotation is
# evaluated at definition time and raises TypeError.
from __future__ import annotations

import argparse
import os
import re
import shutil
import sys
import time
from datetime import datetime
from pathlib import Path

import requests
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

sys.path.insert(0, str(Path(__file__).parent))
from _shared import write_atomic, append_atomic  # noqa: E402

try:
    import bibtexparser
    from bibtexparser.bwriter import BibTexWriter
    HAS_BIBTEX = True
except ImportError:
    HAS_BIBTEX = False

# ── CONFIG ────────────────────────────────────────────────────────────────────
INVENTOR_LAST  = "Hakimi"
INVENTOR_FIRST = "Shabnam"
BIB_OUT        = Path("refs/patents.bib")
BAK_OUT        = Path("refs/patents.bib.bak")
HOLDER         = "Toyota Research Institute"

PEDS_BASE      = "https://ped.uspto.gov/api/queries"          # RETIRED March 2025
ODP_SEARCH_URL = "https://api.uspto.gov/api/v1/patent/applications/search"
ODP_APP_URL    = "https://api.uspto.gov/api/v1/patent/applications/{appnum}/meta-data"

HEADERS = {
    "Accept": "application/json",
    "User-Agent": "cv-updater/1.0 (shabnamhakimi@gmail.com)",
}


def _load_dotenv(path: Path = Path(".env")) -> None:
    """Load KEY=VALUE lines from a local .env file into os.environ.

    No-op if the file is missing. Existing environment variables always
    win over the file (uses setdefault), and the file is gitignored.
    """
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def get_api_key() -> str:
    """Load the USPTO ODP API key from the environment or a local .env file."""
    _load_dotenv()
    key = os.environ.get("USPTO_API_KEY", "")
    if not key:
        print("  [error] USPTO_API_KEY not set.")
        print("          Get your key at https://data.uspto.gov (My ODP)")
        print("          Then either:")
        print("            export USPTO_API_KEY='your_key_here'")
        print("          or add this line to a local .env file (gitignored):")
        print("            USPTO_API_KEY=your_key_here")
        sys.exit(1)
    return key

# ── KNOWN PATENT NUMBERS ──────────────────────────────────────────────────────
# Canonical list of granted US patent numbers.
# Add new numbers here as patents are granted; run --mode refresh to update.
# Plain number strings only — no "US" prefix.
KNOWN_PATENT_NUMBERS = [
    "12524477",   # Sumner et al. 2025 — application exploration
    "12524132",   # Zhang et al. 2025 — drift detection
    "12541651",   # Chen et al. 2026 — psychological complexity
    "12493401",   # Hong et al. 2025 — moodboard augmentation
    "12425255",   # Shamma et al. 2025 — co-worker remote encounter
    "12400077",   # Hakimi et al. 2025 — statistical data understanding
    "12210808",   # Lee et al. 2025 — simulated humans
    "12613892",   # Hong et al. 2025 — stylistic preferences
    "11934476",   # Hakimi et al. 2024 — web search contextualization
    "11868600",   # Carter et al. 2024 — ranked choice
    "12032618",   # Chen et al. 2024 — infer thoughts/coding scheme
    "11579684",   # Arechiga et al. 2023 — AR goal assistant
    "12062121",   # Arechiga et al. 2024 — digital persona
    "12084080",   # Rosman et al. 2024 — robot user interfaces
]
# ─────────────────────────────────────────────────────────────────────────────


# ── BACKUP ───────────────────────────────────────────────────────────────────

def backup_bib(src: Path, dst: Path) -> None:
    """Copy src to dst, stamping the backup with a timestamp comment."""
    if not src.exists():
        return
    stamp   = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    content = src.read_text(encoding="utf-8")
    header  = f"% BACKUP created {stamp} by fetch_patents.py\n\n"
    write_atomic(dst, header + content)
    print(f"  Backed up existing file → {dst}")


# ── MANUAL ENTRY DETECTION ───────────────────────────────────────────────────

def extract_manual_entries(bib_path: Path) -> list[str]:
    """
    Parse patents.bib and return raw BibTeX strings for any entry whose
    keywords field contains 'manual'.
    Always uses regex — bibtexparser v1 silently drops @patent entries.
    """
    if not bib_path.exists():
        return []
    return _extract_manual_regex(bib_path)


def _extract_manual_bibtexparser(bib_path: Path) -> list[str]:
    with open(bib_path, encoding="utf-8") as f:
        db = bibtexparser.load(f)
    manual = [e for e in db.entries
              if "manual" in e.get("keywords", "").lower()]
    if not manual:
        return []
    writer        = BibTexWriter()
    writer.indent = "  "
    db.entries    = manual
    raw           = writer.write(db)
    # Split back into individual entry strings
    return [e.strip() for e in re.split(r'\n(?=@)', raw) if e.strip()]


def _extract_manual_regex(bib_path: Path) -> list[str]:
    """Fallback regex-based extractor if bibtexparser is not installed."""
    text    = bib_path.read_text(encoding="utf-8")
    entries = re.split(r'\n(?=@)', text)
    manual  = []
    for entry in entries:
        kw_match = re.search(r'keywords\s*=\s*\{([^}]*)\}', entry, re.IGNORECASE)
        if kw_match and "manual" in kw_match.group(1).lower():
            manual.append(entry.strip())
    return manual


# ── USPTO FETCH ───────────────────────────────────────────────────────────────

def fetch_patent_odp(patent_number: str, api_key: str) -> dict | None:
    """
    Query the USPTO Open Data Portal for a single patent by grant number.
    Uses POST /api/v1/patent/applications/search with patentNumber field.
    Returns the applicationMetaData sub-dict from the first hit.
    """
    payload = {
        "q": f"applicationMetaData.patentNumber:{patent_number}",
        "pagination": {"offset": 0, "limit": 1},
    }
    headers = {**HEADERS, "Content-Type": "application/json", "x-api-key": api_key}
    try:
        r = requests.post(ODP_SEARCH_URL, json=payload, headers=headers,
                          timeout=20, verify=False)
        r.raise_for_status()
        results = r.json()
        bag = (results.get("patentFileWrapperDataBag") or
               results.get("results") or [])
        if not bag:
            return None
        first = bag[0]
        return first.get("applicationMetaData", first)
    except Exception as e:
        print(f"    [warn] ODP query failed for {patent_number}: {e}")
        return None


def fetch_patent_public_search(patent_number: str) -> dict | None:
    """Fallback: USPTO Patent Public Search PDF-info endpoint."""
    url = (f"https://ppubs.uspto.gov/dirsearch-public"
           f"/patents/{patent_number}/pdf-info")
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        if r.status_code == 200:
            return r.json()
    except Exception:
        pass
    return None


def parse_patent_record(record: dict, patent_number: str) -> dict:
    """Normalize a USPTO API response into a consistent flat dict."""
    out = {"number": patent_number, "title": "", "inventors": [], "year": "????"}

    # ODP uses inventionTitle; PEDS used patentTitle
    for key in ("inventionTitle", "patentTitle", "title"):
        if record.get(key):
            out["title"] = record[key].strip().rstrip(".")
            break

    # ODP uses patentIssuanceDate; PEDS used patentGrantDate
    for key in ("patentIssuanceDate", "patentGrantDate", "grantDate",
                "issueDate", "patentIssueDate"):
        if record.get(key):
            out["year"] = str(record[key])[:4]
            break

    # ODP returns inventors as a list of dicts with firstName/lastName
    for key in ("inventors", "inventorNameArrayText", "inventorList"):
        raw = record.get(key)
        if raw:
            if isinstance(raw, list):
                for inv in raw:
                    if isinstance(inv, str):
                        out["inventors"].append(inv)
                    elif isinstance(inv, dict):
                        last  = inv.get("lastName", inv.get("last", ""))
                        first = inv.get("firstName", inv.get("first", ""))
                        if last:
                            out["inventors"].append(
                                f"{last}, {first}".strip(", "))
            break

    return out


def make_cite_key(record: dict) -> str:
    last       = record["inventors"][0].split(",")[0].strip() \
                 if record["inventors"] else "Unknown"
    first_word = re.sub(r"[^a-zA-Z]", "", record["title"].split()[0]) \
                 if record["title"] else "patent"
    return f"{last}{record['year']}{first_word}"


def confirm_holder(patent_number: str, title: str,
                   suggested: str = HOLDER) -> str:
    """
    Interactively confirm the assignee/holder for a patent.
    """
    print(f"\n  Assignee confirmation for US {patent_number}:")
    print(f"    Title    : {title[:70]}")
    print(f"    Suggested: {suggested}")
    print(f"    Press Enter to accept, type a new value, or '?' to mark TODO: ",
          end="", flush=True)
    try:
        user_input = input().strip()
    except (EOFError, KeyboardInterrupt):
        print(f"\n    [non-interactive] Using suggested: {suggested}")
        return suggested
    if user_input == "":
        return suggested
    elif user_input == "?":
        return "TODO: verify assignee"
    else:
        return user_input


def confirm_status(patent_number: str, title: str,
                   suggested: str = "Granted") -> str:
    """
    Interactively confirm whether a patent is Granted or Filed.
    USPTO PEDS primarily returns granted patents, but application
    numbers can appear too.
    """
    print(f"    Status suggested: {suggested}  "
          f"(Enter to accept, or type 'Filed'): ",
          end="", flush=True)
    try:
        user_input = input().strip()
    except (EOFError, KeyboardInterrupt):
        return suggested
    if user_input == "":
        return suggested
    elif user_input.lower() in ("filed", "f"):
        return "Filed"
    elif user_input.lower() in ("granted", "g"):
        return "Granted"
    else:
        return suggested


def record_to_bibtex(record: dict, keywords: str = "selected",
                     holder: str = HOLDER, status: str = "Granted") -> str:
    cite_key = make_cite_key(record)
    inv_str  = " and ".join(record["inventors"]) \
               if record["inventors"] else "Hakimi, Shabnam"
    lines = [f"@patent{{{cite_key},"]
    lines.append(f"  author   = {{{inv_str}}},")
    lines.append(f"  title    = {{{record['title']}}},")
    lines.append(f"  number   = {{US~{record['number']}}},")
    lines.append(f"  year     = {{{record['year']}}},")
    lines.append(f"  holder   = {{{holder}}},")
    lines.append(f"  note     = {{U.S. Patent and Trademark Office, "
                 f"Washington, DC. Status: {status}}},")
    lines.append(f"  keywords = {{{keywords}}},")
    lines.append("}")
    return "\n".join(lines)


def make_stub(patent_number: str, holder: str = HOLDER,
              status: str = "Granted") -> str:
    return (
        f"@patent{{STUB{patent_number},\n"
        f"  author   = {{Hakimi, Shabnam}},\n"
        f"  title    = {{TODO: fetch title for US {patent_number}}},\n"
        f"  number   = {{US~{patent_number}}},\n"
        f"  year     = {{????}},\n"
        f"  holder   = {{{holder}}},\n"
        f"  note     = {{U.S. Patent and Trademark Office, Washington, DC."
        f" Status: {status}}},\n"
        f"  keywords = {{}},\n"
        f"}}"
    )


# ── MODES ─────────────────────────────────────────────────────────────────────

def mode_refresh(dry_run: bool) -> None:
    """
    1. Back up existing patents.bib → patents.bib.bak
    2. Extract any manually-added entries (keywords containing 'manual')
    3. Re-fetch all KNOWN_PATENT_NUMBERS from USPTO
    4. Write rebuilt file: USPTO entries + preserved manual entries
    """

    # Step 1 — backup
    print("Step 1: Backing up existing patents.bib...")
    backup_bib(BIB_OUT, BAK_OUT)

    # Step 2 — extract manual entries
    print("\nStep 2: Scanning for manually-added entries (keywords=manual)...")
    manual_entries = extract_manual_entries(BIB_OUT)
    if manual_entries:
        print(f"  Found {len(manual_entries)} manual entry/entries — "
              f"will preserve:")
        for e in manual_entries:
            key = re.search(r'@\w+\{(\S+),', e)
            print(f"    • {key.group(1) if key else '(unknown key)'}")
    else:
        print("  No manual entries found.")

    # Step 3 — fetch from USPTO
    print(f"\nStep 3: Fetching {len(KNOWN_PATENT_NUMBERS)} patents from USPTO ODP...")
    api_key         = get_api_key()
    fetched_entries = []
    failed          = []

    for num in KNOWN_PATENT_NUMBERS:
        print(f"  US {num} ...", end=" ", flush=True)
        record = fetch_patent_odp(num, api_key)
        if record is None:
            record = fetch_patent_public_search(num)
        if record:
            normalized       = parse_patent_record(record, num)
            # ODP returns assignee under assigneeEntityName or applicantName
            suggested_holder = (record.get("assigneeEntityName") or
                                record.get("assigneeName") or
                                record.get("applicantName") or
                                HOLDER)
            suggested_status = ("Filed" if not record.get("patentNumber")
                                else "Granted")
            if not dry_run:
                holder = confirm_holder(num, normalized["title"],
                                        suggested=suggested_holder)
                status = confirm_status(num, normalized["title"],
                                        suggested=suggested_status)
            else:
                holder = suggested_holder
                status = suggested_status
            fetched_entries.append(
                record_to_bibtex(normalized, keywords="selected",
                                 holder=holder, status=status))
            print(f"✓  [{status}] {normalized['title'][:50]}...")
        else:
            if not dry_run:
                holder = confirm_holder(num, "UNKNOWN — stub entry",
                                        suggested=HOLDER)
                status = confirm_status(num, "UNKNOWN — stub entry")
            else:
                holder = HOLDER
                status = "Granted"
            fetched_entries.append(make_stub(num, holder=holder, status=status))
            failed.append(num)
            print("✗  not found — stub written")
        time.sleep(0.3)

    # Step 4 — assemble output
    stamp  = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    header = (
        "%==========================================================="
        "===================\n"
        "% PATENTS — auto-generated by fetch_patents.py\n"
        f"% Last refreshed: {stamp}\n"
        "% Source: USPTO Open Data Portal (ODP) — api.uspto.gov\n"
        "%\n"
        "% To add a patent manually:\n"
        "%   1. Add an @patent entry below with  keywords = {manual}\n"
        "%   2. It will be preserved automatically on the next refresh.\n"
        "%   3. If it is also a USPTO-tracked patent, add its number to\n"
        "%      KNOWN_PATENT_NUMBERS in fetch_patents.py instead.\n"
        "%\n"
        "% keywords = {selected}  → shown when selectedOnlyPatents is true\n"
        "% keywords = {manual}    → manually added; preserved across refreshes\n"
        "%==========================================================="
        "===================\n\n"
    )

    sections = [header + "\n\n".join(fetched_entries)]

    if manual_entries:
        manual_block = (
            "\n\n% ── MANUALLY ADDED ENTRIES "
            "(preserved automatically) ─────────────────────\n"
            "% These entries have  keywords = {manual}  and are not fetched\n"
            "% from USPTO. Edit them here; they will survive future refreshes.\n\n"
            + "\n\n".join(manual_entries)
        )
        sections.append(manual_block)

    output = "\n".join(sections) + "\n"

    if not dry_run:
        write_atomic(BIB_OUT, output)
        print(f"\nStep 4: Wrote {len(fetched_entries)} USPTO entries "
              f"+ {len(manual_entries)} manual entries → {BIB_OUT}")
    else:
        print("\n[dry-run] Would write:\n")
        print(output[:2000], "...(truncated)")

    if failed:
        print(f"\n⚠  Could not fetch: {failed}")
        print("   Stubs written — fill in manually or re-run later.")


def mode_discover(dry_run: bool) -> None:
    """Search USPTO ODP by inventor name for patents not in KNOWN_PATENT_NUMBERS."""
    print(f"Searching USPTO ODP for patents by {INVENTOR_FIRST} {INVENTOR_LAST}...")
    api_key = get_api_key()
    # Search by inventor first+last name (ODP requires dotted sub-field paths)
    payload = {
        "q": (f"applicationMetaData.inventorBag.lastName:{INVENTOR_LAST}"
              f" AND applicationMetaData.inventorBag.firstName:{INVENTOR_FIRST}"),
        "pagination": {"offset": 0, "limit": 50},
    }
    headers = {**HEADERS, "Content-Type": "application/json", "x-api-key": api_key}
    try:
        r = requests.post(
            ODP_SEARCH_URL,
            json=payload,
            headers=headers,
            timeout=20,
            verify=False,
        )
        r.raise_for_status()
        results = r.json()
        bag = (results.get("patentFileWrapperDataBag") or
               results.get("results") or [])
        # applicationNumberText lives at the wrapper level, not inside applicationMetaData
        docs = [(h.get("applicationMetaData", h), h.get("applicationNumberText", ""))
                for h in bag]
    except Exception as e:
        print(f"[error] USPTO ODP discovery search failed: {e}")
        sys.exit(1)

    print(f"  Found {len(docs)} total records.")
    new_entries = []
    for doc, top_app_num in docs:
        patent_num = doc.get("patentNumber", "")
        app_num    = top_app_num or doc.get("applicationNumberText", "")
        # Use patent number for granted, application number for filed
        num    = patent_num or app_num
        status_hint = "Granted" if patent_num else "Filed"
        if not num:
            continue
        if num in KNOWN_PATENT_NUMBERS:
            continue
        title = doc.get("inventionTitle", doc.get("patentTitle", "unknown title"))
        print(f"\n  NEW [{status_hint}]: {num} — {title[:60]}")
        normalized       = parse_patent_record(doc, num)
        suggested_holder = (doc.get("assigneeEntityName") or
                            doc.get("assigneeName") or
                            doc.get("applicantName") or
                            HOLDER)
        suggested_status = status_hint
        if not dry_run:
            holder = confirm_holder(num, title, suggested=suggested_holder)
            status = confirm_status(num, title, suggested=suggested_status)
        else:
            holder = suggested_holder
            status = suggested_status
            print(f"    [dry-run] holder={holder}, status={status}")
        new_entries.append(
            record_to_bibtex(normalized, keywords="manual",
                             holder=holder, status=status)
        )

    if not new_entries:
        print("  No new patents found beyond known list.")
        return

    note = (
        "\n\n% --- USPTO discover: review these and add numbers to "
        "KNOWN_PATENT_NUMBERS ---\n"
        "% Entries are tagged  keywords = {manual}  so they survive "
        "a refresh.\n"
        "% Once verified, move the number to KNOWN_PATENT_NUMBERS and\n"
        "% change keywords to {selected} or {} as appropriate.\n\n"
    )

    if not dry_run:
        backup_bib(BIB_OUT, BAK_OUT)
        append_atomic(BIB_OUT, note + "\n\n".join(new_entries))
        print(f"\nAppended {len(new_entries)} new entry/entries to {BIB_OUT}")
        print("⚠  Review, then move verified numbers to KNOWN_PATENT_NUMBERS.")
    else:
        print("\n[dry-run] Would append:")
        for e in new_entries:
            print(e, "\n")


# ── CHECK-STATUS MODE ────────────────────────────────────────────────────

def _parse_app_number(number_field: str) -> str | None:
    """Extract bare application number from 'US App.~18/976,524' format."""
    m = re.search(r'(\d{2})/?([\d,]+)', number_field)
    if not m:
        return None
    return m.group(1) + m.group(2).replace(",", "")


def fetch_app_status_odp(app_number: str, api_key: str) -> dict | None:
    """
    Query USPTO ODP by application number to check if a patent has been granted.
    Returns the applicationMetaData dict if found, None otherwise.
    """
    payload = {
        "q": f"applicationNumberText:{app_number}",
        "pagination": {"offset": 0, "limit": 1},
    }
    headers = {**HEADERS, "Content-Type": "application/json", "x-api-key": api_key}
    try:
        r = requests.post(ODP_SEARCH_URL, json=payload, headers=headers,
                          timeout=20, verify=False)
        r.raise_for_status()
        results = r.json()
        bag = (results.get("patentFileWrapperDataBag") or
               results.get("results") or [])
        if not bag:
            return None
        first = bag[0]
        return first.get("applicationMetaData", first)
    except Exception as e:
        print(f"    [warn] ODP query failed for app {app_number}: {e}")
        return None


def _extract_filed_entries(bib_path: Path) -> list[dict]:
    """
    Parse patents.bib and return info for each Filed entry:
    {cite_key, app_number, number_field, line_start, raw_text}
    """
    text = bib_path.read_text(encoding="utf-8")
    entries = re.split(r'\n(?=@patent\{)', text)
    filed = []
    offset = 0
    for entry in entries:
        if not entry.strip().startswith("@patent{"):
            offset += entry.count("\n") + 1
            continue
        status_m = re.search(r'status\s*=\s*\{([^}]*)\}', entry, re.IGNORECASE)
        if status_m and status_m.group(1).strip().lower() == "filed":
            key_m = re.search(r'@patent\{(\S+),', entry)
            num_m = re.search(r'number\s*=\s*\{([^}]*)\}', entry, re.IGNORECASE)
            if key_m and num_m:
                app_num = _parse_app_number(num_m.group(1))
                if app_num:
                    filed.append({
                        "cite_key": key_m.group(1),
                        "app_number": app_num,
                        "number_field": num_m.group(1),
                        "raw_text": entry,
                    })
        offset += entry.count("\n") + 1
    return filed


def _update_entry_to_granted(raw: str, patent_number: str) -> str:
    """Rewrite a Filed entry's status, number, and note to Granted."""
    # Format patent number with commas: 12613892 -> 12,613,892
    num = patent_number
    if num.isdigit() and len(num) > 3:
        parts = []
        while len(num) > 3:
            parts.append(num[-3:])
            num = num[:-3]
        parts.append(num)
        formatted = ",".join(reversed(parts))
    else:
        formatted = patent_number

    updated = raw
    # Update number field
    updated = re.sub(
        r'(number\s*=\s*\{)[^}]*(})',
        rf'\g<1>US~{formatted}\2',
        updated,
    )
    # Update status field
    updated = re.sub(
        r'(status\s*=\s*\{)[^}]*(})',
        r'\g<1>Granted\2',
        updated,
    )
    # Update note field — collapse to single line
    updated = re.sub(
        r'note\s*=\s*\{[^}]*\}',
        'note     = {U.S. Patent and Trademark Office, Washington, DC}',
        updated,
    )
    return updated


def mode_check_status(dry_run: bool) -> None:
    """
    Scan patents.bib for Filed entries, query USPTO by application number,
    and update any that have been granted in-place.
    """
    if not BIB_OUT.exists():
        print(f"  {BIB_OUT} not found.")
        return

    filed = _extract_filed_entries(BIB_OUT)
    if not filed:
        print("  No Filed entries found in patents.bib.")
        return

    print(f"  Found {len(filed)} Filed patent(s). Checking USPTO...\n")
    api_key = get_api_key()
    updates = []

    for entry in filed:
        print(f"  {entry['cite_key']} (app {entry['app_number']}) ...", end=" ", flush=True)
        record = fetch_app_status_odp(entry["app_number"], api_key)
        if record and record.get("patentNumber"):
            patent_num = str(record["patentNumber"])
            print(f"GRANTED as US {patent_num}")
            updates.append((entry, patent_num))
        else:
            print("still pending")
        time.sleep(0.3)

    if not updates:
        print("\n  No status changes found.")
        return

    print(f"\n  {len(updates)} patent(s) newly granted:")
    for entry, patent_num in updates:
        print(f"    {entry['cite_key']}: app {entry['app_number']} → US {patent_num}")

    if dry_run:
        print("\n  [dry-run] No changes written.")
        return

    # Apply updates in-place
    backup_bib(BIB_OUT, BAK_OUT)
    content = BIB_OUT.read_text(encoding="utf-8")
    new_known = []
    for entry, patent_num in updates:
        updated = _update_entry_to_granted(entry["raw_text"], patent_num)
        content = content.replace(entry["raw_text"], updated)
        new_known.append(patent_num)

    write_atomic(BIB_OUT, content)
    print(f"\n  Updated {len(updates)} entry/entries in {BIB_OUT}")

    # Remind to add to KNOWN_PATENT_NUMBERS
    if new_known:
        print("\n  Add to KNOWN_PATENT_NUMBERS in fetch_patents.py:")
        for num in new_known:
            print(f'    "{num}",')


# ── MAIN ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Fetch USPTO patent data and write refs/patents.bib",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  python fetch_patents.py                # refresh from USPTO\n"
            "  python fetch_patents.py --dry-run      # preview only\n"
            "  python fetch_patents.py --mode discover  # find new patents\n"
        ),
    )
    parser.add_argument(
        "--mode", choices=["refresh", "discover", "check-status"],
        default="refresh",
    )
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if args.mode == "refresh":
        mode_refresh(args.dry_run)
    elif args.mode == "discover":
        mode_discover(args.dry_run)
    elif args.mode == "check-status":
        mode_check_status(args.dry_run)


if __name__ == "__main__":
    main()