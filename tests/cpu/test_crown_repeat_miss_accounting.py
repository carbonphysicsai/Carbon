"""A crown repeat that misses, through retain -> _contend (Validator, CROWN_REPEAT_MISS_ACCOUNTING_20261029).

The miner's counted grade takes its exam-cap slot, files its Ladder document once, and contends for the crown. The
crown repeat of its state misses the registered tolerance and the Carbon control rebuild on the same host reproduces:
the outcome is `candidate_not_reproducible` (V7). This pins what the miner is charged and shown:

(a) the hotkey's exam-cap slot count went up by exactly one and was not handed back;
(b) one Ladder entry, from the first (counted) grade, and none from the repeat or the control, which are the uncounted
    `repeat_grade` regrades (no slot, no Ladder, nothing filed under the miner's submission);
(c) the result carries exactly {outcome, reason, evaluation_key}: no alert, no grade values.

The first grade itself is stood in for (its binding is covered by test_pool_consider and test_regrade_retained_entry);
the repeat and the control run through the real `_repeat_of`, `repeat_grade` and `_control_check`, and the contention
through the real `_contend` and `BankPromotion` on the real v4 evidence.
"""

# ruff: noqa: F811  (the imported `case` fixture is received as a test argument)
import copy
import hashlib
import json

from test_counted_bank_grade import CONTRACT, _counted, _rows
from test_exam_cap import HOTKEY, Clock, _record, make_cap
from test_exam_cap import _adapter as cap_adapter
from test_physical_dual_pack_end_to_end import case  # noqa: F401
from test_pool_consider import _adapter_for, _register_koth, _v4

from carbon.battery.pool_store import PoolStore
from carbon.challenge_validator import bank_promotion as bp
from carbon.challenge_validator import koth_registry
from carbon.challenge_validator import lean_recipe_retention as retention
from tests.cpu._crown_repeat import stored_grade_repeat

ORIGIN_ENTRY = "sha256:" + "a" * 64
CONTROL_ENTRY = "sha256:" + "b" * 64
CONTROL = {
    "entry_id": CONTROL_ENTRY,
    "reference_total": 0.5,
    "reference_fingerprint": "sha256:" + "c" * 64,
    "control_basis": "within_noise",
    "evaluation_pack_digest": "sha256:" + "d" * 64,
}


def test_a_repeat_miss_with_a_reproducing_control_is_counted_once_feeds_the_ladder_once_and_shows_only_the_outcome(
    case, tmp_path, monkeypatch
):
    inputs, pin, artifacts = _v4(case)
    pool_adapter = _adapter_for(case, tmp_path)
    # The receiver's selected pack is the one the control was measured on (a rotation would make it none_registered).
    pool_adapter.discovery.evaluation_pack_digest = CONTROL["evaluation_pack_digest"]
    _register_koth(
        monkeypatch, tmp_path, pool_adapter.challenge_id, noise=1e-9, minima=(0.0, 0.0)
    )
    monkeypatch.setattr(koth_registry, "control", lambda challenge, **_: dict(CONTROL))
    store = PoolStore(tmp_path / "pool.sqlite", clock=lambda: 123.0)
    first = "rtsk_" + "1" * 64
    pool_adapter.ledger.record_recipe_task_intent(
        pool_adapter.contract_digest, first, "owner-hotkey", "sha256:" + "8" * 64
    )
    stored = stored_grade_repeat(store)

    cap = make_cap(tmp_path, Clock())
    _record(cap, CONTRACT, "rtsk_a", 360 * 5)
    counted_adapter = cap_adapter(cap, CONTRACT)

    calls, ladder, contest = [], [], {}

    def regrade(adapter, entry_id, **kwargs):
        calls.append((entry_id, kwargs))
        if kwargs.get("repeat_index"):
            # An uncounted regrade: the contender's own repeat (beyond the tolerance) or the control's (reproduces).
            if entry_id == CONTROL_ENTRY:
                evidence = {"model_p": {"score_status": bp.SCORED, "total_score": 0.5}}
            else:
                evidence = copy.deepcopy(stored(first)["evidence"])
                evidence["model_p"]["total_score"] += 0.5
            path = tmp_path / ("grade-" + hashlib.sha256(entry_id.encode()).hexdigest())
            path.write_text(json.dumps(evidence))
            return {
                "private_evaluation_state": "BOUND_DEVELOPMENT_ONLY",
                "private_evaluation_path": str(path),
            }
        # The counted first grade of the miner's own submission: its Ladder document is filed here, once.
        ladder.append(entry_id)
        contest.update(
            retention._contend(
                pool_adapter,
                store,
                first,
                artifacts,
                inputs,
                pin,
                retention._repeat_of(
                    pool_adapter,
                    first,
                    ORIGIN_ENTRY,
                    artifact_directory=tmp_path,
                    entry_directory=tmp_path,
                ),
            )
        )
        return {
            "entry_id": "sha256:bank",
            "private_evaluation_state": "BOUND_DEVELOPMENT_ONLY",
            "ladder_feedback_state": "RECORDED",
            "koth_comparison": dict(contest),
        }

    result = _counted(counted_adapter, "rtsk_a", monkeypatch, regrade)

    # (c) exactly the three fields, the V7 outcome, no alert.
    assert set(result["koth_comparison"]) == {"outcome", "reason", "evaluation_key"}
    assert result["koth_comparison"]["outcome"] == bp.CANDIDATE_NOT_REPRODUCIBLE
    assert result["koth_comparison"]["reason"] == bp.CONTROL_REPRODUCED
    assert store.incumbent() is None  # no crown moved

    # (a) one exam-cap slot for the miner, taken by the counted grade and not handed back.
    assert _rows(cap) == [("rtsk_a", "GRADED", "RESERVED", HOTKEY, 5)]

    # (b) one counted grade and one Ladder document; the repeat and the control are uncounted regrades.
    counted = [entry for entry, kwargs in calls if kwargs.get("counted")]
    uncounted = [
        (entry, kwargs) for entry, kwargs in calls if not kwargs.get("counted")
    ]
    assert counted == ["sha256:origin"] and ladder == ["sha256:origin"]
    assert {entry for entry, _ in uncounted} == {ORIGIN_ENTRY, CONTROL_ENTRY}
    for _entry, kwargs in uncounted:
        assert kwargs["repeat_index"] == 1
        assert not {"counted", "pool_store", "promotion", "exam_se"} & set(kwargs)
