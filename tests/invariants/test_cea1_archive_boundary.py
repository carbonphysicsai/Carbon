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


def test_alpha_profile_preparation_cannot_issue_ack_or_finalize() -> None:
    source = (ROOT / "carbon/evidence_archive/alpha_profile.py").read_text(
        encoding="utf-8"
    )
    assert 'ALPHA_PROFILE_ID = "carbon.alpha-evidence-archive.private.v1"' in source
    assert "acknowledgement_implemented: bool = False" in source
    assert "eligible_for_real_acknowledgement: bool = False" in source
    assert "eligible_for_c_ea2: bool = False" in source
    assert "ArchiveAcknowledgement" not in source
    assert "EvidenceArchive(" not in source
    assert "finalize_submission" not in source
    assert "carbon.chain" not in source


def test_alpha_provider_package_cannot_issue_ack_or_gain_network_authority() -> None:
    combined = "\n".join(
        (ROOT / path).read_text(encoding="utf-8")
        for path in (
            "carbon/evidence_archive/alpha_activation.py",
            "carbon/evidence_archive/alpha_capacity.py",
            "carbon/evidence_archive/alpha_package.py",
            "carbon/evidence_archive/alpha_recovery.py",
            "carbon/evidence_archive/aws_provider.py",
        )
    )
    assert "ArchiveAcknowledgement(" not in combined
    assert "eligible_for_real_acknowledgement: bool = False" in combined
    assert "eligible_for_c_ea2: bool = False" in combined
    assert "finalize_submission" not in combined
    assert "carbon.chain" not in combined
    assert "carbon.rewards" not in combined
    assert "def delete" not in combined
