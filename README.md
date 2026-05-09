![Build Status](https://github.com/shabtastic/cv-that-is-awesome/actions/workflows/build.yml/badge.svg)

# Shabnam Hakimi — CV in LaTeX (Awesome-CV)

## Project Structure

```
cv/
├── cv.tex                      # Master file — all toggles and preamble patches live here
├── resume.tex                  # Shorter resume variant
├── awesome-cv.cls              # Awesome-CV class file
├── fonts/                      # SourceSans3 and Roboto TTF files (required by cls)
├── sections/
│   ├── education.tex
│   ├── experience.tex
│   ├── grants.tex
│   ├── talks.tex               # Uses cventries (not cvhonors) — see Talks section below
│   ├── teaching.tex
│   ├── service.tex
│   ├── reviewer.tex
│   ├── mentorship.tex
│   └── memberships.tex
├── refs/
│   ├── journals.bib            # @article entries (peer-reviewed journals)
│   ├── preprints.bib           # @unpublished entries
│   ├── conference.bib          # @inproceedings entries
│   ├── presentations.bib       # @misc entries (selected conference presentations)
│   ├── patents.bib             # @patent entries
│   └── scicomm.bib             # @misc entries (science communication)
└── scripts/
    ├── _shared.py              # Shared utilities (manual fingerprints, dedup logic)
    ├── update_refs.py          # Master orchestrator — runs all fetch scripts + dedup
    ├── fetch_orcid.py          # Fetch publications from ORCID
    ├── fetch_pubmed.py         # Fetch publications from PubMed
    ├── fetch_patents.py        # Fetch/discover patents from USPTO (interactive)
    ├── fetch_scholar.py        # Google Scholar fetch (optional; see note below)
    ├── add_ref.py             # Add a single reference manually (interactive)
    └── review_bib.py          # Review and edit entries in an existing .bib file
```

---

## First-Time Setup

### 1. Install LaTeX
Requires **TeX Live 2022+** or **MiKTeX** with XeLaTeX and the following packages:
`biblatex`, `biber`, `etoolbox`, `fontspec`, `fontawesome5`, `geometry`, `parskip`

### 2. Fonts
The cls expects TTF files in a `fonts/` directory alongside `cv.tex`:

| File | Used for |
|---|---|
| `SourceSans3-Regular.ttf` (+ Bold, Italic, BoldItalic, Light, LightItalic, SemiBold, SemiBoldItalic) | Header / name |
| `Roboto-Regular.ttf` (+ Bold, Italic, BoldItalic, Thin, Light, Medium) | Body text |

Download SourceSans3 from [adobe-fonts/source-sans](https://github.com/adobe-fonts/source-sans/releases)
and Roboto from [Google Fonts](https://fonts.google.com/specimen/Roboto).

### 3. Install Python dependencies
```bash
make setup                    # installs requests, bibtexparser, pytest
pip install scholarly         # optional — for Google Scholar fetching
```
`make check-deps` verifies the required deps are importable before a run.

### 4. Configure scripts
Edit the `CONFIG` block at the top of each fetch script:

**`scripts/fetch_orcid.py`**
```python
ORCID_ID = "0000-0003-4122-6041"
```

**`scripts/fetch_pubmed.py`**
```python
PUBMED_AUTHOR = "Hakimi S"
ADMIN_EMAIL   = "you@example.com"   # required by NCBI policy
```

**`scripts/fetch_patents.py`** — requires a free USPTO Open Data Portal API key:
1. Register at [developer.uspto.gov](https://developer.uspto.gov) → "Sign Up"
2. After logging in, go to **My Account → API Keys** and generate a key
3. Add it to your shell profile so it persists across sessions:
   ```bash
   echo 'export USPTO_API_KEY="your_key_here"' >> ~/.zshrc
   source ~/.zshrc
   ```
   > The script reads `os.environ["USPTO_API_KEY"]` at runtime and exits with a clear error if it is not set.

---

## Building the CV

### One-command build:
```bash
make
```
> ⚠️ The `Makefile` references `main.tex` — update it to `cv.tex` if you haven't already.

### Manual build sequence:
```bash
xelatex cv.tex
biber cv
xelatex cv.tex
xelatex cv.tex
```

### Clean auxiliary files:
```bash
make clean
# or manually:
rm -f cv.aux cv.bbl cv.bcf cv.blg cv.log cv.out cv.run.xml cvbibcounts.tex
```

> ⚠️ Awesome-CV requires **XeLaTeX**, not pdflatex or lualatex.

---

## Toggle Reference

All toggles are set near the top of `cv.tex`. Flip `true`/`false` to show or hide sections
and control filtering.

### Section visibility

| Toggle | Default | Effect |
|---|---|---|
| `showJournals` | `true` | Peer-reviewed journal publications |
| `showPreprints` | `true` | Preprints & working papers |
| `showConferenceProceedings` | `true` | Conference proceedings |
| `showConferencePresentations` | `true` | Selected conference presentations |
| `showPatents` | `true` | Patents section |
| `showSciComm` | `true` | Science communication subsection |
| `showBookChapters` | `true` | Book chapters (if any) |
| `showTalks` | `true` | Invited talks subsection |
| `showGrants` | `true` | Grants & Awards section |
| `showTeaching` | `true` | Teaching section |
| `showService` | `true` | Professional Service section |
| `showReviewer` | `true` | Reviewing section |
| `showMentorship` | `true` | Mentorship section |
| `showMemberships` | `true` | Memberships section |
| `showReferences` | `true` | References section |
| `showFullReferences` | `false` | `true` = list referees; `false` = "Available upon request" |
| `showFullCVNote` | `false` | `true` = closing line "Full CV available upon request." (industry/speaking presets) |

### Selected-only filtering

When a `selectedOnly` toggle is true, only `.bib` entries with `keywords = {selected}` appear.

| Toggle | Default | Effect |
|---|---|---|
| `selectedOnlyPublications` | `false` | Changes section heading to "Selected Publications" |
| `selectedOnlyJournals` | `false` | Filter journals to `keywords={selected}` only |
| `selectedOnlyPreprints` | `false` | Filter preprints |
| `selectedOnlyConferenceProceedings` | `false` | Filter conference proceedings |
| `selectedOnlyPresentations` | `true` | Filter presentations |
| `selectedOnlyPatents` | `false` | Filter patents (mirrors `\patentFilter`) |

### Show-all overrides
For sections that default to a curated subset:

| Toggle | Default | Effect |
|---|---|---|
| `showAllTalks` | `false` | `true` = show all talks; `false` = "Selected Invited Talks" |
| `showAllGrants` | `false` | `true` = show all grants |
| `showAllTeaching` | `false` | `true` = show all teaching entries |
| `showAllService` | `false` | `true` = show all service entries |

### Bibliography numbering

| Toggle | Default | Effect |
|---|---|---|
| `showBibNumbers` | `true` | Show [1], [2], … labels before each entry |
| `reverseBibNumbers` | `false` | `true` = N…1 (most recent first); `false` = 1…N |

### Patent filter
Patents use a separate `\def` rather than a toggle:
```latex
\def\patentFilter{selected}   % only keywords={selected} entries
\def\patentFilter{all}        % all entries
```

---

## Marking Entries

### Selected entries
Add `keywords = {selected}` to any `.bib` entry to include it in filtered views:
```bibtex
@article{Hakimi2021pairing,
  ...
  keywords = {selected},
}
```
Multiple keywords are comma-separated: `keywords = {selected, manual}`.

### Manual / protected entries
Add `keywords = {manual}` (or include `manual` among other keywords) to prevent
the deduplicator and fetch scripts from ever removing or overwriting that entry:
```bibtex
@article{Hakimi2015enhanced,
  ...
  keywords = {manual, selected},
}
```
Manual entries take priority over auto-fetched entries in all deduplication conflicts.

### Keyword tagging during interactive review
Press `[k]` at any prompt during interactive review to add or edit keyword tags
on the current entry before accepting or marking it. Tags are comma-separated;
`manual` is always preserved when already present. Leave blank to keep existing
tags, or enter `-` to clear all non-`manual` tags.

```
  Current keywords: (none)
  Add tags (comma-separated). Leave blank to keep current. Enter - to clear.
  Tags: selected, highlight
```

After tagging the entry is re-displayed so you can confirm before accepting.



---

## Bolding Your Name in References

Name bolding is handled automatically by the `boldifown` name formatter defined
in the `cv.tex` preamble. No manual `.bib` edits needed for standard entries.

For entries with complex or non-standard author lists (e.g. equal contributions,
consortium papers), use the `usera` field to supply a pre-formatted author string:

```bibtex
@article{Hakimi2021pairing,
  author = {Hakimi, Shabnam and Sinclair, Adrienne H. and ...},
  usera  = {\cvbibname{Hakimi,~S}\cvfnmark{equalcontrib},
             Sinclair,~AH\cvfnmark{equalcontrib}, Stanley,~M, ...},
  ...
}
```

- `\cvbibname{...}` — renders the name in bold (same weight as the auto-bold formatter)
- `\cvfnmark{equalcontrib}` — renders a superscript `*`
- When `usera` is present it replaces the normal `\printnames{author}` output entirely
- When absent, `\printnames{author}` runs normally with `boldifown` applied

The `*` legend is printed once below the Publications section heading via `\cvpublegend`.

---

## Talks Section

`sections/talks.tex` uses `cventries` / `cventry` (not `cvhonors`).
This keeps the left margin aligned with all other sections.

Field mapping:
```
\cventry
  {Talk title in quotes}   % position field → appears on row 2, left
  {Venue name}             % title field    → appears on row 1, left (bold)
  {City, State}            % location field → appears on row 1, right (italic)
  {Year}                   % date field     → appears on row 2, right (italic)
  {}                       % description   → empty
```

---

## Updating References

### Fetch from all sources (ORCID + PubMed + Scholar) then dedup:
```bash
python scripts/update_refs.py
make fetch            # equivalent via Makefile
```

### Dry run — preview without writing:
```bash
python scripts/update_refs.py --dry-run
make fetch-dry
```

### Fetch from specific sources only:
```bash
python scripts/update_refs.py --sources orcid pubmed
```

### Deduplicate only (no network fetch):
```bash
python scripts/update_refs.py --dedup-only
make dedup
```

### Patents — manual step required:
The patent fetch script is interactive and must be run separately.
Requires `USPTO_API_KEY` to be set in your environment (see [First-Time Setup](#4-configure-scripts) above).
```bash
python scripts/fetch_patents.py               # refresh known patents from USPTO
python scripts/fetch_patents.py --mode discover  # search for new patents by inventor name
python scripts/fetch_patents.py --dry-run     # preview changes
```

---

## Reviewing Skipped & Rejected Entries

Before the interactive review loop, each fetch script silently filters entries
in three categories. Two flags let you inspect and correct these filters.

### What gets silently filtered

| Filter | Matched by | Stored in |
|---|---|---|
| Already in `.bib` | DOI, PMID, or normalised title | The `.bib` file |
| Matches a `manual` fingerprint | cite key, DOI, PMID, or title | Entries with `keywords={manual}` |
| Previously rejected | DOI, PMID, or normalised title | `refs/.<source>_rejected.json` |

### `--show-skipped` — audit what was filtered and why

Prints a tagged line for every filtered entry during a normal fetch run:

```
[skip-exist]    10.1038/s41562-021-01234-5 already in refs/journals.bib
[skip-manual]   Hakimi2019reward matches a protected manual entry
[skip-rejected] 34127854: Neural correlates of adaptive learning...
```

Works per-source or across all sources:
```bash
python scripts/update_refs.py --show-skipped
python scripts/fetch_pubmed.py --show-skipped
```

### `--review-rejected` — triage the rejection list interactively

Loads each source's `refs/.<source>_rejected.json` and presents entries one by
one. For each you can keep it rejected or un-reject it (remove from the list).
Un-rejected entries will reappear as candidates on the next normal fetch run.

```bash
# Review rejection lists for all sources
python scripts/update_refs.py --review-rejected

# Review a single source
python scripts/update_refs.py --review-rejected pubmed
python scripts/fetch_orcid.py --review-rejected
python scripts/fetch_scholar.py --review-rejected

# Preview without writing changes
python scripts/update_refs.py --review-rejected --dry-run
```

> **Tip:** If you mis-rejected something, run `--review-rejected` to un-reject
> it, then run a normal fetch to pull it back in for interactive review.

---

## Adding a Reference Manually

Use `add_ref.py` to add a single entry to any `.bib` file without running a
full fetch. The entry is always written with at least `keywords = {manual}` so
it is protected from deduplication.

### Input modes

| Mode | Flag | Description |
|---|---|---|
| DOI lookup | `--doi DOI` | Fetches metadata from Crossref, opens in `$EDITOR` |
| PMID lookup | `--pmid PMID` | Fetches metadata from PubMed, opens in `$EDITOR` |
| Manual entry | `--manual` | Opens a blank BibTeX template in `$EDITOR` |
| Fully interactive | _(no flag)_ | Prompts for mode and `.bib` file interactively |

### Examples

```bash
# Fully interactive — prompts for mode, bib file, editor, and tags
python scripts/add_ref.py

# Pre-fill from Crossref by DOI
python scripts/add_ref.py --doi 10.1038/s41562-021-01234-5

# Pre-fill from PubMed by PMID
python scripts/add_ref.py --pmid 34127854

# Open a blank template; write to a specific bib file
python scripts/add_ref.py --manual --bib refs/conference.bib

# Preview without writing
python scripts/add_ref.py --doi 10.1038/s41562-021-01234-5 --dry-run
```

After editing in `$EDITOR` (fallback: `nano`), you are prompted for keyword
tags. `manual` is always included automatically. Supported target `.bib` files:
`journals.bib`, `preprints.bib`, `conference.bib`, `presentations.bib`,
`scicomm.bib`, `patents.bib`.

---

## Reviewing an Existing .bib File

Use `review_bib.py` to walk through entries already in a `.bib` file and edit,
re-tag, or delete them interactively. This is separate from the fetch pipeline —
it operates purely on what is already on disk.

### Actions

| Key | Action |
|---|---|
| `e` | Open entry in `$EDITOR`; re-display after saving |
| `k` | Add/edit keyword tags interactively; re-display |
| `m` | Toggle `manual` on/off in keywords; re-display |
| `d` | Mark for deletion (confirmed as a batch before writing) |
| `s` | Skip — leave unchanged, move to next entry |
| `o` | Open DOI in browser (shown only when entry has a DOI field) |
| `q` | Stop reviewing; write all changes made so far |

`e`, `k`, and `m` re-display the entry after acting so you can keep editing
before moving on. Deletions are collected and shown as a confirmation summary
before anything is written. Every write is preceded by a timestamped `.bak`
backup of the original file.

### Examples

```bash
# Review all entries in a bib file
python scripts/review_bib.py refs/journals.bib

# Review only entries tagged 'selected'
python scripts/review_bib.py refs/conference.bib --filter selected

# Resume after quitting at entry 12
python scripts/review_bib.py refs/journals.bib --start 12

# Preview changes without writing
python scripts/review_bib.py refs/preprints.bib --dry-run
```

All six `.bib` files are supported: `journals.bib`, `preprints.bib`,
`conference.bib`, `presentations.bib`, `scicomm.bib`, `patents.bib`.

---

## Google Scholar

Google Scholar blocks automated scraping. `fetch_scholar.py` will:
- **Skip silently** with a helpful message if `scholarly` is not installed (exit 0)
- **Attempt a fetch** if `scholarly` is installed
- **Warn and exit cleanly** (exit 0) if Scholar rate-limits or blocks the request,
  so it never causes `update_refs.py` to report a hard error

To reduce rate-limit risk, set a ScraperAPI key in `fetch_scholar.py`:
```python
SCRAPER_API_KEY = "your_key_here"
```

For a reliable manual alternative:
1. Go to your Google Scholar profile
2. Select all publications → Export → BibTeX
3. Append to the appropriate `.bib` file and add `keywords = {manual}`
4. Run `python scripts/update_refs.py --dedup-only` to remove any duplicates

---

## How `_shared.py` Works

`scripts/_shared.py` contains utilities shared across all fetch scripts:

- **`load_manual_fingerprints(bib_path)`** — reads a `.bib` file and returns a
  dict of `{keys, dois, pmids, titles}` for all `keywords={manual}` entries
- **`fingerprint_matches(entry, fp)`** — returns `True` if a candidate fetched entry
  matches any manual fingerprint (by cite key, DOI, PMID, or title)
- **`is_manual(entry)`** — returns `True` if an entry's keywords contain `"manual"`
- **`interactive_review(candidates, rejected_file)`** — walks through candidate
  BibTeX entries with actions `a/e/k/m/r/s/o` (accept, edit, keywords, manual,
  reject+remember, skip, open DOI)
- **`review_rejected(rejected_file)`** — interactively triages a rejection list;
  un-rejected entries are removed from the JSON so they reappear on the next fetch
- **`prompt_keywords(current)`** / **`inject_keywords(bibtex, kw)`** —
  interactive keyword tagging helpers used by both the review loop and `add_ref.py`

Each fetch script imports these at startup:
```python
sys.path.insert(0, str(Path(__file__).parent))
from _shared import load_manual_fingerprints, fingerprint_matches
```
This ensures the functions are available whether scripts are run standalone
(`python scripts/fetch_orcid.py`) or as subprocesses via `update_refs.py`.

---

## Color Themes

Change `\colorlet{awesome}{...}` in `cv.tex` to one of:
`awesome-emerald`, `awesome-skyblue`, `awesome-red`, `awesome-pink`,
`awesome-orange`, `awesome-nephritis`, `awesome-concrete`, `awesome-darknight`

Or use a custom color:
```latex
\colorlet{awesome}{black}    % current setting — monochrome
```