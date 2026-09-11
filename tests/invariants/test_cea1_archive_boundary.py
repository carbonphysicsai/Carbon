from pathlib import Path

import pytest

pytestmark = pytest.mark.invariant

ROOT = Path(__file__).resolve().parents[2]


def test_archive_does_not_own_science_finalization_network_or_settlement() -> None:
    source = (ROOT / "carbon/evidence_archive/service.py").read_text(encoding="utf-8")
    forbidden = (
        "carbon.chain",
        "carbon.scoring",
        "carbon.rewards",
        "carbon.leaderboard",
        "set_weights",
        "eligible_for_emission",
        "finalize_submission",
        "settlement",
    )
    assert all(value not in source for value in forbidden)


def test_synthetic_acknowledgement_is_structurally_ineligible_downstream() -> None:
    source = (ROOT / "carbon/evidence_archive/model.py").read_text(encoding="utf-8")
    assert "synthetic_only: bool = True" in source
    assert "eligible_for_real_finalization: bool = False" in source
    assert "eligible_for_network_use: bool = False" in source
    assert "qualification_origin is not QualificationOrigin.FIXTURE" in source


def test_c01_finalization_seam_remains_unimplemented_by_cea1() -> None:
    model = (ROOT / "carbon/execution/model.py").read_text(encoding="utf-8")
    assert "archive_acknowledgement_ref: None" in model
    assert "C_EA2_ACKNOWLEDGEMENT_REQUIRED" in model
    assert "evidence_archive" not in model


def test_archive_has_no_generic_history_deletion_or_persisted_key_value() -> None:
    combined = "\n".join(
        (ROOT / path).read_text(encoding="utf-8")
        for path in (
            "carbon/evidence_archive/model.py",
            "carbon/evidence_archive/service.py",
            "carbon/evidence_archive/storage.py",
        )
    )
    assert "def delete" not in combined
    assert "key_bytes" not in (ROOT / "carbon/evidence_archive/model.py").read_text(
        encoding="utf-8"
    )
    assert "INSERT INTO cea1_artifact VALUES" in combined
    assert "payload BLOB" not in combined


def test_profile_and_service_are_closed_to_synthetic_loopback_scope() -> None:
    model = (ROOT / "carbon/evidence_archive/model.py").read_text(encoding="utf-8")
    objects = (ROOT / "carbon/evidence_archive/object_service.py").read_text(
        encoding="utf-8"
    )
    assert 'SYNTHETIC_PROFILE_ID = "carbon.synthetic-evidence-archive.dev.v1"' in model
    assert "AdmissionKind.FIXTURE" in model
    assert '"127.0.0.1"' in objects
    assert "self.server.tenant_id" in objects
