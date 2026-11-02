"""INCUMBENT RE-MEASURE (`crown_average.Active.measure_incumbent`, `lean_recipe_retention.remeasure_incumbent_pack`, the
receiver's one-shot ``--remeasure-king``): the sitting king's N-rebuild mean is filed before the averaged rule is switched on,
so no crown pauses as KING_UNMEASURED.

Claims: the king is rebuilt at the rule's N seeds for its own submission (the same `run_average` a challenger runs; never seed
0), as host-owned derived rebuilds; a GRAPH king's rebuilds carry its retained source (seam B) and a CATALOG king's carry none;
its mean is filed and `screening` then compares mean with mean; an infrastructure fault mid-run is retried and the record is
the same as a clean run's, a run whose rebuilds all fail files nothing and a later run measures cleanly; a re-run that does
not reproduce is FAILED_INFRA, never a second record; a seed-fragile king is filed without a mean (still unmeasured); an
entry that is not the sitting king is refused; nothing private is returned; the operator flags are all-or-none.
"""

from __future__ import annotations

import hashlib
from types import SimpleNamespace

import pytest

from carbon.battery.pool_store import PoolStore, StateError
from carbon.challenge_validator import bank_promotion as bp
from carbon.challenge_validator import crown_average as ca
from carbon.challenge_validator import lean_recipe_retention as retention
from carbon.challenge_validator.interface import digest
from carbon.development_session.construction_recipe import ConstructionRecipe
from carbon.research import DirectTaskStateV3, ResearchTaskId

CHALLENGE = "electric-motor-magnetics"
KEY = digest("evaluation context")
CROWN_KEY = bytes(range(64))
N = 10
KING = "rtsk_" + "a" * 64
OTHER = "rtsk_" + "b" * 64


class _Rule:
    seed_range = 2**31 - 1

    def n_for(self, challenge_id):
        return N

    def margin_for(self, challenge_id):
        return 0.0035

    def margin_digest_for(self, challenge_id):
        return digest("margin")


def _comparator():
    return {
        "challenge": CHALLENGE,
        "rebuild_noise": {"value": 0.03, "measurement_digest": digest("noise")},
        "baseline_total": 0.5,
    }


def _body(total, status=bp.SCORED):
    return {"evidence": {"model_p": {"score_status": status, "total_score": total}}}


class _Repeat:
    """``rebuild_at(seed)`` -> a grade body; ``totals`` maps a call index to a total (default 0.70), ``fail`` the call
    indices that raise (an infrastructure fault)."""

    def __init__(self, totals=None, fail=(), status=bp.SCORED):
        self.calls, self.totals, self.fail, self.status = (
            [],
            totals or {},
            set(fail),
            status,
        )

    def rebuild_at(self, seed):
        index = len(self.calls)
        self.calls.append(seed)
        if index in self.fail:
            raise OSError("construction lane down")
        return _body(self.totals.get(index, 0.70), self.status)

    def rebuild_again_at(self, seed):
        return _body(0.70, self.status)


def _store(tmp_path, king=KING):
    tmp_path.mkdir(parents=True, exist_ok=True)
    store = PoolStore(tmp_path / "pool.sqlite3")
    with store.transaction() as db:
        store._set_incumbent(db, king, "fixture", expected=None)
    return store


def _active():
    return ca.Active(_Rule(), CROWN_KEY)


def test_the_king_is_measured_at_the_rules_seeds_and_screening_then_compares_means(
    tmp_path,
):
    store, repeat = _store(tmp_path), _Repeat()
    out = _active().measure_incumbent(store, KING, KEY, _comparator(), repeat)
    assert out == {"outcome": ca.KING_MEASURED, "reason": ca.FIRST_BEATS_BASELINE}
    assert set(out) == {"outcome", "reason"}  # no seed, total or mean is returned
    assert repeat.calls == ca.derive_seeds(
        CROWN_KEY, CHALLENGE, KING, N, _Rule.seed_range
    )
    assert 0 not in repeat.calls
    assert store.crown_mean(KING) == pytest.approx(0.70)
    # with the king's mean filed, the screening comparison reads the MEAN, not the single grade
    pair = {
        "candidate": {"submission_id": OTHER, **_body(0.71)},
        "incumbent": {"submission_id": KING, **_body(0.90)},
    }
    screened_pair, _ = _active().screening(store, pair, _comparator())
    assert screened_pair["incumbent"]["evidence"]["model_p"][
        "total_score"
    ] == pytest.approx(0.70)


def test_without_the_re_measure_the_king_is_unmeasured(tmp_path):
    store = _store(tmp_path)
    pair = {"candidate": None, "incumbent": {"submission_id": KING, **_body(0.90)}}
    with pytest.raises(ca.CrownAverageUnavailable, match=ca.KING_UNMEASURED):
        _active().screening(store, pair, _comparator())


def test_a_mid_run_infra_fault_is_retried_and_files_the_same_record_as_a_clean_run(
    tmp_path,
):
    clean = _store(tmp_path / "clean")
    _active().measure_incumbent(clean, KING, KEY, _comparator(), _Repeat())
    faulted = _store(tmp_path / "faulted")
    repeat = _Repeat(fail={4})  # the fifth rebuild fails once, then its retry runs
    out = _active().measure_incumbent(faulted, KING, KEY, _comparator(), repeat)
    assert out["outcome"] == ca.KING_MEASURED
    assert repeat.calls[4] == repeat.calls[5]  # the same seed again
    assert faulted.crown_mean(KING) == clean.crown_mean(KING)


def test_a_run_whose_rebuilds_all_fail_files_nothing_and_a_later_run_measures(tmp_path):
    store = _store(tmp_path)
    down = _Repeat(fail=set(range(100)))
    assert _active().measure_incumbent(store, KING, KEY, _comparator(), down) == {
        "outcome": bp.UNAVAILABLE,
        "reason": ca.REBUILD_UNAVAILABLE,
    }
    assert store.crown_mean(KING) is None
    out = _active().measure_incumbent(store, KING, KEY, _comparator(), _Repeat())
    assert out["outcome"] == ca.KING_MEASURED and store.crown_mean(
        KING
    ) == pytest.approx(0.70)


def test_a_re_run_that_does_not_reproduce_is_infra_never_a_second_record(tmp_path):
    store = _store(tmp_path)
    _active().measure_incumbent(store, KING, KEY, _comparator(), _Repeat())
    drifted = _Repeat(totals={0: 0.71})
    assert _active().measure_incumbent(store, KING, KEY, _comparator(), drifted) == {
        "outcome": bp.FAILED_INFRA,
        "reason": "crown_average_record_changed",
    }
    assert store.crown_mean(KING) == pytest.approx(0.70)


def test_a_seed_fragile_king_is_filed_without_a_mean(tmp_path):
    store = _store(tmp_path)
    out = _active().measure_incumbent(
        store, KING, KEY, _comparator(), _Repeat(status="GATE_FAILED")
    )
    assert out == {"outcome": ca.KING_UNSTABLE, "reason": ca.UNSTABLE}
    assert (
        store.crown_mean(KING) is None
    )  # still unmeasured: the operator decides (keep-with-flag)


def test_an_entry_that_is_not_the_sitting_king_is_refused(tmp_path):
    store = _store(tmp_path)
    repeat = _Repeat()
    with pytest.raises(ca.CrownAverageUnavailable, match=ca.NOT_THE_KING):
        _active().measure_incumbent(store, OTHER, KEY, _comparator(), repeat)
    empty = PoolStore(tmp_path / "empty.sqlite3")
    with pytest.raises(ca.CrownAverageUnavailable, match=ca.NOT_THE_KING):
        _active().measure_incumbent(empty, KING, KEY, _comparator(), repeat)
    assert repeat.calls == []


# --- through the receiver's rebuild path: a graph king and a catalog king -----------------------------------------


class _Origin:
    def __init__(self, kind):
        source = {"kind": kind}
        self._requests = {KING: SimpleNamespace(recipe={"source": source})}
        self.read = []

    def _source_envelope(self, identity, recipe):
        self.read.append(identity)
        return b"retained-king-envelope"


class _Host:
    owner = ca.HOST_OWNER
    evaluation_pack_digest = "sha256:" + "e" * 64

    def __init__(self):
        self._views, self._seeds, self.started = {}, {}, []

    def _task_id(self, request):
        return ResearchTaskId(
            "rtsk_" + hashlib.sha256(request.key.encode()).hexdigest()
        )

    def _seed_for(self, value):
        return self._seeds.get(value, 0)

    def set_rebuild_seed(self, value, seed):
        self._seeds[value] = seed

    def start_research_task(self, request, *, measure_query=False, **graph):
        value = self._task_id(request).value
        self._views[value] = True
        self.started.append((self._seeds[value], graph.get("graph_source")))
        return SimpleNamespace(task=SimpleNamespace(state=DirectTaskStateV3.QUEUED))

    def run_queued_task(self, task_id):
        pass

    def get_research_result(self, request):
        return SimpleNamespace(task=SimpleNamespace(state=DirectTaskStateV3.SUCCEEDED))


def _adapter(origin, host):
    derived = {}

    class Adapter:
        _measure_query = False
        _derived_owners = derived

        def owner(self, submission_id):
            return "miner" if submission_id == KING else derived.get(submission_id)

        def _provider(self, owner):
            return host if owner == ca.HOST_OWNER else origin

        def _request(
            self, owner, recipe, *, evaluation_pack_digest, rebuild=None, rerun=0
        ):
            return SimpleNamespace(key=f"{owner}|{rebuild}|{rerun}")

        def _ended_on_infra(self, hotkey, task_id, provider):
            return False

        def deriving(self, task_value, host_owner):
            import contextlib

            @contextlib.contextmanager
            def held():
                derived[task_value] = host_owner
                try:
                    yield
                finally:
                    derived.pop(task_value, None)

            return held()

    return Adapter()


@pytest.mark.parametrize("kind", ["graph", "catalog"])
def test_a_graph_king_and_a_catalog_king_are_re_measured_through_the_rebuild_path(
    tmp_path, monkeypatch, kind
):
    monkeypatch.setattr(ConstructionRecipe, "from_dict", classmethod(lambda cls, d: d))
    monkeypatch.setattr(
        retention,
        "retain_rebuild_evidence",
        lambda adapter, task_value, **kwargs: {
            "submission_id": task_value,
            "evidence": {"model_p": {"score_status": bp.SCORED, "total_score": 0.72}},
        },
    )
    origin, host = _Origin(kind), _Host()
    repeat = retention._repeat_of(
        _adapter(origin, host), KING, "sha256:" + "5" * 64,
        artifact_directory=tmp_path, entry_directory=tmp_path,
    )  # fmt: skip
    store = _store(tmp_path)
    out = _active().measure_incumbent(store, KING, KEY, _comparator(), repeat)
    assert out["outcome"] == ca.KING_MEASURED
    assert store.crown_mean(KING) == pytest.approx(0.72)
    seeds = [seed for seed, _source in host.started]
    assert (
        len(host.started) == N + 1 and 0 not in seeds
    )  # N rebuilds + the host-fault second build
    sources = {source for _seed, source in host.started}
    assert sources == ({b"retained-king-envelope"} if kind == "graph" else {None})
    assert (origin.read != []) == (kind == "graph")


def test_the_retention_entry_needs_the_installed_rule_and_a_pool_store(
    tmp_path, monkeypatch
):
    monkeypatch.setattr(ca, "ACTIVE", None)
    call = {
        "submission_id": KING,
        "evaluation_key": KEY,
        "entry_id": "sha256:" + "5" * 64,
        "artifact_directory": tmp_path,
        "entry_directory": tmp_path,
    }
    with pytest.raises(
        retention.RetentionUnavailable, match="crown_average_not_installed"
    ):
        retention.remeasure_incumbent_pack(SimpleNamespace(), _store(tmp_path), **call)
    monkeypatch.setattr(ca, "ACTIVE", _active())
    with pytest.raises(
        retention.RetentionUnavailable, match="remeasure_pool_store_required"
    ):
        retention.remeasure_incumbent_pack(SimpleNamespace(), None, **call)


@pytest.mark.parametrize(
    "argv",
    [
        ["--remeasure-king", KING],
        ["--remeasure-king", KING, "--evaluation-key", KEY, "--remeasure-entry", "e"],
        ["--evaluation-key", KEY],
        ["--remeasure-king", KING, "--regrade-entry", "e"],
    ],
)
def test_the_operator_flags_are_all_or_none(tmp_path, argv, monkeypatch):
    from carbon.challenge_validator import cpu_pin, direct_receiver

    monkeypatch.setattr(cpu_pin, "require", lambda: None)
    with pytest.raises(SystemExit) as stopped:
        direct_receiver.main(["--config", str(tmp_path / "c.json"), *argv])
    assert stopped.value.code == 2


def test_state_error_carries_the_changed_code():
    assert StateError("crown_average_changed").code == "crown_average_changed"
