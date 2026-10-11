"""SCORE-PROOF-01: the sealed confirmation questions, on fixtures (no solve,
no sealed material): the draw is the host's own, disjoint from EV4's public
conditions and the quiz's Q3, in the shard tool's job shape; refinement
follows REF-RESOLVE-01's policy."""

from __future__ import annotations

import json
import stat

import pytest

from carbon.battery.value import contract as ev
from scripts.dev.battery import score_proof_questions as spq


@pytest.fixture
def quiz(tmp_path):
    q = tmp_path / "quiz"
    q.mkdir()
    (q / "draws.json").write_text(
        json.dumps({"q3": [{"scenario_id": "q3-0", "condition": [20.0, 0.25]}]})
    )
    return q


def test_the_draw_is_sealed_disjoint_and_in_the_shard_job_shape(tmp_path, quiz):
    work = tmp_path / "w"
    out = spq.draw(work, 12, quiz)
    assert out["questions"] == 12 and out["jobs"] == 12 * 35
    for name in ("seed", "contract.json", "jobs.json", "records.jsonl"):
        assert stat.S_IMODE((work / name).stat().st_mode) == 0o600
    assert stat.S_IMODE(work.stat().st_mode) == 0o700
    contract, digest = ev.load(work / "contract.json")
    assert digest == out["contract_digest"]
    drawn = {tuple(s["conditions"][0]) for s in contract["scenarios"]["development"]}
    base, _ = ev.load(spq.BASE_CONTRACT)
    assert not drawn & spq.public_conditions(base)
    assert (20.0, 0.25) not in drawn
    jobs = json.loads((work / "jobs.json").read_bytes())
    assert jobs["fingerprint"] == digest
    assert set(jobs["jobs"][0]) == {"case_id", "c1", "c2", "t_amb_c", "soc0"}
    with pytest.raises(SystemExit):
        spq.draw(work, 12)  # never redrawn over sealed questions


def test_the_draw_is_deterministic_in_its_seed_and_differs_across_seeds():
    base, _ = ev.load(spq.BASE_CONTRACT)
    envelope = base["operating_conditions"]["envelope"]
    a = spq.draw_conditions(b"a" * 32, 20, envelope, set())
    assert a == spq.draw_conditions(b"a" * 32, 20, envelope, set())
    assert a != spq.draw_conditions(b"b" * 32, 20, envelope, set())
    assert len(set(a)) == 20
    for t_amb, soc0 in a:
        assert envelope["t_amb_c"][0] <= t_amb <= envelope["t_amb_c"][1]
        assert envelope["soc0"][0] <= soc0 <= envelope["soc0"][1]


def test_refinement_asks_for_failed_and_unresolved_references_only(tmp_path):
    work = tmp_path / "w"
    spq.draw(work, 2)
    contract = json.loads((work / "contract.json").read_bytes())
    jobs = json.loads((work / "jobs.json").read_bytes())["jobs"]
    failed = {"case_id": jobs[0]["case_id"], "status": "REFERENCE_SOLVER_FAILED"}
    added = spq.refine_jobs(contract, [failed], jobs)
    assert added == [{**jobs[0], "refined": True}]
    # Already refined: never asked twice.
    assert spq.refine_jobs(contract, [failed], jobs + added) == []
    assert spq.refine({"x": 1} and work)["refine_jobs"] == 0  # no records yet
