"""Crown ORIGIN REBIND (`lean_recipe_retention.rebind_origin`, the receiver's one-shot ``--rebind-origin``; Validator (c)): after
an image move the king's origin task stays on the old root, so it is rebound on this root through the receiver's own provider.

Claims: one derived request under the king's OWN hotkey, the king's exact admitted recipe, this pack, is admitted with the
rebind flag set first (a graph king carrying its retained source, checked against the submission digest) and CANCELLED at
once (never built or graded), and the pool store files the rebind; a second run is the same task and record; a non-king, an
unadmitted king, a graph king without its source or with a tampered one are refused before anything starts; the re-measure
follows a filed rebind only when its hotkey is the king's and the provider holds exactly the rebind request; the provider
admits a graph source for a flagged rebind task only (a miner's own task still cannot pass one); the flags are all-or-none.
"""

from __future__ import annotations

import hashlib
import threading
from types import SimpleNamespace

import pytest

from carbon.battery.pool_store import PoolStore
from carbon.challenge_validator import lean_recipe_retention as retention
from carbon.challenge_validator.interface import digest
from carbon.development_session import direct_graph_construction_worker as worker
from carbon.development_session.construction_recipe import ConstructionRecipe
from carbon.registry.model import ChallengeKey
from carbon.research import DirectTaskStateV3, ResearchTaskId

KING = "rtsk_" + "a" * 64
OTHER = "rtsk_" + "b" * 64
HOTKEY = "5Fking"
CHALLENGE = "f08-ribbed-bracket"
GRAPH = {
    "source": {"kind": "graph", "submission_digest": "sha256:" + "d" * 64},
    "procedure": {"steps": 7},
}
CATALOG = {"source": {"kind": "catalog", "catalog_id": "c"}, "procedure": {"steps": 7}}


class _Recipe:
    def __init__(self, document):
        self.document = document

    def to_dict(self):
        return self.document


class _Provider:
    """The king's own provider on this root: records the order of the rebind steps."""

    evaluation_pack_digest = "sha256:" + "e" * 64

    def __init__(self):
        self._views, self._requests, self.log = {}, {}, []

    def _task_id(self, request):
        return ResearchTaskId(
            "rtsk_" + hashlib.sha256(request.key.encode()).hexdigest()
        )

    def set_origin_rebind(self, task_value):
        self.log.append(("flag", task_value))

    def start_research_task(self, request, *, measure_query=False, graph_source=None):
        value = self._task_id(request).value
        self.log.append(("start", value, graph_source))
        self._requests[value] = request
        self._views[value] = SimpleNamespace(state=DirectTaskStateV3.QUEUED)

    def cancel_research_task(self, request):
        self.log.append(("cancel", request.task_id.value))
        self._views[request.task_id.value] = SimpleNamespace(
            state=DirectTaskStateV3.CANCELLED
        )


def _adapter(provider):
    class Adapter:
        _measure_query = False
        discovery = SimpleNamespace(
            info=SimpleNamespace(challenge_key=ChallengeKey(CHALLENGE, "1.7"))
        )

        def _provider(self, owner):
            assert owner == HOTKEY
            return provider

        def _request(
            self, owner, recipe, *, evaluation_pack_digest, rebuild=None, rerun=0
        ):
            return SimpleNamespace(
                key=f"{owner}|{rebuild}|{evaluation_pack_digest}",
                recipe=recipe.to_dict(),
            )

    return Adapter()


def _store(tmp_path, strategy, king=KING):
    tmp_path.mkdir(parents=True, exist_ok=True)
    store = PoolStore(tmp_path / "pool.sqlite3")
    store.admit(
        KING,
        request_digest=digest(["request", KING]),
        hotkey=HOTKEY,
        challenge=CHALLENGE,
        strategy=strategy,
        binding={"challenge": {"id": CHALLENGE}},
    )
    with store.transaction() as db:
        store._set_incumbent(db, king, "fixture", expected=None)
    return store


@pytest.fixture
def plain(monkeypatch):
    monkeypatch.setattr(
        ConstructionRecipe, "from_dict", classmethod(lambda cls, d: _Recipe(d))
    )

    def checked(recipe, raw):
        if raw != b"king-envelope":
            raise ValueError("direct_graph_source_differs")
        return raw

    monkeypatch.setattr(worker, "_checked_envelope", checked)


def test_a_graph_king_is_rebound_under_its_own_hotkey_and_cancelled_at_once(
    tmp_path, plain
):
    provider = _Provider()
    store = _store(tmp_path, GRAPH)
    out = retention.rebind_origin(
        _adapter(provider), store, submission_id=KING, source_envelope=b"king-envelope"
    )
    origin = out["origin"]
    assert out["state"] == "ORIGIN_REBOUND"
    assert provider.log == [
        ("flag", origin),
        ("start", origin, b"king-envelope"),
        ("cancel", origin),
    ]
    assert provider._views[origin].state is DirectTaskStateV3.CANCELLED
    assert provider._requests[origin].recipe == GRAPH
    assert store.origin_rebind(KING) == {"origin": origin, "hotkey": HOTKEY}
    # idempotent: the same task, no second start or cancel, the same record
    again = retention.rebind_origin(
        _adapter(provider), store, submission_id=KING, source_envelope=b"king-envelope"
    )
    assert again == out and len(provider.log) == 3


def test_a_catalog_king_needs_no_source(tmp_path, plain):
    provider = _Provider()
    out = retention.rebind_origin(
        _adapter(provider), _store(tmp_path, CATALOG), submission_id=KING
    )
    assert provider.log[1] == ("start", out["origin"], None)


@pytest.mark.parametrize(
    ("strategy", "king", "submission", "source", "code"),
    [
        (GRAPH, OTHER, KING, b"king-envelope", "rebind_not_the_sitting_king"),
        (GRAPH, KING, OTHER, b"king-envelope", "rebind_king_not_admitted"),
        (GRAPH, KING, KING, None, "rebind_graph_source_required"),
        (GRAPH, KING, KING, b"tampered", "rebind_graph_source_differs"),
    ],
)
def test_the_rebind_refuses_before_anything_starts(
    tmp_path, plain, strategy, king, submission, source, code
):
    provider = _Provider()
    store = _store(tmp_path, strategy, king=king)
    with pytest.raises(retention.RetentionUnavailable, match=code):
        retention.rebind_origin(
            _adapter(provider), store, submission_id=submission, source_envelope=source
        )
    assert provider.log == [] and store.origin_rebind(KING) is None


def test_the_remeasure_follows_a_filed_rebind_only_when_it_is_the_kings_own(
    tmp_path, plain
):
    provider = _Provider()
    store = _store(tmp_path, GRAPH)
    adapter = _adapter(provider)
    origin = retention.rebind_origin(
        adapter, store, submission_id=KING, source_envelope=b"king-envelope"
    )["origin"]
    assert (
        retention._rebound_origin(adapter, store, KING, store.origin_rebind(KING))
        == origin
    )
    with pytest.raises(
        retention.RetentionUnavailable, match="remeasure_rebind_hotkey_differs"
    ):
        retention._rebound_origin(
            adapter, store, KING, {"origin": origin, "hotkey": "5Fother"}
        )
    provider._requests[origin] = SimpleNamespace(key="changed", recipe=GRAPH)
    with pytest.raises(
        retention.RetentionUnavailable, match="remeasure_rebind_differs"
    ):
        retention._rebound_origin(adapter, store, KING, store.origin_rebind(KING))


def test_a_second_different_rebind_record_for_a_king_refuses(tmp_path):
    from carbon.battery.pool_store import StateError

    store = _store(tmp_path, GRAPH)
    store.record_origin_rebind(KING, "rtsk_" + "1" * 64, HOTKEY)
    store.record_origin_rebind(KING, "rtsk_" + "1" * 64, HOTKEY)  # the same: a no-op
    with pytest.raises(StateError, match="origin_rebind_changed"):
        store.record_origin_rebind(KING, "rtsk_" + "2" * 64, HOTKEY)


def test_the_provider_admits_a_graph_source_only_for_a_flagged_rebind_task():
    from carbon.development_session.research_tasks import DirectDevelopmentTasksV3

    provider = object.__new__(DirectDevelopmentTasksV3)
    provider.owner, provider._entropy, provider._lock = (
        HOTKEY,
        b"\x07" * 32,
        threading.RLock(),
    )
    provider._task_seeds, provider._origin_rebinds, provider._views = {}, set(), {}
    request = SimpleNamespace(recipe=GRAPH)
    provider._task_id = lambda r: ResearchTaskId("rtsk_" + "9" * 64)
    assert provider._derived_rebuild(request) is False  # a miner's own task
    provider.set_origin_rebind("rtsk_" + "9" * 64)
    assert provider._derived_rebuild(request) is True
    provider._views["rtsk_" + "9" * 64] = object()
    with pytest.raises(ValueError, match="before the task starts"):
        provider.set_origin_rebind("rtsk_" + "9" * 64)


@pytest.mark.parametrize(
    "argv",
    [
        ["--rebind-origin", KING],
        ["--rebind-source", "x.json"],
        ["--rebind-origin", KING, "--remeasure-king", KING],
    ],
)
def test_the_rebind_flags_are_all_or_none(tmp_path, argv, monkeypatch):
    from carbon.challenge_validator import cpu_pin, direct_receiver

    monkeypatch.setattr(cpu_pin, "require", lambda: None)
    with pytest.raises(SystemExit) as stopped:
        direct_receiver.main(["--config", str(tmp_path / "c.json"), *argv])
    assert stopped.value.code == 2
