"""
Exercise the interactive-review paths of _shared.py and the add_ref.py
manual flow. These were previously only ever verified by hand.

We stub stdin via monkeypatching builtins.input so the tests run headless,
and stub $EDITOR via a tiny shell wrapper that writes a fixed bibtex blob.

Skips the add_ref.py test when `requests` is unavailable since the module
imports it at load time; the _shared.py tests don't need network deps.
"""

import os
import subprocess
import sys
import tempfile
import textwrap
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))

from _shared import interactive_review  # noqa: E402


# ---------------------------------------------------------------------------
# interactive_review
# ---------------------------------------------------------------------------

@pytest.fixture
def fake_input(monkeypatch):
    """Return a function that queues up a list of input() responses."""
    def _install(responses):
        it = iter(responses)
        monkeypatch.setattr(
            "builtins.input",
            lambda prompt="": next(it),
        )
    return _install


def candidate(bibtex, doi="10.1/x", reject_key=None, source="TEST"):
    return (bibtex, doi, reject_key or doi, source)


class TestInteractiveReview:
    def test_accept_path(self, tmp_path, fake_input):
        rj = tmp_path / "r.json"
        fake_input(["a"])
        accepted, rejected = interactive_review(
            [candidate("@article{k, title={T}, doi={10.1/x}, keywords={}}")],
            rj,
        )
        assert len(accepted) == 1
        assert rejected == {}

    def test_manual_path_injects_manual_keyword(self, tmp_path, fake_input):
        """Pressing 'm' must add keywords={manual} even if original was empty."""
        rj = tmp_path / "r.json"
        fake_input(["m"])
        accepted, _ = interactive_review(
            [candidate("@article{k, title={T}, doi={10.1/x}, keywords={}}")],
            rj,
        )
        assert "keywords = {manual}" in accepted[0]

    def test_manual_preserves_prior_keyword_edits(self, tmp_path, fake_input):
        """'k' to add 'selected', then 'm' must end with both tags."""
        rj = tmp_path / "r.json"
        # inputs: k (edit keywords), "selected" (new tag), m (mark manual)
        fake_input(["k", "selected", "m"])
        accepted, _ = interactive_review(
            [candidate("@article{k, title={T}, doi={10.1/x}, keywords={}}")],
            rj,
        )
        assert "keywords = {manual, selected}" in accepted[0]

    def test_reject_saves_with_title(self, tmp_path, fake_input):
        rj = tmp_path / "r.json"
        fake_input(["r", ""])  # reject + empty note
        accepted, new_rej = interactive_review(
            [candidate(
                "@article{k, title={Rejected paper}, doi={10.1/x}}",
                doi="10.1/x",
                reject_key="10.1/x",
            )],
            rj,
        )
        assert accepted == []
        assert new_rej == {"10.1/x": "Rejected paper"}

    def test_reject_with_note(self, tmp_path, fake_input):
        rj = tmp_path / "r.json"
        fake_input(["r", "wrong DOI from source"])
        _, new_rej = interactive_review(
            [candidate(
                "@article{k, title={Paper}, doi={10.1/x}}",
                reject_key="10.1/x",
            )],
            rj,
        )
        assert new_rej["10.1/x"].endswith("wrong DOI from source")

    def test_skip_leaves_both_empty(self, tmp_path, fake_input):
        rj = tmp_path / "r.json"
        fake_input(["s"])
        accepted, rejected = interactive_review(
            [candidate("@article{k, title={T}, doi={10.1/x}}")],
            rj,
        )
        assert accepted == [] and rejected == {}

    def test_previously_rejected_skipped_silently(
        self, tmp_path, fake_input, capsys,
    ):
        rj = tmp_path / "r.json"
        rj.write_text('{"10.1/x": "already rejected"}')
        fake_input([])  # no input needed — should auto-skip
        accepted, _ = interactive_review(
            [candidate("@article{k, title={T}, doi={10.1/x}}")],
            rj,
        )
        assert accepted == []
        assert "Previously rejected" in capsys.readouterr().out

    def test_keyword_edit_in_inner_loop(self, tmp_path, fake_input):
        """'k' then 'a' — keyword editor runs in the inner loop, then accept."""
        rj = tmp_path / "r.json"
        fake_input(["k", "selected", "a"])
        accepted, _ = interactive_review(
            [candidate("@article{k, title={T}, doi={10.1/x}, keywords={}}")],
            rj,
        )
        assert "keywords = {selected}" in accepted[0]

    def test_multiple_candidates(self, tmp_path, fake_input):
        rj = tmp_path / "r.json"
        fake_input(["a", "s", "m"])
        cands = [
            candidate("@article{a, title={A}, doi={10.1/a}}", doi="10.1/a",
                      reject_key="10.1/a"),
            candidate("@article{b, title={B}, doi={10.1/b}}", doi="10.1/b",
                      reject_key="10.1/b"),
            candidate("@article{c, title={C}, doi={10.1/c}, keywords={}}",
                      doi="10.1/c", reject_key="10.1/c"),
        ]
        accepted, _ = interactive_review(cands, rj)
        # a accepted, b skipped, c accepted as manual
        assert len(accepted) == 2
        assert "title={A}" in accepted[0] or "{A}" in accepted[0]
        assert "keywords = {manual}" in accepted[1]


# ---------------------------------------------------------------------------
# add_ref.py --manual end-to-end
# ---------------------------------------------------------------------------

pytest.importorskip("requests", reason="add_ref.py imports requests at load")


class TestAddRefManualFlow:
    @pytest.fixture
    def sandbox(self, tmp_path):
        """Isolated repo copy so writes don't mutate refs/."""
        import shutil
        for d in ("scripts", "refs"):
            shutil.copytree(REPO / d, tmp_path / d)
        (tmp_path / "cv.tex").write_text(
            r"\addbibresource{refs/journals.bib}" + "\n"
        )
        return tmp_path

    @pytest.fixture
    def fake_editor(self, tmp_path):
        """Script that writes a known BibTeX entry, ignoring existing
        file contents. Returns the path to the shell wrapper."""
        script = tmp_path / "fake-editor.sh"
        script.write_text(textwrap.dedent("""
            #!/bin/bash
            cat > "$1" <<'ENTRY'
            @article{Synth2099test,
              author   = {Test, Author and Hakimi, Shabnam},
              title    = {A synthetic entry for interactive testing},
              journal  = {Test Journal},
              year     = {2099},
              doi      = {10.1/synth-interactive},
              keywords = {},
            }
            ENTRY
        """).lstrip())
        script.chmod(0o755)
        return script

    def test_manual_flow_appends_via_atomic(self, sandbox, fake_editor):
        """Run add_ref.py --manual non-interactively and confirm the
        entry reaches refs/journals.bib through append_atomic, with
        keywords auto-injecting manual and leaving no tmp files."""
        bib = sandbox / "refs" / "journals.bib"
        before_bytes = bib.read_bytes()

        # Stdin: 1 (bib=journals.bib), "selected" (kw tags), y (write)
        # The template is inferred from the bib choice so no template prompt.
        result = subprocess.run(
            [sys.executable, "scripts/add_ref.py", "--manual"],
            cwd=sandbox,
            input="1\nselected\ny\n",
            capture_output=True,
            text=True,
            env={**os.environ, "EDITOR": str(fake_editor)},
            timeout=15,
        )
        assert result.returncode == 0, result.stderr or result.stdout

        after_bytes = bib.read_bytes()
        assert len(after_bytes) > len(before_bytes), "file did not grow"
        # Bytewise exact: file == original + appended block (no corruption)
        appended = after_bytes[len(before_bytes):].decode("utf-8")
        assert "Synth2099test" in appended
        assert "keywords = {manual, selected}" in appended
        assert "% --- manually added ---" in appended

        # No leftover atomic-write tempfiles
        leftovers = [
            p.name for p in (sandbox / "refs").iterdir()
            if p.name.startswith(".journals.bib.")
        ]
        assert leftovers == []
