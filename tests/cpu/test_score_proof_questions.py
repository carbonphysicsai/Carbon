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


def test_a_fresh_set_excludes_every_condition_an_earlier_set_drew(
    tmp_path, monkeypatch
):
    """CUSTODY-03-EXT-01: fresh sealed confirmation questions never repeat a
    condition of a set already drawn or used (`--exclude-work`)."""
    first = tmp_path / "score-proof-1"
    spq.draw(first, 30)
    earlier, _ = ev.load(first / "contract.json")
    taken = {tuple(s["conditions"][0]) for s in earlier["scenarios"]["development"]}
    # Force the second seed to be the first's: without the exclusion it would
    # draw exactly the same conditions.
    monkeypatch.setattr(spq, "seed", lambda work: (first / "seed").read_bytes())
    second = tmp_path / "score-proof-2"
    out = spq.draw(second, 30, exclude_works=[first])
    fresh, _ = ev.load(second / "contract.json")
    drawn = {tuple(s["conditions"][0]) for s in fresh["scenarios"]["development"]}
    assert out["questions"] == 30 and len(drawn) == 30
    assert not drawn & taken
    assert spq.work_conditions([first], second) == taken
    assert spq.work_conditions([], second) == set()


def test_the_exclusion_reads_only_an_earlier_score_proof_set_beside_this_one(
    tmp_path,
):
    """The Validator's reading of CUSTODY-03-EXT-01: `--exclude-work` reads
    the first score-proof set only (a sibling `score-proof-<n>` with the
    sealed contract), never EV5's sealed batch, `graphite-confirmation-v1`
    or another set."""
    private = tmp_path / "private"
    first = private / "score-proof-1"
    spq.draw(first, 5)
    fresh = private / "score-proof-2"
    assert spq.excluded_work(first, fresh)[0] == first.resolve()

    def refused(earlier, work=fresh):
        with pytest.raises(SystemExit, match="exclude_work_not_a_score_proof_set"):
            spq.excluded_work(earlier, work)

    # Another set's name, even with a score-proof contract.
    for name in ("ev5-sealed-14", "graphite-confirmation-v1", "score-proof-x"):
        other = private / name
        other.mkdir()
        (other / "contract.json").write_bytes((first / "contract.json").read_bytes())
        refused(other)
    # Not beside this draw's work directory.
    elsewhere = tmp_path / "elsewhere" / "score-proof-1"
    elsewhere.mkdir(parents=True)
    (elsewhere / "contract.json").write_bytes((first / "contract.json").read_bytes())
    refused(elsewhere)
    # A symlink to the first set, and the draw's own directory.
    link = private / "score-proof-3"
    link.symlink_to(first)
    refused(link)
    refused(first, work=first)
    # A score-proof-named directory whose contract is not the sealed one.
    foreign = private / "score-proof-4"
    foreign.mkdir()
    (foreign / "contract.json").write_text(
        '{"contract_id": "graphite-confirmation-v1"}'
    )
    refused(foreign)
    # The draw refuses before writing anything.
    with pytest.raises(SystemExit, match="exclude_work_not_a_score_proof_set"):
        spq.draw(private / "score-proof-5", 5, exclude_works=[foreign])
    assert not (private / "score-proof-5" / "contract.json").exists()
