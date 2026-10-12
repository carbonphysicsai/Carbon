"""Draft coverage and non-blocking notices, not physical-law verification."""

import json
from pathlib import Path

import pytest

from carbon.challenge_pipeline.onboarding import packet
from carbon.challenge_pipeline.onboarding import reconcile as r

ROOT = Path(__file__).resolve().parents[2]
FAMILIES = ("f02", "cooling-cell", "motor", "f13")
TYPES = {
    "bound",
    "initial_condition",
    "monotone",
    "balance",
    "invariance",
    "limit",
    "smoothness",
}


def metadata(family="motor"):
    return {
        "schema": "carbon.physics-contract.draft.v1",
        "challenge": family,
        "maturity": "DRAFT",
        "status": "HUMAN_INPUT",
        "runtime_enabled": False,
    }


def put(tmp_path, content):
    path = tmp_path / r.PHYSICS_DIRECTORY / "motor.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


@pytest.mark.parametrize("family", FAMILIES)
def test_four_drafts_bind_sources_outputs_holds_and_no_adopted_budgets(family):
    data = packet.read_json(ROOT / r.PHYSICS_DIRECTORY / f"{family}.json")
    assert metadata(family).items() <= data.items()
    assert {
        "laws",
        "validity",
        "required_outputs",
        "tolerances",
        "probes",
        "gates",
    } <= data.keys()
    assert data["validity"]["outside_or_unknown"] == "UNRESOLVED_NOT_CANDIDATE_FAILURE"
    assert data["calibration"]["status"] == "NOT_RUN"
    assert data["calibration"]["holds"] and data["calibration"]["recalibrate_on"]
    assert data["gates"] == {
        "status": "HUMAN_INPUT",
        "adopted": False,
        "allocations": None,
        "score_use": None,
    }
    for key in ("quantile", "multiplier", "absolute_floors", "sampling_uncertainty"):
        assert data["tolerances"][key] is None
    assert data["tolerances"]["calibration_status"] == "NOT_RUN"
    assert all(
        data["probes"][key] is None for key in ("density", "pair_count", "path_step")
    )
    ids = [law["id"] for law in data["laws"]]
    assert ids and len(set(ids)) == len(ids)
    assert {"balance", "bound", "invariance", "limit"} <= {
        law["type"] for law in data["laws"]
    }
    for law in data["laws"]:
        assert law["status"] == "HUMAN_INPUT" and law["type"] in TYPES
        assert law["statement"] and law["conditions"] and law["calibration"]
        assert law["required_outputs"]
        assert set(law["required_outputs"]) <= data["required_outputs"].keys()
        assert law["sources"] and set(law["sources"]) <= data["sources"].keys()
    for output in data["required_outputs"].values():
        assert output["availability"] and output["sources"]
        assert set(output["sources"]) <= data["sources"].keys()
    for source in data["sources"].values():
        if not source.startswith("https://"):
            assert (ROOT / source).is_file(), source
    notice = r.physics_contract_notice(ROOT, family)
    assert notice["state"] == "DRAFT_PRESENT"
    assert notice["observed_sha256"] == packet.digest(
        (ROOT / r.PHYSICS_DIRECTORY / f"{family}.json").read_bytes()
    )
    assert not notice["blocking"] and not notice["authority_granted"]


def test_missing_is_an_advisory_with_no_authority(tmp_path):
    result = r.physics_contract_notice(tmp_path, "battery-v3")
    assert result["state"] == "MISSING"
    assert result["message"] == "physics contract missing"
    assert result["observed_sha256"] is None
    assert not result["blocking"] and not result["authority_granted"]


def test_unknown_repository_is_not_an_absent_contract(tmp_path):
    result = r.physics_contract_notice(tmp_path / "unavailable-repo", "motor")
    assert result["state"] == "UNAVAILABLE_NOT_ABSENCE"


def test_notice_does_not_evaluate_descriptive_law_text(tmp_path):
    path = put(tmp_path, json.dumps({**metadata(), "laws": ["1/0"]}))
    result = r.physics_contract_notice(tmp_path, "motor")
    assert result["state"] == "DRAFT_PRESENT"
    assert result["observed_sha256"] == packet.digest(path.read_bytes())
    assert "metadata only" in result["basis"]
    assert not result["authority_granted"]


@pytest.mark.parametrize(
    "body",
    [
        "{",
        "[]",
        '{"value": NaN}',
        json.dumps({**metadata(), "runtime_enabled": True}),
        json.dumps(metadata("f02")),
    ],
)
def test_bad_or_mismatched_drafts_are_unavailable_not_absent(tmp_path, body):
    put(tmp_path, body)
    notice = r.physics_contract_notice(tmp_path, "motor")
    assert notice["state"] == "UNAVAILABLE_NOT_ABSENCE"
    assert "not evidence of absence" in notice["message"]
    assert notice["observed_sha256"] is not None
    assert body not in notice["message"]


def test_size_bound_and_read_error_are_not_missing(tmp_path, monkeypatch):
    path = put(tmp_path, "x" * (packet.LIMIT + 1))
    assert (
        r.physics_contract_notice(tmp_path, "motor")["state"]
        == "UNAVAILABLE_NOT_ABSENCE"
    )
    path.write_text(json.dumps(metadata()))

    def denied(*args, **kwargs):
        raise PermissionError("do not echo this content")

    monkeypatch.setattr(packet, "source_path", denied)
    result = r.physics_contract_notice(tmp_path, "motor")
    assert result["state"] == "UNAVAILABLE_NOT_ABSENCE"
    assert "do not echo" not in json.dumps(result)


def test_link_escape_and_broken_link_are_unavailable(tmp_path):
    outside = tmp_path / "outside"
    outside.mkdir()
    root = tmp_path / "repo"
    root.mkdir()
    target = root / r.PHYSICS_DIRECTORY / "motor.json"
    target.parent.mkdir(parents=True)
    try:
        target.symlink_to(outside / "absent.json")
    except OSError:
        pytest.skip("host lacks symlink permission; canonical Linux exercises this")
    assert (
        r.physics_contract_notice(root, "motor")["state"] == "UNAVAILABLE_NOT_ABSENCE"
    )


@pytest.mark.parametrize(
    "name", ["../motor", "motor/../../hidden", "C:/private", "motor.json", "MOTOR", ""]
)
def test_unsafe_identifiers_cannot_select_arbitrary_files(tmp_path, name):
    with pytest.raises(packet.DraftError, match="identifier"):
        r.physics_contract_notice(tmp_path, name)


def test_aliases_are_only_scope_cautioned_document_lookups():
    for alias, family in r.PHYSICS_ALIASES.items():
        notice = r.physics_contract_notice(ROOT, alias)
        assert notice["state"] == "DRAFT_PRESENT"
        assert notice["path"].endswith(f"/{family}.json")
        assert "does not establish packet-scope coverage" in notice["basis"]
