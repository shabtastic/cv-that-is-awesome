"""
Tests for classify_app_status() in scripts/fetch_patents.py.

Background: --mode check-status originally decided "granted vs pending" purely
on record["patentNumber"]. ODP's applicationMetaData does not reliably populate
that field, so the granted branch could never fire and the mode reported "No
status changes found" as a false negative.

The authoritative signal is applicationStatusDescriptionText. The fixtures below
are the standard USPTO prosecution status strings ODP returns.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from fetch_patents import classify_app_status  # noqa: E402


def rec(status, **extra):
    return {"applicationStatusDescriptionText": status, **extra}


# ── granted ───────────────────────────────────────────────────────────────────

def test_patented_case_is_granted():
    state, num = classify_app_status(rec("Patented Case"))
    assert state == "granted"


def test_patented_case_without_patent_number_reports_none():
    """ODP can mark a case patented before it publishes the grant number."""
    state, num = classify_app_status(rec("Patented Case"))
    assert state == "granted"
    assert num is None


def test_patented_case_with_patent_number_returns_it():
    state, num = classify_app_status(rec("Patented Case", patentNumber=12345678))
    assert state == "granted"
    assert num == "12345678"


def test_patent_number_alone_is_still_granted():
    """Back-compat: if ODP ever does populate the number, trust it."""
    state, num = classify_app_status({"patentNumber": "11934476"})
    assert state == "granted"
    assert num == "11934476"


# ── allowed (issue imminent, not yet granted) ─────────────────────────────────

@pytest.mark.parametrize("status", [
    "Notice of Allowance Mailed -- Application Received in Office of Publications",
    "Publications -- Issue Fee Payment Verified",
    "Issue Fee Payment Received",
    "Application Is Considered Ready for Issue",
])
def test_allowance_states_are_allowed_not_granted(status):
    state, num = classify_app_status(rec(status))
    assert state == "allowed", f"{status!r} should be 'allowed', got {state!r}"
    assert num is None


# ── still in prosecution ──────────────────────────────────────────────────────

@pytest.mark.parametrize("status", [
    "Docketed New Case - Ready for Examination",
    "Non Final Action Mailed",
    "Final Rejection Mailed",
    "Response to Non-Final Office Action Entered and Forwarded to Examiner",
])
def test_prosecution_states_are_pending(status):
    state, num = classify_app_status(rec(status))
    assert state == "pending"
    assert num is None


# ── no data ───────────────────────────────────────────────────────────────────

def test_missing_record_is_unknown_not_pending():
    """A failed lookup must not be reported as a confident 'still pending'."""
    state, num = classify_app_status(None)
    assert state == "unknown"


def test_record_without_status_text_is_unknown():
    state, num = classify_app_status({})
    assert state == "unknown"


def test_status_matching_is_case_insensitive():
    state, _ = classify_app_status(rec("PATENTED CASE"))
    assert state == "granted"
