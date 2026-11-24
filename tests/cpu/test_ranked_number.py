"""A version ranked by another recorded number than its total (owner G-LEAD-83, 24 Nov 2026; `crown_official`, `rerank`).

Claims:
- the crown row may name the accuracy half (``"score": "A"``), the total is the absent key and never spelled; without the key
  every reader is exactly as before, whatever the version;
- the crown decision, its private record, the king page, the board's exact order and the miner's Ladder read the named
  number; no kept grade, record or Ladder document of the old rule is changed;
- a re-rank reads kept grades only: the highest ranked number meets the sitting king by the ordinary decision, once per rule
  entry and exam; a grade with no such number is not ranked and gets none; crowns paused = it waits.

Every grade, digest, hotkey and model here is a SYNTHETIC fixture.
"""

from __future__ import annotations

import json
import os
from types import SimpleNamespace

import pytest

from carbon.challenge_validator import bank_promotion as bp
from carbon.challenge_validator import crown_average as ca
from carbon.challenge_validator import (
    crown_official,
    koth_public,
    ladder_store,
    launch_board,
    operator_pause,
    rerank,
)
from carbon.challenge_validator.interface import digest
from carbon.scoring.sealed_versions import ladder_key
from tests.cpu.crown_fixtures import (
    CHALLENGE,
    KEY,
    _body,
    _comparator,
    _flow,
    _pair,
)

VERSION = "1.8"
MARGIN = 0.02
EXAM = digest("exam")
HOTKEYS = {name: "5" + letter * 47 for name, letter in zip("abk", "ABK", strict=True)}
TASKS = {
    name: "rtsk_" + digest(["task", name]).removeprefix("sha256:") for name in "abk"
}


def _registry(tmp_path, entry):
    path = tmp_path / "crown_official_score.json"
    path.write_text(
        json.dumps(
            {
                "schema": crown_official.SCHEMA,
                "versions": {f"{CHALLENGE} {VERSION}": entry},
            }
        ),
        encoding="utf-8",
    )
    return path


def _install(tmp_path, monkeypatch, entry):
    path = _registry(tmp_path, entry)
    monkeypatch.setattr(crown_official, "ACTIVE", crown_official.ACTIVE)
    monkeypatch.setattr(ca, "ACTIVE", ca.ACTIVE)
    monkeypatch.setattr(crown_official, "REGISTRY", path)
    lines = []
    crown_official.install(CHALLENGE, VERSION, path=path, log=lines.append)
    return lines


@pytest.fixture
def by_accuracy(tmp_path, monkeypatch):
    return _install(tmp_path, monkeypatch, {"margin": MARGIN, "score": "A"})


def _grade(model, total, accuracy, status=bp.SCORED):
    body = _body(model, total, status)
    body["evidence"]["model_p"]["physics_benefit"] = accuracy
    body["evidence"]["model_p"]["design_benefit"] = 0.5
    return body


# -- the row -------------------------------------------------------------------------------------------------------------------


def test_the_row_may_name_the_accuracy_half_and_nothing_else(tmp_path):
    def read(entry):
        return crown_official.registered(
            CHALLENGE, VERSION, path=_registry(tmp_path, entry)
        )

    assert read({"margin": MARGIN, "score": "A"})["score"] == "A"
    assert "score" not in read({"margin": MARGIN})
    for score in ("total", "D", "", None, 1, ["A"]):
        with pytest.raises(crown_official.CrownOfficialInvalid):
            read({"margin": MARGIN, "score": score})
    with pytest.raises(crown_official.CrownOfficialInvalid):
        read({"score": "A"})
    # another number is another rule entry
    assert (
        read({"margin": MARGIN})["digest"]
        != read({"margin": MARGIN, "score": "A"})["digest"]
    )


def test_a_version_without_the_key_reads_its_total_everywhere(tmp_path, monkeypatch):
    lines = _install(tmp_path, monkeypatch, {"margin": MARGIN})
    assert lines == [f"crown_official_score=true margin={MARGIN}"]
    assert set(crown_official.ACTIVE) == {"challenge", "version", "margin", "digest"}
    assert crown_official.reader(CHALLENGE, VERSION) is None
    assert crown_official.label(CHALLENGE, VERSION) == ""
    row = {"score": 0.5, "legs": {"A": 0.4, "D": 0.6}}
    assert crown_official.ranked_row(row, CHALLENGE, VERSION) is row
    assert ladder_store.ladder_label(CHALLENGE, VERSION) == ladder_key(
        CHALLENGE, VERSION
    )
    assert crown_official.comparator(_comparator())["baseline_total"] == 0.5
    assert bp._scored(_grade("a", 0.5, 0.9)) == (bp.SCORED, 0.5)


# -- the decision --------------------------------------------------------------------------------------------------------------


def test_the_crown_is_decided_on_the_accuracy_half(tmp_path, monkeypatch, by_accuracy):
    assert by_accuracy[0].endswith(" score=A")
    king = _grade("k", 0.90, 0.60)
    pairs = {
        # a lower total and a higher accuracy half wins; the other way round does not; within the margin is a tie
        "a": _pair(_grade("a", 0.40, 0.70), king),
        "b": _pair(_grade("b", 0.99, 0.61), king),
    }
    store, promotion = _flow(tmp_path, monkeypatch, pairs)
    for pair in pairs.values():
        pair["expected_incumbent"] = None
    assert promotion.consider_private("b", KEY, _comparator())["outcome"] == (
        bp.INCUMBENT_KEEPS
    )
    assert promotion.consider_private("a", KEY, _comparator())["outcome"] == (
        bp.CHALLENGER
    )
    assert store.incumbent()["model_id"] == "a"
    with store.db() as db:
        (raw,) = db.execute(
            "SELECT body FROM operations WHERE kind='crown_average.v1'"
        ).fetchone()
    private = json.loads(raw)["private"]
    assert private["score"] == "A" and private["rule"] == crown_official.RECORD_RULE
    assert (private["candidate_total"], private["incumbent_total"]) == (0.70, 0.60)
    assert store.crown_decided_by("a") == {"A"} and store.crown_decided_by("k") == set()


def test_an_old_record_stays_beside_the_new_one(tmp_path, monkeypatch, by_accuracy):
    store, promotion = _flow(
        tmp_path,
        monkeypatch,
        {"a": _pair(_grade("a", 0.4, 0.7), _grade("k", 0.9, 0.6))},
    )
    old = {"rule": crown_official.RECORD_RULE, "margin": 0.0129, "candidate_total": 0.4}
    store.record_crown_average("a", KEY, old)
    promotion.store.private_evaluation_pair.pairs["a"]["expected_incumbent"] = None
    assert promotion.consider_private("a", KEY, _comparator())["outcome"] == (
        bp.CHALLENGER
    )
    with store.db() as db:
        rows = [
            json.loads(raw)["private"]
            for (raw,) in db.execute(
                "SELECT body FROM operations WHERE kind='crown_average.v1' ORDER BY rowid"
            )
        ]
    assert rows[0] == old and len(rows) == 2 and rows[1]["score"] == "A"


def test_a_grade_with_no_stored_accuracy_does_not_count_and_is_never_read_as_its_total(
    by_accuracy,
):
    assert bp._scored(_grade("a", 0.9, None)) == (crown_official.UNRANKED, None)
    with pytest.raises(bp.StateError):
        bp._scored(_grade("a", 0.9, 1.5))
    king = _grade("k", 0.9, 0.6)
    out = bp.compare_private_pair(
        _pair(_grade("a", 0.9, None), king), crown_official.comparator(_comparator())
    )
    assert (out["outcome"], out["reason"]) == (
        bp.INCUMBENT_KEEPS,
        "candidate_not_scored",
    )


@pytest.mark.parametrize("design", [0.0, 0, None, float("nan"), True, "0.5", -0.1])
def test_a_grade_that_does_not_show_its_row_check_passed_never_ranks(
    by_accuracy, design
):
    """MODEL_ROW_DEPENDENT is a design value of exactly 0.0 with the accuracy half untouched (`pool_menu.score`)."""
    contender = _grade("a", 0.9, 0.99)
    contender["evidence"]["model_p"]["design_benefit"] = design
    assert bp._scored(contender) == (crown_official.UNRANKED, None)
    out = bp.compare_private_pair(
        _pair(contender, _grade("k", 0.9, 0.6)),
        crown_official.comparator(_comparator()),
    )
    assert out["outcome"] == bp.INCUMBENT_KEEPS
    row = {"status": bp.SCORED, "score": 0.9, "legs": {"A": 0.99, "D": design}}
    shown = crown_official.ranked_row(row, CHALLENGE, VERSION)
    assert (shown["status"], shown["score"]) == (crown_official.UNRANKED, None)
    kept = _kept("a", 0.9, 0.99)
    kept["evidence"]["model_p"]["design_benefit"] = design
    ranked, unranked = rerank.ranking(
        rerank.kept(_Kept([kept]), challenge_id=CHALLENGE, exam=EXAM), "A"
    )
    assert ranked == [] and unranked == {"row_check_unknown": 1}
    exact = launch_board.exact_best_totals(
        _Kept([kept]),
        challenge_id=CHALLENGE,
        exam_key=EXAM,
        value=crown_official.reader(CHALLENGE, VERSION),
    )
    assert exact == {}


def test_the_row_checks_own_finding_is_a_design_value_of_exactly_zero():
    import inspect

    from carbon.scoring import pool_menu

    text = inspect.getsource(pool_menu.score)
    branch = text[
        text.index("if row_dependent:") : text.index("for task in tasks:\n        rows")
    ]
    assert '"D": 0.0' in branch and '"state": MODEL_ROW_DEPENDENT' in branch


def test_a_total_version_never_reads_the_row_check(tmp_path, monkeypatch):
    _install(tmp_path, monkeypatch, {"margin": MARGIN})
    body = _grade("a", 0.5, 0.9)
    body["evidence"]["model_p"]["design_benefit"] = 0.0
    assert bp._scored(body) == (bp.SCORED, 0.5)


def test_a_first_crown_never_meets_a_baseline_of_another_number(by_accuracy):
    out = bp.compare_private_pair(
        _pair(_grade("a", 0.9, 0.9), None), crown_official.comparator(_comparator())
    )
    assert (out["outcome"], out["reason"]) == (
        bp.UNAVAILABLE,
        "baseline_floor_unregistered",
    )


# -- the Ladder, the king page, the board --------------------------------------------------------------------------------------


def test_the_ladder_gets_a_new_key_and_the_accuracy_half(by_accuracy):
    assert ladder_store.ladder_label(CHALLENGE, VERSION) == (
        ladder_key(CHALLENGE, VERSION) + "+accuracy"
    )
    # another version keeps its own
    assert ladder_store.ladder_label(CHALLENGE, "1.7") == ladder_key(CHALLENGE, "1.7")
    row = {"status": "x", "score": 0.5, "legs": {"A": 0.4, "D": 0.6}}
    assert crown_official.ranked_row(row, CHALLENGE, VERSION) == {**row, "score": 0.4}
    assert row["score"] == 0.5
    unscored = {"status": "x", "score": None, "legs": {"A": 0.4, "D": 0.6}}
    assert crown_official.ranked_row(unscored, CHALLENGE, VERSION) is unscored


def test_old_ladder_documents_are_neither_served_nor_rewritten(tmp_path, monkeypatch):
    from carbon.challenge_validator.ledger import AttemptLedger
    from carbon.registry.model import ChallengeKey

    root = tmp_path / "receiver"
    root.mkdir(mode=0o700)
    os.chmod(root, 0o700)
    ledger = AttemptLedger(root / "attempts.sqlite3")
    store, key = ladder_store.LadderStore(ledger), ChallengeKey(CHALLENGE, VERSION)

    def record(total, accuracy):
        graded = {
            "status": bp.SCORED,
            "score": total,
            "legs": {"A": accuracy, "D": 0.5},
            "gates": {"g": "PASS"},
        }
        return store.record(
            "5Miner",
            key,
            EXAM,
            crown_official.ranked_row(graded, CHALLENGE, VERSION),
            exam_version="exam-1",
            gates=("g",),
            rebuild_noise=None,
        )

    def rows():
        with ledger._db() as db:
            return db.execute(
                "SELECT evaluation_version, best, latest FROM ladder_feedback_v2 ORDER BY 1"
            ).fetchall()

    _install(tmp_path, monkeypatch, {"margin": MARGIN})
    assert record(0.9, 0.5)["total"] == 0.9
    (old,) = rows()
    _install(tmp_path, monkeypatch, {"margin": MARGIN, "score": "A"})
    assert store.served("5Miner", key, EXAM) == {"best": None, "latest": None}
    assert ladder_store.board_rows(ledger.path, key, EXAM) == []
    assert record(0.9, 0.5)["total"] == 0.5
    assert old in rows() and len(rows()) == 2
    ((hotkey, best, _latest),) = ladder_store.board_rows(ledger.path, key, EXAM)
    assert (hotkey, best["total"]) == ("5Miner", 0.5)
    # the old row again, with nothing lost
    _install(tmp_path, monkeypatch, {"margin": MARGIN})
    assert store.served("5Miner", key, EXAM)["best"]["total"] == 0.9


class _Kept:
    """The pool store's readers, over synthetic evaluations."""

    def __init__(self, bodies, king=None, decided=(), paused=()):
        self.bodies, self.king, self.decided = bodies, king, set(decided)
        self.paused = list(paused)
        self.decisions = []

    def private_evaluation_bodies(self):
        return list(self.bodies)

    def incumbent(self):
        return None if self.king is None else {"model_id": self.king, "reason": "x"}

    def incumbent_standing(self, model_id, *, value=None):
        for body in reversed(self.bodies):
            if body["submission_id"] == model_id:
                model = body["evidence"]["model_p"]
                number = model["total_score"] if value is None else value(model)
                return {"owner": body["owner"], "total": float(number)}
        return None

    def events(self, kind):
        return [
            {"body": {"model_id": TASKS["b"], "previous": None}},
            {"body": {"model_id": TASKS["a"], "previous": TASKS["b"]}},
        ]

    def crown_decided_by(self, model_id):
        return {"A"} if model_id in self.decided else set()

    def paused_crowns(self):
        return self.paused

    def record_crown_decision(self, *fields):
        self.decisions.append(fields)


def _kept(name, total, accuracy, status=bp.SCORED, exam=EXAM, task=None):
    return {
        "submission_id": TASKS[name] if task is None else task,
        "owner": {"hotkey": HOTKEYS[name], "request_digest": digest(["request", name])},
        "evaluation_key": KEY,
        "recipe_digest": digest(["recipe", name]),
        "evidence": {
            "challenge": CHALLENGE,
            "evaluation_pack_digest": exam,
            "evaluation_version": "exam-1",
            "entry_id": digest(["entry", name]),
            "source_receipt_sha256": digest("pin"),
            "model_p": {
                "score_status": status,
                "total_score": total,
                "physics_benefit": accuracy,
                "design_benefit": 0.5,
                "gate_outcomes": {"g": "PASS"},
            },
        },
    }


def test_the_king_page_and_the_exact_order_read_the_ranked_number(by_accuracy):
    store = _Kept([_kept("a", 0.5, 0.75), _kept("b", 0.75, 0.5)], king=TASKS["a"])
    value = crown_official.reader(CHALLENGE, VERSION)

    def view(**extra):
        return koth_public.PoolKingView(
            open_store=lambda: store,
            epoch_of=lambda model: 7,
            exam_version_label="exam",
            rebuild_noise_of=lambda: None,
            **extra,
        )

    assert view(value=value).king()["total"] == 0.75
    assert view().king()["total"] == 0.5
    exact = launch_board.exact_best_totals(
        store, challenge_id=CHALLENGE, exam_key=EXAM, value=value
    )
    assert exact == {HOTKEYS["a"]: 0.75, HOTKEYS["b"]: 0.5}
    # a change of king decided on the total keeps its total; one decided on the ranked number shows that
    shown = [c["total"] for c in view(value=value).crown_changes(v3=True)]
    assert shown == [0.5, 0.75]
    store.decided = {TASKS["a"]}
    shown = [c["total"] for c in view(value=value).crown_changes(v3=True)]
    assert shown == [0.75, 0.75]
    assert [c["total"] for c in view().crown_changes(v3=True)] == [0.5, 0.75]


# -- the re-rank ---------------------------------------------------------------------------------------------------------------


def test_the_ranking_is_the_kept_number_and_invents_none():
    other = "rtsk_" + "9" * 64
    rows = rerank.kept(
        _Kept(
            [
                _kept("a", 0.9, 0.5),
                _kept("b", 0.1, 0.8),
                _kept("k", 0.2, 0.8),
                _kept("a", 0.9, None, task=other),
                _kept(
                    "a",
                    None,
                    0.9,
                    status="MANDATORY_GATE_FAILED",
                    task=other[:-1] + "8",
                ),
                _kept("a", 0.9, 0.99, exam=digest("other exam"), task=other[:-1] + "7"),
                _kept("a", 0.9, 0.99, task="krb_derived"),
            ]
        ),
        challenge_id=CHALLENGE,
        exam=EXAM,
    )
    ranked, unranked = rerank.ranking(rows, "A")
    # the oldest of equals first
    assert [r["submission_id"] for r in ranked] == [TASKS["b"], TASKS["k"], TASKS["a"]]
    assert unranked == {"no_stored_number": 1, "MANDATORY_GATE_FAILED": 1}
    assert rerank.ranking(rows, "total")[0][0]["submission_id"] == TASKS["a"]
    start = dict(rerank.backfill_order(rows, "A"))
    assert [r["submission_id"] for r in start[HOTKEYS["b"]]] == [TASKS["b"]]
    own = [r["submission_id"] for r in start[HOTKEYS["a"]]]
    assert own == [TASKS["a"], other[:-1] + "8"]


def _adapter():
    return SimpleNamespace(discovery=SimpleNamespace(evaluation_pack_digest=EXAM))


def _step(tmp_path, store, outcomes, calls, registered=lambda hotkey: True):
    def reconsider(record):
        calls.append(record)
        return outcomes.pop(0)

    return rerank.step(
        _adapter(),
        store,
        root=tmp_path,
        artifacts=None,
        entries=None,
        registered=registered,
        reconsider=reconsider,
        start=lambda adapter, rows, score: (0, 0),
    )


def test_the_highest_meets_the_king_once(tmp_path, by_accuracy):
    store = _Kept([_kept("k", 0.9, 0.5), _kept("a", 0.1, 0.8)], king=TASKS["k"])
    calls = []
    won = {"outcome": bp.CHALLENGER, "reason": "r", "evaluation_key": KEY}
    assert _step(tmp_path, store, [won], calls) is True
    assert [c["submission_id"] for c in calls] == [TASKS["a"]]
    assert set(calls[0]) == {"submission_id", "evaluation_key", "entry_id", "pin"}
    # the decision is filed, as any crown decision is (`winner_eligibility` reads it)
    assert store.decisions == [(TASKS["a"], KEY, bp.CHALLENGER, "r")]
    (line,) = rerank._log_path(tmp_path).read_text(encoding="utf-8").splitlines()
    assert json.loads(line)["rule_digest"] == crown_official.ACTIVE["digest"]
    assert "0.8" not in line
    # a later start decides nothing again
    assert _step(tmp_path, store, [], calls) is True and len(calls) == 1


def test_a_paused_or_undecided_crown_is_tried_again(tmp_path, by_accuracy):
    store = _Kept([_kept("k", 0.9, 0.5), _kept("a", 0.1, 0.8)], king=TASKS["k"])
    calls = []
    for reason in (bp.CROWNS_PAUSED, bp.CROWN_QUEUED, bp.INCUMBENT_REGRADE_REQUIRED):
        waits = {"outcome": bp.UNAVAILABLE, "reason": reason, "evaluation_key": KEY}
        assert _step(tmp_path, store, [waits], calls) is False
    assert not rerank._log_path(tmp_path).exists()
    keeps = {"outcome": bp.INCUMBENT_KEEPS, "reason": "tie", "evaluation_key": KEY}
    assert _step(tmp_path, store, [keeps], calls) is True and len(calls) == 4


def test_a_hotkey_not_registered_now_is_not_contended_for(tmp_path, by_accuracy):
    store = _Kept(
        [_kept("k", 0.9, 0.5), _kept("a", 0.1, 0.8), _kept("b", 0.1, 0.7)],
        king=TASKS["k"],
    )
    calls = []
    # the chain cannot be read: it waits, and nothing is started or written
    assert _step(tmp_path, store, [], calls, registered=None) is False and calls == []
    won = {"outcome": bp.CHALLENGER, "reason": "r", "evaluation_key": KEY}
    here = {HOTKEYS["b"], HOTKEYS["k"]}
    assert _step(tmp_path, store, [won], calls, registered=here.__contains__) is True
    assert [c["submission_id"] for c in calls] == [TASKS["b"]]
    line = json.loads(rerank._log_path(tmp_path).read_text(encoding="utf-8"))
    assert (line["ranked"], line["unregistered"]) == (3, 1)


def test_registration_is_the_receivers_own_snapshot():
    snapshot = SimpleNamespace(resolve={HOTKEYS["a"]: "member"}.get)
    window = SimpleNamespace(latest=lambda: snapshot)
    registered = rerank.registered_now(window)
    assert registered(HOTKEYS["a"]) is True and registered(HOTKEYS["b"]) is False
    assert rerank.registered_now(None) is None
    assert rerank.registered_now(SimpleNamespace(latest=lambda: None)) is None


def test_the_sitting_king_first_changes_nothing(tmp_path, by_accuracy):
    store = _Kept([_kept("k", 0.9, 0.8), _kept("a", 0.1, 0.7)], king=TASKS["k"])
    calls = []
    assert _step(tmp_path, store, [], calls) is True
    assert calls == [] and store.decisions == []


def test_a_version_ranked_by_its_total_is_never_re_ranked(tmp_path, monkeypatch):
    _install(tmp_path, monkeypatch, {"margin": MARGIN})
    store = _Kept([_kept("a", 0.9, 0.8)])
    assert _step(tmp_path, store, [], []) is True
    assert not rerank._log_path(tmp_path).exists()
    from carbon.challenge_validator import auto_grade

    assert auto_grade.AutoGrader._rerank_due(SimpleNamespace()) is False


def test_the_receiver_runs_it_until_it_is_decided(monkeypatch, by_accuracy):
    from carbon.challenge_validator import auto_grade

    grader = auto_grade.AutoGrader.__new__(auto_grade.AutoGrader)
    grader.intake = SimpleNamespace(adapter=None)
    grader.root = grader.artifacts = grader.entries = None
    grader._pool = lambda: None
    answers = [False, RuntimeError("x"), True]
    ran = []

    def step(*args, **kwargs):
        ran.append(1)
        answer = answers.pop(0)
        if isinstance(answer, Exception):
            raise answer
        return answer

    monkeypatch.setattr(rerank, "step", step)
    grader._rerank()
    assert grader._rerank_due() is False  # spaced
    grader._rerank()
    assert len(ran) == 1
    grader._rerank_next = 0.0
    grader._rerank()  # a failure never leaves the step
    grader._rerank_next = 0.0
    grader._rerank()
    assert len(ran) == 3 and grader._rerank_due() is False


def test_the_pause_flag_is_the_ordinary_one(tmp_path, monkeypatch, by_accuracy):
    pairs = {"a": _pair(_grade("a", 0.4, 0.7), _grade("k", 0.9, 0.6))}
    store, promotion = _flow(tmp_path, monkeypatch, pairs)
    pairs["a"]["expected_incumbent"] = None
    monkeypatch.setattr(operator_pause, "crowns_paused", lambda directory: True)
    out = promotion.consider_private("a", KEY, _comparator())
    assert out["reason"] == bp.CROWNS_PAUSED and store.incumbent() is None
