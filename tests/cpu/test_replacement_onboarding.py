"""Three held proposals, not license inference, stage adoption or panel execution."""

import copy
import json
from pathlib import Path

import pytest

from carbon.challenge_pipeline.onboarding import packet
from scripts.dev.onboarding import run_replacements as runner

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def generated():
    return runner.generate(ROOT)


def test_four_tools_per_named_brief_do_not_claim_exit(generated):
    assert set(generated) == runner.CHALLENGES
    for name, row in generated.items():
        assert row["packet"]["challenge"] == name
        assert packet.render(row["packet"]).count("\n## ") == 10
        assert row["packet"]["maturity"] == "DRAFT_ONLY"
        assert row["law"]["P"] is not row["law"]["Q"]
        assert row["law"]["Q"] is not row["law"]["w"]
        assert row["law"]["T2a"]["near_refinement_bands"] == 2
        assert row["law"]["diversity"] is None
        assert row["law"]["bank"]["E"] is None
        assert row["panel"]["registration_status"] == "PROPOSED_NOT_DISPATCHABLE"
        assert row["panel"]["case_count"] is None
        assert not row["status"]["tested_challenge_claim"]
        assert all(not stage["exit_verified"] for stage in row["status"]["stages"])
        assert row["limits"]["solver_runs"] == row["limits"]["spend"] == 0


def test_intake_keeps_ingredients_distinct_from_complete_coverage(generated):
    for row in generated.values():
        intake = row["intake"]
        assert intake["disposition"] == "HOLD_OPEN_SET_NOT_CONFIRMED"
        assert not intake["run_authorized"]
        assert (
            intake["research_basis"]["commit"]
            == "2861b3bee63d8c7f143821fcbde6f2a941741775"
        )
        assert any(field["state"] == "HUMAN_INPUT" for field in intake["inputs"])
        assert any(
            field["state"] == "CUSTOMER_OR_MOCK_OWNER_INPUT"
            for field in intake["inputs"]
        )
        review = intake["question_law_review"]
        assert len({review[key] for key in ("P", "Q", "w")}) == 3
        assert review["T2a"]["working_refinement_bands"] == 2
        assert not review["threshold_variation_renews_E"]
        assert review["E"] is review["B"] is review["distinct_winners"] is None
        panel = intake["panel_review"]
        assert panel["exact_design_condition_rung_tuples"] is None
        assert panel["accepted_pins"] is None
        assert panel["completed_and_scheduled_reuse_inventory"] is None
        assert panel["equivalent_cases"] == (
            panel["primary_cases"]
            + panel["refined_cases"] * panel["refined_cost_multiplier"]
            + panel["control_equivalents"]
            + panel["independent_witness_equivalents"]
            + panel["failed_attempt_allowance"]
        )
    assert (
        generated["solenoid-pole"]["intake"]["inputs"][-1]["state"] == "NOT_APPLICABLE"
    )


def test_source_identity_is_checked_not_invented(generated):
    for row in generated.values():
        for source in row["basis"]:
            assert source["sha256"] == packet.digest(
                packet.source_path(ROOT, source["path"]).read_bytes()
            )
        assert all(
            packet.verify_sources(field["sources"], ROOT)
            for field in row["brief"]["fields"].values()
        )
    changed = copy.deepcopy(generated["bolted-joint"]["brief"])
    changed["fields"]["geometry"]["sources"][0]["sha256"] = "0" * 64
    with pytest.raises(packet.DraftError):
        packet.generate(changed, ROOT)


def test_duplicate_entries_refused(tmp_path):
    config = packet.read_json(ROOT / runner.SOURCES)
    config["entries"][-1] = config["entries"][0]
    target = tmp_path / runner.SOURCES
    target.parent.mkdir(parents=True)
    target.write_text(json.dumps(config))
    with pytest.raises(packet.DraftError, match="three explicit"):
        runner.generate(tmp_path)


def test_retained_hashes_and_contained_repeated_writes(tmp_path, generated):
    target = tmp_path / runner.SOURCES
    target.parent.mkdir(parents=True)
    target.write_bytes((ROOT / runner.SOURCES).read_bytes())
    first = runner.write(tmp_path, generated)
    assert first == runner.write(tmp_path, generated)
    retained = packet.read_json(ROOT / (runner.OUTPUT + "/manifest.json"))
    assert set(retained["challenges"]) == runner.CHALLENGES
    assert retained["input_sha256"] == packet.digest(
        (ROOT / runner.SOURCES).read_bytes()
    )
    for files in retained["challenges"].values():
        assert "intake" in files
        for item in files.values():
            assert item["sha256"] == packet.digest(
                packet.source_path(ROOT, item["path"]).read_bytes()
            )
    assert not (tmp_path / "carbon").exists()
    with pytest.raises(packet.DraftError, match="three explicit"):
        runner.write(tmp_path, {"../unowned": generated["solenoid-pole"]})
