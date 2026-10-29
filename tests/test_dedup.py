"""
Tests for update_refs.dedup_bib_file().

cv.tex prints each .bib in file order, so dedup must only REMOVE the
duplicate entries -- never reorder, reformat, or rewrap the rest of the file.
(It used to re-serialize through bibtexparser's BibTexWriter, whose default
sorts entries alphabetically by cite key and turns % comments into @comment.)
"""

import re
import sys
import textwrap
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from update_refs import dedup_bib_file  # noqa: E402


HEADER = textwrap.dedent("""\
    %==========================================================================
    % JOURNALS -- keep NEWEST-FIRST
    %==========================================================================

    """)


def entry(key, doi=None, keywords=None, year=2020, extra=""):
    lines = [f"@article{{{key},", f"  title    = {{Title {key}}},",
             f"  year     = {{{year}}},"]
    if doi:
        lines.append(f"  doi      = {{{doi}}},")
    if keywords is not None:
        lines.append(f"  keywords = {{{keywords}}},")
    if extra:
        lines.append(extra)
    lines.append("}")
    return "\n".join(lines)


def write(tmp_path, *entries, header=HEADER):
    bib = tmp_path / "journals.bib"
    bib.write_text(header + "\n\n".join(entries) + "\n", encoding="utf-8")
    return bib


def keys(bib):
    return re.findall(r"@\w+\{([^,]+),", bib.read_text(encoding="utf-8"))


@pytest.fixture(autouse=True)
def _cwd(tmp_path, monkeypatch):
    # backup_bib() writes next to the file; keep everything inside tmp_path.
    monkeypatch.chdir(tmp_path)


class TestNoDuplicates:
    def test_file_is_untouched(self, tmp_path):
        bib = write(tmp_path, entry("z2026", year=2026), entry("a2001", year=2001))
        before = bib.read_bytes()
        assert dedup_bib_file(bib) == 0
        assert bib.read_bytes() == before


class TestRemovesOnlyTheDuplicate:
    def test_duplicate_key_keeps_order_and_header(self, tmp_path):
        survivors = [entry("z2026", year=2026), entry("m2020", year=2020),
                     entry("a2001", year=2001)]
        bib = write(tmp_path, survivors[0], survivors[1],
                    entry("m2020", year=2020), survivors[2])
        assert dedup_bib_file(bib) == 1
        # Exactly the original file minus the duplicate: newest-first order
        # (not alphabetical), header comment verbatim, formatting untouched.
        assert bib.read_text(encoding="utf-8") == \
            HEADER + "\n\n".join(survivors) + "\n"

    def test_duplicate_doi(self, tmp_path):
        bib = write(tmp_path, entry("z2026", doi="10.1/x", year=2026),
                    entry("other", doi="10.1/X", year=2010),
                    entry("a2001", year=2001))
        assert dedup_bib_file(bib) == 1
        assert keys(bib) == ["z2026", "a2001"]

    def test_fetched_copy_of_manual_entry_is_removed(self, tmp_path):
        bib = write(tmp_path, entry("hand", doi="10.1/m", keywords="manual"),
                    entry("fetched", doi="10.1/m"))
        assert dedup_bib_file(bib) == 1
        assert keys(bib) == ["hand"]

    def test_manual_entry_replaces_earlier_fetched_copy_in_place(self, tmp_path):
        bib = write(tmp_path, entry("new", year=2026),
                    entry("fetched", doi="10.1/m", year=2015),
                    entry("mid", year=2012),
                    entry("hand", doi="10.1/m", keywords="manual, selected",
                          year=2015),
                    entry("old", year=2001))
        assert dedup_bib_file(bib) == 1
        assert keys(bib) == ["new", "mid", "hand", "old"]

    def test_manual_without_doi_replaces_only_its_own_copy(self, tmp_path):
        # Regression: the old replace filter compared doi == doi, so a manual
        # entry with no DOI also wiped every earlier entry with no DOI.
        bib = write(tmp_path, entry("k"), entry("nodoi1"), entry("nodoi2"),
                    entry("k", keywords="manual"))
        assert dedup_bib_file(bib) == 1
        assert keys(bib) == ["nodoi1", "nodoi2", "k"]

    def test_two_manual_duplicates_are_both_kept(self, tmp_path, capsys):
        # CLAUDE.md: keywords={manual} entries are protected from dedup.
        # Two hand-entered copies is for a human to resolve, so warn loudly.
        bib = write(tmp_path, entry("hand1", doi="10.1/m", keywords="manual"),
                    entry("mid"),
                    entry("hand2", doi="10.1/m", keywords="manual"))
        before = bib.read_bytes()
        assert dedup_bib_file(bib) == 0
        assert bib.read_bytes() == before
        out = capsys.readouterr().out
        assert "hand2" in out and "hand1" in out and "keeping both" in out

    def test_manual_replacing_two_copies_counts_both(self, tmp_path):
        bib = write(tmp_path, entry("k"), entry("other", doi="10.1/d"),
                    entry("keep"),
                    entry("k", doi="10.1/d", keywords="manual"))
        assert dedup_bib_file(bib) == 2
        assert keys(bib) == ["keep", "k"]

    def test_doi_forms_are_normalized(self, tmp_path):
        bib = write(tmp_path, entry("a", doi="https://doi.org/10.1000/X"),
                    entry("b", doi="10.1000/x"))
        assert dedup_bib_file(bib) == 1
        assert keys(bib) == ["a"]

    def test_quoted_manual_keyword_is_recognised(self, tmp_path):
        bib = tmp_path / "journals.bib"
        bib.write_text(
            entry("fetched", doi="10.1/q") + "\n\n"
            '@article{hand,\n  title = {T},\n  year = {2020},\n'
            '  doi = "10.1/q",\n  keywords = "manual",\n}\n')
        assert dedup_bib_file(bib) == 1
        assert keys(bib) == ["hand"]

    def test_malformed_file_is_left_untouched(self, tmp_path):
        from _shared import BibParseError
        bib = write(tmp_path, entry("a"), entry("a"),
                    "@article{bad,\n  title = {Unclosed,\n}")
        before = bib.read_bytes()
        with pytest.raises(BibParseError):
            dedup_bib_file(bib)
        assert bib.read_bytes() == before

    def test_nested_braces_and_comments_between_entries_survive(self, tmp_path):
        tricky = entry("t", year=2024,
                       extra="  note     = {See {Appendix {A}} for details},")
        bib = write(tmp_path, tricky, "% a note between entries",
                    entry("t", year=2024), entry("a", year=2001))
        dedup_bib_file(bib)
        text = bib.read_text(encoding="utf-8")
        assert keys(bib) == ["t", "a"]
        assert "{See {Appendix {A}} for details}" in text
        assert "% a note between entries" in text
        assert "@comment" not in text


class TestDryRun:
    def test_dry_run_changes_nothing(self, tmp_path):
        bib = write(tmp_path, entry("a"), entry("a"))
        before = bib.read_bytes()
        assert dedup_bib_file(bib, dry_run=True) == 1
        assert bib.read_bytes() == before
