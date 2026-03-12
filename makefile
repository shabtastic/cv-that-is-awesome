# Makefile
# --------

.PHONY: all clean fetch fetch-dry dedup

all:
  xelatex cv.tex
  biber cv
  xelatex cv.tex
  xelatex cv.tex

clean:
  rm -f cv.aux cv.bbl cv.bcf cv.blg cv.log cv.out cv.run.xml cv.toc cvbibcounts.tex

fetch:
  python scripts/update_refs.py

fetch-dry:
  python scripts/update_refs.py --dry-run

dedup:
  python scripts/update_refs.py --dedup-only