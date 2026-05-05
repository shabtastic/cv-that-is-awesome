"""
Tests for scripts/_shared.py — the module that underpins every .bib
mutation and every dedup decision in the fetch pipeline.

Scope is deliberately narrow: only stdlib + pytest. We never import a
fetcher module (they require `requests`), so these tests run anywhere
`python3 -m pytest` works.

What matters here is that the Tier 1 hardening fixes stay fixed:
  - title normalization has one canonical form used everywhere
  - brace extraction handles nested/multi-line BibTeX
  - atomic writes survive simulated rename failure
  - corrupted rejection JSON is moved aside, not silently swallowed
"""

import json
import os
import sys
import textwrap
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from _shared import (  # noqa: E402
    _extract_braced_field,
    _load_manual_fingerprints_regex,
    append_atomic,
    fingerprint_matches,
    inject_keywords,
    load_all_titles,
    load_existing_dois,
    load_rejected,
    normalize_doi,
    normalize_title,
    save_rejected,
    write_atomic,
)


# ---------------------------------------------------------------------------
# normalize_title
# ---------------------------------------------------------------------------

class TestNormalizeTitle:
    @pytest.mark.parametrize("raw, expected", [
        # Empty / whitespace
        ("", ""),
        ("   ", ""),
        # Plain ASCII
        ("A simple title", "a simple title"),
        # LaTeX braces, including nested
        ("{AI}-driven learning", "ai driven learning"),
        ("{{AI}-driven learning}", "ai driven learning"),
        ("{fMRI} of {Pten} variation", "fmri of pten variation"),
        # LaTeX commands
        (r"\emph{fMRI} of reward", "fmri of reward"),
        (r"\textbf{Bold} and \textit{italic}", "bold and italic"),
        # Unicode accents drop to ASCII
        ("résumé: a paper", "resume a paper"),
        ("naïve Bayes", "naive bayes"),
        # Punctuation becomes whitespace (does NOT fuse words)
        ("Adaptive Learning—Pt. 1", "adaptive learning pt 1"),
        ("Reward, motivation, & learning", "reward motivation learning"),
        # Multiple whitespace collapses
        ("foo    bar\n\tbaz", "foo bar baz"),
    ])
    def test_cases(self, raw, expected):
        assert normalize_title(raw) == expected

    def test_distinct_titles_stay_distinct(self):
        # Regression: punctuation-as-space must not fuse distinct titles.
        a = normalize_title("Learning part 1")
        b = normalize_title("Learning Pt. 1")
        c = normalize_title("Learningpt1")
        assert a == "learning part 1"
        assert b == "learning pt 1"
        assert a != b
        assert c == "learningpt1"
        assert a != c


# ---------------------------------------------------------------------------
# _extract_braced_field — brace-balanced BibTeX field extraction
# ---------------------------------------------------------------------------

class TestExtractBracedField:
    def test_simple(self):
        entry = "@article{k, title = {Hello world}, year = {2020}}"
        assert _extract_braced_field(entry, "title") == "Hello world"
        assert _extract_braced_field(entry, "year") == "2020"

    def test_nested_braces(self):
        # The canonical regression case: {{AI}-driven learning}
        entry = "@article{k, title = {{AI}-driven learning}, year = {2020}}"
        assert _extract_braced_field(entry, "title") == "{AI}-driven learning"

    def test_multiline(self):
        entry = textwrap.dedent("""
            @article{k,
              title = {Multi-line
                       title continues here},
              year = {2020},
            }
        """)
        got = _extract_braced_field(entry, "title")
        assert "Multi-line" in got and "continues here" in got

    def test_missing_field(self):
        entry = "@article{k, year = {2020}}"
        assert _extract_braced_field(entry, "title") == ""

    def test_case_insensitive_field_name(self):
        entry = "@article{k, Title = {Hi}}"
        assert _extract_braced_field(entry, "title") == "Hi"

    def test_field_name_word_boundary(self):
        # "booktitle" must not match when asked for "title"
        entry = "@inproceedings{k, booktitle = {Proc. X}, title = {Paper}}"
        assert _extract_braced_field(entry, "title") == "Paper"
        assert _extract_braced_field(entry, "booktitle") == "Proc. X"


# ---------------------------------------------------------------------------
# fingerprint_matches — cross-path consistency
# ---------------------------------------------------------------------------

@pytest.fixture
def manual_bib(tmp_path):
    bib = tmp_path / "manual.bib"
    bib.write_text(textwrap.dedent("""
        @article{foo2020,
          author   = {X, Y},
          title    = {{AI}-driven learning},
          doi      = {10.1/ABC},
          note     = {PMID: 12345},
          keywords = {manual},
        }
        @article{bar2021,
          author   = {A, B},
          title    = {résumé: a study},
          keywords = {manual},
        }
        @article{notmanual2022,
          author   = {C, D},
          title    = {Unrelated},
          keywords = {selected},
        }
    """))
    return bib


class TestFingerprintMatches:
    def test_stores_canonical_title(self, manual_bib):
        fp = _load_manual_fingerprints_regex(manual_bib)
        assert "ai driven learning" in fp["titles"]
        assert "resume a study" in fp["titles"]
        # Non-manual entry is excluded
        assert "unrelated" not in fp["titles"]

    def test_stores_lowercased_doi(self, manual_bib):
        fp = _load_manual_fingerprints_regex(manual_bib)
        assert "10.1/abc" in fp["dois"]

    def test_stores_pmid(self, manual_bib):
        fp = _load_manual_fingerprints_regex(manual_bib)
        assert "12345" in fp["pmids"]

    @pytest.mark.parametrize("candidate_title", [
        "AI-driven learning",          # same title, no braces
        "{AI}-driven learning",        # with braces
        "ai-driven learning",          # lowercase variant
    ])
    def test_title_variants_all_match(self, manual_bib, candidate_title):
        fp = _load_manual_fingerprints_regex(manual_bib)
        cand = {"ID": "new", "doi": "", "note": "", "title": candidate_title}
        assert fingerprint_matches(cand, fp) is True

    def test_doi_case_insensitive(self, manual_bib):
        fp = _load_manual_fingerprints_regex(manual_bib)
        cand = {"ID": "new", "doi": "10.1/ABC", "note": "", "title": ""}
        assert fingerprint_matches(cand, fp) is True

    def test_accent_match(self, manual_bib):
        fp = _load_manual_fingerprints_regex(manual_bib)
        cand = {"ID": "new", "doi": "", "note": "", "title": "resume: a study"}
        assert fingerprint_matches(cand, fp) is True

    def test_no_match(self, manual_bib):
        fp = _load_manual_fingerprints_regex(manual_bib)
        cand = {"ID": "new", "doi": "",
                "note": "", "title": "something totally different"}
        assert fingerprint_matches(cand, fp) is False

    def test_load_all_titles_agrees_with_manual_fp(self, manual_bib):
        # Both paths must normalize identically, or dedup silently fails.
        fp = _load_manual_fingerprints_regex(manual_bib)
        all_titles = load_all_titles([manual_bib])
        # load_all_titles includes all entries; manual fp is a subset.
        assert fp["titles"].issubset(all_titles)
        assert "unrelated" in all_titles  # non-manual included


# ---------------------------------------------------------------------------
# write_atomic / append_atomic
# ---------------------------------------------------------------------------

class TestAtomicWrites:
    def test_basic_write(self, tmp_path):
        p = tmp_path / "f.txt"
        write_atomic(p, "hello\n")
        assert p.read_text() == "hello\n"

    def test_creates_parent_dirs(self, tmp_path):
        p = tmp_path / "sub" / "nested" / "f.txt"
        write_atomic(p, "x")
        assert p.read_text() == "x"

    def test_overwrites(self, tmp_path):
        p = tmp_path / "f.txt"
        p.write_text("old")
        write_atomic(p, "new")
        assert p.read_text() == "new"

    def test_append_atomic(self, tmp_path):
        p = tmp_path / "f.txt"
        append_atomic(p, "a\n")
        append_atomic(p, "b\n")
        assert p.read_text() == "a\nb\n"

    def test_append_creates_file(self, tmp_path):
        p = tmp_path / "new.txt"
        append_atomic(p, "first")
        assert p.read_text() == "first"

    def test_rename_failure_preserves_original(self, tmp_path):
        """Simulated os.replace failure must not clobber the existing file
        or leak tempfiles in the parent directory."""
        p = tmp_path / "f.txt"
        p.write_text("original\n")

        with patch("os.replace", side_effect=OSError("simulated")):
            with pytest.raises(OSError):
                write_atomic(p, "NEW CONTENT")

        assert p.read_text() == "original\n"
        leftovers = [q.name for q in tmp_path.iterdir()
                     if q.name.startswith(".f.txt.")]
        assert leftovers == [], f"leaked tmp files: {leftovers}"

    def test_tmp_file_lands_in_same_dir(self, tmp_path):
        """A cross-filesystem tempfile would defeat atomic rename. Verify
        the tempfile's parent matches the target's parent before rename.
        """
        p = tmp_path / "f.txt"
        captured = {}

        real_replace = os.replace

        def spy(src, dst):
            captured["src_parent"] = Path(src).parent.resolve()
            captured["dst_parent"] = Path(dst).parent.resolve()
            real_replace(src, dst)

        with patch("os.replace", side_effect=spy):
            write_atomic(p, "x")

        assert captured["src_parent"] == captured["dst_parent"]


# ---------------------------------------------------------------------------
# load_rejected / save_rejected
# ---------------------------------------------------------------------------

class TestRejected:
    def test_missing_file_returns_empty(self, tmp_path):
        assert load_rejected(tmp_path / "nope.json") == {}

    def test_valid_roundtrip(self, tmp_path):
        p = tmp_path / "r.json"
        save_rejected(p, {"a": "b", "c": "d"})
        assert load_rejected(p) == {"a": "b", "c": "d"}

    def test_corrupted_json_moved_aside(self, tmp_path, capsys):
        p = tmp_path / "r.json"
        p.write_text("not valid json {{{")
        result = load_rejected(p)
        assert result == {}
        assert not p.exists(), "corrupted file should have been renamed"
        corrupt = [q for q in tmp_path.iterdir() if ".corrupt." in q.name]
        assert len(corrupt) == 1
        err = capsys.readouterr().err
        assert "unreadable" in err
        assert str(p) in err

    def test_wrong_toplevel_type(self, tmp_path, capsys):
        p = tmp_path / "r.json"
        p.write_text(json.dumps([1, 2, 3]))
        result = load_rejected(p)
        assert result == {}
        err = capsys.readouterr().err
        assert "not a JSON object" in err
        # Wrong-type file is NOT moved aside (still valid JSON); user
        # decides whether to fix or delete it.
        assert p.exists()


# ---------------------------------------------------------------------------
# inject_keywords
# ---------------------------------------------------------------------------

class TestNormalizeDoi:
    @pytest.mark.parametrize("raw, expected", [
        ("10.1234/abc", "10.1234/abc"),
        ("10.1234/ABC", "10.1234/abc"),
        ("  10.1234/abc  ", "10.1234/abc"),
        ("https://doi.org/10.1234/abc", "10.1234/abc"),
        ("http://doi.org/10.1234/abc", "10.1234/abc"),
        ("https://dx.doi.org/10.1234/abc", "10.1234/abc"),
        ("doi.org/10.1234/abc", "10.1234/abc"),
        ("doi:10.1234/abc", "10.1234/abc"),
        ("DOI:10.1234/ABC", "10.1234/abc"),
        ("", ""),
        ("   ", ""),
        (None, ""),
    ])
    def test_cases(self, raw, expected):
        assert normalize_doi(raw) == expected

    def test_load_existing_dois_deduplicates_across_forms(self, tmp_path):
        # A .bib with mixed URL-prefix and bare DOIs should dedup identically.
        bib = tmp_path / "mixed.bib"
        bib.write_text(textwrap.dedent("""
            @article{a, doi = {10.1/abc}, title={T1}}
            @article{b, doi = {https://doi.org/10.2/def}, title={T2}}
            @article{c, doi = {DOI:10.3/GHI}, title={T3}}
        """))
        dois = load_existing_dois(bib)
        assert dois == {"10.1/abc", "10.2/def", "10.3/ghi"}

    def test_load_existing_dois_handles_list(self, tmp_path):
        a = tmp_path / "a.bib"
        b = tmp_path / "b.bib"
        a.write_text("@article{x, doi={10.1/a}}")
        b.write_text("@article{y, doi={10.2/b}}")
        assert load_existing_dois([a, b]) == {"10.1/a", "10.2/b"}

    def test_load_existing_dois_missing_file(self, tmp_path):
        assert load_existing_dois(tmp_path / "nope.bib") == set()


class TestInjectKeywords:
    def test_replaces_existing(self):
        bib = "@article{k, title = {X}, keywords = {old}, }"
        out = inject_keywords(bib, "new")
        assert "keywords = {new}" in out
        assert "keywords = {old}" not in out

    def test_adds_when_missing(self):
        bib = "@article{k,\n  title = {X},\n}"
        out = inject_keywords(bib, "manual")
        assert "keywords = {manual}" in out

    def test_preserves_other_fields(self):
        bib = "@article{k, author = {X, Y}, title = {T}, keywords = {old}}"
        out = inject_keywords(bib, "new, manual")
        assert "author = {X, Y}" in out
        assert "title = {T}" in out
