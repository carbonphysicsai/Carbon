"""Eight explicit public briefs: drafts are reproducible, not accepted stages."""

import copy
import importlib.util
import json
from pathlib import Path

import pytest

from carbon.challenge_pipeline.onboarding import packet

ROOT = Path(__file__).resolve().parents[2]
DIRECTORY = ROOT / "docs/development/challenge_pipeline/onboarding-runs"


def runner():
    spec = importlib.util.spec_from_file_location(
        "run_remaining", ROOT / "scripts/dev/onboarding/run_remaining.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def generated():
    return runner().generate(ROOT)


def test_all_eight_runs_keep_four_tools_and_no_accepted_exits(generated):
    assert set(generated) == runner().CHALLENGES
    for challenge, result in generated.items():
        assert result["packet"]["challenge"] == challenge
        assert packet.render(result["packet"]).count("\n## ") == 10
        assert result["packet"]["maturity"] == "DRAFT_ONLY"
        assert result["law"]["P"] is not result["law"]["Q"]
        assert result["law"]["Q"] is not result["law"]["w"]
        assert result["law"]["diversity"] is None
        assert result["law"]["bank"]["threshold_variation_renews_exposure"] is False
        assert result["law"]["T2a"]["near_refinement_bands"] == 2
        assert result["law"]["T2a"]["minimum_distinct_feasible"] == 5
        assert result["law"]["T2a"]["minimum_distinct_infeasible"] == 5
        assert result["panel"]["case_count"] is None
        assert result["panel"]["registration_status"] == "PROPOSED_NOT_DISPATCHABLE"
        assert not result["status"]["tested_challenge_claim"]
        assert all(not stage["exit_verified"] for stage in result["status"]["stages"])
        assert result["limits"] == {
            "solved_export_supplied": False,
            "numeric_panel_seed_supplied": False,
            "reuse_receipts_supplied": False,
            "solver_runs": 0,
            "spend": 0,
            "stage_exits_verified": False,
        }


def test_source_extraction_and_crosswalk_are_not_numeric_inference(generated):
    for result in generated.values():
        fields = result["packet"]["fields"]
        assert fields["P"]["status"] == "SOURCE_EXTRACT"
        assert fields["buyer"]["status"] == "HUMAN_INPUT"
        assert fields["confirmation"]["recommendation"] is None
        assert result["panel"]["cost"]["cpu_hours_without_reuse"] is None
    f02 = generated["f02"]["law"]
    assert f02["k"]["recommendation"] == 8
    assert f02["k"]["status"] == "HUMAN_INPUT"
    assert f02["source_proposal_status"] == "RETAINED_PROPOSAL_NOT_OWNER_ACCEPTANCE"
    assert all(
        result["law"]["k"]["recommendation"] is None
        for challenge, result in generated.items()
        if challenge != "f02"
    )


def test_only_explicit_public_sources_and_digest_pins_are_retained(generated):
    for result in generated.values():
        for row in result["basis"]:
            target = packet.source_path(ROOT, row["path"])
            assert packet.digest(target.read_bytes()) == row["sha256"]
        for row in result["brief"]["fields"].values():
            assert packet.verify_sources(row["sources"], ROOT)
    altered = copy.deepcopy(generated["f02"]["brief"])
    altered["fields"]["P"]["sources"][0]["sha256"] = "0" * 64
    with pytest.raises(packet.DraftError):
        packet.generate(altered, ROOT)


def test_duplicate_brief_cannot_silently_overwrite_an_application(tmp_path):
    module = runner()
    config = json.loads((DIRECTORY / "run-sources.json").read_text(encoding="utf-8"))
    config["entries"][-1] = config["entries"][0]
    destination = tmp_path / module.SOURCES
    destination.parent.mkdir(parents=True)
    destination.write_text(json.dumps(config), encoding="utf-8")
    with pytest.raises(packet.DraftError, match="eight explicit"):
        module.generate(tmp_path)


def test_retained_outputs_and_markdown_are_digest_bound():
    manifest = json.loads((DIRECTORY / "generated/manifest.json").read_text())
    assert manifest["drafts_not_adoption"]
    assert manifest["input_sha256"] == packet.digest(
        (DIRECTORY / "run-sources.json").read_bytes()
    )
    assert set(manifest["challenges"]) == runner().CHALLENGES
    for files in manifest["challenges"].values():
        assert set(files) == {
            "brief",
            "packet",
            "packet_markdown",
            "law",
            "panel",
            "status",
            "basis",
            "limits",
        }
        for row in files.values():
            target = packet.source_path(ROOT, row["path"])
            assert packet.digest(target.read_bytes()) == row["sha256"]


def test_write_is_bounded_and_same_inputs_repeat_without_new_evidence(
    tmp_path, generated
):
    module = runner()
    config = tmp_path / module.SOURCES
    config.parent.mkdir(parents=True)
    config.write_bytes((DIRECTORY / "run-sources.json").read_bytes())
    before = module.write(tmp_path, generated)
    after = module.write(tmp_path, generated)
    assert before == after
    assert len(list((tmp_path / module.OUTPUT).glob("*/*.json"))) == 56
    assert not (tmp_path / "carbon").exists()
    bad = {"../unowned": generated["f02"]}
    with pytest.raises(packet.DraftError, match="eight explicit"):
        module.write(tmp_path, bad)
