# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository purpose

LaTeX source for Shabnam Hakimi's CV, built on the Awesome-CV class. The same `cv.tex` produces three output flavors (full academic, industry, speaking) driven by toggles. Bibliographies are auto-fetched from ORCID, PubMed, USPTO, and (optionally) Google Scholar via the Python scripts in `scripts/`.

See `README.md` for the user-facing documentation (setup, toggle reference, script usage). This file captures the architectural details that aren't obvious from skimming.

## Build commands

```bash
make full        # cv-full.pdf       (all sections, unfiltered)
make industry    # cv-industry.pdf   (selected pubs, condensed)
make speaking    # cv-speaking.pdf   (talks emphasis)
make all         # all three
make clean       # removes *.aux/*.bbl/*.bcf/etc. AND all built PDFs
make fetch       # runs scripts/update_refs.py (ORCID+PubMed+Scholar)
make fetch-dry   # dry run
make dedup       # scripts/update_refs.py --dedup-only
make setup       # pip install requirements-dev.txt (requests, bibtexparser, pytest)
make check-deps  # verify Python deps are importable
make test        # pytest tests/
make validate    # scripts/validate_bib.py (static bib linter)
```

`make pdf` runs the core compile (`xelatex → biber → xelatex → xelatex`) against whatever `cv-preset.tex` currently holds. **XeLaTeX is required** — pdflatex/lualatex will break fontspec + Awesome-CV.

Single-file compile (bypassing make):
```bash
cp config/full.tex cv-preset.tex   # pick a preset
xelatex cv.tex && biber cv && xelatex cv.tex && xelatex cv.tex
```

CI (`.github/workflows/build.yml`) builds all three presets on every push to `main` and attaches the PDFs to a GitHub release tagged `cv-<sha>`.

## Preset architecture

`cv.tex` is the single master file. It declares every toggle with its default, then near the end does `\input{cv-preset}` to load overrides. The three `config/*.tex` files are preset override snippets; the Makefile's preset targets `cp config/<name>.tex cv-preset.tex` before running `pdf`.

- `cv-preset.tex` is **tracked in git** (not gitignored) so fresh clones compile cleanly. The Makefile overwrites it at build time, so expect it to be dirty after a build.
- The Makefile has a fallback rule that copies `config/full.tex` to `cv-preset.tex` if missing.
- **To add a new preset:** create `config/<name>.tex` mirroring the structure of `config/full.tex`, then add a `<name>:` target in the Makefile and a matching step in `.github/workflows/build.yml`.
- **To add a new toggle:** declare it with `\newtoggle{...}` and a default in `cv.tex` **before** the `\input{cv-preset}` line, then set it in each `config/*.tex`.

## LaTeX architecture — non-obvious bits

### Two-pass bibliography counter (`cvbibcounts.tex`)
`cv.tex` implements its own per-section bibliography numbering (supporting forward/reverse order) independent of biblatex's internal numbering. Each `\printbibliography` is wrapped in `\startbibsection{name}` / `\finishbibsection{name}`. `\finishbibsection` writes the section's entry count to `cvbibcounts.tex`, which the next compile reads back in. **Numbers are wrong on the first pass** — this is expected. `cvbibcounts.tex` is a build artifact but is explicitly listed in `.gitignore`.

### First-pass `.bbl` guard
`\printbibliography` is redefined to no-op until `cv.bbl` exists. This is why `xelatex` is allowed to fail on the first pass in CI (`|| true`) — without the guard, the first xelatex run writes a malformed `.bcf` that biber then refuses to process.

### Custom `status` field on patents
Biber drops unknown BibTeX fields by default, silently breaking any `\iffieldequalstr{status}{...}` test. `cv.tex` uses `\DeclareSourcemap` to copy the raw `status` value into the known `addendum` field at source-mapping time. Patent bibchecks (`grantedpatents`, `filedpatents`, etc.) test `addendum` for this reason. A `\DeclareFieldFormat[patent]{addendum}{}` suppresses the visible addendum on patents so it's filter-only.

### Own-name bolding
Name bolding is implemented by redefining the `default` biblatex name format inside `\AtBeginDocument` (so it fires after `standard.bbx` sets its defaults). `\cvownfamilyname` (set to `Hakimi`) controls who gets bolded. Entries whose `.bib` record uses the `usera` field bypass the formatter entirely — use `\cvbibname{...}` manually there (typical case: equal-contribution papers with `\cvfnmark{equalcontrib}`).

### `cventry` spacing
`cv.tex` patches `\cventry` via `\pretocmd` (not `\apptocmd`) and tracks whether the previous entry had bullets via the `prevhaddesc` bool. `cvitems` has large negative `\vspace` values (`-4.0mm`) tuned empirically to compensate for the way the environment interacts with `\cventry`'s tabular. Do not "clean up" these negative vspaces without rebuilding and visually verifying every section — comments in `cv.tex` flag this hazard.

### `talks.tex` uses `\cventry`, not `\cvhonors`
This is intentional, to keep the left margin aligned with other sections. Field mapping is documented in `README.md` § Talks.

## Reference data (`refs/`)

Split by entry type: `journals.bib` (@article), `preprints.bib` (@unpublished), `conference.bib` (@inproceedings), `presentations.bib` (@misc, selected talks), `patents.bib` (@patent), `scicomm.bib` (@misc, keyword=scicomm), `chapters.bib` (@incollection).

Two keywords carry semantics:
- `keywords = {manual}` — entry is protected from dedup + never overwritten by fetch scripts. Hand-added entries should always include this.
- `keywords = {selected}` — included when a `selectedOnly*` toggle is active. Use `keywords = {manual, selected}` to combine.

**When editing `.bib` files by hand**, prefer the interactive tools: `python scripts/review_bib.py refs/<file>.bib` (browse/edit/tag/delete) or `python scripts/add_ref.py --doi <DOI>` (new entry from Crossref). Both auto-apply `keywords = {manual}`.

## Scripts (`scripts/`)

`update_refs.py` orchestrates all fetchers and runs dedup. Each fetcher (`fetch_orcid.py`, `fetch_pubmed.py`, `fetch_scholar.py`, `fetch_patents.py`) silently filters out entries that (a) are already in the `.bib`, (b) match a `manual` fingerprint, or (c) appear in `refs/.<source>_rejected.json`. Use `--show-skipped` to audit what got filtered, `--review-rejected` to un-reject.

`fetch_patents.py` is **not** called by `update_refs.py` — it's interactive and requires `USPTO_API_KEY` in the environment. Run it manually. Three modes: `--mode refresh` (default, re-fetches all known patents), `--mode discover` (searches by inventor name for new ones), `--mode check-status` (scans Filed entries in `patents.bib`, queries USPTO by application number, and updates any that have been granted in-place).

All fetchers share `_shared.py` for manual-fingerprint loading, interactive review, and keyword prompting. When adding a new fetcher, import from `_shared` via the `sys.path.insert(0, str(Path(__file__).parent))` pattern at the top of the existing scripts so it works both standalone and as a subprocess of `update_refs.py`.

## When making changes

- **Toggle / preset changes:** update all three `config/*.tex` files as needed, and re-verify each preset builds (`make all`).
- **Changes to bibliography machinery in `cv.tex`:** rebuild twice (once to write `cvbibcounts.tex`, once to read it) and visually check the first and last entry of each subsection. Reverse-order mode (`reverseBibNumbers`) is the usual regression vector.
- **Spacing tweaks in `cv.tex`:** the negative-vspace values around `cvitems` and `\cventry` are load-bearing. Build and eyeball the Teaching and Service sections (densest `\cventry` blocks) after any change.
- **Verify what you changed matches what you intended** — this is a long single `cv.tex` file with many interacting patches; prefer surgical edits over rewrites.
