#!/usr/bin/env python3
"""
check_pagebreaks.py
===================
Verify the typeset PDFs obey the two page-break style rules set in cv.tex
(toggle: keepCitationsWhole):

  R5  no bibliography entry is split across a page break
  R6  no heading is stranded at the foot of a page without its content

Both rules are enforced in TeX, where a silent lapse looks identical to a
clean run -- a hook that stops firing produces no error. This script checks
the rendered output instead, which is the only place the rules are observable.

Headings are read from the PDF outline (cv.tex emits \\pdfbookmark for every
\\cvsection and \\cvsubsection), NOT guessed from text shape. An earlier
text-shape heuristic mistook a wrapped memberships line for a heading.

Usage:
    python scripts/check_pagebreaks.py cv-full.pdf cv-industry.pdf
    python scripts/check_pagebreaks.py            # all built cv-*.pdf

Exit status: 0 if every PDF is clean, 1 otherwise.
Requires: pypdf, and pdftotext (poppler) on PATH.
"""
import re
import subprocess
import sys
from pathlib import Path

try:
    from pypdf import PdfReader
except ImportError:
    sys.exit("check_pagebreaks: pypdf not installed (pip install pypdf)")

# Which cv.tex toggle governs each rule. A preset may switch one off
# deliberately (config/speaking.tex drops R6 to stay at three pages), so the
# expected result is read from the preset config rather than hardcoded here --
# re-enable the toggle and this check starts enforcing it again automatically.
RULE_TOGGLE = {
    "R5": "keepCitationsWhole",
    "R6": "keepHeadingsWithContent",
}
CONFIG_DIR = Path("config")

ENTRY_RE = re.compile(r"^\s*\[\d+\]")
# Page furniture: the running footer carries the date, name, and page number.
FOOTER_RE = re.compile(r"Shabnam Hakimi|Curriculum Vitae|^\s*\d+\s*$")
# A heading is "stranded" if fewer than this many content lines follow it
# on the same page.
MIN_LINES_UNDER_HEADING = 2


def page_lines(pdf: str, n: int) -> list[str]:
    """Content lines of page n (1-indexed), footer stripped."""
    out = subprocess.run(
        ["pdftotext", "-layout", "-f", str(n), "-l", str(n), pdf, "-"],
        capture_output=True, text=True,
    ).stdout
    return [l for l in out.split("\n") if l.strip() and not FOOTER_RE.search(l)]


def heading_pages(pdf: str) -> dict[int, list[str]]:
    """page number (1-indexed) -> heading titles landing on it, from the outline."""
    reader = PdfReader(pdf)
    found: dict[int, list[str]] = {}

    def walk(node):
        for item in node:
            if isinstance(item, list):
                walk(item)
                continue
            try:
                page = reader.get_destination_page_number(item) + 1
                found.setdefault(page, []).append(str(item.title))
            except Exception:
                pass

    try:
        walk(reader.outline)
    except Exception:
        pass
    return found


def disabled_rules(pdf: str) -> set[str]:
    """Rules a preset has deliberately switched off, read from its config."""
    stem = Path(pdf).stem                      # cv-speaking
    preset = stem[3:] if stem.startswith("cv-") else stem
    cfg = CONFIG_DIR / f"{preset}.tex"
    if not cfg.exists():
        return set()
    # Strip LaTeX comments first: a commented-out \togglefalse must NOT read
    # as "disabled", or commenting the override back out would silently switch
    # the check off instead of switching it on.
    lines = []
    for raw in cfg.read_text(encoding="utf-8", errors="replace").split("\n"):
        lines.append(re.sub(r"(?<!\\\\)%.*$", "", raw))
    text = "\n".join(lines)
    return {
        rule for rule, toggle in RULE_TOGGLE.items()
        if re.search(r"\\togglefalse\{" + toggle + r"\}", text)
    }


def check(pdf: str) -> list[str]:
    problems = []
    off = disabled_rules(pdf)
    reader = PdfReader(pdf)
    npages = len(reader.pages)
    headings = heading_pages(pdf)

    for n in range(1, npages + 1):
        cur = page_lines(pdf, n)
        if not cur:
            continue

        # R5: a page that opens mid-entry means the previous page split one.
        if n > 1:
            prev = page_lines(pdf, n - 1)
            opens_continuation = (
                not ENTRY_RE.match(cur[0])
                and cur[0].startswith("   ")
                and any(ENTRY_RE.match(l) for l in prev)
            )
            if opens_continuation and "R5" not in off:
                problems.append(
                    f"R5 p{n}: opens mid-entry -- {cur[0].strip()[:60]!r}"
                )

        # R6: a heading on this page with too little content beneath it.
        if "R6" in off:
            continue
        for title in headings.get(n, []):
            needle = title.strip()[:28]
            for i, line in enumerate(cur):
                if needle and needle in line:
                    if len(cur) - (i + 1) < MIN_LINES_UNDER_HEADING:
                        problems.append(
                            f"R6 p{n}: heading {title!r} stranded "
                            f"({len(cur) - (i + 1)} line(s) beneath it)"
                        )
                    break
    return problems


def main() -> int:
    args = sys.argv[1:]
    pdfs = args or sorted(str(p) for p in Path(".").glob("cv-*.pdf"))
    if not pdfs:
        print("No PDFs to check (build them first: make all)")
        return 0

    failed = False
    for pdf in pdfs:
        if not Path(pdf).exists():
            print(f"{pdf}: not built, skipping")
            continue
        problems = check(pdf)
        pages = len(PdfReader(pdf).pages)
        if problems:
            failed = True
            print(f"{pdf} ({pages}pp): {len(problems)} problem(s)")
            for p in problems:
                print(f"    {p}")
        else:
            off = disabled_rules(pdf)
            note = f" ({', '.join(sorted(off))} disabled by preset)" if off else ""
            print(f"{pdf} ({pages}pp): OK{note}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
