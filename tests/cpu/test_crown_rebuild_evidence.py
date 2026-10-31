"""The crown's averaging rebuild as an evidence-only derived task (slice 3, behind fakes).

Claims: the derived task is its own identity (origin, seed and repeat) and the default task identity is exactly what it
always was; it runs under the host-owned synthetic owner, found by the retention helpers only while `deriving` holds it
and never through the ledger's intents; its seed is set before it starts and a retry cannot change it; its artifacts
are retained and graded by the UNCOUNTED regrade only (no counted grade, exam-cap slot, Ladder document, pool filing or
KOTH filing) and its only output is the bound evaluation evidence; the host-fault second build is a different task.
"""

from __future__ import annotations

import hashlib
import json
from contextlib import contextmanager
from types import SimpleNamespace
from typing import ClassVar

import pytest

from carbon.challenge_validator import crown_average as ca
from carbon.challenge_validator import lean_recipe_retention as retention
from carbon.challenge_validator.lean_recipe import LeanRecipeAdapter
from carbon.development_session.construction_recipe import ConstructionRecipe
from carbon.registry.model import ChallengeKey
from carbon.research import DirectTaskStateV3, ResearchTaskId

ORIGIN = "rtsk_" + "a" * 64
HOST = ca.HOST_OWNER


# --- the request identity ----------------------------------------------------------------------------------


class _Recipe:
    digest = "sha256:" + "d" * 64

    def to_dict(self):
        return {"recipe": "x"}


def _adapter_for_request():
    info = SimpleNamespace(
        challenge_key="key",
        public_train_digest="t",
        practice_inputs_digest="p",
        interface_digest="i",
        construction_limits_digest="l",
    )
    material = {
        "construction_limits_document": {"reconstruction_resource_policy": {"w": 1}}
    }
    return SimpleNamespace(
        discovery=SimpleNamespace(info=info, _material=material),
        contract_digest="sha256:" + "c" * 64,
        _measure_query=False,
        _identities={
            "rule_digest": "r",
            "challenge_info_digest": "ci",
            "manifest_digest": "m",
            "construction_kit_digest": "k",
        },
    )


def _key(adapter, hotkey="miner", **extra):
    captured = {}

    class Request:
        def __init__(self, *args):
            captured["idempotency"] = args[1]

    from carbon import research

    original = research.DirectStartTaskRequestV3
    research.DirectStartTaskRequestV3 = Request
    try:
        LeanRecipeAdapter._request(
            adapter,
            hotkey,
            _Recipe(),
            evaluation_pack_digest="sha256:" + "e" * 64,
            **extra,
        )
    finally:
        research.DirectStartTaskRequestV3 = original
    return captured["idempotency"]


def test_the_default_task_identity_is_exactly_what_it_always_was():
    adapter = _adapter_for_request()
    binding = (
        "miner\0"
        + adapter.contract_digest
        + "\0"
        + _Recipe.digest
        + "\0EVALUATION_PACK\0"
        + "sha256:"
        + "e" * 64
    )
    expected = "lean-recipe-" + hashlib.sha256(binding.encode()).hexdigest()
    assert _key(adapter) == expected
    # an infra rerun is unchanged too
    rerun = (
        "lean-recipe-"
        + hashlib.sha256((binding + "\0INFRA_RERUN\0" + "2").encode()).hexdigest()
    )
    assert _key(adapter, rerun=2) == rerun


def test_a_derived_rebuild_is_its_own_identity_bound_to_origin_seed_and_repeat():
    adapter = _adapter_for_request()
    base = _key(adapter, HOST)
    one = _key(adapter, HOST, rebuild=f"{ORIGIN}\0{5}\0{0}")
    assert one != base
    assert one != _key(adapter, HOST, rebuild=f"{ORIGIN}\0{6}\0{0}")  # another seed
    assert one != _key(
        adapter, HOST, rebuild=f"{ORIGIN}\0{5}\0{1}"
    )  # the host-fault second build
    assert one != _key(
        adapter, HOST, rebuild=f"rtsk_{'b' * 64}\0{5}\0{0}"
    )  # another origin
    assert one == _key(
        adapter, HOST, rebuild=f"{ORIGIN}\0{5}\0{0}"
    )  # deterministic: a retry finds it


# --- the host-owned owner ------------------------------------------------------------------------------------


def test_the_host_owner_is_found_only_while_deriving_holds_the_task():
    fake = SimpleNamespace(_derived_owners={})
    holding = LeanRecipeAdapter.deriving.__wrapped__
    assert holding is not None
    with LeanRecipeAdapter.deriving(fake, "rtsk_x", HOST):
        assert fake._derived_owners == {"rtsk_x": HOST}
        assert LeanRecipeAdapter.owner(fake, "rtsk_x") == HOST
        with (
            pytest.raises(RuntimeError, match="already held"),
            LeanRecipeAdapter.deriving(fake, "rtsk_x", HOST),
        ):
            pass
    assert fake._derived_owners == {}


def test_the_host_owner_is_not_a_chain_hotkey_and_never_a_ledger_intent():
    import re

    assert not re.fullmatch(r"[1-9A-HJ-NP-Za-km-z]{47,48}", HOST)
    from pathlib import Path

    source = Path(retention.__file__).read_text(encoding="utf-8")
    body = source[source.index("def rebuild_at_seed") : source.index("def _repeat_of")]
    assert "record_recipe_task_intent" not in body and "record_catalog" not in body


# --- the evidence-only retention -----------------------------------------------------------------------------


def test_the_evidence_is_retained_and_graded_uncounted_and_nothing_is_filed(
    tmp_path, monkeypatch
):
    calls = {}
    bound = tmp_path / "evaluation.json"
    bound.write_text(json.dumps({"model_p": {"score_status": "SCORED"}}))

    def retained(adapter, task_id, **kwargs):
        calls["retained"] = (task_id, kwargs)
        return ("provider", "task", {"entry_id": "sha256:" + "5" * 64}, {}, {})

    def regrade(adapter, entry_id, **kwargs):
        calls["regrade"] = (entry_id, kwargs)
        return {
            "private_evaluation_state": "BOUND_DEVELOPMENT_ONLY",
            "private_evaluation_path": str(bound),
        }

    def forbidden(*args, **kwargs):
        raise AssertionError("a counted or filing step ran")

    monkeypatch.setattr(retention, "_retain_served_artifacts", retained)
    monkeypatch.setattr(retention, "regrade_retained_entry", regrade)
    for name in (
        "_grade_selected_pack",
        "_counted_bank_grade",
        "_retain_private_pack_binding",
        "_retain_public_synthetic_measurement",
        "_contend",
    ):
        monkeypatch.setattr(retention, name, forbidden)
    result = retention.retain_rebuild_evidence(
        SimpleNamespace(),
        "rtsk_" + "9" * 64,
        artifact_directory=tmp_path / "a",
        entry_directory=tmp_path / "e",
    )
    assert result == {
        "submission_id": "rtsk_" + "9" * 64,
        "evidence": {"model_p": {"score_status": "SCORED"}},
    }
    _entry, kwargs = calls["regrade"]
    # the uncounted regrade: a repeat index, and none of the arguments that would count or file anything
    assert kwargs["repeat_index"] == 1
    assert not {"counted", "promotion", "pool_store", "exam_se"} & set(kwargs)


@pytest.mark.parametrize(
    "answer",
    [
        {"private_evaluation_state": "UNBOUND", "private_evaluation_reason": "x"},
        {},
        {
            "private_evaluation_state": "BOUND_DEVELOPMENT_ONLY",
            "private_evaluation_path": "/nonexistent/evidence.json",
        },
    ],
)
def test_an_unbound_or_unreadable_grade_is_unavailable_not_a_grade(
    tmp_path, monkeypatch, answer
):
    monkeypatch.setattr(
        retention,
        "_retain_served_artifacts",
        lambda *a, **k: (None, None, {"entry_id": "e"}, {}, {}),
    )
    monkeypatch.setattr(retention, "regrade_retained_entry", lambda *a, **k: answer)
    with pytest.raises(retention.RetentionUnavailable):
        retention.retain_rebuild_evidence(
            SimpleNamespace(),
            ORIGIN,
            artifact_directory=tmp_path,
            entry_directory=tmp_path,
        )


# --- the orchestration -----------------------------------------------------------------------------------------


class _Provider:
    def __init__(self, owner, state=DirectTaskStateV3.QUEUED):
        self.owner = owner
        self.evaluation_pack_digest = "sha256:" + "e" * 64
        self._views, self._seeds, self.log = {}, {}, []
        self.state = state
        self._requests = {}

    def _task_id(self, request):
        return ResearchTaskId(
            "rtsk_" + hashlib.sha256(request.key.encode()).hexdigest()
        )

    def _seed_for(self, value):
        return self._seeds.get(value, 0)

    def set_rebuild_seed(self, value, seed):
        self.log.append(("seed", value, seed))
        self._seeds[value] = seed

    def start_research_task(self, request, *, measure_query=False):
        self.log.append(("start", request.key))
        value = self._task_id(request).value
        self._views[value] = True
        return SimpleNamespace(task=SimpleNamespace(state=self.state))

    def run_queued_task(self, task_id):
        self.log.append(("run", task_id.value))
        self.state = DirectTaskStateV3.SUCCEEDED

    def get_research_result(self, request):
        return SimpleNamespace(task=SimpleNamespace(state=self.state))


def _fixture(state=DirectTaskStateV3.QUEUED):
    origin_provider = _Provider("miner")
    host = _Provider(HOST, state)
    recipe = ConstructionRecipe.from_dict  # patched below
    keys = []
    origin_provider._requests[ORIGIN] = SimpleNamespace(recipe={"r": 1})

    class Adapter:
        _measure_query = False
        discovery = SimpleNamespace(
            info=SimpleNamespace(
                challenge_key=ChallengeKey("electric-motor-magnetics", "1.5")
            )
        )
        _derived_owners: ClassVar[dict] = {}

        def owner(self, submission_id):
            return (
                "miner"
                if submission_id == ORIGIN
                else self._derived_owners.get(submission_id)
            )

        def _provider(self, owner):
            return host if owner == HOST else origin_provider

        def _request(self, owner, recipe, *, evaluation_pack_digest, rebuild=None):
            assert owner == HOST and rebuild is not None
            keys.append(rebuild)
            return SimpleNamespace(key=f"{owner}|{rebuild}")

        @contextmanager
        def deriving(self, task_value, host_owner):
            self._derived_owners[task_value] = host_owner
            try:
                yield
            finally:
                self._derived_owners.pop(task_value, None)

    return Adapter(), host, keys, recipe


def test_rebuild_at_seed_runs_a_derived_host_task_and_returns_only_the_evidence(
    tmp_path, monkeypatch
):
    adapter, host, keys, _ = _fixture()
    monkeypatch.setattr(ConstructionRecipe, "from_dict", classmethod(lambda cls, d: d))
    held = {}

    def evidence(adapter_, task_value, **kwargs):
        held["owner"] = adapter_.owner(
            task_value
        )  # found only because deriving holds it
        return {"submission_id": task_value, "evidence": {"ok": 1}}

    monkeypatch.setattr(retention, "retain_rebuild_evidence", evidence)
    result = retention.rebuild_at_seed(
        adapter,
        ORIGIN,
        4242,
        host_owner=HOST,
        artifact_directory=tmp_path,
        entry_directory=tmp_path,
    )
    assert result["evidence"] == {"ok": 1} and held["owner"] == HOST
    # the seed is set BEFORE the task starts, then the task runs, in that order
    kinds = [entry[0] for entry in host.log]
    assert kinds == ["seed", "start", "run"]
    assert host.log[0][2] == 4242
    assert keys == [f"{ORIGIN}\0{4242}\0{0}"]
    assert adapter._derived_owners == {}  # released


def test_the_second_build_of_a_seed_is_a_different_task(tmp_path, monkeypatch):
    adapter, host, keys, _ = _fixture()
    monkeypatch.setattr(ConstructionRecipe, "from_dict", classmethod(lambda cls, d: d))
    monkeypatch.setattr(
        retention,
        "retain_rebuild_evidence",
        lambda a, t, **k: {"submission_id": t, "evidence": {}},
    )
    first = retention.rebuild_at_seed(
        adapter,
        ORIGIN,
        77,
        repeat=0,
        host_owner=HOST,
        artifact_directory=tmp_path,
        entry_directory=tmp_path,
    )
    host.state = DirectTaskStateV3.QUEUED
    second = retention.rebuild_at_seed(
        adapter,
        ORIGIN,
        77,
        repeat=1,
        host_owner=HOST,
        artifact_directory=tmp_path,
        entry_directory=tmp_path,
    )
    assert first["submission_id"] != second["submission_id"]
    assert keys == [f"{ORIGIN}\0{77}\0{0}", f"{ORIGIN}\0{77}\0{1}"]


def test_a_retry_reuses_the_task_and_cannot_change_its_seed(tmp_path, monkeypatch):
    adapter, host, _keys, _ = _fixture()
    monkeypatch.setattr(ConstructionRecipe, "from_dict", classmethod(lambda cls, d: d))
    monkeypatch.setattr(
        retention,
        "retain_rebuild_evidence",
        lambda a, t, **k: {"submission_id": t, "evidence": {}},
    )
    call = {
        "host_owner": HOST,
        "artifact_directory": tmp_path,
        "entry_directory": tmp_path,
    }
    retention.rebuild_at_seed(adapter, ORIGIN, 77, **call)
    retention.rebuild_at_seed(
        adapter, ORIGIN, 77, **call
    )  # the same seed again is a retry
    assert [e[0] for e in host.log].count("seed") == 1  # set once
    # another seed is another task (the label binds it); only a corrupted store could hold the wrong seed
    (value,) = host._seeds
    host._seeds[value] = 99
    with pytest.raises(retention.RetentionUnavailable, match="rebuild_seed_changed"):
        retention.rebuild_at_seed(adapter, ORIGIN, 77, **call)


@pytest.mark.parametrize(
    "state",
    [
        DirectTaskStateV3.FAILED_INFRA,
        DirectTaskStateV3.REFUSED,
        DirectTaskStateV3.UNRESOLVED,
        DirectTaskStateV3.CANCELLED,
    ],
)
def test_a_derived_task_that_did_not_succeed_is_unavailable(
    tmp_path, monkeypatch, state
):
    adapter, _host, _keys, _ = _fixture(state)
    monkeypatch.setattr(ConstructionRecipe, "from_dict", classmethod(lambda cls, d: d))
    monkeypatch.setattr(
        retention,
        "retain_rebuild_evidence",
        lambda *a, **k: pytest.fail("evidence retained from a failed task"),
    )
    with pytest.raises(retention.RetentionUnavailable, match="rebuild_task_"):
        retention.rebuild_at_seed(
            adapter,
            ORIGIN,
            5,
            host_owner=HOST,
            artifact_directory=tmp_path,
            entry_directory=tmp_path,
        )


def test_an_unknown_origin_is_unavailable(tmp_path):
    adapter, _host, _keys, _ = _fixture()
    with pytest.raises(
        retention.RetentionUnavailable, match="rebuild_origin_unavailable"
    ):
        retention.rebuild_at_seed(
            adapter,
            "rtsk_" + "f" * 64,
            5,
            host_owner=HOST,
            artifact_directory=tmp_path,
            entry_directory=tmp_path,
        )


# --- the repeat object carries the rebuild --------------------------------------------------------------------


def test_the_repeat_carries_both_builds_and_the_host_fault_pair_is_the_second(
    tmp_path, monkeypatch
):
    asked = []
    monkeypatch.setattr(
        retention,
        "rebuild_at_seed",
        lambda adapter, origin, seed, **kw: (
            asked.append((origin, seed, kw["repeat"], kw["host_owner"]))
            or {"submission_id": "d", "evidence": {}}
        ),
    )
    repeat = retention._repeat_of(
        SimpleNamespace(),
        ORIGIN,
        "sha256:" + "5" * 64,
        artifact_directory=tmp_path,
        entry_directory=tmp_path,
    )
    repeat.rebuild_at(9)
    repeat.rebuild_again_at(9)
    assert asked == [(ORIGIN, 9, 0, HOST), (ORIGIN, 9, 1, HOST)]


def test_the_average_asks_the_second_build_for_the_host_fault_pair(tmp_path):
    """`Active.decide` uses `rebuild_again_at` for the host-fault check, not the first build again."""
    from carbon.challenge_validator import bank_promotion as bp
    from carbon.challenge_validator.interface import digest
    from tests.cpu.test_crown_average_wiring import (
        CHALLENGE,
        KEY,
        Repeat,
        _active,
        _body,
        _comparator,
        _pair,
        _Pairs,
        _store,
    )

    store = _store(tmp_path)
    a = _body("a", 0.70)
    store.private_evaluation_pair = _Pairs({"a": _pair(a, None)})
    flow = bp.BankPromotion(store, registered_source_receipt_sha256=digest("pin"))
    repeat = Repeat("a", [0.70] * 10)
    second = []
    repeat.rebuild_again_at = lambda seed: (
        second.append(seed) or repeat.rebuild_at(seed)
    )
    flow.consider_private(
        "a", KEY, _comparator(), repeat=repeat, average=_active(tmp_path)
    )
    assert len(second) == 1 and CHALLENGE
