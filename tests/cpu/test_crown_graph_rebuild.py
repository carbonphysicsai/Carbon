"""The crown average's rebuild of a GRAPH recipe (receiver seam B, the Validator's design ruled for crown_average).

Claims: the host-owned derived rebuild takes its graph source from the ORIGIN task's retained envelope (the host owner
has no workspace), so a graph king and a graph challenger both average through `crown_average.run_average` at
non-zero seeds; an origin whose retained source cannot be read is unavailable and starts nothing; the provider accepts
``graph_source`` only for the host owner's task with a validator-set rebuild seed (never a miner's task, never an
unseeded one, never a non-bytes or a bundle source), checks the bytes against the recipe's submission digest like any
intake (a tampered envelope is refused and nothing is retained), and never reads a workspace for them; the official
seed 0 stays refused by `set_rebuild_seed`.
"""

from __future__ import annotations

import hashlib
import threading
from contextlib import contextmanager
from types import SimpleNamespace
from typing import ClassVar

import pytest

from carbon.challenge_validator import bank_promotion as bp
from carbon.challenge_validator import crown_average as ca
from carbon.challenge_validator import lean_recipe_retention as retention
from carbon.development_session.construction_recipe import ConstructionRecipe
from carbon.registry.model import ChallengeKey
from carbon.research import (
    DirectStartTaskRequestV3,
    DirectTaskStateV3,
    ResearchTaskId,
)
from carbon.research.errors import ResearchServiceErrorCode
from carbon.research.lifecycle import ResearchTaskProviderError

HOST = ca.HOST_OWNER
KING = "rtsk_" + "a" * 64
CHALLENGER = "rtsk_" + "b" * 64
GRAPH = {"source": {"kind": "graph", "submission_digest": "sha256:" + "0" * 64}}
TOTALS = {KING: 0.70, CHALLENGER: 0.80}


# --- the orchestration (behind fakes, like test_crown_rebuild_evidence) ------------------------------------------


class _Origin:
    """A miner's provider holding its retained graph source (`_source_envelope`)."""

    def __init__(self, sources):
        self.sources = sources
        self._requests = {
            origin: SimpleNamespace(recipe={**GRAPH, "origin": origin})
            for origin in sources
        }
        self.read = []

    def _source_envelope(self, identity, recipe):
        self.read.append(identity)
        if self.sources[identity] is None:
            raise ValueError("retained direct graph source differs")
        return self.sources[identity]


class _Host:
    """The host owner's provider: no workspace, so a graph task must be GIVEN its source."""

    owner = HOST
    evaluation_pack_digest = "sha256:" + "e" * 64

    def __init__(self):
        self._views, self._seeds, self.started = {}, {}, {}

    def _task_id(self, request):
        return ResearchTaskId(
            "rtsk_" + hashlib.sha256(request.key.encode()).hexdigest()
        )

    def _seed_for(self, value):
        return self._seeds.get(value, 0)

    def set_rebuild_seed(self, value, seed):
        assert seed != 0
        self._seeds[value] = seed

    def start_research_task(self, request, *, measure_query=False, graph_source=None):
        if graph_source is None:
            raise AssertionError("a graph rebuild reached the host without its source")
        value = self._task_id(request).value
        self._views[value] = True
        self.started[value] = (request.origin, self._seeds[value], graph_source)
        return SimpleNamespace(task=SimpleNamespace(state=DirectTaskStateV3.QUEUED))

    def run_queued_task(self, task_id):
        pass

    def get_research_result(self, request):
        return SimpleNamespace(task=SimpleNamespace(state=DirectTaskStateV3.SUCCEEDED))


def _adapter(origin, host):
    class Adapter:
        _measure_query = False
        discovery = SimpleNamespace(
            info=SimpleNamespace(
                challenge_key=ChallengeKey("ribbed-bracket-static-response", "1.4")
            )
        )
        _derived_owners: ClassVar[dict] = {}

        def owner(self, submission_id):
            if submission_id in origin.sources:
                return "miner"
            return self._derived_owners.get(submission_id)

        def _provider(self, owner):
            return host if owner == HOST else origin

        def _request(
            self, owner, recipe, *, evaluation_pack_digest, rebuild=None, rerun=0
        ):
            assert owner == HOST and rebuild is not None
            return SimpleNamespace(
                key=f"{owner}|{rebuild}|{rerun}", origin=recipe["origin"]
            )

        def _ended_on_infra(self, hotkey, task_id, provider):
            return False

        @contextmanager
        def deriving(self, task_value, host_owner):
            self._derived_owners[task_value] = host_owner
            try:
                yield
            finally:
                self._derived_owners.pop(task_value, None)

    return Adapter()


def _graded(host):
    def evidence(adapter, task_value, **kwargs):
        origin, _seed, _source = host.started[task_value]
        return {
            "submission_id": task_value,
            "evidence": {
                "model_p": {"score_status": bp.SCORED, "total_score": TOTALS[origin]}
            },
        }

    return evidence


class _Rule:
    seed_range = 2**31 - 1

    def n_for(self, challenge_id):
        return 3

    def margin_for(self, challenge_id):
        return 0.01


def test_a_graph_king_and_a_graph_challenger_average_from_their_retained_sources(
    tmp_path, monkeypatch
):
    monkeypatch.setattr(ConstructionRecipe, "from_dict", classmethod(lambda cls, d: d))
    origin = _Origin({KING: b"king-envelope", CHALLENGER: b"challenger-envelope"})
    host = _Host()
    adapter = _adapter(origin, host)
    monkeypatch.setattr(retention, "retain_rebuild_evidence", _graded(host))
    custody = {"artifact_directory": tmp_path, "entry_directory": tmp_path}

    def average(model, king_mean):
        repeat = retention._repeat_of(adapter, model, "sha256:" + "5" * 64, **custody)
        return ca.run_average(
            key=bytes(range(64)),
            challenge_id="ribbed-bracket-static-response",
            submission_id=model,
            rule=_Rule(),
            rebuild=repeat.rebuild_at,
            rebuild_again=repeat.rebuild_again_at,
            king_mean=king_mean,
            baseline_floor=0.5,
            tolerance=0.03,
        )

    king = average(KING, None)
    assert (king["outcome"], king["private"]["mean"]) == (
        bp.FIRST_INCUMBENT,
        pytest.approx(0.70),
    )
    challenger = average(CHALLENGER, king["private"]["mean"])
    assert challenger["outcome"] == bp.CHALLENGER
    # every derived build got ITS origin's retained bytes, at a non-zero validator seed (3 seeds + the host-fault pair)
    by_origin = {}
    for model, seed, source in host.started.values():
        by_origin.setdefault(model, []).append((seed, source))
        assert seed != 0
    assert {m: len(v) for m, v in by_origin.items()} == {KING: 4, CHALLENGER: 4}
    assert {s for _seed, s in by_origin[KING]} == {b"king-envelope"}
    assert {s for _seed, s in by_origin[CHALLENGER]} == {b"challenger-envelope"}
    assert set(origin.read) == {KING, CHALLENGER}


def test_an_unreadable_retained_source_is_unavailable_and_starts_nothing(
    tmp_path, monkeypatch
):
    monkeypatch.setattr(ConstructionRecipe, "from_dict", classmethod(lambda cls, d: d))
    origin = _Origin({KING: None})
    host = _Host()
    adapter = _adapter(origin, host)
    with pytest.raises(
        retention.RetentionUnavailable, match="rebuild_graph_source_unavailable"
    ):
        retention.rebuild_at_seed(
            adapter,
            KING,
            77,
            host_owner=HOST,
            artifact_directory=tmp_path,
            entry_directory=tmp_path,
        )
    assert host.started == {} and host._seeds == {}


# --- the provider's own refusal (the real start_research_task) ----------------------------------------------------


class _Admitted(Exception):
    """Raised where the real provider would retain the admitted bytes: the guard and the envelope check passed."""


def _provider(owner, recipe, *, seeded=True, tmp_path=None):
    from carbon.development_session.research_tasks import DirectDevelopmentTasksV3

    provider = object.__new__(DirectDevelopmentTasksV3)
    provider.owner = owner
    provider._entropy = b"\x07" * 32
    provider._lock = threading.RLock()
    provider._task_seeds = {}
    provider._idempotency, provider._views, provider._requests = {}, {}, {}
    provider._measured_tasks = set()
    provider.image_resolver = None
    provider.ledger = SimpleNamespace(root=tmp_path)
    provider.retained = []
    provider._bindings = lambda request: None
    provider._verify_images = lambda: None
    provider._resolved_image = lambda request: None

    def retain(identity, source_envelope):
        provider.retained.append(source_envelope)
        raise _Admitted

    provider._retain_source = retain
    request = DirectStartTaskRequestV3(
        ChallengeKey(
            recipe.to_dict()["challenge"]["id"],
            recipe.to_dict()["challenge"]["version"],
        ),
        "lean-recipe-" + "1" * 64,
        recipe.to_dict(),
        *("sha256:" + str(i) * 64 for i in range(2, 10)),
    )
    if seeded:
        provider._task_seeds[provider._task_id(request).value] = 4242
    return provider, request


@pytest.fixture
def graph_case():
    pytest.importorskip("jax")
    from test_f08_f02_graph_adapters import SERVED, _case

    from carbon.development_session.profile import canonical

    key = next(k for k in SERVED if k[1] == "1.4")
    recipe, raw_manifest, files, staging = _case(key, {"steps": 4})
    _other, other_manifest, other_files, _ = _case(key, {"steps": 4, "batch_size": 4})
    return (
        recipe,
        canonical(staging.envelope(raw_manifest, files)),
        canonical(staging.envelope(other_manifest, other_files)),
    )


def _code(call):
    with pytest.raises(ResearchTaskProviderError) as refused:
        call()
    return refused.value.code


@pytest.fixture
def no_workspace(monkeypatch):
    from carbon.development_session import construction_recipe

    def forbidden(*args, **kwargs):
        raise AssertionError("a derived graph rebuild read a workspace")

    monkeypatch.setattr(construction_recipe, "graph_envelope_from_workspace", forbidden)


def test_the_host_owners_seeded_task_admits_its_origins_bytes_without_a_workspace(
    graph_case, no_workspace, tmp_path
):
    recipe, envelope, _ = graph_case
    provider, request = _provider(HOST, recipe, tmp_path=tmp_path)
    with pytest.raises(_Admitted):
        provider.start_research_task(request, graph_source=envelope)
    assert provider.retained == [envelope]


def test_a_tampered_envelope_is_refused_and_nothing_is_retained(
    graph_case, no_workspace, tmp_path
):
    recipe, envelope, another = graph_case
    provider, request = _provider(HOST, recipe, tmp_path=tmp_path)
    flipped = bytearray(envelope)
    flipped[len(flipped) // 2] ^= 1
    for tampered in (bytes(flipped), another, envelope + b" ", b"{}"):
        assert (
            _code(
                lambda tampered=tampered: provider.start_research_task(
                    request, graph_source=tampered
                )
            )
            is ResearchServiceErrorCode.REFERENCE_MISMATCH
        )
    assert provider.retained == []


def test_a_miner_task_or_an_unseeded_task_cannot_pass_a_graph_source(
    graph_case, no_workspace, tmp_path
):
    recipe, envelope, _ = graph_case
    for provider, request in (
        _provider(
            "5Fminer", recipe, tmp_path=tmp_path
        ),  # a miner's own task, even with a seed
        _provider(
            HOST, recipe, seeded=False, tmp_path=tmp_path
        ),  # not a derived rebuild
    ):
        assert (
            _code(
                lambda provider=provider, request=request: provider.start_research_task(
                    request, graph_source=envelope
                )
            )
            is ResearchServiceErrorCode.REQUEST_TYPE_INVALID
        )
        assert provider.retained == []
    provider, request = _provider(HOST, recipe, tmp_path=tmp_path)
    assert (
        _code(
            lambda: provider.start_research_task(
                request, graph_source=envelope.decode()
            )
        )
        is ResearchServiceErrorCode.REQUEST_TYPE_INVALID
    )


def test_a_bundle_recipe_cannot_pass_a_graph_source(tmp_path):
    bundle = SimpleNamespace(
        to_dict=lambda: {
            "challenge": {"id": "ribbed-bracket-static-response", "version": "1.4"},
            "source": {"kind": "bundle"},
        }
    )
    provider, request = _provider(HOST, bundle, tmp_path=tmp_path)
    assert (
        _code(lambda: provider.start_research_task(request, graph_source=b"x"))
        is ResearchServiceErrorCode.REQUEST_TYPE_INVALID
    )


def test_the_official_seed_stays_refused():
    from carbon.development_session.research_tasks import DirectDevelopmentTasksV3

    provider = object.__new__(DirectDevelopmentTasksV3)
    provider._views, provider._task_seeds = {}, {}
    with pytest.raises(ValueError, match="rebuild seed invalid"):
        provider.set_rebuild_seed("rtsk_" + "c" * 64, 0)
