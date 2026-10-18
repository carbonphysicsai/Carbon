"""Private DEVELOPMENT reuse from real binder inputs and inert original bytes.

Source pins are synthetic operator fixtures, not production registrations. These
tests execute no model, solver, network or qualification. No result promotes.
"""

from copy import deepcopy

import pytest
from test_score_lab_private_evaluation_evidence import (
    _graph_case,
    _result,
    _source_receipt,
)

from carbon.battery.pool_store import PoolStore, StateError
from carbon.challenge_validator.bank_promotion import (
    BankPromotion,
    private_evaluation_key,
)
from carbon.challenge_validator.interface import digest
from carbon.scoring.solver_benchmark_v3 import register_pack


@pytest.fixture
def case(tmp_path):
    return _graph_case(tmp_path)


@pytest.fixture
def store(tmp_path):
    return PoolStore(tmp_path / "private.sqlite", clock=lambda: 123.0)


def admitted(store, case, model, *, state=None, recipe=None, version=None):
    entry = case["entry"]
    recipe = recipe or entry["recipe_digest"]
    store.admit(
        model,
        request_digest=digest(["request", model]),
        hotkey="fixture-" + model,
        challenge=entry["challenge"],
        strategy={},
        binding={
            "challenge": {
                "id": entry["challenge"],
                "version": version or entry["challenge_version"],
            },
            "recipe_digest": recipe,
        },
    )
    store.retain_model(
        model,
        recipe_digest=recipe,
        seed=0,
        state=case["originals"]["build/output/state.npz"] if state is None else state,
        reconstruction={"scope": "SYNTHETIC_DEVELOPMENT"},
    )
    store.mark(model, "RECONSTRUCTED")


def inputs(case, *, version="synthetic-eval-v1", **changes):
    receipt, pin = _source_receipt(case, version=version)
    args = {
        "entry": case["entry"],
        "custody_receipt_raw": case["custody_receipt_raw"],
        "trusted_job": case["job"],
        "registration": case["registration"],
        "references": case["references"],
        "measured_model": case["measured"],
        "score_pack": case["pack"],
        "graph_originals": case["graph_originals"],
        "expected_result_digest": case["result"]["result_digest"],
        "ordered_query_bytes": case["ordered_query_bytes"],
        "evaluation_source_receipt_raw": receipt,
    }
    args.update(changes)
    return pin, args


def operation_count(store):
    with store.db() as db:
        return db.execute("SELECT COUNT(*) FROM operations").fetchone()[0]


def test_actual_binder_retains_private_pair_without_promotion_or_battery_pool(
    store, case
):
    for model in ("inc", "candidate"):
        admitted(store, case, model)
    store.set_incumbent("inc", "historical fixture")
    before = store.events()
    pin, args = inputs(case)
    flow = BankPromotion(store, registered_source_receipt_sha256=pin)
    inc = flow.retain_private("inc", **args)
    candidate = flow.retain_private("candidate", **args)
    key = candidate["evaluation_key"]
    pair = flow.private_pair("candidate", key)
    assert pair["scope"] == "PRIVATE_OPERATOR_DEVELOPMENT"
    assert pair["expected_incumbent"] == "inc"
    assert pair["candidate"] == candidate
    assert pair["incumbent"] == inc
    assert flow.private_pair("candidate", key) == pair
    assert flow.retain_private("inc", **args) == inc
    assert operation_count(store) == 2
    assert store.events() == before
    assert store.pool() is None  # generic source; no Battery case layout used
    with pytest.raises(StateError, match="accepted_score_unavailable"):
        flow.consider(candidate)
    assert store.incumbent()["model_id"] == "inc"


def test_missing_pin_and_pack_are_typed_refusals_without_cache(store, case):
    admitted(store, case, "m")
    pin, args = inputs(case)
    with pytest.raises(StateError, match="source_pin_missing"):
        BankPromotion(store).retain_private("m", **args)
    flow = BankPromotion(store, registered_source_receipt_sha256=pin)
    with pytest.raises(StateError, match="score_compatibility_unavailable"):
        flow.retain_private("m", **{**args, "score_pack": None})
    with pytest.raises(StateError, match="private_evaluation_inputs_invalid"):
        flow.retain_private("m", sidecar={"status": "BOUND_DEVELOPMENT_ONLY"})
    with pytest.raises(StateError, match="source_pin_override"):
        BankPromotion(store).retain_private(
            "m", registered_source_receipt_sha256=pin, **args
        )
    assert operation_count(store) == 0


def test_relabelled_old_reference_result_refuses_at_real_core(store, case):
    admitted(store, case, "m")
    pin, args = inputs(case)
    changed = deepcopy(case["references"])
    changed[0]["outputs"] = [0.3]
    args["references"] = changed
    args["expected_result_digest"] = _result(case, references=changed)["result_digest"]
    with pytest.raises(StateError, match="source_case_binding"):
        BankPromotion(store, registered_source_receipt_sha256=pin).retain_private(
            "m", **args
        )
    assert operation_count(store) == 0


@pytest.mark.parametrize("change", ["state", "recipe", "challenge_version"])
def test_retained_model_substitution_is_refused(store, case, change):
    options = (
        {"state": b"other retained model"}
        if change == "state"
        else (
            {"recipe": digest("other recipe")}
            if change == "recipe"
            else {"version": "other-version"}
        )
    )
    admitted(store, case, "m", **options)
    pin, args = inputs(case)
    with pytest.raises(StateError, match="private_evaluation_model_binding"):
        BankPromotion(store, registered_source_receipt_sha256=pin).retain_private(
            "m", **args
        )
    assert operation_count(store) == 0


def test_candidate_gate_failure_stays_in_result_not_shared_evaluation(store, case):
    for model in ("inc", "failed"):
        admitted(store, case, model)
    store.set_incumbent("inc", "historical fixture")
    pin, args = inputs(case)
    flow = BankPromotion(store, registered_source_receipt_sha256=pin)
    inc = flow.retain_private("inc", **args)
    measured = deepcopy(case["measured"])
    measured["cases"][0]["gates"]["toy_gate"] = False
    failed_args = {
        **args,
        "measured_model": measured,
        "expected_result_digest": _result(case, measured=measured)["result_digest"],
    }
    failed = flow.retain_private("failed", **failed_args)
    assert failed["evaluation_key"] == inc["evaluation_key"]
    pair = flow.private_pair("failed", failed["evaluation_key"])
    assert (
        pair["candidate"]["evidence"]["model_p"]["score_status"]
        == "SCIENTIFIC_INADMISSIBLE"
    )
    assert pair["candidate"]["evidence"]["model_p"]["performance_score"] is None
    assert (
        pair["candidate"]["evidence"]["model_result_digest"]
        != inc["evidence"]["model_result_digest"]
    )
    with pytest.raises(StateError, match="accepted_score_unavailable"):
        flow.consider(failed)


@pytest.mark.parametrize("status", ["UNRESOLVED", "FAILED_INFRA"])
def test_reference_failure_remains_typed_private_evidence(store, case, status):
    admitted(store, case, "m")
    references = [{"id": "toy-case", "status": status}]
    receipt, pin = _source_receipt(case, references=references)
    _, args = inputs(case)
    args.update(
        references=references,
        evaluation_source_receipt_raw=receipt,
        expected_result_digest=_result(case, references=references)["result_digest"],
    )
    flow = BankPromotion(store, registered_source_receipt_sha256=pin)
    saved = flow.retain_private("m", **args)
    cached = flow.private_pair("m", saved["evaluation_key"])["candidate"]
    assert cached["evidence"]["reference_coverage"][status] == 1
    model = cached["evidence"]["model_p"]
    assert model["score_status"] == (
        "FAILED_INFRA" if status == "FAILED_INFRA" else "INDETERMINATE_EVIDENCE"
    )
    assert model["performance_score"] is None
    with pytest.raises(StateError, match="accepted_score_unavailable"):
        flow.consider(cached)
    assert store.incumbent() is None


def test_new_version_refreshes_incumbent_once_and_preserves_old_result_and_clock(
    store, case
):
    for model in ("inc", "candidate"):
        admitted(store, case, model)
    store.set_incumbent("inc", "historical fixture")
    with store.db() as db:
        since = db.execute("SELECT since FROM incumbent").fetchone()
    original_events = store.events()
    old_pin, old_args = inputs(case)
    old_flow = BankPromotion(store, registered_source_receipt_sha256=old_pin)
    old = old_flow.retain_private("inc", **old_args)
    store.clock = lambda: 999.0
    pin, args = inputs(case, version="synthetic-eval-v2")
    flow = BankPromotion(store, registered_source_receipt_sha256=pin)
    candidate = flow.retain_private("candidate", **args)
    assert candidate["evaluation_key"] != old["evaluation_key"]
    with pytest.raises(StateError, match="incumbent_evaluation_required"):
        flow.private_pair("candidate", candidate["evaluation_key"])
    refreshed = flow.retain_private("inc", **args)
    assert (
        flow.private_pair("candidate", candidate["evaluation_key"])["incumbent"]
        == refreshed
    )
    assert flow.retain_private("inc", **args) == refreshed
    assert old_flow.private_pair("inc", old["evaluation_key"])["incumbent"] == old
    assert operation_count(store) == 3
    assert store.events() == original_events
    with store.db() as db:
        assert db.execute("SELECT since FROM incumbent").fetchone() == since


def test_pack_change_requires_compatible_incumbent_even_with_same_evaluation(
    store, case
):
    for model in ("inc", "candidate"):
        admitted(store, case, model)
    store.set_incumbent("inc", "historical fixture")
    pin, args = inputs(case)
    flow = BankPromotion(store, registered_source_receipt_sha256=pin)
    old = flow.retain_private("inc", **args)
    pack = register_pack(
        {
            **{k: v for k, v in case["pack"].items() if k != "pack_digest"},
            "accuracy_ceiling": 0.2,
        }
    )
    revised_args = {
        **args,
        "score_pack": pack,
        "expected_result_digest": _result(case, pack=pack)["result_digest"],
    }
    revised = flow.retain_private("candidate", **revised_args)
    assert (
        revised["evidence"]["evaluation_version_digest"]
        == old["evidence"]["evaluation_version_digest"]
    )
    assert revised["evaluation_key"] != old["evaluation_key"]
    with pytest.raises(StateError, match="incumbent_evaluation_required"):
        flow.private_pair("candidate", revised["evaluation_key"])


def test_changed_same_version_result_never_overwrites_history(store, case):
    admitted(store, case, "m")
    pin, args = inputs(case)
    flow = BankPromotion(store, registered_source_receipt_sha256=pin)
    first = flow.retain_private("m", **args)
    measured = deepcopy(case["measured"])
    measured["cases"][0]["gates"]["toy_gate"] = False
    changed = {
        **args,
        "measured_model": measured,
        "expected_result_digest": _result(case, measured=measured)["result_digest"],
    }
    with pytest.raises(StateError, match="private_evaluation_changed"):
        flow.retain_private("m", **changed)
    assert flow.private_pair("m", first["evaluation_key"])["candidate"] == first
    assert operation_count(store) == 1


@pytest.mark.parametrize("mutation", ["owner", "state", "void", "role", "body"])
def test_cached_private_data_is_rejoined_to_current_owner_and_retained_state(
    store, case, mutation
):
    admitted(store, case, "m")
    pin, args = inputs(case)
    flow = BankPromotion(store, registered_source_receipt_sha256=pin)
    saved = flow.retain_private("m", **args)
    with store.transaction() as db:
        if mutation == "owner":
            db.execute("UPDATE submissions SET hotkey='another-owner'")
        elif mutation == "state":
            db.execute("UPDATE models SET state=?", (b"substituted",))
        elif mutation == "void":
            db.execute("UPDATE submissions SET state='VOID'")
        elif mutation == "role":
            db.execute("UPDATE operations SET kind='historical-other-role'")
        else:
            db.execute("UPDATE operations SET body='{}'")
    with pytest.raises(
        StateError,
        match=(
            "private_evaluation_owner_changed"
            if mutation == "owner"
            else "private_evaluation_corrupt"
            if mutation in {"role", "body"}
            else "private_evaluation_model_binding"
        ),
    ):
        flow.private_pair("m", saved["evaluation_key"])


def test_lookup_requires_current_source_pin_and_reports_incumbent_cas_identity(
    store, case
):
    for model in ("inc", "candidate"):
        admitted(store, case, model)
    store.set_incumbent("inc", "historical fixture")
    pin, args = inputs(case)
    flow = BankPromotion(store, registered_source_receipt_sha256=pin)
    flow.retain_private("inc", **args)
    saved = flow.retain_private("candidate", **args)
    pair = flow.private_pair("candidate", saved["evaluation_key"])
    changed = BankPromotion(
        store, registered_source_receipt_sha256=digest("other source")
    )
    with pytest.raises(StateError, match="evaluation_source_changed"):
        changed.private_pair("candidate", saved["evaluation_key"])
    store.set_incumbent("other", "concurrent historical fixture", expected="inc")
    with pytest.raises(StateError, match="incumbent_moved"):
        store.set_incumbent(
            "candidate", "fixture CAS check", expected=pair["expected_incumbent"]
        )


def test_scoring_version_and_execution_profile_are_explicit_compatibility(store, case):
    admitted(store, case, "m")
    pin, args = inputs(case)
    saved = BankPromotion(store, registered_source_receipt_sha256=pin).retain_private(
        "m", **args
    )
    sidecar = deepcopy(saved["evidence"])
    sidecar["score_compatibility"]["execution_profile_digest"] = digest(
        "other execution profile"
    )
    assert private_evaluation_key(sidecar) != saved["evaluation_key"]
    sidecar["score_compatibility"]["scoring_version"] = "unsupported-scoring-version"
    with pytest.raises(StateError, match="score_compatibility_unavailable"):
        private_evaluation_key(sidecar)
