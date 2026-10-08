"""Challenge-neutral design-question banks (VALIDATOR-23 slice 3a).

A toy question law exercises the neutral layer: staged solves, resumption,
live and non-live questions, exposure per window draw, and Merkle proofs.
Then battery's Q3 law fills a small bank through the quiz's real lattice,
refine and settle with a scripted truth solve. Every live reference seals
into the score bridge (#827) exactly as a question.

Synthetic roots and scripted solves only: no container, chain, network or
spend. Not a security audit (AGENTS.md §13).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPOSITORY = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPOSITORY / "tests" / "cpu"))

from test_challenge_validator_battery_bank import adapter
from test_challenge_validator_tuning_quiz import scripted_solve
from test_design_score_bridge import _panel, _task

from carbon.challenge_validator import bank_proof
from carbon.challenge_validator import design_bank as db
from carbon.challenge_validator.bank import BankRefused
from carbon.challenge_validator.battery_q3_bank import BatteryQ3Law
from carbon.design_search import score_bridge as bridge


class ToyLaw(db.QuestionLaw):
    """Two stages; odd-numbered questions have no feasible design."""

    name = "toy"
    challenge_id = "toy-challenge"
    terminal = ("OK", "NONE_FEASIBLE")

    def draw(self, role, count):
        return [
            {
                "question_id": f"{role}/q{n}",
                "task": _task(f"{role}-q{n}"),
                "draw": {"n": n},
            }
            for n in range(count)
        ]

    @staticmethod
    def _done(directory):
        path = directory / "records.jsonl"
        if not path.exists():
            return set()
        return {json.loads(line)["case_id"] for line in path.read_text().splitlines()}

    def next_stage(self, questions, work):
        for stage in ("", "second"):
            jobs = [{"case_id": f"{q}/{stage or 'first'}"} for q in sorted(questions)]
            if {j["case_id"] for j in jobs} - self._done(work / stage):
                return (stage, jobs)
        return None

    def references(self, questions, work):
        return {
            q: (
                {"status": "OK", "panel": _panel(1, 2)}
                if inputs["draw"]["n"] % 2 == 0
                else {"status": "NONE_FEASIBLE"}
            )
            for q, inputs in questions.items()
        }


def solve_all(directory, workers):
    jobs = json.loads((directory / "jobs.json").read_text())["jobs"]
    with (directory / "records.jsonl").open("a") as handle:
        for job in jobs:
            handle.write(json.dumps({"case_id": job["case_id"], "status": "OK"}) + "\n")


@pytest.fixture
def toy(tmp_path, monkeypatch):
    monkeypatch.setitem(
        db.DESIGN_BANKS, "toy", {"k": 2, "size": 4, "retire_at": 2, "values": "TEST"}
    )
    return db.DesignBank(tmp_path / "bank", ToyLaw(), solve_all)


def test_a_tranche_is_solved_through_every_stage_then_sealed(toy):
    [result] = toy.top_up()
    assert result["state"] == "SEALED"
    # Half the drawn questions are live; the others are recorded, never asked.
    assert toy.ledger.deficit(toy.bank, 4) == 2
    # The next fill draws the deficit as a new tranche.
    [again] = toy.top_up()
    assert again["state"] == "SEALED" and again["tranche"].endswith("-T2")


def test_a_failed_stage_is_pending_and_a_rerun_resumes(tmp_path, monkeypatch):
    monkeypatch.setitem(
        db.DESIGN_BANKS, "toy", {"k": 2, "size": 4, "retire_at": 2, "values": "TEST"}
    )
    calls = []

    def flaky(directory, workers):
        calls.append(directory.name)
        if len(calls) == 1:
            return  # the solve wrote nothing (an infrastructure failure)
        solve_all(directory, workers)

    bank = db.DesignBank(tmp_path / "bank", ToyLaw(), flaky)
    [first] = bank.top_up()
    assert first["state"] == "PENDING" and first["jobs"] == 4
    finished, refill = bank.top_up()
    # The rerun finished T1 rather than drawing it again, then drew the
    # live deficit (two of T1's four questions have no feasible design).
    assert (finished["tranche"], finished["state"]) == ("bank-design:toy-T1", "SEALED")
    assert (refill["tranche"], refill["state"]) == ("bank-design:toy-T2", "SEALED")


def test_every_question_draw_is_one_exposure_and_its_proof_verifies(toy):
    toy.top_up()
    toy.ledger.draw_window(toy.bank, 1, {"all": 2}, retire_at=2)
    drawn = toy.ledger.window_cases(toy.bank, 1)
    assert len(drawn["cases"]) == 2
    roots = {t["tranche"]: t["root"] for t in drawn["tranches"]}
    for case_id, case in drawn["cases"].items():
        assert case["reference"]["status"] == "OK"
        assert bank_proof.verify(
            case_id,
            case["inputs"],
            case["reference"],
            case["proof"],
            roots[case["tranche"]],
        )
    # The same window again adds no exposure; a second window adds one more.
    toy.ledger.draw_window(toy.bank, 1, {"all": 2}, retire_at=2)
    assert exposures(toy) == {case_id: 1 for case_id in drawn["cases"]}
    toy.ledger.draw_window(toy.bank, 2, {"all": 2}, retire_at=2)
    assert exposures(toy) == {case_id: 2 for case_id in drawn["cases"]}


def exposures(bank):
    with bank.ledger._db() as db:
        rows = db.execute(
            "SELECT case_id, exposures FROM cases WHERE bank = ? AND exposures > 0",
            (bank.bank,),
        ).fetchall()
    return {row[0]: row[1] for row in rows}


def test_a_malformed_task_is_refused_at_the_draw(tmp_path, monkeypatch):
    monkeypatch.setitem(
        db.DESIGN_BANKS, "toy", {"k": 2, "size": 2, "retire_at": 2, "values": "TEST"}
    )

    class Altered(ToyLaw):
        def draw(self, role, count):
            found = super().draw(role, count)
            found[0]["task"] = {**found[0]["task"], "candidates": ["a"]}
            return found

    bank = db.DesignBank(tmp_path / "bank", Altered(), solve_all)
    with pytest.raises(BankRefused) as refused:
        bank.top_up()
    assert refused.value.code == "bank_design_task_malformed"


def test_an_unregistered_bank_has_no_values(tmp_path):
    class Unregistered(ToyLaw):
        name = "unregistered"

    bank = db.DesignBank(tmp_path / "bank", Unregistered(), solve_all)
    with pytest.raises(db.ProducerRefused) as refused:
        bank.top_up()
    assert refused.value.code == "producer_design_bank_unregistered"


# -- battery Q3, the first law ------------------------------------------------------------


def test_battery_q3_questions_are_solved_refined_settled_and_bridge_ready(
    tmp_path, monkeypatch
):
    from carbon.battery import quiz_stratum as qs
    from carbon.battery.value import quiz as bq
    from carbon.challenge_validator.tuning import _records, _refined_records
    from carbon.design_search import battery_q3_v8 as v8
    from carbon.design_search import tasks

    monkeypatch.setitem(
        db.DESIGN_BANKS, "battery-q3", {**db.DESIGN_BANKS["battery-q3"], "size": 3}
    )
    target = adapter(tmp_path / "producer-state").target
    law = BatteryQ3Law(target, repository=REPOSITORY)
    solves = []

    def solve(directory, workers):
        solves.append(directory.name)
        scripted_solve(directory, edge=True)

    bank = db.DesignBank(tmp_path / "bank", law, solve)
    [result] = bank.top_up()
    assert result["state"] == "SEALED"
    # Two stages: the lattice, then the band-edge refine.
    assert solves == ["bank-design:battery-q3-T1", "refine"]
    work = tmp_path / "bank" / "work" / "bank-design:battery-q3-T1"
    contract = qs.contract(REPOSITORY)
    leaves = bank.ledger._leaves("bank-design:battery-q3-T1")
    assert len(leaves) == 3
    entries = [inputs["draw"] for _, inputs, _ in leaves]
    settled = qs.settle(
        _records(work),
        qs.refine_points(contract, entries, _records(work)),
        _refined_records(work),
    )
    questions = []
    for case_id, inputs, reference in leaves:
        tasks._verify_task_digest(inputs["task"])
        assert inputs["task"]["identity"]["challenge"] == v8.JOB
        assert reference["status"] in BatteryQ3Law.terminal
        if reference["status"] != "OK":
            continue
        grid = bq.q3_grid(contract, qs.scenario(inputs["draw"]))
        assert [row["values"] for row in reference["panel"]] == [
            v8._projection(contract, settled[job["case_id"]]) for job in grid
        ]
        questions.append(
            {
                "question_id": case_id,
                "task": inputs["task"],
                "reference": {k: reference[k] for k in ("status", "panel")},
            }
        )
    assert questions, "a scripted battery must leave at least one live question"
    # Every live question seals into the score bridge as it is.
    assert bridge.seal_score_bank(questions)["sealed"] is True
    # The question ids are opaque: no condition value appears in them.
    for case_id, inputs, _ in leaves:
        for value in inputs["draw"]["condition"]:
            assert str(value) not in case_id
