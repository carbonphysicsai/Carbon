"""The Challenge Roadmap pipeline: transcription, queue, bound, leaderboard and
the rules that keep its records coherent."""

from __future__ import annotations

import copy
import json
import re
from pathlib import Path

import pytest

from carbon.challenge_pipeline import ladder, proposals, render
from carbon.challenge_pipeline.lessons import LESSONS, LessonError, load_lessons
from carbon.challenge_pipeline.lessons import validate as validate_lesson
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
    early["phase_1"][0]["status"] = "done"
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


# --- the construction ladder (rev 2.2, OWNER-CHALLENGE-ROADMAP-03) -----------

REPOSITORY = Path(__file__).resolve().parents[2]


def test_the_ladder_is_challenge_admission_section_3():
    text = (REPOSITORY / "Design_Specs/Challenge_Admission.md").read_text()
    section = text.split("## 3. Track A", 1)[1].split("### 3.1", 1)[0]
    rows = dict(re.findall(r"^\| (\d) \| (.+?) \|$", section, flags=re.MULTILINE))
    assert {int(k): v for k, v in rows.items()} == ladder.LEVELS
    roadmap = " ".join(
        (REPOSITORY / "Design_Specs/Challenge_Roadmap.md").read_text().split()
    )
    for step in ladder.CLIMB_PROCEDURE:
        assert step.split(",")[0].split(" (")[0] in roadmap
    for step in ladder.LAUNCH:
        assert step.split(":")[0].split(",")[0].lower() in roadmap.lower()


def test_battery_is_on_the_ladder_at_level_0_and_no_other_family_is_yet():
    _, _, _, records = load_state()
    battery = records["f05"]["construction"]
    assert (battery["challenge"], battery["level"]) == (
        "battery-fastcharge-ageing-development-v1",
        0,
    )
    assert ladder.state_of(battery, 0) == "OPEN"
    assert [ladder.state_of(battery, n) for n in range(1, 6)] == ["NOT_RUN"] * 5
    assert battery["levels"][0]["expansion_record"] == ladder.newest_record(
        battery["challenge"], REPOSITORY
    )
    assert all(
        r["construction"] == ladder.empty()
        for fid, r in records.items()
        if fid != "f05"
    )


def _challenge(tmp_path, token="synthetic-heat-v1", records=2):
    """A Challenge that is not battery: its own expansion records and test."""
    folder = tmp_path / ladder.EXPANSIONS / token
    folder.mkdir(parents=True)
    for n in range(records):
        (folder / f"{n:04d}.json").write_text("{}")
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests/test_rebuilds.py").write_text("")
    (tmp_path / "evidence.md").write_text("")
    return token


def _level(token, n, state="OPEN", record=0, evidence=None):
    return {
        "level": n,
        "state": state,
        "proposal": None if n == 0 else f"{ladder.PROPOSALS}/{token}/level-{n}.json",
        "expansion_record": f"{ladder.EXPANSIONS}/{token}/{record:04d}.json",
        "reconstruction": "tests/test_rebuilds.py",
        "evidence": evidence,
    }


def _proposal(token="synthetic-heat-v1", level=1, status="ACCEPTED", **changes):
    """Graphite's proposal for one level of a synthetic Challenge."""
    proposal = {
        "schema": "carbon.challenge-pipeline.level-proposal.v1",
        "challenge": token,
        "level": level,
        "recorded_at": "2026-10-02T12:00:00Z",
        "proposed_by": {"agent": "graphite", "role": "planner", "session": "gs-0001"},
        "capabilities": [
            {
                "id": "objective.loss_expressions",
                "adds": "loss terms composed from a bounded operation set",
                "bounds": "add, multiply, abs, square over registered quantities; depth 3",
                "rationale": "physics-weighted losses improved held-out error in development",
                "sources": ["method-card:example-0001"],
                "reconstruction": "compile the expression tree into the JAX and PyTorch losses",
                "attack_surface": "expression parser; nonfinite gradients",
            }
        ],
        "left_out": ["arbitrary code in the loss"],
        "status": status,
    }
    if status != "PROPOSED":
        proposal["decision"] = dict(SIGNED, by="Ryan")
    proposal.update(changes)
    return proposal


def _file_proposal(tmp_path, proposal):
    path = (
        tmp_path
        / ladder.PROPOSALS
        / proposal["challenge"]
        / f"level-{proposal['level']}.json"
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(proposal))
    return path


def test_any_challenge_climbs_one_level_at_a_time(tmp_path):
    token = _challenge(tmp_path)
    _file_proposal(tmp_path, _proposal(token))
    climbed = {
        "challenge": token,
        "level": 1,
        "chosen": None,
        "levels": [
            _level(token, 0, "TESTED", 0, "evidence.md"),
            _level(token, 1, "OPEN", 1),
        ],
    }
    ladder.validate(climbed, "synthetic", tmp_path)
    for broken, message in (
        (dict(climbed, levels=[_level(token, 0, record=0), _level(token, 1, record=1)]),
         "one level at a time"),
        (dict(climbed, levels=[climbed["levels"][0], dict(_level(token, 2, record=1))]),
         "contiguous from 0"),
        (dict(climbed, level=0), "highest listed level"),
        (dict(climbed, levels=[climbed["levels"][0], _level(token, 1, record=0)]),
         "newest expansion record"),
    ):  # fmt: skip
        with pytest.raises(ladder.LadderError, match=message):
            ladder.validate(broken, "synthetic", tmp_path)


def test_a_level_is_reached_only_with_its_expansion_record_and_reconstruction(tmp_path):
    token = _challenge(tmp_path, records=1)
    base = {
        "challenge": token,
        "level": 0,
        "chosen": None,
        "levels": [_level(token, 0)],
    }
    ladder.validate(base, "synthetic", tmp_path)
    no_rebuild = dict(_level(token, 0), reconstruction="tests/missing.py")
    elsewhere = dict(_level(token, 0), expansion_record="docs/0000.json")
    tested_bare = _level(token, 0, "TESTED")
    open_with_evidence = _level(token, 0, evidence="evidence.md")
    for entry, message in (
        (no_rebuild, "reconstruction"),
        (elsewhere, "names the expansion record"),
        (tested_bare, "needs its evidence"),
        (open_with_evidence, "no evidence yet"),
        (dict(_level(token, 0), state="NOT_RUN"), "unlisted level is NOT_RUN"),
    ):
        with pytest.raises(ladder.LadderError, match=message):
            ladder.validate(dict(base, levels=[entry]), "synthetic", tmp_path)
    with pytest.raises(ladder.LadderError, match="contract token"):
        ladder.validate(dict(base, challenge=None), "synthetic", tmp_path)


def test_a_level_above_0_starts_from_graphites_accepted_proposal(tmp_path, protocol):
    token = _challenge(tmp_path)
    climbed = {
        "challenge": token,
        "level": 1,
        "chosen": None,
        "levels": [
            _level(token, 0, "TESTED", 0, "evidence.md"),
            _level(token, 1, "OPEN", 1),
        ],
    }
    with pytest.raises(ladder.LadderError, match="proposal is .* in the repository"):
        ladder.validate(climbed, "synthetic", tmp_path)
    unproposed = dict(climbed["levels"][1], proposal=None)
    with pytest.raises(ladder.LadderError, match="Graphite's accepted proposal"):
        ladder.validate(
            dict(climbed, levels=[climbed["levels"][0], unproposed]),
            "synthetic",
            tmp_path,
        )
    path = _file_proposal(tmp_path, _proposal(token, status="PROPOSED"))
    with pytest.raises(ladder.LadderError, match="not ACCEPTED"):
        ladder.validate(climbed, "synthetic", tmp_path)
    path.write_text(json.dumps(_proposal(token)))
    ladder.validate(climbed, "synthetic", tmp_path)


def test_graphite_proposes_and_the_contract_owner_decides(protocol, tmp_path):
    proposals.validate(_proposal(status="PROPOSED"), "p", protocol)
    proposals.validate(_proposal(), "p", protocol)
    engineer = {"agent": "engineer", "role": "planner", "session": "x"}
    capability = _proposal()["capabilities"][0]
    for proposal, message in (
        (_proposal(proposed_by=engineer), "agent: graphite"),
        (_proposal(decision=dict(SIGNED, by="Harshdeep")), "technical owner"),
        (_proposal(status="PROPOSED", decision=SIGNED), "no decision yet"),
        (_proposal(capabilities=[dict(capability, sources=[])]), "sources"),
        (_proposal(capabilities=[dict(capability, id="loss")]), "<group>.<name>"),
        (_proposal(capabilities=[capability, capability]), "unique"),
        (_proposal(capabilities=[], left_out=[]), "why the level adds nothing"),
        (_proposal(level=6), "level is 0-5"),
    ):
        with pytest.raises(proposals.ProposalError, match=message):
            proposals.validate(proposal, "p", protocol)
    # Filed under its own challenge and level.
    directory = tmp_path / "proposals"
    (directory / "synthetic-heat-v1").mkdir(parents=True)
    (directory / "synthetic-heat-v1/level-2.json").write_text(json.dumps(_proposal()))
    with pytest.raises(proposals.ProposalError, match="its own challenge and level"):
        proposals.load_proposals(protocol, directory)


def test_test_iterate_needs_a_ladder_and_frozen_results_a_frozen_level(
    protocol, battery
):
    ids, locked = {"f04"}, _locked(protocol)
    gated = dict(battery["gates"], scope=SIGNED, design=SIGNED)
    flow = dict(battery, family="f04", stage="test", gates=gated)
    validate_record(flow, locked, ids)
    with pytest.raises(
        PipelineError, match="needs a construction contract on the ladder"
    ):
        validate_record(dict(flow, construction=ladder.empty()), locked, ids)
    evidence = dict(
        battery["evidence"], frozen="carbon/challenge_pipeline/protocol.json"
    )
    frozen_run = dict(flow, evidence=evidence, suite="suite-v1", rho=0.5)
    with pytest.raises(PipelineError, match="chosen construction level, FROZEN"):
        validate_record(frozen_run, locked, ids)
    level = dict(
        battery["construction"]["levels"][0],
        state="FROZEN",
        evidence="carbon/challenge_pipeline/protocol.json",
    )
    construction = dict(battery["construction"], levels=[level], chosen=0)
    validate_record(dict(frozen_run, construction=construction), locked, ids)
    # Ready for deployment needs the chosen level miners will get.
    ready = dict(
        flow,
        stage="ready",
        gates=dict(gated, track_a=dict(SIGNED, by="Ryan"), track_b=SIGNED),
    )
    with pytest.raises(PipelineError, match="chosen construction level miners get"):
        validate_record(ready, locked, ids)


def test_the_climb_is_internal_and_miners_get_the_chosen_level(tmp_path):
    token = _challenge(tmp_path)
    _file_proposal(tmp_path, _proposal(token))
    tested = {
        "challenge": token,
        "level": 1,
        "chosen": 0,
        "levels": [
            _level(token, 0, "FROZEN", 0, "evidence.md"),
            _level(token, 1, "TESTED", 1, "evidence.md"),
        ],
    }
    # The best level need not be the highest tested.
    ladder.validate(tested, "synthetic", tmp_path)
    for broken, message in (
        (dict(tested, chosen=None), "only the chosen level is FROZEN"),
        (dict(tested, chosen=1), "only the chosen level is FROZEN"),
        (dict(tested, chosen=3), "TESTED or FROZEN level the climb reached"),
        (
            dict(
                tested,
                chosen=1,
                levels=[
                    _level(token, 0, "TESTED", 0, "evidence.md"),
                    _level(token, 1, "OPEN", 1),
                ],
            ),
            "TESTED or FROZEN level the climb reached",
        ),
    ):
        with pytest.raises(ladder.LadderError, match=message):
            ladder.validate(broken, "synthetic", tmp_path)
    assert ladder.LAUNCH[0].startswith("Choose the Challenge's construction level")


# --- lessons after every execution --------------------------------------------


def _lesson(**changes):
    entry = {
        "schema": "carbon.challenge-pipeline.lesson.v1",
        "lesson_id": "2026-10-02-example",
        "recorded_at": "2026-10-02T12:00:00Z",
        "challenge": "synthetic-heat-v1",
        "stage": "test_iterate",
        "execution": {"kind": "test_run", "ref": "abc123", "description": "ran it"},
        "expected": "it passes",
        "observed": "it passed",
        "keep": ["the check"],
        "change": [],
        "protocol_elements": ["suite_v1.A5"],
        "proposed_revision": None,
        "status": "RECORDED",
    }
    entry.update(changes)
    return entry


def test_the_committed_lessons_are_valid_and_cover_the_ladder_fix(protocol):
    entries = load_lessons(protocol)
    assert len(entries) >= 5 and len(list(LESSONS.glob("*.json"))) == len(entries)
    fix = next(
        e for e in entries if e["lesson_id"].endswith("construction-ladder-dropped")
    )
    assert fix["status"] == "ADOPTED"
    assert fix["decision"]["ref"] == "OWNER-CHALLENGE-ROADMAP-03"


def test_a_lesson_records_one_execution(protocol):
    validate_lesson(_lesson(), "2026-10-02-example", protocol)
    revision = {"target": "suite_v1.A5", "text": "repeat seeds three times"}
    for entry, name, message in (
        (_lesson(), "2026-10-02-other", "file name"),
        (_lesson(recorded_at="2026-10-03T00:00:00Z"), "2026-10-02-example", "recorded date"),
        (_lesson(recorded_at="2026-10-02T12:00:00+02:00"), "2026-10-02-example", "UTC"),
        (_lesson(execution={"kind": "chat", "ref": "x", "description": "y"}),
         "2026-10-02-example", "kind one of"),
        (_lesson(protocol_elements=[]), "2026-10-02-example", "at least one protocol element"),
        (_lesson(observed=" "), "2026-10-02-example", "observed is a statement"),
        (_lesson(challenge="Battery!"), "2026-10-02-example", "Challenge token"),
        (_lesson(proposed_revision=revision), "2026-10-02-example", "makes the lesson PROPOSED"),
        (_lesson(status="PROPOSED"), "2026-10-02-example", "needs a proposed revision"),
        (_lesson(status="ADOPTED", proposed_revision=revision),
         "2026-10-02-example", "needs a decision"),
        (_lesson(decision=SIGNED), "2026-10-02-example", "only an adopted or declined"),
    ):  # fmt: skip
        with pytest.raises(LessonError, match=message):
            validate_lesson(entry, name, protocol)
    validate_lesson(
        _lesson(status="PROPOSED", proposed_revision=revision),
        "2026-10-02-example",
        protocol,
    )


def test_after_lock_only_the_process_owner_adopts_a_revision(protocol):
    revision = {"target": "suite_v1.A5", "text": "repeat seeds three times"}
    adopted = _lesson(status="ADOPTED", proposed_revision=revision, decision=SIGNED)
    validate_lesson(adopted, "2026-10-02-example", protocol)
    with pytest.raises(LessonError, match="by a named owner"):
        validate_lesson(
            dict(adopted, decision=dict(SIGNED, by="Someone")),
            "2026-10-02-example",
            protocol,
        )
    with pytest.raises(LessonError, match="by the process owner"):
        validate_lesson(adopted, "2026-10-02-example", _locked(protocol))
    validate_lesson(
        dict(adopted, decision=dict(SIGNED, by="Fitz")),
        "2026-10-02-example",
        _locked(protocol),
    )


def test_the_view_shows_the_ladder_and_the_lessons():
    text = render.render()
    assert (
        "## Construction ladder" in text and "## Lessons and proposed revisions" in text
    )
    assert (
        "| f05 Battery electrothermal response | `battery-fastcharge-ageing-development-v1` | 0 | – | OPEN | NOT_RUN"
        in text
    )
    for step in ladder.CLIMB_PROCEDURE:
        assert step in text
    # Graphite's proposals for every level: level-plan-3 filed one per level
    # for battery (2026-10-03); the technical owner accepted all six.
    assert "**Graphite's level proposals.**" in text
    assert (
        "| `battery-fastcharge-ageing-development-v1` |"
        + " ACCEPTED |" * len(ladder.LEVELS)
        in text
    )
    assert ladder.CLIMB_PROCEDURE[0].startswith(
        "Graphite proposes the level's capabilities"
    )
