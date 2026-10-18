"""Unbound common results never become bank evidence or promotion.

Raw score fixtures lack the complete private evaluation binding.
Pure config/factory and scheduling tests use test sources, without private
file access or solve jobs. Canonical acceptance belongs to the composition owner.
"""

from dataclasses import replace
from types import SimpleNamespace
import hashlib

import pytest

from carbon.battery.pool_store import PoolStore, StateError, canonical
from carbon.challenge_validator.bank_promotion import (
    BankPromotion,
    BankResult,
    BankVersion,
)
from carbon.challenge_validator.batch_source import BatchSource, ProducerRefused
from carbon.challenge_validator.interface import digest
from carbon.rewards import winner_eligibility
from carbon.scoring import ScoreEngine
from carbon.scoring.solver_benchmark_v3 import COUNT_KEYS, register_pack


@pytest.fixture
def store(tmp_path):
    store = PoolStore(tmp_path / "synthetic.sqlite", clock=lambda: 123.0)
    store.bind({"rule_digest": digest("fixture rule")})
    # A synthetic private-bank snapshot, not scientific reference evidence.
    with store.transaction() as db:
        for index in range(store.rule["active_batches"]):
            db.execute(
                "INSERT INTO batches VALUES(?,'screening',?,?,'{}','PREPARED',"
                "'COMPLETE',?,NULL,NULL)",
                (
                    digest(["bank", index]),
                    f"fixture-{index}",
                    index,
                    digest(["references", index]),
                ),
            )
    store.open_pool()
    return store


def version(store, name="v1"):
    return BankVersion.current(
        store,
        evaluation_digest=digest(["exam", name]),
        pack_digest=digest(["pack", name]),
    )


def scored(store, model, value=1.0, *, bank=None, status="SCORED_DEVELOPMENT"):
    store.admit(
        model,
        request_digest=digest(model),
        hotkey="fixture-" + model,
        challenge="fixture",
        strategy={},
        binding={},
    )
    artifact = store.retain_model(
        model,
        recipe_digest=digest(["recipe", model]),
        seed=0,
        state=model.encode(),
        reconstruction={"scope": "SYNTHETIC_DEVELOPMENT"},
    )
    store.mark(model, "RECONSTRUCTED")
    bank = bank or version(store)
    return BankResult.from_common_score(
        model,
        bank,
        artifact,
        {
            "schema": "carbon.scoring.solver-benchmark-score.v3",
            "status": "DEVELOPMENT_ONLY",
            "pack_digest": bank.pack_digest,
            "models": [
                {
                    "artifact_digest": artifact,
                    "status": status,
                    "performance_score": value,
                }
            ],
        },
    )


def test_raw_common_score_cannot_cache_compare_or_promote(store):
    flow = BankPromotion(store)
    first, second = scored(store, "m1"), scored(store, "m2")
    before = store.pool()
    for result in (first, second):
        assert not result.ready
        with pytest.raises(StateError, match="evaluation_binding_unavailable"):
            flow.consider(result)
        with pytest.raises(StateError, match="evaluation_binding_unavailable"):
            flow.retain(result)
        with pytest.raises(StateError, match="evaluation_binding_unavailable"):
            store.record_bank_result(result, expected_incumbent=None, promote=True)
    assert store.incumbent() is None
    assert flow.cached("m1", first.version) is None
    assert store.pool() == before
    assert store.events("final_frozen") == []
    assert store.events("final_decided") == []
    with store.db() as db:
        assert db.execute("SELECT COUNT(*) FROM finals").fetchone() == (0,)
        assert db.execute(
            "SELECT COUNT(*) FROM batches WHERE kind='finalist'"
        ).fetchone() == (0,)
    assert store.events("bank_comparison") == []


def test_real_common_score_engine_output_lacks_bank_evidence(store):
    retained = scored(store, "m")
    pack = register_pack(
        {
            "schema": "carbon.scoring.solver-benchmark-pack.v3",
            "scope": "SYNTHETIC_DEVELOPMENT",
            "challenge": "fixture",
            "benchmark_registration_digest": digest("fixture registration"),
            "physics_contract": {
                "version": "fixture",
                "definition_digest": digest("fixture physics"),
            },
            "output": {
                "quantity": "fixture",
                "unit": "fixture",
                "metric": "mean_absolute_error",
            },
            "hard_gates": ["fixture_physics"],
            "accuracy_ceiling": 0.25,
            "performance_objective": "maximize_paired_speedup",
        }
    )
    benchmark = {
        "schema": "carbon.score-lab.solver-benchmark-result.v2",
        "scope": pack["scope"],
        "challenge": pack["challenge"],
        "registration_digest": pack["benchmark_registration_digest"],
        "physics_contract": pack["physics_contract"],
        "output": pack["output"],
        "ranking": None,
        "models": [
            {
                "artifact_digest": retained.artifact_digest,
                "by_role": {
                    "P": {
                        "status": "MEASURED_DEVELOPMENT",
                        "attempted": 1,
                        "counts": {k: int(k == "resolved") for k in COUNT_KEYS},
                        "gate_failures": {"fixture_physics": 0},
                        "mandatory_gates_pass": True,
                        "mean_absolute_error": 0.1,
                        "paired_speedup": 2.0,
                    }
                },
            }
        ],
    }
    bank = BankVersion.current(
        store,
        evaluation_digest=digest("fixture registration"),
        pack_digest=pack["pack_digest"],
    )
    result = BankResult.from_common_score(
        "m",
        bank,
        retained.artifact_digest,
        ScoreEngine.score_solver_benchmark_v3(benchmark, pack),
    )
    assert not result.ready
    with pytest.raises(StateError, match="evaluation_binding_unavailable"):
        BankPromotion(store).consider(result)
    assert store.events("final_frozen") == []
    assert store.incumbent() is None


def test_old_cache_is_readable_but_cannot_replay_a_promotion(store):
    flow = BankPromotion(store)
    first, second = scored(store, "m1"), scored(store, "m2")
    # Simulate an eef80 development cache. Historical rows are readable,
    # never grandfathered into accepted evidence by their old decision.
    with store.transaction() as db:
        result_op = store._bank_operation("bank_result", "m1", first.version.identity)
        comparison_op = store._bank_operation(
            "bank_comparison", "m1", first.version.identity
        )
        db.execute(
            "INSERT INTO operations VALUES(?,'bank_result','RECORDED',?)",
            (result_op, canonical(first.document())),
        )
        db.execute(
            "INSERT INTO operations VALUES(?,'bank_comparison','DECIDED',?)",
            (
                comparison_op,
                canonical({"result_digest": first.identity, "decision": "PROMOTE"}),
            ),
        )
    store.set_incumbent("m2", "bank_comparison_development")
    events = store.events()
    assert flow.cached("m1", first.version) == first
    assert not flow.cached("m1", first.version).ready
    assert store.bank_comparison(first)["decision"] == "PROMOTE"  # history only
    with pytest.raises(StateError, match="evaluation_binding_unavailable"):
        flow.consider(first)
    assert store.incumbent()["model_id"] == "m2"
    assert store.events() == events
    changed = scored(store, "m1", value=2.0)
    with pytest.raises(StateError, match="bank_result_changed"):
        store.bank_comparison(changed)
    with pytest.raises(StateError, match="evaluation_binding_unavailable"):
        flow.consider(changed)


@pytest.mark.parametrize("change", ["pool", "references", "evaluation"])
def test_old_same_pack_score_cannot_be_relabelled_as_a_new_bank(store, change):
    old = scored(store, "m1")
    store.set_incumbent("m1", "bank_comparison_development")
    original_events = store.events("incumbent")
    with store.db() as db:
        original_since = db.execute("SELECT since FROM incumbent").fetchone()
    store.clock = lambda: 999.0
    with store.transaction() as db:
        if change == "pool":
            db.execute("UPDATE pool SET version=version+1")
        elif change == "references":
            db.execute("UPDATE batches SET references_digest=?", (digest("new refs"),))
    bank = BankVersion.current(
        store,
        evaluation_digest=digest("new evaluation")
        if change == "evaluation"
        else old.version.evaluation_digest,
        pack_digest=old.version.pack_digest,
    )
    assert bank != old.version
    relabelled = replace(old, version=bank)
    assert relabelled.result_json == old.result_json
    assert relabelled.version.pack_digest == old.version.pack_digest
    with pytest.raises(StateError, match="evaluation_binding_unavailable"):
        BankPromotion(store).consider(relabelled)
    assert store.bank_result("m1", bank.identity) is None
    assert store.events("incumbent") == original_events
    with store.db() as db:
        assert db.execute("SELECT since FROM incumbent").fetchone() == original_since


@pytest.mark.parametrize(
    "status",
    [
        "RECONSTRUCTED",
        "SCORE_UNAVAILABLE",
        "FAILED_INFRA",
        "SCIENTIFIC_INADMISSIBLE",
        "INDETERMINATE_EVIDENCE",
    ],
)
def test_unavailable_or_inadmissible_evidence_never_compares_or_promotes(store, status):
    result = scored(store, "m", value=None, status=status)
    with pytest.raises(StateError, match="evaluation_binding_unavailable"):
        BankPromotion(store).consider(result)
    assert store.incumbent() is None
    assert store.events("bank_comparison") == []


@pytest.mark.parametrize("value", [None, True, "2.0", 10**309])
def test_non_numeric_or_unrepresentable_value_is_not_a_score(store, value):
    result = scored(store, "m", value=value)
    with pytest.raises(StateError, match="evaluation_binding_unavailable"):
        BankPromotion(store).consider(result)
    assert store.incumbent() is None


def test_withdrawn_bank_and_invalidated_model_cannot_promote(store):
    result = scored(store, "m")
    store.mark("m", "VOID")
    with pytest.raises(StateError, match="evaluation_binding_unavailable"):
        BankPromotion(store).consider(result)
    store.mark("m", "RECONSTRUCTED")
    with store.transaction() as db:
        db.execute(
            "INSERT INTO withdrawn_batches VALUES(?,'fixture',0)",
            (result.version.references[0][0],),
        )
    with pytest.raises(StateError, match="evaluation_binding_unavailable"):
        BankPromotion(store).consider(result)
    assert store.bank_result("m", result.version.identity) is None


@pytest.mark.parametrize(
    "field,value",
    [
        ("rule_digest", digest("other rule")),
        ("pool_version", 17),
        ("references", ((digest("other batch"), digest("other references")),)),
    ],
)
def test_changed_bank_or_rule_cannot_promote(store, field, value):
    result = scored(store, "m", bank=replace(version(store), **{field: value}))
    with pytest.raises(StateError, match="evaluation_binding_unavailable"):
        BankPromotion(store).consider(result)
    assert store.incumbent() is None


def test_wrong_pack_or_retained_artifact_is_rejected(store):
    result = scored(store, "m")
    with pytest.raises(ValueError, match="bank_result_binding"):
        replace(result, version=replace(result.version, pack_digest=digest("other")))
    other = scored(store, "other")
    wrong = replace(other, submission_id="m")
    with pytest.raises(StateError, match="evaluation_binding_unavailable"):
        BankPromotion(store).consider(wrong)
    assert store.incumbent() is None


def test_unbound_score_cannot_move_existing_incumbent(store):
    scored(store, "m1")
    candidate = scored(store, "m2")
    store.set_incumbent("m1", "bank_comparison_development")
    before = store.events()
    with pytest.raises(StateError, match="evaluation_binding_unavailable"):
        BankPromotion(store).consider(candidate)
    assert store.incumbent()["model_id"] == "m1"
    assert store.bank_result("m2", candidate.version.identity) is None
    assert store.events() == before


def test_invalidated_incumbent_evidence_cannot_support_a_comparison(store):
    flow = BankPromotion(store)
    scored(store, "m1")
    store.set_incumbent("m1", "bank_comparison_development")
    candidate = scored(store, "m2")
    store.mark("m1", "VOID")
    with pytest.raises(StateError, match="evaluation_binding_unavailable"):
        flow.consider(candidate)
    assert store.incumbent()["model_id"] == "m1"
    assert flow.cached("m2", candidate.version) is None


def test_development_first_result_cannot_take_legacy_weight_shortcut(store):
    scored(store, "m")
    store.set_incumbent("m", "bank_comparison_development")
    with pytest.raises(
        winner_eligibility.RewardFailure, match="PROMOTION_DEVELOPMENT_ONLY"
    ):
        winner_eligibility.battery_promotion(SimpleNamespace(store=store))


class Source(BatchSource):
    challenge_id = "fixture"

    def identities(self):
        return {"rule_digest": digest("fixture rule")}

    def cadence(self):
        return {"every_blocks": 10, "active": 3}

    def draw(self, role, *, kind, size=None):
        raise AssertionError("no fresh solve")

    def jobs(self, fingerprint):
        return []

    def solve(self, work, **options):
        raise AssertionError("no fresh solve")

    def ingest(self, fingerprint, records):
        return True

    def sealed(self, fingerprint):
        return None

    def export(self, fingerprint):
        return {}

    def check(self, fingerprint):
        return None


def test_bank_path_serves_no_finalists_and_keeps_registered_maintenance():
    source = Source()
    lean = source.for_comparison("cached_bank")
    assert source.kinds() == ("screening", "finalist")  # legacy unchanged
    assert lean.kinds() == ("screening",)
    assert lean.cadence() == source.cadence()
    assert lean.identities() == source.identities()
    assert source.for_comparison("fresh_final") is source
    with pytest.raises(ProducerRefused, match="producer_kind_refused"):
        lean.draw("never", kind="finalist")


def test_producer_disables_finalist_draw_refill_and_republish(monkeypatch):
    from carbon.challenge_validator.producer import Producer

    source = Source().for_comparison("cached_bank")
    producer = object.__new__(Producer)
    producer.sources = {source.challenge_id: source}
    producer.journal = SimpleNamespace(find=lambda *args: None)
    monkeypatch.setattr(producer, "_retire", lambda *args: [])
    monkeypatch.setattr(producer, "_release", lambda *args: None)
    monkeypatch.setattr(producer, "_withdrawn", lambda *args: False)
    monkeypatch.setattr(
        producer,
        "_scheduled",
        lambda cid, kind="screening": {
            2: "pending-" + kind,
        },
    )
    published, filled = [], []
    monkeypatch.setattr(producer, "publish", lambda cid, fp: published.append(fp))

    def fill(cid, slot, block, role, kind="screening"):
        filled.append(kind)
        return "filled"

    monkeypatch.setattr(producer, "_fill", fill)
    with pytest.raises(ProducerRefused, match="producer_kind_refused"):
        producer.draw("fixture", "never", kind="finalist")
    report = producer.tick(20)
    assert published == ["pending-screening"]
    assert filled == ["screening"]
    assert report["fixture"]["finalist"] == {"filled": [], "unfilled": []}


@pytest.mark.parametrize("mode", [None, True, "", "skip_finals", ["cached_bank"]])
def test_unknown_comparison_mode_is_refused(mode):
    with pytest.raises(ProducerRefused, match="producer_comparison_refused"):
        Source().for_comparison(mode)


@pytest.mark.parametrize("mode", [None, "fresh_final", "cached_bank"])
def test_real_config_factory_selects_comparison_routing(tmp_path, monkeypatch, mode):
    from carbon.challenge_validator import family_source, producer as pr

    # Exercise the real owner approval and factory routing with a synthetic
    # source constructor, without opening any deployment or bank state.
    decision = tmp_path / ".agent" / "decisions" / "fixture.md"
    decision.parent.mkdir(parents=True)
    decision.write_bytes(b"OWNER-FIXTURE-01\n")
    source = Source()
    monkeypatch.setattr(
        family_source,
        "family_source_class",
        lambda cid: (lambda deployment, repository: source)
        if cid == source.challenge_id
        else None,
    )
    spec = {
        "deployment": "unused-fixture-deployment",
        "approval": {
            "record": "OWNER-FIXTURE-01",
            "file": decision.name,
            "sha256": hashlib.sha256(decision.read_bytes()).hexdigest(),
        },
    }
    if mode is not None:
        spec["comparison"] = mode
    config = {
        "schema": pr.CONFIG_SCHEMA,
        "service_account": "fixture-account",
        "producer_dir": str(tmp_path / "unused-producer"),
        "sources": {source.challenge_id: spec},
    }
    # File custody remains covered by the existing POSIX tests. This test
    # isolates the parser/factory and never claims a real deployment.
    monkeypatch.setattr(pr, "_read_private", lambda path: config)
    loaded = pr.load_config("fixture", account="fixture-account")
    monkeypatch.setattr(pr, "load_config", lambda path: loaded)

    class Captured(pr.Producer):
        def __init__(self, directory, sources, **kwargs):
            self.sources = {s.challenge_id: s for s in sources}

    made = Captured.from_config("fixture", repository=tmp_path)
    selected = made.sources[source.challenge_id]
    assert selected.kinds() == (
        ("screening",) if mode == "cached_bank" else ("screening", "finalist")
    )
    assert selected.cadence() == source.cadence()
    assert selected.identities() == source.identities()
    spec["approval"]["sha256"] = "0" * 64
    with pytest.raises(ProducerRefused, match="producer_challenge_not_approved"):
        Captured.from_config("fixture", repository=tmp_path)


@pytest.mark.parametrize("mode", [None, True, "", "skip_finals", ["cached_bank"]])
def test_config_rejects_unknown_comparison_before_source_creation(monkeypatch, mode):
    from carbon.challenge_validator import producer as pr

    config = {
        "schema": pr.CONFIG_SCHEMA,
        "service_account": "fixture-account",
        "producer_dir": "unused",
        "sources": {
            "fixture": {
                "deployment": "unused",
                "approval": {},
                "comparison": mode,
            }
        },
    }
    monkeypatch.setattr(pr, "_read_private", lambda path: config)
    with pytest.raises(ProducerRefused, match="producer_config_malformed"):
        pr.load_config("fixture", account="fixture-account")
    with pytest.raises(ProducerRefused, match="producer_comparison_refused"):
        pr.source_for("fixture", config["sources"]["fixture"])
