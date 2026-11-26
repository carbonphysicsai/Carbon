"""The crown confirmation set (owner CROWN-CONFIRMATION-SET, 25 Nov 2026, verbatim: "approved: new crowns on Motor 1.9,
RB 2.0 and joint must also hold on a small confirmation set, fingerprinted at open and published at close; shown scores
stay on the open set."; door-code 8314, Lead GO 8421).

Claims:
1. REGISTRATION: a crown row may carry a ``confirmation`` block; an empty block is the owner's line with nothing ruled
   (every crown it decides waits); a block with an unknown key or value refuses. No public repository row carries one
   (1.8 unchanged).
2. DECISION: a crown change on such a version is applied only when the contender's confirmation number holds (above
   the king's; an equal one only under a registered tie rule "confirms", bank 8442); a lower number or an invalid
   confirmation answer keeps the king (no winner with no king; a gate-failed
   king is still dethroned); an unruled value or a missing record waits, filed like a queued crown, never crowned on the
   open rule alone. A version without a block decides exactly as before.
3. BINDING: a confirmation record stands only for the grade whose dual measurement and pack it names.
4. GRADE: the confirmation rows are bank pool rows answered in the same inference, and they enter NO part of the grade
   (the returned measure is identical to the grade without them); their number is the physics family value on those
   rows, kept in the capture only; a gate-failed grade keeps none; the material must match the registration.
5. CASE ERRORS v2 (S2): every case carries its signed error (answer minus truth) for a scalar output and NaN for a
   waveform; the confirmation cases join the file as source 2; the trust record never reads them.

Every value is a SYNTHETIC fixture, never a production value.
"""

from __future__ import annotations

import dataclasses
import json
import math
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

from test_pool_exam import ARGUMENTS, CEILING, FAST, exam_rows, toy_binding
from test_pool_multiclass_regions import (  # noqa: F401  (geometric_v1_stand_in is a fixture)
    geometric_v1_stand_in,
)
from test_pool_physics_score import _registered, _sets
from test_pool_plugin import SHELL, fake_measure, good_serve
from test_pool_plugin import toy_target as exam_target

from carbon.battery.pool_store import StateError
from carbon.challenge_validator import bank_promotion as bp
from carbon.challenge_validator import crown_official
from carbon.scoring import case_errors, pool_exam, pool_version
from carbon.scoring import pool_physics_score as pps
from carbon.scoring import pool_proof_suite as suite

ROOT = Path(__file__).resolve().parents[2]
EXAM = "sha256:" + "e" * 64
DUAL = "sha256:" + "d" * 64
KEY = "sha256:" + "1" * 64
RULED = {"number": "A", "first_crown": "open_rule_only", "tie": "not_confirmed"}


@pytest.fixture(autouse=True)
def _no_installed_rule(monkeypatch):
    monkeypatch.setattr(crown_official, "ACTIVE", None)


def _registry(tmp_path, versions):
    path = tmp_path / "crown_official_score.json"
    path.write_text(
        json.dumps({"schema": crown_official.SCHEMA, "versions": versions}),
        encoding="utf-8",
    )
    return path


def _install(tmp_path, entry):
    path = _registry(tmp_path, {"zz-synthetic 1.0": entry})
    return crown_official.install(
        "zz-synthetic", "1.0", path=path, log=lambda line: None
    )


def _record(value=0.5, status="MEASURED", dual=DUAL, exam=EXAM):
    return crown_official.confirmation_record(
        {"confirmation": {"status": status, "value": value, "sets_sha256": "a" * 64}},
        exam,
        dual,
    )


# ---------------------------------------------------------------- 1. registration


def test_a_row_may_carry_a_confirmation_block_and_an_empty_one_is_the_unruled_line(
    tmp_path,
):
    path = _registry(
        tmp_path,
        {
            "a 1": {"margin": 0.01, "confirmation": {}},
            "b 1": {"margin": 0.01, "confirmation": RULED},
            "c 1": {"margin": 0.01},
            "d 1": {"margin": 0.01, "score": "A", "confirmation": {"number": "A"}},
        },
    )
    assert crown_official.registered("a", "1", path=path)["confirmation"] == {}
    assert crown_official.registered("b", "1", path=path)["confirmation"] == RULED
    assert "confirmation" not in crown_official.registered("c", "1", path=path)
    both = crown_official.registered("d", "1", path=path)
    assert (both["score"], both["confirmation"]) == ("A", {"number": "A"})


@pytest.mark.parametrize(
    "block",
    [
        None,
        [],
        {"number": "total"},
        {"first_crown": "speed_matched_zero"},
        {"tie": "maybe"},
        {"number": "A", "extra": 1},
    ],
)
def test_a_malformed_confirmation_block_refuses(tmp_path, block):
    path = _registry(tmp_path, {"a 1": {"margin": 0.01, "confirmation": block}})
    with pytest.raises(crown_official.CrownOfficialInvalid) as refused:
        crown_official.registered("a", "1", path=path)
    assert refused.value.code == "crown_official_confirmation_malformed"


def test_no_public_repository_row_carries_a_block_and_the_live_row_is_unchanged():
    """The versions whose rows carry a confirmation block live on carbon-internal until they open (owner G-LEAD-122)."""
    rows = json.loads(Path(crown_official.REGISTRY).read_bytes())["versions"]
    assert {name for name, row in rows.items() if "confirmation" in row} == set()
    # the live 1.8 row is exactly as before
    assert rows["electric-motor-magnetics 1.8"] == {"margin": 0.0129, "score": "A"}


def test_install_logs_whether_the_confirmation_is_ruled(tmp_path):
    lines = []
    path = _registry(tmp_path, {"zz 1": {"margin": 0.01, "confirmation": {}}})
    crown_official.install("zz", "1", path=path, log=lines.append)
    assert lines == ["crown_official_score=true margin=0.01 confirmation=unset"]


# ---------------------------------------------------------------- 2. the verdict


def test_no_block_means_no_confirmation_verdict(tmp_path):
    _install(tmp_path, {"margin": 0.01})
    assert crown_official.confirm(False, None, None) is None


@pytest.mark.parametrize(
    "block, first, mine, theirs, verdict",
    [
        # nothing ruled: every crown waits, whatever the numbers
        ({}, False, 0.9, 0.1, ("WAIT", crown_official.CROWN_CONFIRMATION_UNSET)),
        ({}, True, 0.9, None, ("WAIT", crown_official.CROWN_CONFIRMATION_UNSET)),
        # the number and tie ruled, the first crown not: a challenger is decided, a first crown waits
        (
            {"number": "A", "tie": "not_confirmed"},
            False,
            0.6,
            0.5,
            ("CONFIRMED", None),
        ),
        (
            {"number": "A", "tie": "not_confirmed"},
            True,
            0.6,
            None,
            ("WAIT", crown_official.CROWN_CONFIRMATION_UNSET),
        ),
        # the number and first crown ruled, the tie not (bank 8442): a first crown is decided, a challenger waits
        (
            {"number": "A", "first_crown": "open_rule_only"},
            True,
            0.6,
            None,
            ("CONFIRMED", None),
        ),
        (
            {"number": "A", "first_crown": "open_rule_only"},
            False,
            0.6,
            0.5,
            ("WAIT", crown_official.CROWN_CONFIRMATION_UNSET),
        ),
        (RULED, True, 0.6, None, ("CONFIRMED", None)),
        (
            RULED,
            False,
            0.5,
            0.5,
            ("NOT_CONFIRMED", crown_official.CROWN_NOT_CONFIRMED),
        ),
        (
            {**RULED, "tie": "confirms"},
            False,
            0.5,
            0.5,
            ("CONFIRMED", None),
        ),
        (
            RULED,
            False,
            0.4,
            0.5,
            ("NOT_CONFIRMED", crown_official.CROWN_NOT_CONFIRMED),
        ),
    ],
)
def test_the_verdict_matrix(tmp_path, block, first, mine, theirs, verdict):
    _install(tmp_path, {"margin": 0.01, "confirmation": block})
    king = None if theirs is None else _record(theirs)
    assert crown_official.confirm(first, _record(mine), king) == verdict


def test_a_missing_or_unavailable_record_waits_and_an_invalid_answer_is_not_confirmed(
    tmp_path,
):
    _install(tmp_path, {"margin": 0.01, "confirmation": RULED})
    unavailable = ("WAIT", crown_official.CROWN_CONFIRMATION_UNAVAILABLE)
    assert crown_official.confirm(False, None, _record(0.5)) == unavailable
    assert crown_official.confirm(False, _record(0.9), None) == unavailable
    assert (
        crown_official.confirm(False, _record(None, "UNAVAILABLE"), _record(0.5))
        == unavailable
    )
    king_invalid = _record(None, "INVALID")
    assert crown_official.confirm(False, _record(0.9), king_invalid) == unavailable
    assert crown_official.confirm(True, _record(None, "INVALID"), None) == (
        "NOT_CONFIRMED",
        crown_official.CROWN_NOT_CONFIRMED,
    )


@pytest.mark.parametrize(
    "found",
    [
        {"status": "MEASURED", "value": math.nan},
        {"status": "MEASURED", "value": True},
        {"status": "MEASURED"},
        {"status": "MAYBE", "value": 0.5},
        "MEASURED",
    ],
)
def test_a_capture_of_another_shape_is_unavailable(found):
    record = crown_official.confirmation_record({"confirmation": found}, EXAM, DUAL)
    assert (record["status"], record["value"]) == ("UNAVAILABLE", None)


def test_a_version_without_a_confirmation_set_files_no_record():
    assert crown_official.confirmation_record({}, EXAM, DUAL) is None
    assert crown_official.confirmation_record({"accuracy": {}}, EXAM, DUAL) is None


# ---------------------------------------------------------------- 3. binding


def test_a_record_stands_only_for_the_grade_it_names():
    record = _record(0.5)
    evidence = {"dual_measurement_receipt_sha256": DUAL, "evaluation_pack_digest": EXAM}
    assert crown_official.bound_to(record, evidence) is record
    for other in (
        {**evidence, "dual_measurement_receipt_sha256": "sha256:" + "0" * 64},
        {**evidence, "evaluation_pack_digest": "sha256:" + "0" * 64},
        {},
    ):
        assert crown_official.bound_to(record, other) is None
    assert crown_official.bound_to({**record, "schema": "other"}, evidence) is None


# ---------------------------------------------------------------- 2b. consider_private applies the verdict


class _Store:
    """A STAND-IN pool store: one king, filed confirmation records, the pause and queue reads empty."""

    def __init__(self, king, records):
        self.king, self.records, self.set_to, self.vacated = king, records, None, None

    def record_baseline(self, *a):
        pass

    def incumbent(self):
        return None if self.king is None else {"model_id": self.king}

    def confirmation(self, submission_id, key):
        return self.records.get(submission_id)

    def set_incumbent(self, submission_id, reason, *, expected):
        self.set_to = submission_id

    def vacate_incumbent(self, expected, reason):
        self.vacated = expected

    def record_crown_average(self, *a, **k):
        pass

    def paused_crowns(self):
        return []


def _row(submission_id):
    return {
        "submission_id": submission_id,
        "evidence": {
            "dual_measurement_receipt_sha256": DUAL + submission_id,
            "evaluation_pack_digest": EXAM,
        },
    }


def _consider(tmp_path, monkeypatch, outcome, *, king="king", records=(), block=RULED):
    _install(tmp_path, {"margin": 0.01, "confirmation": block})
    store = _Store(king, dict(records))
    # The constructor wants a real PoolStore; the stand-in keeps the question to the decision (test_crown_grade_repeat).
    promotion = bp.BankPromotion.__new__(bp.BankPromotion)
    promotion.store = store
    promotion.registered_source_receipt_sha256 = "sha256:" + "5" * 64
    pair = {
        "evaluation_key": KEY,
        "expected_incumbent": king,
        "candidate": _row("cand"),
        "incumbent": None if king is None else _row(king),
    }
    monkeypatch.setattr(promotion, "private_pair", lambda *a: pair)
    monkeypatch.setattr(promotion, "_state_dir", lambda: tmp_path)
    # the crown's private verification record reads real evidence; its own tests cover it
    monkeypatch.setattr(promotion, "_record_official_crown", lambda *a: None)
    monkeypatch.setattr(bp, "compare_private_pair", lambda p, c: dict(outcome))
    comparator = {"challenge": "zz-synthetic", "score_pack_digest": EXAM}
    decided = promotion.consider_private("cand", KEY, comparator)
    return decided, store


def _mine(value, who="cand", status="MEASURED"):
    return who, _record(value, status, dual=DUAL + who)


CHALLENGE = {
    "outcome": bp.CHALLENGER,
    "reason": "exceeds_incumbent_beyond_rebuild_noise",
}


def test_a_confirmed_challenger_is_crowned(tmp_path, monkeypatch):
    decided, store = _consider(
        tmp_path, monkeypatch, CHALLENGE, records=[_mine(0.6), _mine(0.5, "king")]
    )
    assert decided["outcome"] == bp.CHALLENGER and store.set_to == "cand"


def test_a_challenger_below_the_king_on_the_confirmation_set_keeps_the_king(
    tmp_path, monkeypatch
):
    decided, store = _consider(
        tmp_path, monkeypatch, CHALLENGE, records=[_mine(0.4), _mine(0.5, "king")]
    )
    assert (decided["outcome"], decided["reason"]) == (
        bp.INCUMBENT_KEEPS,
        crown_official.CROWN_NOT_CONFIRMED,
    )
    assert store.set_to is None and store.vacated is None
    # no number leaves with the decision
    assert "0.4" not in json.dumps(decided) and "0.5" not in json.dumps(decided)


def test_a_record_of_another_grade_does_not_stand_in_and_the_crown_waits(
    tmp_path, monkeypatch
):
    stale = ("cand", _record(0.9, dual=DUAL + "other"))
    decided, store = _consider(
        tmp_path, monkeypatch, CHALLENGE, records=[stale, _mine(0.5, "king")]
    )
    assert (decided["outcome"], decided["reason"]) == (
        bp.UNAVAILABLE,
        crown_official.CROWN_CONFIRMATION_UNAVAILABLE,
    )
    assert store.set_to is None


def test_an_unruled_block_waits_every_crown(tmp_path, monkeypatch):
    decided, store = _consider(
        tmp_path,
        monkeypatch,
        CHALLENGE,
        records=[_mine(0.9), _mine(0.1, "king")],
        block={},
    )
    assert decided["reason"] == crown_official.CROWN_CONFIRMATION_UNSET
    assert store.set_to is None


def test_a_first_crown_not_confirmed_has_no_winner(tmp_path, monkeypatch):
    first = {
        "outcome": bp.FIRST_INCUMBENT,
        "reason": "first_scored_contender_beats_baseline",
    }
    decided, store = _consider(
        tmp_path,
        monkeypatch,
        first,
        king=None,
        records=[_mine(None, status="INVALID")],
    )
    assert decided["outcome"] == bp.NO_WINNER and store.set_to is None


def test_a_gate_failed_king_is_dethroned_even_when_his_challenger_is_not_confirmed(
    tmp_path, monkeypatch
):
    failed = {"outcome": bp.CHALLENGER, "reason": "incumbent_failed_mandatory_gate"}
    decided, store = _consider(
        tmp_path, monkeypatch, failed, records=[_mine(None, status="INVALID")]
    )
    assert decided["outcome"] == bp.DETHRONED
    assert store.vacated == "king" and store.set_to is None


def test_the_waits_are_filed_and_swept_like_a_queued_crown():
    from carbon.challenge_validator import crown_pause_sweep

    assert crown_official.CROWN_CONFIRMATION_UNSET in crown_pause_sweep.WAITING_REASONS
    assert (
        crown_official.CROWN_CONFIRMATION_UNAVAILABLE
        in crown_pause_sweep.WAITING_REASONS
    )
    source = (ROOT / "carbon/challenge_validator/lean_recipe_retention.py").read_text(
        encoding="utf-8"
    )
    paused = source[source.index("paused = outcome.get") :][:600]
    assert "CROWN_CONFIRMATION_UNSET" in paused
    assert "CROWN_CONFIRMATION_UNAVAILABLE" in paused


def test_the_store_files_one_record_per_grade(tmp_path):
    from carbon.battery.pool_store import PoolStore

    store = PoolStore(tmp_path / "pool.sqlite3", clock=lambda: 123.0)
    record = _record(0.5)
    store.record_confirmation("rtsk_x", KEY, record)
    store.record_confirmation("rtsk_x", KEY, record)  # the same record again: kept
    assert store.confirmation("rtsk_x", KEY) == record
    assert store.confirmation("rtsk_y", KEY) is None
    with pytest.raises(StateError):
        store.record_confirmation("rtsk_x", KEY, _record(0.6))
    with pytest.raises(StateError):
        store.record_confirmation("rtsk_x", KEY, {"schema": "other"})


# ---------------------------------------------------------------- 4. the grade


def _confirmation_sets():
    # distinct target ids and designs; the same classes as the open sets (each set holds every class)
    return tuple(
        (
            exam_target(f"in{s}k7", 730 + s),
            exam_target(f"edge{s}k7", 740 + s, shell=SHELL),
            exam_target(f"step{s}k7", 750 + s, shell=SHELL),
        )
        for s in range(2)
    )


def _grade(open_sets, policies, material, *, confirming=None, serve=good_serve):
    groups = () if confirming is None else confirming
    rows = exam_rows(open_sets + groups)
    outputs = serve([r["inputs"] for r in rows])
    capture = {}
    result = pool_exam.measure_pool(
        binding=toy_binding(),
        sets=open_sets,
        policies=policies,
        bank_rows=rows,
        outputs=outputs,
        repeats=[outputs, outputs],
        base_measure=fake_measure,
        base_arguments=ARGUMENTS,
        speed_call_seconds=FAST,
        ceiling_seconds=CEILING,
        capture=capture,
        confirmation_sets=confirming,
        **material,
    )
    return result, capture


def _confirming_policies(threshold=2.5):
    open_sets, confirming = _sets(), _confirmation_sets()
    # the class map holds every target of both (the exam seats build one map for the pack)
    policies, material = _registered(open_sets + confirming, threshold=threshold)
    plain = policies
    policies = dataclasses.replace(policies, confirmation={"sets_sha256": "a" * 64})
    return open_sets, confirming, plain, policies, material


@pytest.mark.usefixtures("geometric_v1_stand_in")
def test_the_confirmation_rows_enter_no_part_of_the_grade(monkeypatch):
    open_sets, confirming, plain, policies, material = _confirming_policies()
    without, plain_capture = _grade(open_sets, plain, material)
    seen = []
    real = suite._physics_a_gen

    def recording(specs, predict, policies):
        value = real(specs, predict, policies)
        seen.append(({spec.target_id for spec in specs}, value))
        return value

    monkeypatch.setattr(suite, "_physics_a_gen", recording)
    with_set, capture = _grade(open_sets, policies, material, confirming=confirming)
    assert with_set == without
    assert "confirmation" not in json.dumps(with_set)
    assert "confirmation" not in plain_capture
    found = capture["confirmation"]
    assert found["status"] == "MEASURED" and found["sets"] == 2
    # the number is the physics family value of each confirmation set (the open sets' own call), mean over the sets
    confirmation_ids = [{spec.target_id for spec in group} for group in confirming]
    values = [value for ids, value in seen if ids in confirmation_ids]
    assert len(values) == 2
    assert found["value"] == pytest.approx(sum(values) / 2)


@pytest.mark.usefixtures("geometric_v1_stand_in")
def test_a_model_worse_only_on_the_confirmation_rows_keeps_its_open_grade():
    open_sets, confirming, _plain, policies, material = _confirming_policies()
    def keys(the_sets):
        return {tuple(sorted(r["inputs"].items())) for r in exam_rows(the_sets)}

    hidden = keys(confirming) - keys(open_sets)

    def worse_there(rows):
        out = good_serve(rows)
        return [
            [v + 5.0 for v in answer]
            if tuple(sorted(row.items())) in hidden
            else answer
            for row, answer in zip(rows, out)
        ]

    good, good_capture = _grade(open_sets, policies, material, confirming=confirming)
    bad, bad_capture = _grade(
        open_sets, policies, material, confirming=confirming, serve=worse_there
    )
    assert bad == good
    worse, better = bad_capture["confirmation"], good_capture["confirmation"]
    # the answers there are further from truth: a lower number, or answers the validity check refuses
    assert worse["status"] == "INVALID" or worse["value"] < better["value"]


@pytest.mark.usefixtures("geometric_v1_stand_in")
def test_a_gate_failed_grade_keeps_no_confirmation_number():
    open_sets, confirming, _plain, policies, material = _confirming_policies(
        threshold=1.5
    )
    result, capture = _grade(open_sets, policies, material, confirming=confirming)
    assert result["gates"][pool_exam.ACCURACY_GATE] is False
    assert capture["confirmation"] == {
        "status": "UNAVAILABLE",
        "reason": "gated",
        "sets_sha256": "a" * 64,
    }


@pytest.mark.usefixtures("geometric_v1_stand_in")
def test_the_material_must_match_the_registration():
    open_sets, confirming, plain, policies, material = _confirming_policies()
    with pytest.raises(pool_exam.ExamRefused) as refused:
        _grade(open_sets, policies, material)
    assert refused.value.code == "confirmation_sets_do_not_match_the_registration"
    with pytest.raises(pool_exam.ExamRefused) as refused:
        _grade(open_sets, plain, material, confirming=confirming)
    assert refused.value.code == "confirmation_sets_do_not_match_the_registration"
    # a confirmation target that is an open target is the exam's fault
    with pytest.raises(pool_exam.ExamRefused) as refused:
        _grade(open_sets, policies, material, confirming=(open_sets[0],))
    assert refused.value.code == "confirmation_target_is_an_open_target"


def test_the_pool_constants_register_the_fingerprint_and_the_material_must_carry_it():
    rule = pool_version._confirmation({"sets_sha256": "a" * 64})
    assert rule == {"sets_sha256": "a" * 64}
    assert pool_version._confirmation(pool_version._ABSENT) is None
    for bad in ({"sets_sha256": "A" * 64}, {"sets_sha256": "a" * 63}, {}, "x"):
        with pytest.raises(pool_version.PoolConstantsNotRegistered):
            pool_version._confirmation(bad)
    with pytest.raises(pool_version.PoolConstantsNotRegistered):
        pool_version._confirmation(pool_version.HUMAN_INPUT)
    groups = [[{"stand-in": 1}]]
    digest = pool_version.confirmation_sets_sha256(groups)
    material = {pool_version.CONFIRMATION_SETS: groups}
    assert pool_version.confirmation_sets({}, None) is None
    with pytest.raises(pool_exam.ExamRefused) as refused:
        pool_version.confirmation_sets(material, None)
    assert refused.value.code == "confirmation_sets_without_a_registration"
    with pytest.raises(pool_exam.ExamRefused) as refused:
        pool_version.confirmation_sets({}, {"sets_sha256": digest})
    assert refused.value.code == "confirmation_sets_missing_from_the_sealed_pack"
    with pytest.raises(pool_exam.ExamRefused) as refused:
        pool_version.confirmation_sets(material, {"sets_sha256": "0" * 64})
    assert refused.value.code == "confirmation_sets_sha256_mismatch"


def test_the_confirmation_designs_are_plain_bank_rows():
    source = (ROOT / "carbon/scoring/pool_version.py").read_text(encoding="utf-8")
    body = source[source.index("def rows_from_material") :]
    body = body[: body.index("\ndef ")]
    assert "CONFIRMATION_SETS" in body
    # nothing marks a confirmation row: every pool row carries the same record
    assert "POOL_RECORD" in body and "confirmation" not in pool_version.POOL_RECORD


# ---------------------------------------------------------------- 5. case errors v2


@pytest.mark.usefixtures("geometric_v1_stand_in")
def test_the_confirmation_cases_join_the_case_errors_as_source_2_and_trust_skips_them():
    open_sets, confirming, plain, policies, material = _confirming_policies()
    _result, plain_capture = _grade(open_sets, plain, material)
    _result, capture = _grade(open_sets, policies, material, confirming=confirming)
    assert "confirmation_case_errors_unavailable" not in capture
    content, before = capture["case_errors"], plain_capture["case_errors"]
    sources = content["source"]
    n_open = len(before["source"])
    assert sources[:n_open] == before["source"]
    assert set(sources[n_open:]) == {case_errors.SOURCE_CONFIRMATION}
    assert len(sources) > n_open
    arrays = case_errors.to_arrays(content)
    assert set(arrays) == set(case_errors.DTYPES)
    # every row joins a bank row (the confirmation rows are bank rows)
    assert all(row >= 0 for row in content["row_index"])
    # the trust record reads the open cases only (pool_trust's own tests cover T)
    trust = (ROOT / "carbon/scoring/pool_trust.py").read_text(encoding="utf-8")
    assert "case_errors.SOURCE_CONFIRMATION:" in trust


def test_the_signed_error_is_answer_minus_truth_for_a_scalar_and_nan_for_a_waveform():
    sink = case_errors.Sink()
    one = sink.case(case_errors.SOURCE_TARGET, 0, 0, "fixture:in")
    one.output("f", 0.25, 0.5, 1.0, 0.75)
    one.output("w", 0.1, 1.0, [0.0, 1.0], [0.1, 1.0])
    two = sink.case(case_errors.SOURCE_TARGET, 0, 1, "fixture:in")
    two.output("f", 0.5, 0.5, 1.0, 1.5)
    two.output("w", 0.2, 1.0, [0.0, 1.0], [0.2, 1.0])
    content = case_errors.assemble(sink, [(0,), (1,)], [(0,), (1,)])
    assert content["output_names"] == ["f", "w"]
    assert content["signed_error"] == [[-0.25, None], [0.5, None]]
    assert content["abs_error"] == [[0.25, 0.1], [0.5, 0.2]]
    arrays = case_errors.to_arrays(content)
    assert math.isnan(arrays["signed_error"][0, 1])


def test_a_case_from_an_older_caller_keeps_its_errors_and_no_sign():
    sink = case_errors.Sink()
    sink.case(case_errors.SOURCE_TARGET, 0, 0, "fixture:in").output("f", 0.25, 0.5, 1.0)
    content = case_errors.assemble(sink, [(0,)], [(0,)])
    assert content["abs_error"] == [[0.25]] and content["signed_error"] == [[None]]


def test_the_file_is_v2_and_v1_stays_readable():
    assert case_errors.SCHEMA == "carbon.exam.case-errors.v2"
    assert case_errors.READABLE_SCHEMAS == (
        "carbon.exam.case-errors.v1",
        "carbon.exam.case-errors.v2",
    )


def test_the_relabelled_sink_files_every_case_under_its_source():
    sink = case_errors.Sink()
    front = case_errors.Relabelled(sink, case_errors.SOURCE_CONFIRMATION)
    front.case(case_errors.SOURCE_TARGET, 3, 4, "fixture:in")
    assert [(c.source, c.spec_index, c.case_index) for c in sink.cases] == [(2, 3, 4)]


def test_pool_physics_score_hands_the_answer_to_the_sink():
    source = (ROOT / "carbon/scoring/pool_physics_score.py").read_text(
        encoding="utf-8"
    )
    assert "case.output(output, error, u, truth, prediction[output])" in source
    assert "case.output(output, error, u[output], truth, answer[output])" in source
    assert pps  # the module the claims read
