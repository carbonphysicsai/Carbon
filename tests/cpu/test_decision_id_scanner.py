"""Synthetic unit regressions for the decision-id invariant's parser.

The real repository invariant stays unmocked. These ordinary CPU tests use a
private scanner module and temporary record/source files to exercise parsing
and refusal behavior independently of the repository's current decisions.
"""

from __future__ import annotations

import importlib.util
import subprocess
from pathlib import Path

import pytest


@pytest.fixture(scope="module")
def scanner():
    root = Path(__file__).resolve().parents[1]
    path = root / "invariants" / "test_decision_ids_resolve.py"
    spec = importlib.util.spec_from_file_location("_decision_id_scanner_unit", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize(
    "text, expected, unresolved",
    [
        (
            "# See OWNER-BACKBONE-\n# CATALOG-01.",
            {"OWNER-BACKBONE-CATALOG-01"},
            set(),
        ),
        (
            "(OWNER-BACKBONE-\r\n    # CATALOG-01).",
            {"OWNER-BACKBONE-CATALOG-01"},
            set(),
        ),
        (
            "OWNER-\n    BACKBONE-\n    CATALOG-01",
            {"OWNER-BACKBONE-CATALOG-01"},
            set(),
        ),
        (
            "OWNER-HISTORICAL-\n# RECORD-01",
            {"OWNER-HISTORICAL-RECORD-01"},
            set(),
        ),
        (
            "OWNER-BACKBONE-\n# MISSING-01",
            {"OWNER-BACKBONE-MISSING-01"},
            {"OWNER-BACKBONE-MISSING-01"},
        ),
        ("CATALOG-01", {"CATALOG-01"}, {"CATALOG-01"}),
        (
            "# An unrelated NOTE-\n# CATALOG-01.",
            {"CATALOG-01"},
            {"CATALOG-01"},
        ),
        (
            "OWNER-BACKBONE-CATALOG-01\n# CATALOG-01",
            {"OWNER-BACKBONE-CATALOG-01", "CATALOG-01"},
            {"CATALOG-01"},
        ),
        (
            "OWNER-BACKBONE-\n\n# CATALOG-01",
            {"CATALOG-01"},
            {"CATALOG-01"},
        ),
    ],
)
def test_wrapped_ids_preserve_full_resolution_checks(
    tmp_path, monkeypatch, scanner, text, expected, unresolved
):
    decisions = tmp_path / "decisions"
    decisions.mkdir()
    for identity in ("OWNER-BACKBONE-CATALOG-01", "CATALOG-READINESS-01"):
        (decisions / f"2026-10-28-{identity}.md").write_text(f"# {identity}\n")
    monkeypatch.setattr(scanner, "ROOT", tmp_path)
    monkeypatch.setattr(scanner, "DECISIONS", decisions)
    monkeypatch.setattr(scanner, "HISTORY", tmp_path / "history.md")
    monkeypatch.setattr(scanner, "TICKETS", tmp_path / "tickets")
    scanner.HISTORY.write_text("OWNER-HISTORICAL-\nRECORD-01\n")
    source = tmp_path / "carbon" / "citation.py"
    source.parent.mkdir()
    source.write_text(text)

    def tracked_files(arguments, **kwargs):
        assert arguments == [
            "git",
            "-C",
            str(tmp_path),
            "ls-files",
            "-z",
            "--",
            *scanner.SCANNED,
        ]
        assert kwargs == {"capture_output": True, "check": True}
        return subprocess.CompletedProcess(arguments, 0, stdout=b"carbon/citation.py\0")

    monkeypatch.setattr(subprocess, "run", tracked_files)
    prefixes, pattern = scanner._pattern()
    assert {"OWNER", "CATALOG"} <= prefixes
    declared, cited = scanner._resolved(pattern), scanner._cited(pattern)
    assert set(cited) == expected
    assert set(cited) - declared == unresolved
    scan = {"declared": declared, "cited": cited}
    if unresolved:
        with pytest.raises(AssertionError, match="cited ids with no decision"):
            scanner.test_every_cited_id_resolves_or_is_listed(scan)
    else:
        scanner.test_every_cited_id_resolves_or_is_listed(scan)
