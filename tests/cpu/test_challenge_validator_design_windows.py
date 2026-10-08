"""Design questions on battery's banked screening windows (VALIDATOR-23 slice
3b; rule `v2-bank-design`).

A producer under `v2-bank-design` fills its pool bank and its battery Q3
design bank with scripted truth solves, ticks, and publishes slot 1. The
screening window carries `k` design questions, each with its Merkle proof
into a sealed design tranche; the finalist window carries none. An
import-only validator under the same rule verifies every question before it
imports, and refuses a tampered or missing set.

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

from test_challenge_validator_producer import scripted_solve
from test_challenge_validator_tuning_quiz import scripted_solve as quiz_solve

from carbon.battery import exam, seeds, worker
from carbon.battery.daemon import BatteryValidator, rule_digest
from carbon.battery.pool_store import PoolStore
from carbon.challenge_validator import answer_key as ak
from carbon.challenge_validator import bank_proof
from carbon.challenge_validator import design_bank as db
from carbon.challenge_validator import producer as pr
from carbon.challenge_validator.battery import BatteryAdapter
from carbon.challenge_validator.battery_bank import BankedBatterySource

RULE = exam.DEVELOPMENT_RULE_V2_BANK_DESIGN
K = RULE["design"]["k"]


def adapter(directory, *, rule=RULE, import_only=False):
    directory.mkdir(mode=0o700)
    root = seeds.PrivateRoot.create(directory / "root.bin")
    journal = seeds.SeedJournal(directory / "journal.jsonl")
    journal.commit_root(root, seeds.seed_pin("sha256:" + "0" * 64, rule_digest(rule)))
    target = BatteryValidator(
        store=PoolStore(directory / "state.sqlite3", rule=rule),
        backend=worker.DirectBackend(REPOSITORY),
        root=root,
        journal=journal,
        repository=REPOSITORY,
        require_commitment=False,
        import_only=import_only,
        allow_published_cases=not import_only,
    )
    target.start()
    target.lock_path = str(directory / "state.sqlite3.lock")
    target.readonly = False
    return BatteryAdapter(target)


@pytest.fixture(scope="module")
def run(tmp_path_factory):
    """One producer under `v2-bank-design`, ticked at block 0. The design
    bank is registered small for the test (B = 4k)."""
    tmp = tmp_path_factory.mktemp("design")
    saved = db.DESIGN_BANKS["battery-q3"]
    db.DESIGN_BANKS["battery-q3"] = {**saved, "size": 4 * K}
    try:
        source = BankedBatterySource(
            adapter(tmp / "producer-state"),
            tmp / "bank",
            overlay=tmp / "overlay",
            repository=REPOSITORY,
            runner=scripted_solve,
            design_dir=tmp / "design",
            design_solver=lambda work, workers: quiz_solve(work, edge=True),
        )
        key = ak.ProducerKey.create(tmp / "producer.key")
        producer = pr.Producer(tmp / "producer", [source], signing_key=key)
        report = producer.tick(0)[source.challenge_id]
    finally:
        db.DESIGN_BANKS["battery-q3"] = saved
    outbox = tmp / "producer" / "outbox" / source.challenge_id
    packages = [ak.read_private(p) for p in sorted(outbox.glob("*.json"))]
    by_kind = {v["manifest"]["commitment"]["kind"]: v for v in packages}
    return {
        "tmp": tmp,
        "source": source,
        "key": key,
        "report": report,
        "outbox": outbox,
        "by_kind": by_kind,
    }


def test_the_screening_window_carries_k_proven_design_questions(run):
    assert run["report"]["filled"] == [1]
    value = run["by_kind"]["screening"]
    commitment, payload = value["manifest"]["commitment"], value["payload"]
    design = commitment["design"]
    questions = payload["design"]["questions"]
    assert design["bank"] == "design:battery-q3" and design["k"] == K
    assert len(questions) == K
    assert design["selection_digest"] == bank_proof.selection_digest(list(questions))
    roots = {t["tranche"]: t["root"] for t in design["tranches"]}
    for question_id, question in questions.items():
        assert question["reference"]["status"] == "OK"
        assert bank_proof.verify(
            question_id,
            question["inputs"],
            question["reference"],
            question["proof"],
            roots[question["tranche"]],
        )
    # The finalist window carries none.
    finalist = run["by_kind"]["finalist"]
    assert "design" not in finalist["manifest"]["commitment"]
    assert "design" not in finalist["payload"]


def test_each_drawn_question_is_one_exposure(run):
    bank = run["source"].design
    with bank.ledger._db() as db_:
        rows = db_.execute(
            "SELECT exposures, COUNT(*) FROM cases WHERE bank = ? "
            "AND status = 'OK' GROUP BY exposures",
            (bank.bank,),
        ).fetchall()
    assert {r[0]: r[1] for r in rows}.get(1) == K


def test_an_import_only_validator_verifies_and_stores_the_questions(run, tmp_path):
    validator = adapter(tmp_path / "validator", import_only=True)
    result = ak.import_local(validator, run["key"].public_key, run["outbox"])
    assert sorted(p["state"] for p in result["packages"]) == ["IMPORTED", "IMPORTED"]
    screening = run["by_kind"]["screening"]["manifest"]["commitment"]["fingerprint"]
    stored = validator.target.store.design(screening)
    assert stored["bank"] == "design:battery-q3"
    assert len(stored["questions"]) == K
    assert all(q["reference"]["status"] == "OK" for q in stored["questions"].values())


def resigned(run, commitment, payload):
    return ak.verify(ak.package(run["key"], commitment, payload), run["key"].public_key)


def tampered(run, change):
    value = json.loads(json.dumps(run["by_kind"]["screening"]))
    commitment, payload = value["manifest"]["commitment"], value["payload"]
    change(commitment, payload)
    return resigned(run, commitment, payload)


def first(payload):
    return payload["design"]["questions"][min(payload["design"]["questions"])]


@pytest.mark.parametrize(
    ("change", "code"),
    [
        # A reference altered and re-signed by the producer's own key: its
        # proof no longer reaches the committed tranche root.
        (
            lambda c, p: first(p)["reference"]["panel"][0]["values"].update(
                time_to_cv_onset_s=1.0
            ),
            "answer_key_design_proof",
        ),
        # A question's task altered: its digest no longer re-derives.
        (
            lambda c, p: first(p)["inputs"]["task"].update(candidates=["x"]),
            "answer_key_design_malformed",
        ),
        # One question too few for the rule's k.
        (
            lambda c, p: p["design"]["questions"].pop(min(p["design"]["questions"])),
            "answer_key_design_mismatch",
        ),
        # No design questions at all under a design rule.
        (lambda c, p: (c.pop("design"), p.pop("design")), "answer_key_design_missing"),
    ],
)
def test_a_wrong_design_set_imports_nothing(run, tmp_path, change, code):
    validator = adapter(tmp_path / "validator", import_only=True)
    commitment, payload = tampered(run, change)
    with pytest.raises(ak.AnswerKeyRefused) as refused:
        validator.import_answer_key(commitment, payload)
    assert refused.value.code == code
    assert validator.target.store.design(commitment["fingerprint"]) is None


def test_a_rule_without_design_never_takes_design_questions(run, tmp_path):
    """A `v2-bank` producer refuses a design directory, and a design package
    is not this rule's (its rule digest differs)."""
    with pytest.raises(pr.ProducerRefused) as refused:
        BankedBatterySource(
            adapter(tmp_path / "plain", rule=exam.DEVELOPMENT_RULE_V2_BANK),
            tmp_path / "bank",
            repository=REPOSITORY,
            design_dir=tmp_path / "design",
        )
    assert refused.value.code == "producer_design_not_in_rule"
    plain = adapter(tmp_path / "validator", rule=exam.DEVELOPMENT_RULE_V2_BANK)
    value = run["by_kind"]["screening"]
    with pytest.raises(ak.AnswerKeyRefused) as refused:
        plain.import_answer_key(*ak.verify(value, run["key"].public_key))
    assert refused.value.code == "answer_key_identity_mismatch"
