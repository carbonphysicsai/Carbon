"""A KOTH king carries across construction versions (OWNER-KOTH-CARRY-ACROSS-VERSIONS-01).

A king of F08 1.4 survives the bump to 1.5 (same sealed evaluation version, same
pack set) and meets 1.5 challengers under the unchanged takeover rule. A new
evaluation version carries nothing. A rotation keeps the king
(OWNER-EXAM-CAP-ROTATION-01): he is compared on the new set once regraded, and
every comparison is UNAVAILABLE until then. Each carry is recorded once.

The evaluations here are inert, structurally valid paired-dual bindings filed
straight into the pool store: they exercise the store, the carry and the
unchanged comparator, not the binder (covered by the pool-consider tests).
"""

import hashlib
import json

import pytest

from carbon.battery.pool_store import PoolStore, StateError, canonical
from carbon.challenge_validator import koth_carry, score_feed
from carbon.challenge_validator.bank_promotion import (
    CHALLENGER,
    COMPARATOR_SCHEMA,
    INCUMBENT_KEEPS,
    PAIRED_BINDING,
    SEALED_TESTNET_PROMOTION,
    UNAVAILABLE,
    BankPromotion,
    carry_identity,
    private_evaluation_key,
)
from carbon.rewards.winner_eligibility import WinnerLedger, lean_promotion

F08 = "f08-ribbed-bracket"
SEALED = "f08-dual-sealed-grid-8x1-v2"
NOISE = 0.01
OLD_PIN = "sha256:" + "a" * 64
NEW_PIN = "sha256:" + "b" * 64
SET_KEY = "sha256:" + "5" * 64
ROTATED_SET_KEY = "sha256:" + "6" * 64
SCORE_PACK = "sha256:" + "4" * 64


def _d(char):
    return "sha256:" + char * 64


def _evidence(version, total, *, pin, queries="1"):
    """A paired dual binding of one exam: the measured content is the same for
    every version unless ``queries`` changes; the version-named fields differ."""
    named = "c" if version == "1.4" else "d"
    return {
        "schema": PAIRED_BINDING,
        "scope": "PRIVATE_OPERATOR_DEVELOPMENT",
        "status": "BOUND_DEVELOPMENT_ONLY",
        "source_receipt_sha256": pin,
        "challenge": F08,
        "challenge_version": version,
        "evaluation_version": SEALED + "+baseline",
        "evaluation_version_digest": _d(named),
        "evaluation_pack_digest": _d("e" if version == "1.4" else "f"),
        "entry_id": _d("2"),
        "state_digest": None,  # set by _file
        "model_result_digest": _d("3"),
        "score_result_digest": _d("3"),
        "dual_measurement_receipt_sha256": _d("3"),
        "inference_pair_sha256": _d("3"),
        "score_compatibility": {
            "score_pack_digest": SCORE_PACK,
            "scoring_version": "carbon.scoring.dual-benchmark-pack.v4",
            "execution_profile_digest": _d("8"),
        },
        "registration_digest": _d("9"),
        "measurement_contract_digest": _d("9"),
        "producer_digest": _d("9"),
        "common_mask_digest": _d("9"),
        "ordered_query_material_digest": _d(queries),
        "reference_rows_digest": _d("9"),
        "reference_coverage_digest": _d("9"),
        "reference_coverage": {"RESOLVED": 8, "UNRESOLVED": 0, "FAILED_INFRA": 0},
        "official_score": False,
        "official_eligible": False,
        "model_p": {
            "score_status": "SCORED_DEVELOPMENT_CANDIDATE",
            "total_score": total,
        },
    }


def _file(store, submission_id, hotkey, version, total, *, pin, queries="1"):
    """Admit, retain and file one evaluation; returns its evaluation key."""
    state = ("state-" + submission_id).encode()
    import hashlib

    state_digest = "sha256:" + hashlib.sha256(state).hexdigest()
    store.admit(
        submission_id,
        request_digest=_d("7"),
        hotkey=hotkey,
        challenge=F08,
        strategy={"recipe": submission_id},
        binding={
            "challenge": {"id": F08, "version": version},
            "recipe_digest": _d("6"),
        },
    )
    store.retain_model(
        submission_id,
        recipe_digest=_d("6"),
        seed=0,
        state=state,
        reconstruction={"scope": "FIXTURE"},
    )
    store.mark(submission_id, "RECONSTRUCTED")
    evidence = {
        **_evidence(version, total, pin=pin, queries=queries),
        "state_digest": state_digest,
    }
    key = private_evaluation_key(evidence)
    body = {
        "schema": "carbon.challenge-validator.private-evaluation-cache.v1",
        "submission_id": submission_id,
        "owner": {"hotkey": hotkey, "request_digest": _d("7")},
        "recipe_digest": _d("6"),
        "evaluation_key": key,
        "evidence": evidence,
    }
    op = store._bank_operation("private_evaluation.v1", submission_id, key)
    with store.transaction() as db:
        db.execute(
            "INSERT INTO operations VALUES(?,?,?,?)",
            (op, "private_evaluation.v1", "BOUND_DEVELOPMENT_ONLY", canonical(body)),
        )
    return key


def _comparator():
    return {
        "schema": COMPARATOR_SCHEMA,
        "scope": "DEVELOPMENT",
        "challenge": F08,
        "score_pack_digest": SCORE_PACK,
        "rebuild_noise": {"value": NOISE, "measurement_digest": _d("7")},
        "ties": "incumbent_keeps",
        "minimum_source_entry_ids": [],
        "baseline_total": 0.0,
    }


def _old_deployment(tmp_path, total=0.80):
    """F08 1.4's pool store with a live sealed-testnet king."""
    store = PoolStore(tmp_path / "f08-1.4.sqlite", clock=lambda: 100.0)
    store.king_key = _file(store, "king", "king-hotkey", "1.4", total, pin=OLD_PIN)
    store.set_incumbent("king", SEALED_TESTNET_PROMOTION)
    return store


def _new_deployment(tmp_path):
    return PoolStore(tmp_path / "f08-1.5.sqlite", clock=lambda: 200.0)


def _carry(old, new, **overrides):
    arguments = {
        "challenge_id": F08,
        "old_version": "1.4",
        "new_version": "1.5",
        "old_pack_set_key": SET_KEY,
        "new_pack_set_key": SET_KEY,
        "king_source_receipt_sha256": OLD_PIN,
        **overrides,
    }
    return koth_carry.carry(old, new, **arguments)


def _challenge(new, submission_id, total, *, queries="1"):
    key = _file(
        new,
        submission_id,
        submission_id + "-hotkey",
        "1.5",
        total,
        pin=NEW_PIN,
        queries=queries,
    )
    return BankPromotion(
        new, registered_source_receipt_sha256=NEW_PIN
    ).consider_private(submission_id, key, _comparator(), sealed=True)


def test_a_14_king_survives_the_bump_and_meets_15_challengers_under_the_rule(
    tmp_path,
):
    old, new = _old_deployment(tmp_path), _new_deployment(tmp_path)
    assert new.incumbent() is None  # a new deployment: no king, as before
    _carry(old, new)
    assert new.incumbent() == {"model_id": "king", "reason": SEALED_TESTNET_PROMOTION}
    # Within the registered margin: the king keeps the crown.
    within = _challenge(new, "within", 0.80 + NOISE / 2)
    assert (within["outcome"], within["reason"]) == (
        INCUMBENT_KEEPS,
        "within_rebuild_noise_or_tie",
    )
    # A tie keeps the king.
    tie = _challenge(new, "tie", 0.80)
    assert tie["outcome"] == INCUMBENT_KEEPS
    assert new.incumbent()["model_id"] == "king"
    # Beyond the margin: the challenger takes it.
    beyond = _challenge(new, "beyond", 0.80 + 2 * NOISE)
    assert (beyond["outcome"], beyond["incumbent"]) == (CHALLENGER, "king")
    assert new.incumbent() == {
        "model_id": "beyond",
        "reason": SEALED_TESTNET_PROMOTION,
    }
    # The old deployment's record is untouched.
    assert old.incumbent()["model_id"] == "king"


def test_a_challenger_on_another_measured_exam_never_meets_the_carried_king(
    tmp_path,
):
    old, new = _old_deployment(tmp_path), _new_deployment(tmp_path)
    _carry(old, new)
    other = _challenge(new, "other-exam", 0.99, queries="0")
    assert (other["outcome"], other["reason"]) == (
        UNAVAILABLE,
        "incumbent_regrade_required",
    )
    assert new.incumbent()["model_id"] == "king"


def test_the_carry_identity_ignores_only_the_construction_version_fields():
    one = {**_evidence("1.4", 0.8, pin=OLD_PIN), "state_digest": _d("2")}
    two = {**_evidence("1.5", 0.8, pin=NEW_PIN), "state_digest": _d("2")}
    assert private_evaluation_key(one) != private_evaluation_key(two)
    assert carry_identity(one) == carry_identity(two)
    for field, value in (
        ("evaluation_version", SEALED + "+other"),
        ("reference_rows_digest", _d("0")),
        ("producer_digest", _d("0")),
    ):
        assert carry_identity({**two, field: value}) != carry_identity(one)


def test_the_carried_king_is_the_feed_king_and_keeps_his_ledger_clock(tmp_path):
    old, new = _old_deployment(tmp_path), _new_deployment(tmp_path)
    ledger = WinnerLedger(tmp_path / "winners.jsonl")
    crowned = {
        "schema": "carbon.rewards.testnet-winner-ledger.v2",
        "challenge": F08,
        "policy": "sha256:" + "1" * 64,
        "promotion": {**lean_promotion(old), "kind": "FIRST_INCUMBENT"},
        "observed_ms": 5,
        "winner_coldkey": "king-coldkey",
        "eligible": True,
        "reason": "first_incumbent_no_baseline",
        "clock_ms": 5,
    }
    ledger._append(crowned)
    records = ledger.records(F08)
    assert score_feed.king_record(new, records, set())[0] is None  # reset today
    _carry(old, new)
    king, _ = score_feed.king_record(new, records, set())
    assert (king["hotkey"], king["submission_id"], king["crowned_utc_ms"]) == (
        "king-hotkey",
        "king",
        5,
    )
    # The weights publisher's source names the same king; the ledger finds his
    # first record by model id, so his clock is kept and nothing is appended.
    promotion = lean_promotion(new)
    assert (promotion["model_id"], promotion["hotkey"]) == ("king", "king-hotkey")
    assert ledger.observe(None, F08, promotion, {}, 999) == crowned
    assert len(ledger.records(F08)) == 1


def _consider(store, submission_id, version, total, *, pin, queries):
    key = _file(
        store,
        submission_id,
        submission_id + "-hotkey",
        version,
        total,
        pin=pin,
        queries=queries,
    )
    return BankPromotion(store, registered_source_receipt_sha256=pin).consider_private(
        submission_id, key, _comparator(), sealed=True
    )


def test_a_rotation_and_regrade_keep_the_king(tmp_path):
    """OWNER-EXAM-CAP-ROTATION-01 holds (VALIDATOR-KOTH-CARRY-SCOPE-01): a
    rotation is not a reset. Before the king's regrade on the new set nothing
    can be compared; after it he meets challengers under the unchanged rule."""
    store = _old_deployment(tmp_path)
    rotated = {"version": "1.4", "pin": OLD_PIN, "queries": "0"}
    early = _consider(store, "early", total=0.99, **rotated)
    assert (early["outcome"], early["reason"], early["incumbent"]) == (
        UNAVAILABLE,
        "incumbent_regrade_required",
        "king",
    )
    assert store.incumbent()["model_id"] == "king"
    # The regrade files the king's evaluation of the new set under his own id.
    _file(store, "king", "king-hotkey", "1.4", 0.80, pin=OLD_PIN, queries="0")
    within = _consider(store, "within", total=0.80 + NOISE / 2, **rotated)
    assert within["outcome"] == INCUMBENT_KEEPS
    assert store.incumbent()["model_id"] == "king"
    beyond = _consider(store, "beyond", total=0.80 + 2 * NOISE, **rotated)
    assert (beyond["outcome"], store.incumbent()["model_id"]) == (CHALLENGER, "beyond")


def test_a_carry_onto_a_new_pack_set_keeps_the_king_until_regraded(tmp_path):
    """A pack-set change carries the king, marked for a regrade. A 1.4 king
    cannot be regraded by a 1.5 receiver (`regrade_challenge_changed`), so
    every comparison is UNAVAILABLE: never a reset, never a free crown."""
    old, new = _old_deployment(tmp_path), _new_deployment(tmp_path)
    record = _carry(old, new, new_pack_set_key=ROTATED_SET_KEY)
    assert (record["old_pack_set_key"], record["new_pack_set_key"]) == (
        SET_KEY,
        ROTATED_SET_KEY,
    )
    assert record["regrade"] == "REQUIRED"
    assert new.incumbent() == {"model_id": "king", "reason": SEALED_TESTNET_PROMOTION}
    # Even on content the carried evidence measured, it never stands in for
    # the regrade on a changed set.
    for name, queries in (("same-content", "1"), ("new-content", "0")):
        outcome = _challenge(new, name, 0.99, queries=queries)
        assert (outcome["outcome"], outcome["reason"]) == (
            UNAVAILABLE,
            "incumbent_regrade_required",
        )
    assert new.incumbent()["model_id"] == "king"


def _set_key(version, exam):
    """The key a producer's signed set commitment carries for `version`'s packs
    over `exam` (each batch's (case_bank, reference_rows) bytes). Each version's
    packs have their own manifests, which name the version."""
    from carbon.challenge_validator import sealed_pack_import as sp

    contents = {
        "sha256:"
        + hashlib.sha256(b"%s-manifest-%d" % (version.encode(), i)).hexdigest(): {
            "case_bank": "sha256:" + hashlib.sha256(bank).hexdigest(),
            "reference_rows": "sha256:" + hashlib.sha256(rows).hexdigest(),
        }
        for i, (bank, rows) in enumerate(exam)
    }
    return sp.set_commitment_for(
        F08, version, sorted(contents), None, contents=contents
    )["set_key"]


EXAM = ((b"bank-1", b"rows-1"), (b"bank-2", b"rows-2"))


def test_the_same_exam_content_on_15_carries_the_king_with_no_regrade(tmp_path):
    """Rule 1 of the content key: same content, new construction version -> one
    key -> the king carries and meets 1.5 challengers with no regrade."""
    old_key, new_key = _set_key("1.4", EXAM), _set_key("1.5", EXAM)
    assert old_key == new_key
    old, new = _old_deployment(tmp_path), _new_deployment(tmp_path)
    record = _carry(old, new, old_pack_set_key=old_key, new_pack_set_key=new_key)
    assert record["regrade"] == "NOT_REQUIRED"
    beyond = _challenge(new, "beyond", 0.80 + 2 * NOISE)
    assert (beyond["outcome"], beyond["incumbent"]) == (CHALLENGER, "king")


@pytest.mark.parametrize(
    "changed",
    [
        ((b"bank-1", b"rows-9"), (b"bank-2", b"rows-2")),  # one batch's truth
        ((b"bank-9", b"rows-1"), (b"bank-2", b"rows-2")),  # one batch's queries
    ],
)
def test_changed_batch_content_is_a_new_key_and_takes_the_regrade_path(
    tmp_path, changed
):
    """Rule 2: a rotation (reference rows, or separately the case bank, of one
    batch changed) is a new key; the king carries, marked for a regrade, and is
    UNAVAILABLE to challengers until regraded: never a reset."""
    old_key, new_key = _set_key("1.4", EXAM), _set_key("1.5", changed)
    assert old_key != new_key
    old, new = _old_deployment(tmp_path), _new_deployment(tmp_path)
    record = _carry(old, new, old_pack_set_key=old_key, new_pack_set_key=new_key)
    assert record["regrade"] == "REQUIRED"
    outcome = _challenge(new, "challenger", 0.99)
    assert (outcome["outcome"], outcome["reason"]) == (
        UNAVAILABLE,
        "incumbent_regrade_required",
    )
    assert new.incumbent()["model_id"] == "king"


def test_a_new_evaluation_version_resets_the_king(tmp_path, monkeypatch):
    from carbon.scoring import sealed_versions

    real = sealed_versions.evaluation_version
    monkeypatch.setattr(
        sealed_versions,
        "evaluation_version",
        lambda c, v: "f08-new-exam" if v == "1.5" else real(c, v),
    )
    old, new = _old_deployment(tmp_path), _new_deployment(tmp_path)
    with pytest.raises(koth_carry.CarryRefused) as refused:
        _carry(old, new)
    assert refused.value.code == "koth_carry_evaluation_version_changed"
    assert new.incumbent() is None and new.koth_carries() == []


@pytest.mark.parametrize(
    "overrides, code",
    [
        ({"new_version": "1.1"}, "koth_carry_evaluation_version_unknown"),
        ({"new_pack_set_key": None}, "koth_carry_pack_set_unknown"),
        ({"old_pack_set_key": "not-a-key"}, "koth_carry_pack_set_unknown"),
        ({"new_version": "1.4"}, "koth_carry_same_version"),
        ({"king_source_receipt_sha256": None}, "koth_carry_source_pin_missing"),
        (
            {"king_source_receipt_sha256": NEW_PIN},
            "koth_carry_king_evaluation_unavailable",
        ),
        ({"old_version": "1.3"}, "koth_carry_king_not_this_version"),
    ],
)
def test_unknown_or_unmatched_identities_never_carry(tmp_path, overrides, code):
    old, new = _old_deployment(tmp_path), _new_deployment(tmp_path)
    with pytest.raises(koth_carry.CarryRefused) as refused:
        _carry(old, new, **overrides)
    assert refused.value.code == code
    assert new.incumbent() is None and new.koth_carries() == []


def test_the_carry_record_is_written_exactly_once_with_its_fields(tmp_path):
    old, new = _old_deployment(tmp_path), _new_deployment(tmp_path)
    first = _carry(old, new)
    assert _carry(old, new) == first  # a replay returns the first record
    # A later crown on the old deployment never carries a second king in.
    _file(old, "later", "later-hotkey", "1.4", 0.95, pin=OLD_PIN)
    old.set_incumbent("later", SEALED_TESTNET_PROMOTION, expected="king")
    with pytest.raises(koth_carry.CarryRefused) as refused:
        _carry(old, new)
    assert refused.value.code == "koth_carry_deployment_has_history"
    assert new.incumbent()["model_id"] == "king"
    assert new.koth_carries() == [first]
    assert len(new.events("koth_carry")) == 1
    assert first == {
        "schema": koth_carry.CARRY_SCHEMA,
        "challenge_id": F08,
        "king": {"hotkey": "king-hotkey", "submission_id": "king"},
        "old_version": "1.4",
        "new_version": "1.5",
        "evaluation_version": SEALED,
        "old_pack_set_key": SET_KEY,
        "new_pack_set_key": SET_KEY,
        "regrade": "NOT_REQUIRED",
        "king_source_receipt_sha256": OLD_PIN,
        "carried_evaluations": [old.king_key],
        "carried_at": 200.0,
    }
    # The crown event names the carry; nothing is recorded in the old store.
    assert new.events("incumbent")[-1]["body"] == {
        "model_id": "king",
        "reason": SEALED_TESTNET_PROMOTION,
        "previous": None,
        "carried_from_version": "1.4",
    }
    assert old.koth_carries() == []


def test_no_king_nothing_to_carry(tmp_path):
    old = PoolStore(tmp_path / "empty-1.4.sqlite", clock=lambda: 1.0)
    with pytest.raises(koth_carry.CarryRefused) as refused:
        _carry(old, _new_deployment(tmp_path))
    assert refused.value.code == "koth_carry_no_king"


def test_a_deployment_with_its_own_history_takes_no_carry(tmp_path):
    old, new = _old_deployment(tmp_path), _new_deployment(tmp_path)
    _file(new, "own", "own-hotkey", "1.5", 0.5, pin=NEW_PIN)
    new.set_incumbent("own", SEALED_TESTNET_PROMOTION)
    new.vacate_incumbent("own", "incumbent_failed_mandatory_gate")
    with pytest.raises(koth_carry.CarryRefused) as refused:
        _carry(old, new)
    assert refused.value.code == "koth_carry_deployment_has_history"
    assert new.incumbent() is None


def test_a_king_already_admitted_in_the_new_store_is_refused(tmp_path):
    old, new = _old_deployment(tmp_path), _new_deployment(tmp_path)
    _file(new, "king", "king-hotkey", "1.5", 0.5, pin=NEW_PIN)
    with pytest.raises(koth_carry.CarryRefused) as refused:
        _carry(old, new)
    assert refused.value.code == "koth_carry_king_already_admitted"


def test_the_store_refuses_a_moved_or_unretained_king_and_itself(tmp_path):
    old, new = _old_deployment(tmp_path), _new_deployment(tmp_path)
    record = {
        "schema": koth_carry.CARRY_SCHEMA,
        "challenge_id": F08,
        "king": {"hotkey": "king-hotkey", "submission_id": "king"},
        "old_version": "1.4",
        "new_version": "1.5",
        "evaluation_version": SEALED,
        "old_pack_set_key": SET_KEY,
        "new_pack_set_key": SET_KEY,
        "regrade": "NOT_REQUIRED",
        "king_source_receipt_sha256": OLD_PIN,
    }
    for store, wrong, code in (
        (old, record, "koth_carry_same_store"),
        (new, {**record, "king": {"hotkey": "x", "submission_id": "x"}}, None),
        (new, {**record, "king": {**record["king"], "hotkey": "x"}}, None),
    ):
        with pytest.raises(StateError) as refused:
            store.carry_incumbent(old, wrong)
        assert refused.value.code == (code or "koth_carry_king_moved")
    with old.transaction() as db:
        db.execute("DELETE FROM models WHERE model_id='king'")
    with pytest.raises(StateError) as refused:
        new.carry_incumbent(old, record)
    assert refused.value.code == "koth_carry_king_unretained"
    assert new.incumbent() is None


def test_the_operator_command_carries_and_refuses_a_missing_pool(tmp_path, capsys):
    old, new = _old_deployment(tmp_path), _new_deployment(tmp_path)
    argv = [
        "--challenge",
        F08,
        "--old-pool",
        str(old.path),
        "--old-version",
        "1.4",
        "--old-pack-set-key",
        SET_KEY,
        "--new-pool",
        str(new.path),
        "--new-version",
        "1.5",
        "--new-pack-set-key",
        SET_KEY,
        "--king-source-pin",
        OLD_PIN,
    ]
    assert koth_carry.main(argv) == 0
    assert json.loads(capsys.readouterr().out)["king"]["submission_id"] == "king"
    missing = [
        str(tmp_path / "absent.sqlite") if a == str(new.path) else a for a in argv
    ]
    assert koth_carry.main(missing) == 2
    assert json.loads(capsys.readouterr().out) == {
        "refused": "koth_carry_pool_unavailable"
    }
