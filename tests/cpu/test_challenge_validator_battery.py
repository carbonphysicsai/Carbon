"""Battery as the first challenge-neutral validator adapter (VALIDATOR-01).

The central check is replay: the same submissions, sent once through battery's
own deployment path (`deployment.evaluate`) and once through the neutral
`Validator`, onto twin validators sharing one private root, give byte-identical
miner outcomes and identical stored scores, bindings and finals.

The fixtures use real PyBaMM references retained by the exam-design campaign,
as `test_battery_validator_daemon.py` does. Those cases are published
development examples, so the fixtures opt in to them explicitly. The backend
is `DirectBackend`: control flow and exam semantics only, not container
isolation. None of this is a security audit (AGENTS.md §13).
"""

import json
import shutil
import sqlite3
from pathlib import Path

import pytest

from carbon.battery import deployment, exam, seeds
from carbon.battery.challenge import INPUTS
from carbon.battery.daemon import AuthenticatedSubmission, BatteryValidator, rule_digest
from carbon.battery.pool_store import MAX_INFRA_ATTEMPTS, PoolStore, canonical
from carbon.battery.worker import DirectBackend, WorkerFailure
from carbon.challenge_validator import (
    Adapters,
    AttemptLedger,
    Operator,
    ReservedRole,
    Submission,
    Validator,
)
from carbon.challenge_validator.battery import BatteryAdapter, ScoreReplayMismatch
from carbon.reconstruction import capability_registry as registry

REPOSITORY = Path(__file__).resolve().parents[2]
EVIDENCE = REPOSITORY / "docs/development/evidence/exam-design-2026-09-24"
BATTERY = registry.BATTERY_CHALLENGE
DIGEST = registry.contract_digest(BATTERY)
PIN_G = "sha256:" + "1" * 64


@pytest.fixture(scope="module")
def refs():
    found = {}
    lines = (EVIDENCE / "refs-b/out/battery_refs/records.jsonl").read_text()
    for line in lines.splitlines():
        record = json.loads(line)
        if not record.get("refined"):
            found[record["case_id"]] = record
    return found


def batch(refs, role, n=98, prefix=None):
    ids = sorted(c for c in refs if c.startswith((prefix or role) + "-"))[:n]
    cases = [(c, tuple(sorted((k, refs[c]["inputs"][k]) for k in INPUTS))) for c in ids]
    repeats = [(f"{role}-r{j}", ids[j * 40]) for j in range(2)]
    inputs = dict(cases)
    cases += [(d, inputs[o]) for d, o in repeats]
    return seeds.PrivateBatch(role, tuple(cases), tuple(repeats))


class Failing(DirectBackend):
    """DirectBackend whose next `failures` reconstructions fail as
    infrastructure."""

    failures = 0

    def reconstruct(self, identity, recipe, seed):
        if self.failures:
            self.failures -= 1
            raise WorkerFailure("injected", candidate=False)
        return super().reconstruct(identity, recipe, seed)


@pytest.fixture(scope="module")
def backend():
    return Failing(REPOSITORY)


def make(directory, refs, backend, *, rule=None, require_commitment=False):
    directory.mkdir(mode=0o700, exist_ok=True)
    directory.chmod(0o700)
    root_path = directory / "root.bin"
    root = (
        seeds.PrivateRoot.load(root_path)
        if root_path.exists()
        else seeds.PrivateRoot.create(root_path)
    )
    journal = seeds.SeedJournal(directory / "journal.jsonl")
    if not journal.path.exists():
        pin_rule = rule_digest() if rule is None else rule_digest(rule)
        journal.commit_root(root, seeds.seed_pin(PIN_G, pin_rule))
    target = BatteryValidator(
        store=PoolStore(directory / "state.sqlite3", rule=rule),
        backend=backend,
        root=root,
        journal=journal,
        repository=REPOSITORY,
        require_commitment=require_commitment,
        allow_published_cases=True,
    )
    target.lock_path = str(directory / "state.sqlite3.lock")
    target.readonly = False
    target.start()
    if target.store.pool() is None:
        for b in range(4):
            fp = target.import_batch(batch(refs, f"pscreen-B0{b}"), kind="screening")
            target.ingest_references(fp, list(refs.values()))
        fp = target.import_batch(batch(refs, "pfinal", 198), kind="finalist")
        target.ingest_references(fp, list(refs.values()))
        target.open_pool()
    return target


def twins(tmp_path, refs, backend, **kwargs):
    """Two validators over one private root: identical seeds and batches."""
    tmp_path.chmod(0o700)
    first = make(tmp_path / "direct", refs, backend, **kwargs)
    (tmp_path / "neutral").mkdir(mode=0o700)
    shutil.copyfile(tmp_path / "direct/root.bin", tmp_path / "neutral/root.bin")
    (tmp_path / "neutral/root.bin").chmod(0o600)
    second = make(tmp_path / "neutral", refs, backend, **kwargs)
    return first, second


def surfaces(tmp_path, target):
    (tmp_path / "ledger").mkdir(mode=0o700, exist_ok=True)
    ledger = AttemptLedger(tmp_path / "ledger/attempts.sqlite3")
    adapters = Adapters([BatteryAdapter(target)])
    return Validator(adapters, ledger), Operator(adapters, ledger)


def strategy(backbone="knn", **parameters):
    return {
        "schema_version": "1.0",
        "challenge_id": BATTERY,
        "backbone": backbone,
        "parameters": parameters or {"neighbours": 8},
    }


def receipt(n):
    return {"sequence": n, "digest": f"{n:064x}"}


def direct(target, hotkey, body, n):
    return deployment.evaluate(
        target,
        AuthenticatedSubmission(hotkey, receipt(n), BATTERY, "1.0", body, DIGEST),
    )


def neutral(hotkey, body, n, *, raw=None):
    return Submission(
        hotkey=hotkey,
        receipt=receipt(n),
        challenge_id=BATTERY,
        challenge_version="1.0",
        strategy_json=json.dumps(body) if raw is None else raw,
        contract_digest=DIGEST,
    )


# The sequence covers: a first incumbent, two challengers (one rotation and
# finalist comparisons along the way), a duplicate resubmission and a refused
# construction.
SEQUENCE = [
    ("hk1", strategy(neighbours=8)),
    ("hk2", strategy(neighbours=6)),
    ("hk3", strategy(neighbours=4)),
    ("hk1", strategy(neighbours=8)),
    ("hk4", strategy(backbone="not-a-backbone")),
    ("hk5", {**strategy(), "parameters": {"neighbours": -3}}),
]


def test_battery_replays_byte_identically_through_the_neutral_validator(
    tmp_path, refs, backend
):
    first, second = twins(tmp_path, refs, backend)
    validator, _ = surfaces(tmp_path, second)
    states = []
    for n, (hotkey, body) in enumerate(SEQUENCE, start=1):
        expected = direct(first, hotkey, body, n)
        result = validator.evaluate(neutral(hotkey, body, n))
        assert result["kind"] == "OUTCOME"
        assert canonical(result["outcome"]) == canonical(expected)
        states.append(expected["state"])
    assert states == ["SCORED"] * 4 + ["INVALID_CONSTRUCTION"] * 2
    # The stores agree on everything scored, bound, nominated and decided.
    # Only wall-clock columns (`created`, `updated`, `since`, `at`) differ.
    queries = {
        "submissions": "SELECT submission_id, request_digest, hotkey, challenge,"
        " strategy, binding, state, failure FROM submissions ORDER BY submission_id",
        "scores": "SELECT * FROM scores ORDER BY submission_id",
        "finals": "SELECT * FROM finals ORDER BY final_id",
        "predictions": "SELECT * FROM predictions ORDER BY model_id, case_id",
        "models": "SELECT model_id, recipe_digest, seed, state_digest"
        " FROM models ORDER BY model_id",
        "batches": "SELECT * FROM batches ORDER BY fingerprint",
        "pool": "SELECT * FROM pool",
        "incumbent": "SELECT model_id, reason FROM incumbent",
    }
    with (
        sqlite3.connect(first.store.path) as a,
        sqlite3.connect(second.store.path) as b,
    ):
        for table, query in queries.items():
            assert a.execute(query).fetchall() == b.execute(query).fetchall(), table
        submitted = [s for (s,) in a.execute("SELECT submission_id FROM submissions")]
    assert first.store.pool()["version"] >= 1  # the sequence rotated the pool
    # Every outcome read back through the neutral surface is battery's own.
    for sid in submitted:
        hotkey = first.store.submission(sid)["hotkey"]
        read = validator.outcome(DIGEST, sid, hotkey)
        assert canonical(read["outcome"]) == canonical(first.outcome(sid))


def test_a_stale_digest_is_the_one_documented_difference(tmp_path, refs, backend):
    """Battery records a stale digest as INVALID_CONSTRUCTION; the neutral
    validator refuses it before dispatch and records it in its own ledger.
    Slice 1 leaves battery's entry points on battery's behaviour."""
    first, second = twins(tmp_path, refs, backend)
    validator, operator = surfaces(tmp_path, second)
    stale = "sha256:" + "0" * 64
    battery = deployment.evaluate(
        first,
        AuthenticatedSubmission("hk1", receipt(1), BATTERY, "1.0", strategy(), stale),
    )
    assert (battery["state"], battery["failure"]["code"]) == (
        "INVALID_CONSTRUCTION",
        "contract_refused",
    )
    result = validator.evaluate(
        Submission("hk1", receipt(1), BATTERY, "1.0", json.dumps(strategy()), stale)
    )
    assert (result["kind"], result["code"]) == ("REFUSED", "contract_not_served")
    assert second.store.pending_submissions() == []
    assert operator.attempt_counts("hk1")["by_kind"]["REFUSED"] == 1


def test_hostile_strategies_never_reach_battery(tmp_path, refs, backend):
    target = make(tmp_path / "v", refs, backend)
    validator, operator = surfaces(tmp_path, target)
    for raw in (
        json.dumps(strategy()).replace('"neighbours": 8', '"neighbours": NaN'),
        json.dumps(strategy())[:-1] + ', "backbone": "mlp"}',
        "[" * 40 + "]" * 40,
        "x" * 70000,
        b"\xef\xbb\xbf" + json.dumps(strategy()).encode(),
    ):
        result = validator.evaluate(neutral("hk1", None, 1, raw=raw))
        assert result["kind"] == "REFUSED"
    with sqlite3.connect(target.store.path) as db:
        assert db.execute("SELECT COUNT(*) FROM submissions").fetchone() == (0,)
    assert operator.attempt_counts("hk1")["by_kind"]["REFUSED"] == 5


def test_the_operator_score_record_reproduces_the_stored_score(tmp_path, refs, backend):
    target = make(tmp_path / "v", refs, backend)
    validator, operator = surfaces(tmp_path, target)
    result = validator.evaluate(neutral("hk1", strategy(), 1))
    sid = result["outcome"]["submission_id"]
    stored = target.store.score(sid)["record"]
    record = operator.score_record(DIGEST, sid)
    assert record["audience"] == "OPERATOR_ONLY"
    assert record["pinned"] == result["pinned"]
    body = record["record"]
    assert body["aggregate"]["score"] == stored["score"]
    assert body["rule_digest"] == rule_digest() == record["identities"]["rule_digest"]
    assert len(body["cases"]) == stored["n_cases"] == 300
    assert all("gates" in case and "state" in case for case in body["cases"])
    assert set(body["predictions"]) <= set(target.store.active_case_ids())
    # A stored prediction that no longer reproduces the score is refused.
    case_id = body["cases"][0]["case_id"]
    with sqlite3.connect(target.store.path) as db:
        (raw,) = db.execute(
            "SELECT body FROM predictions WHERE model_id=? AND case_id=?",
            (sid, case_id),
        ).fetchone()
        prediction = json.loads(raw)
        prediction["voltage_v"] = [v + 0.05 for v in prediction["voltage_v"]]
        db.execute(
            "UPDATE predictions SET body=? WHERE model_id=? AND case_id=?",
            (json.dumps(prediction), sid, case_id),
        )
    with pytest.raises(ScoreReplayMismatch):
        operator.score_record(DIGEST, sid)


def test_no_miner_facing_result_carries_a_hidden_case_or_seed(tmp_path, refs, backend):
    target = make(tmp_path / "v", refs, backend)
    validator, _ = surfaces(tmp_path, target)
    results = [validator.evaluate(neutral("hk1", strategy(), 1))]
    sid = results[0]["outcome"]["submission_id"]
    results.append(validator.outcome(DIGEST, sid, "hk1"))
    results.append(validator.outcome(DIGEST, sid, "hk2"))
    results.append(validator.served())
    text = json.dumps(results)
    hidden = set(target.store.active_case_ids())
    for kind in ("screening", "finalist"):
        for b in target.store.batches(kind=kind):
            hidden.update(c["case_id"] for c in b["document"]["cases"])
            hidden.add(b["fingerprint"])
    assert hidden and not any(case in text for case in hidden)
    assert target.root.commitment() not in text
    assert results[2]["code"] == "unknown_submission"


def test_pinned_identities_follow_the_battery_rule(tmp_path, refs, backend):
    v1 = BatteryAdapter(make(tmp_path / "v1", refs, backend))
    v2 = BatteryAdapter(make(tmp_path / "v2", refs, backend, rule=exam.RULES["v2"]))
    assert v1.contract_digest == v2.contract_digest == DIGEST
    assert v1.pinned()["rule_digest"] == rule_digest(exam.RULES["v1"])
    assert v2.pinned()["rule_digest"] == rule_digest(exam.RULES["v2"])
    assert v1.pinned()["identities_digest"] != v2.pinned()["identities_digest"]
    assert v1.disclosure_budget() is None
    assert v2.disclosure_budget() == {
        "source": "exam_rule.per_hotkey",
        **exam.RULES["v2"]["per_hotkey"],
    }


def test_reserved_and_sealed_roles_are_refused_without_touching_the_journal(
    tmp_path, refs, backend
):
    target = make(tmp_path / "v", refs, backend)
    _, operator = surfaces(tmp_path, target)
    target.seal_batch("study-sealed", count=4, duplicates=1)
    before = target.journal.public()
    for role, code in (
        ("ev5-confirmation", "seed_role_reserved"),
        ("graphite-confirmation-v1", "seed_role_reserved"),
        ("study-sealed", "seed_role_sealed"),
    ):
        with pytest.raises(ReservedRole) as refused:
            operator.prepare_batch(
                DIGEST, role, kind="screening", count=4, duplicates=1
            )
        assert refused.value.code == code
    assert target.journal.public() == before
    assert [r["code"] for r in operator.ledger.operator_refusals()] == [
        "seed_role_reserved",
        "seed_role_reserved",
        "seed_role_sealed",
    ]
    # Pool batches are not sealed: an ordinary role still prepares.
    fingerprint = operator.prepare_batch(
        DIGEST, "pscreen-fresh", kind="screening", count=4, duplicates=1
    )
    assert target.store.batch(fingerprint)["role"] == "pscreen-fresh"
    assert "pscreen-fresh" not in BatteryAdapter(target).sealed_roles()


def test_unavailable_is_typed_and_records_nothing_in_battery(tmp_path, refs, backend):
    target = make(tmp_path / "v", refs, backend, require_commitment=True)
    validator, operator = surfaces(tmp_path, target)
    result = validator.evaluate(neutral("hk1", strategy(), 1))
    assert (result["kind"], result["code"]) == (
        "UNAVAILABLE",
        "commitment_reader_unavailable",
    )
    with sqlite3.connect(target.store.path) as db:
        assert db.execute("SELECT COUNT(*) FROM submissions").fetchone() == (0,)
    assert operator.attempt_counts("hk1")["by_kind"]["UNAVAILABLE"] == 1


def test_infrastructure_failure_is_typed_never_a_score(
    tmp_path, refs, backend, monkeypatch
):
    target = make(tmp_path / "v", refs, backend)
    validator, operator = surfaces(tmp_path, target)
    # Infrastructure on every attempt: parked, never scored.
    backend.failures = MAX_INFRA_ATTEMPTS
    result = validator.evaluate(neutral("hk1", strategy(), 1))
    assert result["kind"] == "OUTCOME"
    assert result["outcome"]["state"] == "FAILED_INFRA"  # two attempts used
    assert "screening" not in result["outcome"]
    sid = result["outcome"]["submission_id"]
    operator.advance()  # the third attempt
    parked = validator.outcome(DIGEST, sid, "hk1")["outcome"]
    assert parked["state"] == "FAILED_INFRA_EXHAUSTED"
    assert "screening" not in parked
    assert target.store.score(sid) is None
    # A single infrastructure failure is retried under a new attempt.
    backend.failures = 1
    result = validator.evaluate(neutral("hk2", strategy(neighbours=5), 2))
    assert result["outcome"]["state"] == "SCORED"
    sid = result["outcome"]["submission_id"]
    assert target.store.submission(sid)["binding"]["attempt"] == 1
    # An adapter fault is infrastructure too, and its text is not echoed.

    def broken(*args, **kwargs):
        raise RuntimeError("disk full at /private/" + sid)

    monkeypatch.setattr(target, "admit", broken)
    result = validator.evaluate(neutral("hk3", strategy(neighbours=3), 3))
    assert (result["kind"], result["code"]) == ("FAILED_INFRA", "adapter_failure")
    assert "/private/" not in json.dumps(result)
    assert operator.attempt_counts("hk3")["by_kind"]["FAILED_INFRA"] == 1


def _coverage_rule_recorded(tmp_path, refs, backend):
    """GRAPHITE-COVERAGE-PARITY-01 changed outcomes (`daemon.incomplete`)
    under an unchanged RULE and rule_digest, so every outcome, binding,
    refusal and score record written from it on names the coverage rule, and
    a row written before it (no such field) still reads, without one."""
    from carbon.battery import daemon

    identity = daemon.COVERAGE_IDENTITY
    assert identity["name"] == "missing-prediction-is-a-schema-gate-failure.v1"
    assert identity["digest"].startswith("sha256:")
    target = make(tmp_path / "v", refs, backend)
    scored = direct(target, "hk1", strategy(neighbours=8), 1)
    refused = direct(target, "hk2", strategy(backbone="not-a-backbone"), 2)
    assert (scored["state"], refused["state"]) == ("SCORED", "INVALID_CONSTRUCTION")
    for outcome in (scored, refused):
        assert outcome["coverage_rule"] == identity
    sid = scored["submission_id"]
    assert target.store.submission(sid)["binding"]["coverage_rule"] == identity
    assert target.store.score(sid)["record"]["coverage_rule"] == identity
    # The rule and its pinned digest are unchanged: the coverage rule sits
    # beside them, never inside them.
    assert rule_digest(target.rule) == rule_digest() == rule_digest(daemon.RULE)
    assert "coverage" not in json.dumps(daemon.RULE)
    # A row written before the ruling: the field absent, read as written.
    with sqlite3.connect(target.store.path) as db:
        db.execute(
            "UPDATE submissions SET binding=json_remove(binding, '$.coverage_rule'),"
            " failure=json_remove(failure, '$.coverage_rule')"
        )
    for old in (sid, refused["submission_id"]):
        outcome = target.outcome(old)
        assert "coverage_rule" not in outcome
        assert outcome["state"] in ("SCORED", "INVALID_CONSTRUCTION")
        assert daemon.coverage_rule_of(target.store.submission(old)) is None


def test_every_new_record_names_the_coverage_rule_and_old_ones_still_read(
    tmp_path, refs, backend
):
    _coverage_rule_recorded(tmp_path, refs, backend)


def test_a_dropped_coverage_rule_field_is_caught(tmp_path, refs, backend, monkeypatch):
    """Mutation: the outcome reader drops the field (`daemon.coverage_rule_of`,
    the name `outcome` reads); the guard above turns red."""
    from carbon.battery import daemon

    monkeypatch.setattr(daemon, "coverage_rule_of", lambda row: None)
    with pytest.raises(AssertionError):
        _coverage_rule_recorded(tmp_path, refs, backend)


def test_the_adapter_wraps_only_a_locked_battery_validator(tmp_path, refs, backend):
    with pytest.raises(TypeError):
        BatteryAdapter(object())
    target = make(tmp_path / "v", refs, backend)
    del target.lock_path
    with pytest.raises(TypeError):
        BatteryAdapter(target)
