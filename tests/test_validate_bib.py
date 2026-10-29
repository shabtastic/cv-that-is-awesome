"""
Ensures scripts/validate_bib.py runs green on the real refs/*.bib corpus,
and verifies its failure modes. If this fails, either a .bib file has
drifted into an invalid shape, or the validator's rules have grown
out of sync with the corpus.
"""

import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
SCRIPT = REPO / "scripts" / "validate_bib.py"


def run(args, cwd=REPO):
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        cwd=cwd, capture_output=True, text=True,
    )


class TestRealCorpus:
    def test_runs_green(self):
        """The real refs/*.bib files validate with zero errors."""
        r = run([])
        assert r.returncode == 0, (
            f"validate_bib.py failed on real corpus:\n"
            f"--- stdout ---\n{r.stdout}\n--- stderr ---\n{r.stderr}"
        )
        assert "OK:" in r.stdout or "0 error" in r.stdout


class TestFailureModes:
    @pytest.fixture
    def bad_repo(self, tmp_path):
        """Synthetic mini-repo with scripts/ + refs/ + cv.tex."""
        (tmp_path / "refs").mkdir()
        # Copy the scripts dir so relative imports work
        import shutil
        shutil.copytree(REPO / "scripts", tmp_path / "scripts")
        (tmp_path / "cv.tex").write_text(
            r"\addbibresource{refs/ok.bib}" + "\n"
        )
        return tmp_path

    def test_missing_required_field(self, bad_repo):
        (bad_repo / "refs" / "ok.bib").write_text(
            "@article{k, title = {X}}\n"  # no author/year/journal
        )
        r = run(["--no-cvtex"], cwd=bad_repo)
        assert r.returncode == 1
        assert "missing required field 'author'" in r.stdout
        assert "missing required field 'year'" in r.stdout
        assert "missing required field 'journal'" in r.stdout

    def test_unbalanced_braces(self, bad_repo):
        (bad_repo / "refs" / "ok.bib").write_text(
            "@article{k, title = {X}, author = {A}, "
            "year = {2020}, journal = {J}}}"  # extra closing
        )
        r = run(["--no-cvtex"], cwd=bad_repo)
        assert r.returncode == 1
        assert "unbalanced braces" in r.stdout

    def test_duplicate_cite_key_across_files(self, bad_repo):
        entry = ("@article{dup2020, title={X}, author={A}, "
                 "year={2020}, journal={J}}\n")
        (bad_repo / "refs" / "ok.bib").write_text(entry)
        (bad_repo / "refs" / "other.bib").write_text(entry)
        r = run(["--no-cvtex"], cwd=bad_repo)
        assert r.returncode == 1
        assert "duplicate-key" in r.stdout
        assert "dup2020" in r.stdout

    def test_duplicate_doi_across_files(self, bad_repo):
        tmpl = textwrap.dedent("""
            @article{{{key},
              title = {{X}},
              author = {{A}},
              year = {{2020}},
              journal = {{J}},
              doi = {{10.1/abc}},
            }}
        """)
        (bad_repo / "refs" / "ok.bib").write_text(tmpl.format(key="a2020"))
        (bad_repo / "refs" / "other.bib").write_text(tmpl.format(key="b2020"))
        r = run(["--no-cvtex"], cwd=bad_repo)
        assert r.returncode == 1
        assert "duplicate-doi" in r.stdout

    def test_bib_on_disk_not_loaded_in_cvtex(self, bad_repo):
        # ok.bib is loaded, orphan.bib is not
        (bad_repo / "refs" / "ok.bib").write_text(
            "@article{a, title={X}, author={A}, year={2020}, journal={J}}\n"
        )
        (bad_repo / "refs" / "orphan.bib").write_text(
            "@article{b, title={Y}, author={B}, year={2021}, journal={K}}\n"
        )
        r = run([], cwd=bad_repo)
        assert r.returncode == 1
        assert "orphan.bib" in r.stdout
        assert "NOT loaded" in r.stdout

    def test_cvtex_points_to_nonexistent_file(self, bad_repo):
        (bad_repo / "refs" / "ok.bib").write_text(
            "@article{a, title={X}, author={A}, year={2020}, journal={J}}\n"
        )
        (bad_repo / "cv.tex").write_text(
            r"\addbibresource{refs/ok.bib}" + "\n"
            r"\addbibresource{refs/ghost.bib}" + "\n"
        )
        r = run([], cwd=bad_repo)
        assert r.returncode == 1
        assert "ghost.bib" in r.stdout
        assert "does not exist" in r.stdout

    def test_bad_doi_is_warning_not_error(self, bad_repo):
        (bad_repo / "refs" / "ok.bib").write_text(
            "@article{a, title={X}, author={A}, year={2020}, "
            "journal={J}, doi={not-a-doi}}\n"
        )
        r = run(["--no-cvtex"], cwd=bad_repo)
        # Bad DOI is a warning, not an error -- exit 0
        assert r.returncode == 0
        assert "WARN" in r.stdout
        assert "DOI" in r.stdout

    def test_presentations_require_keyword(self, bad_repo):
        # An @unpublished entry in presentations.bib without
        # keywords={presentation} silently fails to render.
        (bad_repo / "refs" / "presentations.bib").write_text(
            "@unpublished{talk2020, title={Talk}, author={A}, year={2020}}\n"
        )
        (bad_repo / "cv.tex").write_text(
            r"\addbibresource{refs/presentations.bib}" + "\n"
        )
        r = run([], cwd=bad_repo)
        assert r.returncode == 1
        assert "keywords={presentation}" in r.stdout

    # -- chronological order ------------------------------------------------
    # cv.tex uses sorting=none, so file order is CV order. An inversion is a
    # visible defect in the rendered CV, so it fails the run (and CI).

    def _write_talks(self, repo, *entries):
        body = "\n\n".join(
            "@unpublished{%s, title={T}, author={A}, year={%d},%s"
            " keywords={presentation}}" % (k, y, f" month={m}," if m else "")
            for k, y, m in entries
        )
        (repo / "refs" / "presentations.bib").write_text(body + "\n")
        (repo / "cv.tex").write_text(
            r"\addbibresource{refs/presentations.bib}" + "\n"
        )

    def test_year_inversion_is_an_error(self, bad_repo):
        self._write_talks(bad_repo, ("old", 2019, None), ("new", 2024, None))
        r = run([], cwd=bad_repo)
        assert r.returncode == 1
        assert "ERROR   presentations.bib:order" in r.stdout

    def test_month_inversion_within_a_year_is_caught(self, bad_repo):
        self._write_talks(bad_repo, ("may", 2026, "may"), ("oct", 2026, "oct"))
        r = run([], cwd=bad_repo)
        assert r.returncode == 1
        assert "oct" in r.stdout and "presentations.bib:order" in r.stdout

    def test_year_only_entry_beside_dated_ones_is_not_an_inversion(self, bad_repo):
        self._write_talks(
            bad_repo, ("jan", 2026, "jan"), ("noyearmonth", 2026, None),
            ("dec25", 2025, "dec"),
        )
        r = run([], cwd=bad_repo)
        assert r.returncode == 0, r.stdout
        assert ":order" not in r.stdout

    def test_newest_first_with_months_passes(self, bad_repo):
        self._write_talks(bad_repo, ("oct", 2026, "oct"), ("may", 2026, "may"))
        r = run([], cwd=bad_repo)
        assert r.returncode == 0, r.stdout
