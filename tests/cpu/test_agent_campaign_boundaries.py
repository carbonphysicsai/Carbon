"""Research checkouts, canaries and the Level-0 study sheet."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from carbon.agent_campaign import boundaries as b
from carbon.agent_campaign import study
from carbon.challenge_readiness import admission

REPOSITORY = Path(__file__).resolve().parents[2]
SHEET = REPOSITORY / "docs/development/mira/level0"


@pytest.mark.parametrize("role", sorted(b.AGENT_ROLES, key=lambda r: r.value))
def test_each_role_checkout_holds_only_its_allowlist(tmp_path, role):
    manifest = b.checkout_manifest(REPOSITORY, role)
    digest = b.materialize(REPOSITORY, manifest, tmp_path / "checkout")
    copied = sorted(
        str(p.relative_to(tmp_path / "checkout"))
        for p in (tmp_path / "checkout").rglob("*")
        if p.is_file()
    )
    assert copied == sorted(b.ALLOWLIST[role])
    assert digest == b.manifest_digest(manifest)
    assert not any("evidence" in p or "ev4" in p.lower() for p in copied)


def test_evaluation_material_is_never_checked_out():
    with pytest.raises(b.BoundaryError, match="evaluation_material"):
        b.checkout_manifest(REPOSITORY, b.Role.EVALUATION)


@pytest.mark.parametrize(
    "path",
    [
        "docs/development/evidence/ev2-2026-10-01/results.json",
        ".agent/DECISIONS.md",
        "carbon/battery/value/ev4_protected_conditions.py",
        "carbon/agent_campaign/controller.py",
        "../outside.txt",
        "/etc/passwd",
    ],
)
def test_denied_and_escaping_paths_are_refused(path):
    with pytest.raises(b.BoundaryError):
        b.checkout_manifest(REPOSITORY, b.Role.CONSTRUCTION, paths=[path])


def test_symlinks_and_unlisted_files_are_refused(tmp_path):
    repository = tmp_path / "repo"
    (repository / "public").mkdir(parents=True)
    (repository / "public" / "ok.py").write_text("x = 1\n")
    secret = tmp_path / "secret.txt"
    secret.write_text("CARBON-CANARY-" + "0" * 32)
    os.symlink(secret, repository / "public" / "link.py")
    with pytest.raises(b.BoundaryError, match="symlink"):
        b.checkout_manifest(repository, b.Role.CONSTRUCTION, paths=["public/link.py"])
    manifest = b.checkout_manifest(
        repository, b.Role.CONSTRUCTION, paths=["public/ok.py"]
    )
    target = tmp_path / "t"
    target.mkdir()
    (target / "stale.txt").write_text("left over")
    with pytest.raises(b.BoundaryError, match="not_empty"):
        b.materialize(repository, manifest, target)
    (repository / "public" / "ok.py").write_text("x = 2\n")
    with pytest.raises(b.BoundaryError, match="digest_mismatch"):
        b.materialize(repository, manifest, tmp_path / "t2")


def test_canaries_are_detected_in_bytes_and_text(tmp_path):
    canaries = b.make_canaries(3)
    assert len(set(canaries)) == 3
    paths = b.plant(tmp_path / "trap", canaries)
    assert all(p.stat().st_mode & 0o777 == 0o600 for p in paths)
    assert b.exposed(b"nothing here", canaries) == []
    assert b.exposed("leaked " + canaries[1], canaries) == [canaries[1]]


def test_committed_study_sheet_is_prepared_not_frozen_or_executed():
    sheet = json.loads((SHEET / "study-sheet.json").read_text())
    assert sheet["state"] == "DRAFT_NOT_FROZEN" and sheet["executed"] is False
    assert set(sheet["pins"]) == admission.PIN_NAMES
    assert sheet["unpinned"] == ["budget", "population"]
    assert sheet["freezable"] is False
    assert set(sheet["checks"]) == admission.CHECKS[admission.LEDGER_TRACK]
    assert set(sheet["checks"].values()) == {"NOT_RUN"}
    assert {s["check"] for s in sheet["specimens"]} == set(sheet["checks"])
    assert sheet["attack_budget"]["monetary_ceiling"] == "HUMAN_INPUT"
    assert sheet["reconstruction"]["tolerances"] == "HUMAN_INPUT"
    assert not any(sheet["claims"].values())
    # An unfreezable sheet cannot satisfy the admission scope check.
    with pytest.raises(admission.AdmissionError, match="unpinned_scope"):
        admission._scope(
            {
                "challenge_id": study.CHALLENGE,
                "challenge_version": "1",
                "pins": sheet["pins"],
            },
            study.CHALLENGE,
        )


def test_committed_inventory_matches_the_live_construction_contract():
    written = json.loads((SHEET / "permission-inventory.json").read_text())
    assert written == study.permission_inventory()
    sheet = json.loads((SHEET / "study-sheet.json").read_text())
    assert sheet["pins"]["permissions"] == study._digest(written)
    assert written["submission_form"].startswith("declarative strategy only")
