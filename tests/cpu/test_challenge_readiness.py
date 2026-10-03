"""The launch-portfolio readiness records (#347).

Each refusal case below starts from a committed record that validates, so a
refusal can only come from the one change the case makes.
"""

from __future__ import annotations

import copy
import json
import socket
import subprocess
from pathlib import Path

import pytest

from carbon.challenge_readiness import record as readiness
from carbon.challenge_readiness.__main__ import main
from carbon.challenge_registry.registry import entries

REPOSITORY = Path(__file__).resolve().parents[2]
BATTERY = "battery-fastcharge-ageing-development-v1"


def committed():
    return {d["challenge_id"]: d for d, _ in readiness.load_all()}


def test_every_launch_portfolio_challenge_has_exactly_one_valid_record():
    launch = {e.challenge_id for e in entries() if e.portfolio == "launch"}
    records = committed()
    assert set(records) == launch
    for document in records.values():
        assert document["status"] == readiness.STATUS
        assert document["population"]["approved"] is None


def test_pilot_counts_are_rederived_from_the_retained_runner_records():
    """A hand-edited count fails here: every pilot is recounted from the
    records.jsonl its evidence names."""
    records = committed()
    counted = 0
    for document in records.values():
        for pilot in document["pilots"]:
            fresh = readiness.import_runner_records(
                REPOSITORY / pilot["evidence"],
                attempt_id=pilot["attempt_id"],
                case_kind=pilot["case_kind"],
                evidence=pilot["evidence"],
                note=pilot["note"],
            )
            assert fresh["outcomes"] == pilot["outcomes"], pilot["attempt_id"]
            counted += 1
    assert counted >= 10


def test_the_summary_keeps_reference_and_infrastructure_failures_apart():
    records = committed()
    battery = readiness.summary(records[BATTERY])
    cold_plate = readiness.summary(records["chip-cold-plate"])
    assert battery["cases_ok"] >= 2604
    assert (battery["reference_failures"], battery["infrastructure_failures"]) == (
        0,
        4,
    )
    assert (
        cold_plate["reference_failures"],
        cold_plate["infrastructure_failures"],
    ) == (2, 0)


@pytest.mark.parametrize(
    ("cid", "ok", "reference_failures", "limits"),
    [
        # CHALLENGE-COLD-PLATE-01: rung 7 and the pilot; two REFERENCE_INVALID
        # diagnostics (the cp-varying fluid, invalid by design).
        ("chip-cold-plate", 20, 2, 7),
        ("electric-motor-magnetics", 17, 0, 4),  # CHALLENGE-MOTOR-01
        ("photonic-coupler", 12, 0, 5),  # CHALLENGE-PHOTONIC-01
    ],
)
def test_each_challenge_design_record_counts_its_pilot_from_the_records(
    cid, ok, reference_failures, limits
):
    s = readiness.summary(committed()[cid])
    assert s["reference_execution"] == "PILOTED"
    assert (s["cases_ok"], s["reference_failures"], s["infrastructure_failures"]) == (
        ok,
        reference_failures,
        0,
    )
    assert s["recommendation"] == "PROCEED"
    assert s["limits_awaiting_approval"] == s["limits_declared"] == limits


UNPILOTED = "unpiloted"


def _unpiloted():
    """The cold plate's committed record with its evidence taken away: the
    shape of a Challenge that has not piloted. Refusals that promote missing
    evidence start from it, now that every committed record has a pilot."""
    document = copy.deepcopy(committed()["chip-cold-plate"])
    document["pilots"] = []
    document["maturity"] = {"baseline": "NOT_STARTED", "reference_execution": "SCOPED"}
    document["recommendation"] = {
        "decision": "NONE",
        "basis": "No reference pilot has run.",
    }
    document["costs"] = [
        {
            "item": c["item"],
            "basis": "unknown",
            "usd": None,
            "unit": "USD",
            "evidence": None,
        }
        for c in document["costs"]
    ]
    document["limits"] = []
    return document


def test_no_challenge_claims_evidence_it_does_not_have():
    for document in committed().values():
        s = readiness.summary(document)
        if s["reference_execution"] != "SCOPED" or s["recommendation"] != "NONE":
            assert s["cases_ok"] > 0, s["challenge_id"]
    specimen = _unpiloted()
    readiness.validate(specimen)
    s = readiness.summary(specimen)
    assert (s["cases_ok"], s["reference_execution"], s["recommendation"]) == (
        0,
        "SCOPED",
        "NONE",
    )
    assert len(s["cost_items_unknown"]) == 7


def _mutated(cid, change):
    document = _unpiloted() if cid == UNPILOTED else copy.deepcopy(committed()[cid])
    readiness.validate(copy.deepcopy(document))  # the specimen passes
    change(document)
    return document


def _set(path, value):
    def change(document):
        target = document
        for key in path[:-1]:
            target = target[key]
        target[path[-1]] = value

    return change


REFUSALS = [
    # missing evidence promoted to a pass
    (
        UNPILOTED,
        _set(("maturity", "reference_execution"), "PILOTED"),
        "maturity_without_evidence",
    ),
    (
        UNPILOTED,
        _set(("recommendation", "decision"), "PROCEED"),
        "recommendation_without_evidence",
    ),
    (
        UNPILOTED,
        _set(("recommendation", "decision"), "NARROW"),
        "recommendation_without_evidence",
    ),
    # unsupported units and versions
    (UNPILOTED, _set(("outputs", 0, "unit"), "celsius"), "unsupported_unit"),
    (BATTERY, _set(("limits", 0, "unit"), "percent"), "unsupported_unit"),
    (
        UNPILOTED,
        _set(("schema",), "carbon.challenge-readiness.v1"),
        "unsupported_schema",
    ),
    (UNPILOTED, _set(("record_version",), 0), "unsupported_record_version"),
    (UNPILOTED, _set(("status",), "QUALIFIED"), "unsupported_status"),
    # identities
    (
        UNPILOTED,
        _set(("challenge_id",), "chip-cold-plates"),
        "unknown_challenge",
    ),
    (
        UNPILOTED,
        _set(("tracking",), "carbonphysicsai/Carbon#999"),
        "tracking_mismatch",
    ),
    (
        BATTERY,
        lambda d: d["pilots"].append(copy.deepcopy(d["pilots"][0])),
        "duplicate_result_identity",
    ),
    # scientific and infrastructure failures are not conflated
    (
        BATTERY,
        _set(("pilots", 0, "outcomes", "GATE_FAILED"), 1),
        "candidate_outcome_in_reference_pilot",
    ),
    (BATTERY, _set(("pilots", 0, "outcomes", "PROBABLY_FINE"), 1), "unknown_outcome"),
    (BATTERY, _set(("pilots", 0, "outcomes"), {}), "pilot_without_cases"),
    # unknown is not zero
    (UNPILOTED, _set(("costs", 0, "usd"), 0), "unknown_cost_with_amount"),
    (BATTERY, _set(("costs", 0, "evidence"), None), "measured_cost_without_evidence"),
    (BATTERY, _set(("costs", 0, "usd"), None), "cost_amount_required"),
    # proposed is not approved
    (
        BATTERY,
        _set(("limits", 0, "approved"), {"value": 0.057, "authority": "OWNER-X"}),
        "approved_limit_without_scientific_approval",
    ),
    (
        UNPILOTED,
        _set(("population", "approved"), "anything"),
        "approved_population_not_supported",
    ),
    (
        UNPILOTED,
        _set(("reviews", "security"), {"state": "APPROVED", "authority": None}),
        "approval_without_authority",
    ),
    (
        UNPILOTED,
        _set(("reviews", "launch"), {"state": "APPROVED", "authority": "OWNER-X"}),
        "launch_approved_before_other_reviews",
    ),
    (
        UNPILOTED,
        _set(("reviews", "customer"), {"state": "NOT_STARTED", "authority": "OWNER-X"}),
        "authority_without_approval",
    ),
    # the training budget study (OWNER-TRAINING-BUDGET-STUDY-01)
    (
        UNPILOTED,
        lambda d: d.pop("training_budget_study"),
        "exact_keys_required",
    ),
    (
        BATTERY,
        _set(("training_budget_study", "state"), "DONE"),
        "invalid_training_budget_study",
    ),
    (
        BATTERY,
        _set(("training_budget_study", "state"), "COMPLETE"),
        "study_finished_without_result",
    ),
    (
        BATTERY,
        _set(("training_budget_study", "result"), "docs/development/X.md"),
        "study_result_before_finish",
    ),
    (
        BATTERY,
        lambda d: d["training_budget_study"].update(
            state="COMPLETE", result="docs/development/X.md"
        ),
        "study_complete_without_owner_decision",
    ),
    (
        BATTERY,
        lambda d: d["training_budget_study"].update(
            state="STOPPED", result="docs/development/X.md", decision="OWNER-X"
        ),
        "study_decision_before_complete",
    ),
]


@pytest.mark.parametrize(("cid", "change", "code"), REFUSALS)
def test_a_record_is_refused_for_the_one_thing_wrong_with_it(cid, change, code):
    document = _mutated(cid, change)
    with pytest.raises(readiness.ReadinessError) as refused:
        readiness.validate(document)
    assert refused.value.code == code


def test_an_approved_limit_is_accepted_only_under_the_same_scientific_authority():
    def approve(document):
        document["reviews"]["scientific"] = {
            "state": "APPROVED",
            "authority": "OWNER-SCI-1",
        }
        document["limits"][0]["approved"] = {"value": 0.057, "authority": "OWNER-SCI-1"}

    readiness.validate(_mutated(BATTERY, approve))

    def other_authority(document):
        approve(document)
        document["limits"][0]["approved"]["authority"] = "OWNER-SCI-2"

    with pytest.raises(readiness.ReadinessError) as refused:
        readiness.validate(_mutated(BATTERY, other_authority))
    assert refused.value.code == "approved_limit_without_scientific_approval"


def test_importing_evidence_starts_nothing_and_opens_no_connection(
    tmp_path, monkeypatch
):
    def forbidden(*args, **kwargs):
        raise AssertionError("import must only read the file")

    monkeypatch.setattr(socket, "socket", forbidden)
    monkeypatch.setattr(subprocess, "Popen", forbidden)
    records = tmp_path / "records.jsonl"
    records.write_text(
        "\n".join(json.dumps({"status": s}) for s in ("OK", "OK", "FAILED_INFRA"))
    )
    pilot = readiness.import_runner_records(
        records, attempt_id="a", case_kind="ordinary", evidence="e", note="n"
    )
    assert pilot["outcomes"] == {"OK": 2, "FAILED_INFRA": 1}


def test_the_table_command_renders_and_refuses_an_invalid_directory(tmp_path, capsys):
    assert main(["table"]) == 0
    table = capsys.readouterr().out
    assert all(cid in table for cid in committed()) and "PROCEED" in table
    bad = _unpiloted()
    bad["maturity"]["reference_execution"] = "CAMPAIGN_COMPLETE"
    (tmp_path / "chip-cold-plate.v1.json").write_text(json.dumps(bad))
    assert main(["table", "--records", str(tmp_path)]) == 2
    assert json.loads(capsys.readouterr().out)["refused"] == (
        "maturity_without_evidence"
    )


def test_a_record_must_live_under_its_own_name(tmp_path):
    document = committed()["chip-cold-plate"]
    (tmp_path / "cold-plate.json").write_text(json.dumps(document))
    with pytest.raises(readiness.ReadinessError) as refused:
        readiness.load_all(tmp_path)
    assert refused.value.code == "record_filename_mismatch"


def test_the_published_table_matches_the_records():
    doc = (REPOSITORY / "docs/development/CHALLENGE_READINESS.md").read_text()
    assert readiness.table(readiness.load_all()) in doc


def _all_reviews_approved(document):
    for axis in readiness.REVIEW_AXES:
        document["reviews"][axis] = {"state": "APPROVED", "authority": "OWNER-X"}


def test_launch_is_refused_until_the_training_budget_study_is_complete():
    """No Challenge goes live without its training budget study: with every
    other review approved, launch approval is refused for each unfinished
    study state, and a stopped study (no limit chosen) does not count."""
    for state, result in (
        ("NOT_STARTED", None),
        ("IN_PROGRESS", None),
        ("STOPPED", "docs/development/X_TRAINING_BUDGET_STUDY_RESULT.md"),
    ):

        def unfinished(document, state=state, result=result):
            _all_reviews_approved(document)
            document["training_budget_study"].update(state=state, result=result)

        with pytest.raises(readiness.ReadinessError) as refused:
            readiness.validate(_mutated(BATTERY, unfinished))
        assert refused.value.code == "launch_approved_before_training_budget_study"

    # A completed budget study advances to the separate admission gate. The
    # joint positive specimen lives in test_challenge_admission.py.
    def complete(document):
        _all_reviews_approved(document)
        document["training_budget_study"] = {
            "state": "COMPLETE",
            "result": "docs/development/X_TRAINING_BUDGET_STUDY_RESULT.md",
            "decision": "OWNER-X",
        }

    with pytest.raises(readiness.ReadinessError) as refused:
        readiness.validate(_mutated(BATTERY, complete))
    assert refused.value.code == "launch_approved_before_admission_tests"


def test_every_record_starts_without_a_training_budget_study():
    for path in readiness.RECORDS.glob("*.json"):
        document, _ = readiness.load(path)
        assert document["training_budget_study"] == {
            "state": "NOT_STARTED",
            "result": None,
            "decision": None,
        }
