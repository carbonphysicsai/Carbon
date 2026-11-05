"""Route (b) (Carbon Validator 5 Nov 10:53 + 10:57): a king who predates the judge image is REBUILT from his admitted
recipe on it, graded like a challenger, and filed under a DERIVED pool row linked to him.

Claims:
- the link (`king_rebuild.v1`) is write-once and king-only: the recipe and hotkey must be the king's admission;
- the incumbent lookup resolves the king's evaluation on the current key through the link, under HIS submission id;
- his standing is the rebuilt grade, while his own models row and old evaluation stay byte-identical;
- a derived ``krb_`` row can never enter contention (recontend files ``rtsk_`` tasks only);
- `rebuild_king` builds his own recipe at the official seed, host-owned, grades it uncounted on the active pack, files
  it under the derived row and links it only once it is bound;
- the upkeep rebuilds a king whose parent moved, stops his contention with ONE owner line on a capability gap, and
  retries anything else.

Real pool store and real private evaluations (synthetic graph case); the build and the grade are stand-ins.
"""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest
from test_bank_private_evaluation import admitted, inputs
from test_score_lab_private_evaluation_evidence import _graph_case

from carbon.battery.pool_store import PoolStore, StateError
from carbon.challenge_validator import bank_promotion as bp
from carbon.challenge_validator import king_upkeep, recontend
from carbon.challenge_validator import lean_recipe_retention as retention
from carbon.challenge_validator.interface import digest

JUDGE = "sha256:" + "5" * 64


@pytest.fixture
def door(tmp_path):
    """The king graded only on the OLD evaluation version; a challenger on the NEW one (the 5 Nov state)."""
    case = _graph_case(tmp_path)
    store = PoolStore(tmp_path / "private.sqlite", clock=lambda: 123.0)
    for model in ("king", "challenger"):
        admitted(store, case, model)
    store.set_incumbent("king", "historical fixture")
    old_pin, old_args = inputs(case)
    bp.BankPromotion(store, registered_source_receipt_sha256=old_pin).retain_private(
        "king", **old_args
    )
    pin, args = inputs(case, version="synthetic-eval-v2")
    flow = bp.BankPromotion(store, registered_source_receipt_sha256=pin)
    key = flow.retain_private("challenger", **args)["evaluation_key"]
    return SimpleNamespace(
        case=case, store=store, flow=flow, args=args, key=key, pin=pin
    )


def _rebuild_row(door, derived=None):
    """What `rebuild_king` files: the derived row (king's hotkey, request, recipe, binding; the rebuilt state) and its
    evaluation on the challengers' key."""
    store = door.store
    king = store.submission("king")
    derived = derived or retention.king_rebuild_id("king", JUDGE, door.key)
    retention._admit_king_rebuild(
        store,
        derived,
        king,
        {"state.npz": door.case["originals"]["build/output/state.npz"]},
        "rtsk_" + "d" * 64,
        JUDGE,
    )
    door.flow.retain_private(derived, **door.args)
    return derived, king


def _link(door, derived, king, **changes):
    door.store.record_king_rebuild(
        "king",
        derived,
        **{
            "judge_image": JUDGE,
            "evaluation_key": door.key,
            "recipe_digest": king["binding"]["recipe_digest"],
            "hotkey": king["hotkey"],
            **changes,
        },
    )


def _models_row(store, model):
    with store.db() as db:
        return db.execute("SELECT * FROM models WHERE model_id=?", (model,)).fetchone()


def _evaluations_of(store, model):
    return [b for b in store.private_evaluation_bodies() if b["submission_id"] == model]


def test_before_the_rebuild_the_king_cannot_be_met_on_the_new_key(door):
    with pytest.raises(StateError, match="incumbent_evaluation_required"):
        door.flow.private_pair("challenger", door.key)


def test_the_rebuilt_evaluation_is_the_kings_through_the_link_and_history_is_untouched(
    door,
):
    store = door.store
    before_row, before_evals = _models_row(store, "king"), _evaluations_of(
        store, "king"
    )
    derived, king = _rebuild_row(door)
    with pytest.raises(StateError, match="incumbent_evaluation_required"):
        door.flow.private_pair(
            "challenger", door.key
        )  # no link yet: never resolved by guess
    _link(door, derived, king)
    pair = door.flow.private_pair("challenger", door.key)
    assert pair["expected_incumbent"] == "king"
    assert (
        pair["incumbent"]["submission_id"] == "king"
    )  # the contention identity stays the king's
    assert pair["incumbent"]["rebuilt_as"] == derived
    assert pair["incumbent"]["evaluation_key"] == door.key
    # his own models row and old evaluations are byte-identical: a new measurement, not a rescore (invariant 10)
    assert _models_row(store, "king") == before_row
    assert _evaluations_of(store, "king") == before_evals
    record = {
        "submission_id": "challenger",
        "evaluation_key": door.key,
        "pin": door.pin,
    }
    assert not store.awaits_incumbent_regrade(record)


def test_the_kings_standing_is_his_newest_grade_which_is_the_rebuilt_one(tmp_path):
    """Ruling (4): the rebuilt score is his standing, up or down; the king page reads it."""
    store = PoolStore(tmp_path / "s.sqlite3")

    def evaluation(op, sid, total):
        body = {
            "submission_id": sid,
            "owner": {"hotkey": "5K", "request_digest": "r"},
            "evidence": {
                "model_p": {
                    "score_status": "SCORED_DEVELOPMENT_CANDIDATE",
                    "total_score": total,
                }
            },
        }
        with store.transaction() as db:
            db.execute(
                "INSERT INTO operations VALUES(?,?,?,?)",
                (
                    op,
                    "private_evaluation.v1",
                    "BOUND_DEVELOPMENT_ONLY",
                    json.dumps(body),
                ),
            )

    evaluation("e1", "king", 0.80)  # crowned on the old exam
    assert store.incumbent_standing("king")["total"] == pytest.approx(0.80)
    evaluation("e2", "krb_x", 0.61)  # an unlinked derived row is not his
    assert store.incumbent_standing("king")["total"] == pytest.approx(0.80)
    with store.transaction() as db:
        db.execute(
            "INSERT INTO operations VALUES(?,?,?,?)",
            (
                "l1",
                "king_rebuild.v1",
                "RECORDED",
                json.dumps(
                    {"king_submission_id": "king", "derived_submission_id": "krb_x"}
                ),
            ),
        )
    assert store.incumbent_standing("king")["total"] == pytest.approx(
        0.61
    )  # down: the rebuilt grade stands


def test_the_link_is_write_once_and_king_only(door):
    derived, king = _rebuild_row(door)
    _link(door, derived, king)
    _link(door, derived, king)  # the same record again: a no-op
    with pytest.raises(StateError, match="king_rebuild_changed"):
        _link(door, derived, king, judge_image="sha256:" + "6" * 64)
    with pytest.raises(StateError, match="king_rebuild_mismatch"):
        _link(
            door,
            derived,
            king,
            evaluation_key=digest("other key"),
            hotkey="fixture-someone",
        )
    with pytest.raises(StateError, match="king_rebuild_mismatch"):
        _link(
            door,
            derived,
            king,
            evaluation_key=digest("other key"),
            recipe_digest=digest("another recipe"),
        )
    with pytest.raises(StateError, match="king_rebuild_invalid"):
        _link(door, "rtsk_" + "e" * 64, king, evaluation_key=digest("third key"))


def test_a_derived_row_never_enters_contention(door, tmp_path):
    derived, king = _rebuild_row(door)
    _link(door, derived, king)
    root = tmp_path / "state"
    for name in ("artifacts", "entries"):
        (root / "auto-grade" / name).mkdir(parents=True, mode=0o700)
    exam = door.args["score_pack"][
        "pack_digest"
    ]  # any digest: the derived row is filtered before the exam
    planned = recontend.plan(root, door.store.path, exam)
    assert all(not i["submission_id"].startswith("krb_") for i in planned["file"])
    assert derived not in planned["skipped"]


def test_the_derived_id_is_deterministic_and_never_a_task_id():
    one = retention.king_rebuild_id("rtsk_k", JUDGE, digest("key"))
    assert one == retention.king_rebuild_id("rtsk_k", JUDGE, digest("key"))
    assert one.startswith("krb_") and not one.startswith("rtsk_")
    assert one != retention.king_rebuild_id("rtsk_k", JUDGE, digest("other key"))


# --- rebuild_king's wiring ------------------------------------------------------------------------------------------


@pytest.fixture
def wired(door, monkeypatch, tmp_path):
    calls = {}
    adapter = SimpleNamespace(
        owner=lambda sid: "fixture-king",
        ledger=SimpleNamespace(admitted_owner=lambda sid: None),
        _provider=lambda owner: SimpleNamespace(
            inference_image=SimpleNamespace(image_id=JUDGE)
        ),
    )
    import contextlib

    adapter.deriving = lambda task, owner: contextlib.nullcontext()

    def build(adapter_, origin, seed, *, rebuild, host_owner, recipe, graph_source):
        calls["build"] = (origin, seed, rebuild, host_owner)
        calls["built"] = (recipe, graph_source)
        return "rtsk_" + "d" * 64

    def origin(adapter_, base, entries, entry_id, *, incumbent):
        calls["origin"] = (entry_id, incumbent)
        retained = SimpleNamespace(
            digest=calls.get(
                "retained", door.store.submission("king")["binding"]["recipe_digest"]
            ),
            to_dict=lambda: {"source": {"kind": "graph"}},
        )
        files = {"source-envelope.json": b"the king's retained envelope"}
        return None, calls.get("origin_id", "king"), None, None, files, retained

    def retain(adapter_, task_id, *, artifact_directory, entry_directory):
        entry = tmp_path / "entry.json"
        entry.write_text(
            json.dumps(
                {
                    "recipe_digest": calls.get(
                        "recipe",
                        door.store.submission("king")["binding"]["recipe_digest"],
                    ),
                    "challenge": door.case["entry"]["challenge"],
                    "challenge_version": door.case["entry"]["challenge_version"],
                }
            )
        )
        return (
            None,
            None,
            {"entry_id": digest("rebuilt entry"), "entry_path": entry},
            {"state.npz": door.case["originals"]["build/output/state.npz"]},
            None,
        )

    def regrade(adapter_, entry_id, **kwargs):
        calls["regrade"] = (entry_id, kwargs)
        derived = kwargs["file_as"]
        door.flow.retain_private(derived, **door.args)
        return {
            "private_evaluation_state": calls.get("state", "BOUND_DEVELOPMENT_ONLY")
        }

    monkeypatch.setattr(retention, "_derived_build", build)
    monkeypatch.setattr(retention, "_regrade_origin", origin)
    monkeypatch.setattr(retention, "_owner_directory", lambda value, label: value)
    monkeypatch.setattr(retention, "_retain_served_artifacts", retain)
    monkeypatch.setattr(retention, "regrade_retained_entry", regrade)
    monkeypatch.setattr(
        retention, "_private_measurement_bytes", lambda path, limit: path.read_bytes()
    )

    def run():
        return retention.rebuild_king(
            adapter,
            door.store,
            king="king",
            evaluation_key=door.key,
            king_entry=digest("king entry"),
            artifact_directory=tmp_path,
            entry_directory=tmp_path,
        )

    return SimpleNamespace(calls=calls, run=run, adapter=adapter)


def test_rebuild_king_builds_his_recipe_at_the_official_seed_host_owned_and_files_under_the_derived_row(
    door, wired
):
    from carbon.challenge_validator import crown_average

    out = wired.run()
    origin, seed, _label, host = wired.calls["build"]
    assert (origin, seed, host) == ("king", 0, crown_average.HOST_OWNER)
    # his recipe and envelope are his own retained files, read through his origin entry as the sitting king
    recipe, envelope = wired.calls["built"]
    assert recipe.digest == door.store.submission("king")["binding"]["recipe_digest"]
    assert envelope == b"the king's retained envelope"
    assert wired.calls["origin"] == (digest("king entry"), "king")
    assert (
        seed == retention.KING_REBUILD_SEED == 0
    )  # the official seed a challenger's entry gets
    _entry_id, kwargs = wired.calls["regrade"]
    derived = retention.king_rebuild_id("king", JUDGE, door.key)
    assert out["king_rebuild_id"] == derived and kwargs["file_as"] == derived
    assert (
        kwargs["promotion"] is door.store and "counted" not in kwargs
    )  # uncounted, filed in the pool
    assert (
        door.store.king_rebuild_of("king", door.key)["derived_submission_id"] == derived
    )
    assert (
        door.flow.private_pair("challenger", door.key)["incumbent"]["rebuilt_as"]
        == derived
    )


def test_rebuild_king_links_only_a_bound_grade_and_refuses_another_recipe_or_a_non_king(
    door, wired
):
    wired.calls["state"] = "UNAVAILABLE"
    wired.run()
    assert (
        door.store.king_rebuild_of("king", door.key) is None
    )  # an unbound grade is never linked
    wired.calls["recipe"] = digest("a different recipe")
    wired.calls.pop("state")
    with pytest.raises(
        retention.RetentionUnavailable, match="king_rebuild_recipe_differs"
    ):
        wired.run()
    wired.calls.pop("recipe")
    wired.calls["retained"] = digest("a retained recipe that is not his admission")
    with pytest.raises(
        retention.RetentionUnavailable, match="king_rebuild_recipe_differs"
    ):
        wired.run()
    wired.calls.pop("retained")
    wired.calls["origin_id"] = "rtsk_" + "f" * 64
    with pytest.raises(
        retention.RetentionUnavailable, match="king_rebuild_origin_differs"
    ):
        wired.run()
    door.store.set_incumbent("challenger", "test", expected="king")
    with pytest.raises(
        retention.RetentionUnavailable, match="king_rebuild_not_the_sitting_king"
    ):
        wired.run()


def test_the_build_never_reads_the_origin_provider_when_custody_gives_the_recipe(
    monkeypatch,
):
    """Deploy 5 Nov (Motor, bbcabff3): a king admitted under an earlier contract/pack is not in his provider's
    in-memory requests, and the old build head raised a bare KeyError on his task id before any build. With the recipe
    and envelope from custody the origin's owner and provider are never consulted."""
    from carbon import research
    from carbon.research import DirectTaskStateV3

    seen = {}
    done = SimpleNamespace(task=SimpleNamespace(state=DirectTaskStateV3.SUCCEEDED))

    def start(request, *, measure_query, **graph):
        seen["graph"] = graph
        return done

    def refuse_zero(task, seed):
        if not 0 < seed < 2**31 - 1:
            raise ValueError("rebuild seed invalid")
        seen["seed"] = seed

    host = SimpleNamespace(
        evaluation_pack_digest="EXAM",
        _views={},
        _requests={},  # no request for the king: the 5 Nov state
        _task_id=lambda request: SimpleNamespace(value="rtsk_" + "d" * 64),
        set_rebuild_seed=refuse_zero,  # as the real provider: never 0 (it hid Deploy's 12:41 failure when it did not)
        set_origin_rebind=lambda task: seen.setdefault("marked", task),
        _seed_for=lambda task: 0,
        start_research_task=start,
        get_research_result=lambda request: done,
    )

    def provider(owner):
        assert owner == "host", "the origin's provider must not be read"
        return host

    def no_origin_owner(sid):
        raise AssertionError("the origin's owner must not be read")

    adapter = SimpleNamespace(
        owner=no_origin_owner,
        _provider=provider,
        _request=lambda owner, recipe, **k: (owner, recipe, k),
        _measure_query=None,
        discovery=SimpleNamespace(info=SimpleNamespace(challenge_key="K")),
    )
    monkeypatch.setattr(research, "DirectGetTaskRequestV3", lambda *a: a)
    recipe = SimpleNamespace(digest="R", to_dict=lambda: {"source": {"kind": "graph"}})
    task = retention._derived_build(
        adapter,
        "rtsk_" + "a" * 64,
        0,
        rebuild="KING_REBUILD",
        host_owner="host",
        recipe=recipe,
        graph_source=b"envelope",
    )
    assert task == "rtsk_" + "d" * 64
    # the official seed takes the provider's normal path: no derived seed, the validator mark instead
    assert seen == {
        "marked": "rtsk_" + "d" * 64,
        "graph": {"graph_source": b"envelope"},
    }
    with pytest.raises(
        retention.RetentionUnavailable, match="rebuild_graph_source_unavailable"
    ):
        retention._derived_build(
            adapter,
            "rtsk_" + "a" * 64,
            0,
            rebuild="KING_REBUILD",
            host_owner="host",
            recipe=recipe,
        )


# --- the upkeep -----------------------------------------------------------------------------------------------------


class _Pool:
    def __init__(self, store):
        self.store, self.clock, self.waiting, self.blocked = store, store.clock, 1, {}
        self.king_upkeep_attempts = store.king_upkeep_attempts
        self.note_king_upkeep_attempt = store.note_king_upkeep_attempt
        self.record_king_rebuild_blocked = store.record_king_rebuild_blocked
        self.king_rebuild_blocked = store.king_rebuild_blocked

    def incumbent(self):
        return {"model_id": "king"}

    def paused_crowns(self, kind=None):
        return [
            {"submission_id": "rtsk_c", "evaluation_key": digest("key"), "exam": "EXAM"}
        ]

    def awaits_incumbent_regrade(self, record):
        return self.waiting > 0


def _upkeep(tmp_path, monkeypatch, rebuild):
    state = tmp_path / "s"
    state.mkdir(mode=0o700)
    pool = _Pool(PoolStore(state / "p.sqlite3", clock=lambda: 1000.0))
    monkeypatch.setattr(king_upkeep, "king_origin_entry", lambda *a: digest("entry"))
    monkeypatch.setattr(retention, "king_parent_moved", lambda *a, **k: True)
    monkeypatch.setattr(retention, "rebuild_king", rebuild(pool))
    intake = SimpleNamespace(
        adapter=SimpleNamespace(
            discovery=SimpleNamespace(evaluation_pack_digest="EXAM")
        )
    )

    def step():
        return king_upkeep.step(
            pool, intake, root=tmp_path, artifacts=tmp_path, entries=tmp_path
        )

    return pool, step


def test_a_king_whose_parent_moved_is_rebuilt_and_the_queue_can_then_meet_him(
    tmp_path, monkeypatch, capsys
):
    def rebuild(pool):
        def run(*a, **k):
            pool.waiting = 0
            return {
                "private_evaluation_state": "BOUND_DEVELOPMENT_ONLY",
                "king_rebuild_id": "krb_x",
            }

        return run

    _pool, step = _upkeep(tmp_path, monkeypatch, rebuild)
    assert step() == {"step": "rebuild", "state": "DONE"}
    events = [json.loads(x)["event"] for x in capsys.readouterr().err.splitlines()]
    assert events == ["king_rebuild_started", "king_rebuilt"]


def test_a_capability_gap_stops_his_contention_with_one_owner_line(
    tmp_path, monkeypatch, capsys
):
    def rebuild(pool):
        def run(*a, **k):
            raise retention.RetentionUnavailable(retention.KING_REBUILD_GAP)

        return run

    pool, step = _upkeep(tmp_path, monkeypatch, rebuild)
    assert step()["state"] == "BLOCKED"
    assert pool.king_rebuild_blocked("king", "EXAM")["action"] == "owner_keep_or_vacate"
    assert step() is None  # contention for that king stops: no more rounds, no dethrone
    lines = [json.loads(x) for x in capsys.readouterr().err.splitlines()]
    (alert,) = [line for line in lines if line["event"] == "operator_alert"]
    assert alert["code"] == "king_rebuild_capability_gap"


def test_infrastructure_during_the_rebuild_is_a_typed_retry_never_a_block(
    tmp_path, monkeypatch
):
    def rebuild(pool):
        def run(*a, **k):
            raise retention.RetentionUnavailable("rebuild_task_failed_infra")

        return run

    pool, step = _upkeep(tmp_path, monkeypatch, rebuild)
    assert step() == {
        "step": "regrade",
        "state": "FAILED",
        "code": "rebuild_task_failed_infra",
    }
    assert pool.king_rebuild_blocked("king", "EXAM") is None


# --- audit #7 (Validator-2 13:05, MUST-FIX): the krb_ row binds with the REBUILT task's construction binding -----------


def test_a_king_carried_across_a_challenge_version_binds_his_rebuild(tmp_path):
    """Every live king was carried across route D: his admission names the OLD Challenge version, while his rebuilt
    task's entry is on the current one. The derived row takes the rebuilt entry's challenge binding (and keeps his
    hotkey, request and admitted recipe digest), so the real `_private_model` binds it; the admission's binding refuses.
    """
    case = _graph_case(tmp_path)
    store = PoolStore(tmp_path / "private.sqlite", clock=lambda: 123.0)
    admitted(store, case, "king", version="the version he was admitted on")
    store.set_incumbent("king", "carried across route D")
    pin, args = inputs(case, version="synthetic-eval-v2")
    flow = bp.BankPromotion(store, registered_source_receipt_sha256=pin)
    king = store.submission("king")
    state = {"state.npz": case["originals"]["build/output/state.npz"]}
    task = "rtsk_" + "d" * 64
    old = retention.king_rebuild_id("king", JUDGE, "old binding")
    retention._admit_king_rebuild(store, old, king, state, task, JUDGE)
    with pytest.raises(StateError, match="private_evaluation_model_binding"):
        flow.retain_private(
            old, **args
        )  # the admission's old version: the 13:05 failure
    derived = retention.king_rebuild_id("king", JUDGE, "rebuilt binding")
    retention._admit_king_rebuild(
        store, derived, king, state, task, JUDGE, case["entry"]
    )
    key = flow.retain_private(derived, **args)["evaluation_key"]
    row = store.submission(derived)
    assert row["binding"]["challenge"]["version"] == case["entry"]["challenge_version"]
    assert (row["hotkey"], row["request_digest"]) == (
        king["hotkey"],
        king["request_digest"],
    )
    assert row["binding"]["recipe_digest"] == king["binding"]["recipe_digest"]
    store.record_king_rebuild(  # the link still checks his admission: hotkey and admitted recipe digest
        "king",
        derived,
        judge_image=JUDGE,
        evaluation_key=key,
        recipe_digest=king["binding"]["recipe_digest"],
        hotkey=king["hotkey"],
    )
    assert store.king_rebuild_of("king", key)["derived_submission_id"] == derived


# --- audit #5 (Validator-2 13:05 ruling): the repeat gate stays; repeat(king) finds his rebuilt state ----------------


def test_a_dethrone_on_a_rebuilt_king_passes_the_repeat_gate_through_the_link(
    door, monkeypatch, tmp_path
):
    """A DETHRONED reads the king's grade, which is his krb_ grade with no repeat mark, so the real `repeat_gate` asks
    repeat(king). It is the second grade of the linked krb_ row's retained entry, run under the host owner (only the
    GPU re-grade itself is stood in: it returns the same evidence, a bit-exact repeat).
    """
    from carbon.challenge_validator.crown_average import HOST_OWNER

    derived, king = _rebuild_row(door)
    _link(door, derived, king)
    pair = door.flow.private_pair("challenger", door.key)
    assert pair["incumbent"]["rebuilt_as"] == derived
    rebuilt_entry = pair["incumbent"]["evidence"]["entry_id"]
    host_task = "rtsk_" + "d" * 64
    entries = tmp_path / "rebuilt-entries"
    entries.mkdir(mode=0o700)
    (entries / (rebuilt_entry.removeprefix("sha256:") + ".json")).write_text(
        json.dumps({"custody_receipt": {"file": host_task + ".custody.json"}})
    )
    graded, held = [], []

    def second_grade(adapter_, entry_id, **custody):
        graded.append(entry_id)
        held.append(adapter_.owner(host_task))
        rows = {
            pair["candidate"]["evidence"]["entry_id"]: pair["candidate"],
            rebuilt_entry: pair["incumbent"],
        }
        return rows[entry_id]["evidence"]

    monkeypatch.setattr(retention, "repeat_grade", second_grade)
    monkeypatch.setattr(retention, "_owner_directory", lambda value, label: value)
    monkeypatch.setattr(
        retention, "_private_measurement_bytes", lambda path, limit: path.read_bytes()
    )
    import contextlib

    owners = {}

    @contextlib.contextmanager
    def deriving(task, owner):
        owners[task] = owner
        yield
        owners.pop(task)

    adapter = SimpleNamespace(deriving=deriving, owner=lambda task: owners.get(task))
    repeat = retention._repeat_of(
        adapter,
        "challenger",
        pair["candidate"]["evidence"]["entry_id"],
        pool_store=door.store,
        artifact_directory=tmp_path,
        entry_directory=entries,
    )
    dethroned = {"outcome": bp.DETHRONED, "reason": "incumbent_failed_mandatory_gate"}
    assert bp.repeat_gate(pair, dethroned, repeat, {}, 0.0) == dethroned
    assert graded[-1] == rebuilt_entry and held[-1] == HOST_OWNER
    # without the pool (the old code path) the king's state is not found: UNAVAILABLE, no crown move
    bare = retention._repeat_of(
        adapter,
        "challenger",
        pair["candidate"]["evidence"]["entry_id"],
        artifact_directory=tmp_path,
        entry_directory=entries,
    )
    assert bp.repeat_gate(pair, dethroned, bare, {}, 0.0)["outcome"] == bp.UNAVAILABLE
