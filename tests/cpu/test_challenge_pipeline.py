"""The Challenge Roadmap pipeline: transcription, queue, bound, leaderboard and
the rules that keep its records coherent."""

from __future__ import annotations

import copy
import json

import pytest

from carbon.challenge_pipeline import render
from carbon.challenge_pipeline.roadmap import (
    board_rows,
    ff_upper,
    load_families,
    prerequisites_later,
    rank_all,
    speed_score,
)
from carbon.challenge_pipeline.state import (
    PROTOCOL,
    RECORDS,
    RUBRIC,
    PipelineError,
    load_state,
    stage_of,
    validate_protocol,
    validate_record,
    validate_rubric,
)

#: The queue the roadmap page computes with equal weights and no measurements.
QUEUE = [
    "f04", "f02", "f06", "f08", "f01", "f07", "f13", "f17", "f05", "f09", "f11", "f12", "f03",
    "f14", "f19", "f15", "f10", "f16", "f18", "f23", "f20", "f21", "f22", "f25", "f26", "f24",
]  # fmt: skip
SIGNED = {"by": "Harshdeep", "on": "2026-10-02", "ref": "OWNER-EXAMPLE-01"}


@pytest.fixture
def families():
    return load_families()


@pytest.fixture
def protocol():
    return json.loads(PROTOCOL.read_text())


@pytest.fixture
def battery():
    return json.loads((RECORDS / "f05.json").read_text())


def _locked(protocol):
    locked = copy.deepcopy(protocol)
    locked.update(
        state="LOCKED",
        version="1.0",
        suite_version="suite-v1",
        lock={"by": "Fitz", "on": "2026-10-02", "ref": "OWNER-EXAMPLE-LOCK"},
    )
    for step in locked["phase_1"]:
        step.update(status="done", evidence="carbon/challenge_pipeline/protocol.json")
    return locked


def test_the_families_are_the_roadmap_transcription(families):
    fams = families["families"]
    assert [f["id"] for f in fams] == [f"f{i:02d}" for i in range(1, 27)]
    assert [f["n"] for f in fams] == list(range(1, 27))
    ids = {f["id"] for f in fams}
    for f in fams:
        assert (
            f["fL"] in families["frequency_scores"]
            and f["vL"] in families["value_scores"]
        )
        assert f["dom"] in families["domains"] and set(f["needs"]) <= ids - {f["id"]}
        assert 0 < f["est"]["lo"] <= f["est"]["typ"] <= f["est"]["hi"]
    assert families["source"]["artifact_version"] == "1790946516-a04e"


def test_the_queue_matches_the_roadmap_page(families):
    rows = rank_all(families)
    assert [r["family"]["id"] for r in rows] == QUEUE
    assert [round(r["composite"], 2) for r in rows[:3]] == [4.67, 4.67, 4.67]
    # Ties go to solve time, then value, then the v1.0 priority.
    assert [(r["S"], r["V"]) for r in rows[:3]] == [(5, 5), (4, 5), (4, 5)]
    assert rows[0]["move"] == 4 - 1 and all(r["source"] == "estimate" for r in rows)


def test_speed_score_bins():
    assert [speed_score(t) for t in (0.5, 1, 9.9, 10, 59, 60, 599, 600, 1e5)] == [
        1, 2, 2, 3, 3, 4, 4, 5, 5,
    ]  # fmt: skip


def test_a_measured_p50_replaces_the_estimate(families):
    # Laminar flow measured at 5 s would score 2 on solve time and drop
    # below the other 3.67 families that solve more slowly.
    rows = rank_all(families, {"f04": 5.0})
    f04 = next(r for r in rows if r["family"]["id"] == "f04")
    assert (f04["source"], f04["S"], f04["rank"]) == ("measured", 2, 12)
    assert rows[0]["family"]["id"] == "f02"


def test_zero_weights_fall_back_to_equal(families):
    assert [
        r["family"]["id"] for r in rank_all(families, weights={"F": 0, "V": 0, "S": 0})
    ] == QUEUE


def test_prerequisites_ranked_lower_are_flagged(families):
    rows = rank_all(families)
    late = prerequisites_later(rows, lambda fid: "queued")
    assert (
        late["f06"] == ["f14"]
        and late["f07"] == ["f09"]
        and late["f08"] == ["f01", "f12"]
    )
    assert late["f04"] == [] and late["f11"] == []


def test_the_false_feasible_bound():
    for n in (1, 30, 59, 300):
        assert ff_upper(0, n) == pytest.approx(1 - 0.05 ** (1 / n), rel=1e-15)
    assert ff_upper(0, 59) < 0.05 < ff_upper(0, 58)
    assert ff_upper(3, 3) == 1.0
    assert [ff_upper(*bad) for bad in ((1, 0), (-1, 5), (6, 5), (0.5, 5))] == [None] * 4
    stats = pytest.importorskip("scipy.stats")
    for k, n in ((1, 10), (2, 59), (5, 300), (40, 50)):
        assert ff_upper(k, n) == pytest.approx(
            stats.beta.ppf(0.95, k + 1, n - k), rel=1e-9
        )
    assert ff_upper(1, 10) < ff_upper(2, 10) < ff_upper(3, 10)


def _result(stage="ready", **values):
    record = {"stage": stage, "attC": 0, "attH": 0, "attM": 0, "attL": 0}
    record.update(rho=0.8, regret=None, n=60, k=0)
    record.update(values)
    return record


def test_the_leaderboard_lists_results_without_eligibility_until_the_rubric_is_set():
    rows = board_rows({"f05": _result()}, json.loads(RUBRIC.read_text()), {"f05": 4.0})
    assert rows[0]["why"] == ["Rubric not set"] and "position" not in rows[0]
    assert (
        board_rows(
            {"f05": {"stage": "protocol", "rho": None, "attC": None, "attH": None}},
            None,
            {},
        )
        == []
    )


def test_the_leaderboard_gates_and_orders_eligible_challenges():
    rubric = {
        "minRho": 0.5,
        "maxFF": 5.0,
        "minN": 59,
        "maxReg": None,
        "maxC": 0,
        "maxH": 0,
    }
    records = {
        "f01": _result(rho=0.7),
        "f02": _result(rho=0.9, attM=3),
        "f03": _result(rho=0.9),  # same rho as f02, fewer open minor findings
        "f04": _result(rho=0.95, attH=1),
        "f06": _result(rho=0.9, n=30),
        "f07": _result(stage="test", rho=0.99),
        "f08": _result(rho=0.4),
        "f09": _result(rho=0.9, n=80, k=2),
    }
    rows = board_rows(records, rubric, {})
    eligible = [(r["fid"], r["position"]) for r in rows if r["ok"]]
    assert eligible == [("f03", 1), ("f02", 2), ("f01", 3)]
    why = {r["fid"]: r["why"] for r in rows if not r["ok"]}
    assert why["f04"] == ["Open high findings"]
    assert why["f06"] == ["Too few scenarios", "False-feasible bound above threshold"]
    assert why["f07"] == ["Still in test"]
    assert why["f08"] == ["Rank agreement below threshold"]
    assert why["f09"] == ["False-feasible bound above threshold"]
    assert board_rows({"f01": _result(regret=4.0)}, {**rubric, "maxReg": 3.0}, {})[0][
        "why"
    ] == ["Regret above threshold"]


def test_the_committed_state_is_valid_and_battery_defines_the_protocol():
    _, protocol, rubric, records = load_state()
    assert protocol["state"] == "DEFINING" and rubric["minRho"] is None
    assert (
        stage_of(records, "f05") == "protocol" and stage_of(records, "f10") == "queued"
    )
    assert all(r["stage"] == "queued" for fid, r in records.items() if fid != "f05")
    assert render.write(check=True), "run python -m carbon.challenge_pipeline render"


def test_no_family_enters_before_the_protocol_is_locked(protocol, battery):
    ids = {f"f{i:02d}" for i in range(1, 27)}
    flow = dict(
        battery,
        family="f04",
        stage="design",
        gates=dict(battery["gates"], scope=SIGNED),
    )
    with pytest.raises(PipelineError, match="after protocol lock"):
        validate_record(flow, protocol, ids)
    validate_record(flow, _locked(protocol), ids)
    with pytest.raises(PipelineError, match="only battery defines the protocol"):
        validate_record(dict(battery, family="f04"), protocol, ids)
    with pytest.raises(PipelineError, match="only battery defines the protocol"):
        validate_record(battery, _locked(protocol), ids)


def test_each_stage_needs_its_owners_sign_off(protocol, battery):
    ids, locked = {"f04"}, _locked(protocol)
    flow = dict(battery, family="f04", stage="test")
    with pytest.raises(PipelineError, match="needs the scope gate"):
        validate_record(flow, locked, ids)
    wrong = dict(
        flow, gates=dict(battery["gates"], scope=SIGNED, design=dict(SIGNED, by="Ryan"))
    )
    with pytest.raises(PipelineError, match="not the science owner"):
        validate_record(wrong, locked, ids)
    unsigned = dict(
        flow, gates=dict(battery["gates"], scope=SIGNED, design=dict(SIGNED, ref=" "))
    )
    with pytest.raises(PipelineError, match="names its decision"):
        validate_record(unsigned, locked, ids)
    ok = dict(flow, gates=dict(battery["gates"], scope=SIGNED, design=SIGNED))
    validate_record(ok, locked, ids)
    with pytest.raises(PipelineError, match="needs the track_a gate"):
        validate_record(dict(ok, stage="ready"), locked, ids)


def test_results_and_timings_need_their_evidence(protocol, battery):
    ids, locked = {"f05", "f04"}, _locked(protocol)
    with pytest.raises(PipelineError, match="frozen run"):
        validate_record(dict(battery, rho=0.5), protocol, ids)
    bare = dict(protocol, reference_hardware=None, reference_hardware_approval=None)
    with pytest.raises(PipelineError, match="no reference hardware"):
        validate_record(dict(battery, p50s=5.0, hw="owner host"), bare, ids)
    flow = dict(battery, family="f04", stage="queued")
    with pytest.raises(PipelineError, match="off the reference hardware"):
        validate_record(dict(flow, p50s=5.0, hw="owner host"), locked, ids)
    with pytest.raises(PipelineError, match="timing evidence"):
        validate_record(dict(flow, p50s=5.0, hw="runpod-cpu5c-16vcpu"), locked, ids)
    evidence = dict(
        battery["evidence"], timing="carbon/challenge_pipeline/protocol.json"
    )
    validate_record(
        dict(flow, p50s=5.0, hw="runpod-cpu5c-16vcpu", evidence=evidence), locked, ids
    )
    with pytest.raises(PipelineError, match="not in the repository"):
        validate_record(
            dict(flow, evidence=dict(evidence, frozen="nowhere.json")), locked, ids
        )


def test_the_rubric_needs_the_process_owners_approval(protocol):
    rubric = json.loads(RUBRIC.read_text())
    validate_rubric(rubric, protocol)
    proposed = dict(rubric, version="v1", minRho=0.5, maxFF=5.0, minN=59)
    with pytest.raises(PipelineError, match="sign-off"):
        validate_rubric(proposed, protocol)
    with pytest.raises(PipelineError, match="not the process owner"):
        validate_rubric(dict(proposed, approved=SIGNED), protocol)
    validate_rubric(dict(proposed, approved=dict(SIGNED, by="Fitz")), protocol)


def test_the_lock_is_step_eight_and_the_process_owners(protocol):
    validate_protocol(_locked(protocol))
    with pytest.raises(PipelineError, match="step 8 is the lock"):
        validate_protocol(dict(protocol, phase_1=_locked(protocol)["phase_1"]))
    with pytest.raises(PipelineError, match="not the process owner"):
        validate_protocol(dict(_locked(protocol), lock=SIGNED))
    early = copy.deepcopy(protocol)
    early["phase_1"][1].update(status="done", evidence=None)
    with pytest.raises(PipelineError, match="done needs its evidence"):
        validate_protocol(early)


def test_the_reference_hardware_is_the_technical_owners_approval(protocol):
    assert protocol["reference_hardware"] == "runpod-cpu5c-16vcpu"
    validate_protocol(protocol)
    for approval in (None, dict(SIGNED, by="Fitz"), dict(SIGNED, by="Ryan", ref=" ")):
        with pytest.raises(PipelineError):
            validate_protocol(dict(protocol, reference_hardware_approval=approval))
    with pytest.raises(PipelineError, match="hardware it approves"):
        validate_protocol(dict(protocol, reference_hardware=None))
