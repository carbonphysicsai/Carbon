"""Static research handoff checks, not verification of a physical model."""

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DIR = (
    ROOT
    / "docs/development/challenge_pipeline/solver-package-specs/warpage-process-physics"
)
DATA = json.loads((DIR / "assessment.json").read_text(encoding="utf-8"))


def test_source_research_cannot_become_a_reference_or_execution_grant():
    assert DATA["maturity"] == "SPECIFIED"
    for field in (
        "executable",
        "solver_runs_authorised",
        "spend_authorised",
        "protected_data_access",
        "adopted_challenge",
        "synthetic_controls_are_buyer_evidence",
        "source_grades_are_earned_tiers",
    ):
        assert DATA[field] is False
    assert DATA["earned_tier"] == "NOT_DEMONSTRATED"
    assert DATA["dispatch"] == "HOLD"
    assert DATA["matched_customer_law_hash"] is None
    assert DATA["accepted_image_digest"] is None
    assert DATA["cost_status"] == "UNMEASURED"
    assert not DATA["coherent_matched_data_found"]
    assert not DATA["open_formation_calibration_found"]
    assert DATA["parameter_sets_adopted"] == []


def test_full_history_and_data_applicability_not_elastic_snapshot():
    assert DATA["scope"] == "full_3d_complete_history"
    assert len(DATA["verification_stages"]) == 7
    assert "formation_state_transfer" in DATA["verification_stages"]
    assert "full3d_restart" in DATA["verification_stages"]
    assert "surrounding_residual_state" in DATA["must_preserve"]
    document = (DIR / "README.md").read_text(encoding="utf-8")
    for statement in (
        "must not reset",
        "not a scope reduction",
        "Solid Anand is not molten solder",
    ):
        assert statement in document
    assert "HUMAN_INPUT" in document and "outside producer custody" in document


def test_catalogue_hash_is_not_a_download_or_calibration_receipt():
    source = DATA["nist_catalogue"]
    assert source["dataset_doi"] == "10.18434/mds2-4162"
    assert re.fullmatch(r"[0-9a-f]{64}", source["published_sha256"])
    assert source["file_downloaded_or_verified"] is False
    assert source["published_sha256"] in (DIR / "sources.md").read_text(
        encoding="utf-8"
    )


def test_repo_links_exist():
    for name in ("README.md", "sources.md"):
        for target in re.findall(
            r"\]\(([^)]+)\)", (DIR / name).read_text(encoding="utf-8")
        ):
            if "://" not in target:
                assert (DIR / target.split("#")[0]).is_file(), target
