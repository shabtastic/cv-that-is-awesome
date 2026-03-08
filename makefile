```makefile
# Makefile
# --------

.PHONY: all clean fetch

all:
  xelatex main.tex
  biber main
  xelatex main.tex
  xelatex main.tex

clean:
  rm -f *.aux *.bbl *.bcf *.blg *.log *.out *.run.xml *.toc

fetch:
  python scripts/update_refs.py

fetch-dry:
  python scripts/update_refs.py --dry-run

dedup:
  python scripts/update_refs.py --dedup-only
```