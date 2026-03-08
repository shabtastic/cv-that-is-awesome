# Shabnam Hakimi — CV in LaTeX (Awesome-CV)

## Project Structure

```
cv/
├── main.tex                    # Master file — toggles live here
├── awesome-cv.cls              # Awesome-CV class (download separately)
├── fontawesome.sty             # Required by Awesome-CV
├── sections/
│   ├── education.tex
│   ├── experience.tex
│   ├── grants.tex
│   ├── talks.tex
│   ├── teaching.tex
│   └── service.tex             # Also contains reviewer section
├── refs/
│   ├── journals.bib            # @article entries
│   ├── preprints.bib           # @unpublished entries
│   ├── conference.bib          # @inproceedings entries
│   ├── patents.bib             # @patent entries
│   └── scicomm.bib             # @misc entries (keyword: scicomm)
└── scripts/
    ├── update_refs.py          # Master orchestrator
    ├── fetch_orcid.py          # Fetch from ORCID
    ├── fetch_pubmed.py         # Fetch from PubMed
    ├── fetch_patents.py        # Fetch from USPTO
    └── fetch_scholar.py        # (placeholder — see note below)
```

---

## First-Time Setup

### 1. Download Awesome-CV
```bash
git clone https://github.com/posquit0/Awesome-CV.git
cp Awesome-CV/awesome-cv.cls .
cp Awesome-CV/fontawesome.sty .   # if needed
```
Or download the `.cls` directly from the releases page.

### 2. Install LaTeX dependencies
Make sure you have:
- **TeX Live 2022+** or **MiKTeX** with:
  - `biblatex`, `biber`, `etoolbox`, `fontawesome`, `geometry`

### 3. Install Python dependencies
```bash
pip install bibtexparser requests scholarly habanero
```

### 4. Configure your ORCID iD
Edit `scripts/fetch_orcid.py`:
```python
ORCID_ID = "0000-XXXX-XXXX-XXXX"   # ← your ORCID
```

---

## Building the CV

### One-command build:
```bash
make
```

### Manual build sequence:
```bash
xelatex main.tex
biber main
xelatex main.tex
xelatex main.tex
```
> ⚠️ Awesome-CV requires **XeLaTeX**, not pdflatex.

---

## Toggle Reference

Edit the toggles at the top of `main.tex`:

| Toggle | Effect |
|---|---|
| `\toggletrue{showJournals}` | Show journal publications section |
| `\togglefalse{showPatents}` | Hide patents section entirely |
| `\toggletrue{selectedOnlyJournals}` | Show only `keywords={selected}` journal entries |
| `\toggletrue{selectedOnlyPatents}` | Show only `keywords={selected}` patent entries |
| `\togglefalse{showTalks}` | Hide invited talks |
| `\togglefalse{showTeaching}` | Hide teaching section |

---

## Marking Entries as "Selected"

In any `.bib` file, add `keywords = {selected}` to flag an entry:

```bibtex
@article{Hakimi2021pairing,
  ...
  keywords = {selected},
}
```

When `\toggletrue{selectedOnlyJournals}` is set in `main.tex`,
only entries with this keyword will appear.

---

## Bolding Your Name in References

Add this to `main.tex` preamble to bold "Hakimi, Shabnam" everywhere:

```latex
% Bold the CV author's name in all bibliography entries
\renewcommand*{\mkbibnamefamily}[1]{%
  \iffieldequalstr{hash}{YOUR_NAME_HASH}{%  (see biblatex docs)
    \textbf{#1}%
  }{#1}%
}
```

A simpler approach using `boldnames` package:
```latex
\usepackage{xpatch}
% After \addbibresource lines:
\DeclareNameFormat{author}{%
  \ifthenelse{\equal{\namepartfamily}{Hakimi}}{%
    \textbf{\namepartfamily\addcomma\space\namepartgiveni}%
  }{%
    \namepartfamily\addcomma\space\namepartgiveni%
  }%
  \ifthenelse{\value{listcount}<\value{liststop}}{\addcomma\space}{}%
}
```

---

## Updating References

### Fetch from all sources:
```bash
python scripts/update_refs.py
```

### Fetch from specific sources only:
```bash
python scripts/update_refs.py --sources orcid pubmed
python scripts/update_refs.py --sources patents
```

### Dry run (preview without writing):
```bash
python scripts/update_refs.py --dry-run
```

### Deduplicate only (no fetching):
```bash
python scripts/update_refs.py --dedup-only
```

---

## Google Scholar Note

The `scholarly` library (used for Google Scholar) has rate-limiting and
bot-detection issues. For manual Scholar exports:
1. Go to your Google Scholar profile
2. Select all → Export → BibTeX
3. Run `python scripts/update_refs.py --dedup-only` to deduplicate

---

## Color Themes

Change `\colorlet{awesome}{awesome-red}` in `main.tex` to one of:
`awesome-emerald`, `awesome-skyblue`, `awesome-red`, `awesome-pink`,
`awesome-orange`, `awesome-nephritis`, `awesome-concrete`, `awesome-darknight`

---
