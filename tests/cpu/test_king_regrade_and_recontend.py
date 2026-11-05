"""The king's regrade on a changed pack, and the re-contend of the challengers graded while he could not be met.

Deploy 5 Nov 06:15: `regrade_retained_entry` refused every king ``regrade_owner_unavailable`` because it looked his
owner up under the door's CURRENT contract, and each king was admitted under the previous pack's. Claims: (1) the
sitting king's owner resolves from the one contract he was admitted under (ambiguous: refused); any other task keeps
the current-contract lookup and still refuses; (2) the crown re-measure of such a king holds that owner for its span;
(3) `recontend` files, in grading order, exactly the challengers on the current pack graded before the king's
evaluation on their key, with the origin entry their live repeat would use, refuses or reports everything else,
writes nothing on a plan, files each once, and the receiver's own sweep then decides them oldest first.
Synthetic ledgers and pool rows; no model runs.
"""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from carbon.battery.pool_store import PoolStore
from carbon.challenge_validator import bank_promotion as bp
from carbon.challenge_validator import crown_pause_sweep as sweeper
from carbon.challenge_validator import lean_recipe_retention as retention
from carbon.challenge_validator import recontend
from carbon.challenge_validator.interface import digest
from carbon.challenge_validator.ledger import AttemptLedger

OLD_CONTRACT, NEW_CONTRACT = digest("contract, previous pack"), digest(
    "contract, current pack"
)
KING, OTHER = "rtsk_" + "a" * 64, "rtsk_" + "b" * 64
HOTKEY = "5" + "F" * 47


def _ledger(tmp_path):
    directory = tmp_path / "attempts"
    directory.mkdir(mode=0o700)
    return AttemptLedger(directory / "ledger.sqlite3")


def _entry(entries, task):
    entry_id = digest(["entry", task])
    (entries / (entry_id.removeprefix("sha256:") + ".json")).write_text(
        json.dumps(
            {"entry_id": entry_id, "custody_receipt": {"file": task + ".custody.json"}}
        )
    )
    return entry_id


def _origin(tmp_path, ledger, task, incumbent):
    base, entries = tmp_path / "artifacts", tmp_path / "entries"
    base.mkdir(mode=0o700, exist_ok=True)
    entries.mkdir(mode=0o700, exist_ok=True)
    adapter = SimpleNamespace(ledger=ledger, contract_digest=NEW_CONTRACT)
    try:
        retention._regrade_origin(
            adapter, base, entries, _entry(entries, task), incumbent=incumbent
        )
    except retention.RetentionUnavailable as refused:
        return str(refused)
    return "resolved"


def test_the_king_admitted_under_the_previous_contract_resolves_his_owner(tmp_path):
    ledger = _ledger(tmp_path)
    ledger.record_recipe_task_intent(OLD_CONTRACT, KING, HOTKEY, digest("request"))
    assert (
        ledger.owned_outcome(NEW_CONTRACT, KING) is None
    )  # the lookup that refused every king
    assert ledger.admitted_owner(KING) == (OLD_CONTRACT, HOTKEY)
    # past the owner: it now stops only at the retained task's files (absent here), never at the owner
    assert (
        _origin(tmp_path, ledger, KING, incumbent=KING) != "regrade_owner_unavailable"
    )


def test_any_task_but_the_king_keeps_the_current_contract_lookup(tmp_path):
    ledger = _ledger(tmp_path)
    ledger.record_recipe_task_intent(OLD_CONTRACT, OTHER, HOTKEY, digest("request"))
    assert (
        _origin(tmp_path, ledger, OTHER, incumbent=KING) == "regrade_owner_unavailable"
    )
    assert (
        _origin(tmp_path, ledger, OTHER, incumbent=None) == "regrade_owner_unavailable"
    )


def test_an_ambiguous_admission_refuses(tmp_path):
    ledger = _ledger(tmp_path)
    ledger.record_recipe_task_intent(OLD_CONTRACT, KING, HOTKEY, digest("request"))
    ledger.record_recipe_task_intent(
        digest("a third contract"), KING, HOTKEY, digest("request 2")
    )
    assert ledger.admitted_owner(KING) is None  # two contracts: never guessed
    assert (
        _origin(tmp_path, ledger, KING, incumbent=KING) == "regrade_owner_unavailable"
    )


def test_the_regrade_reads_the_king_from_the_pool_it_records_into():
    store = SimpleNamespace(incumbent=lambda: {"model_id": KING})
    assert retention._regrade_incumbent(store) == KING
    assert retention._regrade_incumbent(SimpleNamespace(store=store)) == KING
    assert retention._regrade_incumbent(None) is None
    assert retention._regrade_incumbent(SimpleNamespace(incumbent=lambda: None)) is None


def test_the_crown_remeasure_holds_the_kings_admitted_owner(tmp_path, monkeypatch):
    from carbon.challenge_validator import crown_average

    ledger = _ledger(tmp_path)
    ledger.record_recipe_task_intent(OLD_CONTRACT, KING, HOTKEY, digest("request"))
    held = []

    class Adapter:
        challenge_id = "electric-motor-magnetics"
        discovery = SimpleNamespace(
            evaluation_pack_snapshot=SimpleNamespace(read_json_role=lambda *a, **k: {}),
            evaluation_pack_private_root=None,
            evaluation_pack_public_root=None,
        )

        def __init__(self):
            self.ledger, self._derived_owners = ledger, {}

        def owner(self, submission_id):
            return self._derived_owners.get(submission_id)

        import contextlib

        @contextlib.contextmanager
        def deriving(self, task, owner):
            self._derived_owners[task] = owner
            yield
            self._derived_owners.pop(task)

    adapter = Adapter()

    class Active:
        def measure_incumbent(self, store, sid, key, comparator, repeat):
            held.append(adapter.owner(sid))
            return {"outcome": "KING_MEASURED"}

    monkeypatch.setattr(crown_average, "ACTIVE", Active())
    repeats = []
    monkeypatch.setattr(retention, "_repeat_of", lambda *a, **k: repeats.append(k))
    # Deploy 5 Nov (Motor): the current provider does not hold his request in memory, so his rebuilds take his
    # recipe from custody (`retained_king_source`), never the provider's map
    custody = {"recipe": "his retained recipe", "graph_source": b"his envelope"}
    monkeypatch.setattr(
        retention,
        "retained_king_source",
        lambda adapter_, store_, king, entry, **dirs: (
            custody if (king, entry) == (KING, digest("entry")) else None
        ),
    )
    monkeypatch.setattr(
        "carbon.challenge_validator.koth_registry.comparator", lambda *a, **k: {}
    )
    store = SimpleNamespace(
        incumbent=lambda: {"model_id": KING}, origin_rebind=lambda sid: None
    )
    retention.remeasure_incumbent_pack(
        adapter,
        store,
        submission_id=KING,
        evaluation_key=digest("current key"),
        entry_id=digest("entry"),
        artifact_directory=tmp_path,
        entry_directory=tmp_path,
    )
    assert held == [HOTKEY] and adapter._derived_owners == {}
    assert repeats[0]["source"] is custody


def test_a_rebuild_given_a_custody_source_builds_from_it(monkeypatch):
    builds = []

    def build(adapter_, origin, seed, *, rebuild, host_owner, **source):
        builds.append(source)
        return "rtsk_" + "d" * 64

    import contextlib

    adapter = SimpleNamespace(deriving=lambda task, owner: contextlib.nullcontext())
    monkeypatch.setattr(retention, "_derived_build", build)
    monkeypatch.setattr(retention, "retain_rebuild_evidence", lambda *a, **k: {})
    custody = {"recipe": "his retained recipe", "graph_source": None}
    for source in (custody, None):
        retention.rebuild_at_seed(
            adapter,
            KING,
            7,
            host_owner="host",
            artifact_directory=None,
            entry_directory=None,
            source=source,
        )
    assert builds == [
        custody,
        {},
    ]  # without one: the origin provider's request, as before


# --- recontend -------------------------------------------------------------------------------------------------------

EXAM, OLD_EXAM = digest("current pack"), digest("previous pack")
KEY, OLD_KEY = digest("current key"), digest("previous key")
PIN = digest("pack source receipt")


def _task(n):
    return "rtsk_" + f"{n:064x}"


def _row(store, sid, key, exam=EXAM):
    """A filed private evaluation as the pool store keeps it (only the fields recontend reads)."""
    body = {
        "submission_id": sid,
        "evaluation_key": key,
        "evidence": {
            "evaluation_pack_digest": exam,
            "entry_id": digest(["bank entry", sid]),
            "source_receipt_sha256": PIN,
        },
    }
    with store.transaction() as db:
        db.execute(
            "INSERT INTO operations VALUES(?,?,?,?)",
            (
                digest(["op", sid, key]),
                "private_evaluation.v1",
                "BOUND_DEVELOPMENT_ONLY",
                json.dumps(body),
            ),
        )


def _door(tmp_path):
    """A receiver root whose pool king is on the previous pack, five challengers graded on the current one."""
    root = tmp_path / "state"
    for name in ("artifacts", "entries"):
        (root / "auto-grade" / name).mkdir(parents=True, mode=0o700)
    store = PoolStore(root / "pool.sqlite3")
    store.set_incumbent(KING, bp.SEALED_TESTNET_PROMOTION)
    _row(store, KING, OLD_KEY, exam=OLD_EXAM)
    for n in (1, 2, 3):
        _row(store, _task(n), KEY)
    _row(
        store, _task(9), OLD_KEY, exam=OLD_EXAM
    )  # graded on the previous pack: not this exam
    for n in (
        1,
        2,
        3,
    ):  # a pool grade's bank entry maps to the origin entry the live repeat runs from
        sid = _task(n)
        directory = (
            root
            / "auto-grade"
            / "artifacts"
            / ("rtsk_" + f"{100 + n:064x}" + ".evaluation")
        )
        directory.mkdir(mode=0o700)
        (directory / "regrade-provenance.json").write_text(
            json.dumps(
                {
                    "entry_id": digest(["bank entry", sid]),
                    "origin_entry_id": digest(["origin entry", sid]),
                    "origin_task_id": sid,
                }
            )
        )
    return root, store


def test_before_the_kings_regrade_they_are_filed_pending_for_his_automatic_regrade(
    tmp_path,
):
    root, store = _door(tmp_path)
    pool = root / "pool.sqlite3"
    planned = recontend.plan(root, pool, EXAM)
    assert [i["submission_id"] for i in planned["file"]] == [
        _task(1),
        _task(2),
        _task(3),
    ]
    assert {i["state"] for i in planned["file"]} == {"PENDING_CONTENTION"}
    recontend.file(root, pool, EXAM, apply=True)
    with store.db() as db:
        states = {
            s
            for (s,) in db.execute(
                "SELECT state FROM operations WHERE kind='crown_paused.v1'"
            )
        }
    assert states == {"PENDING_CONTENTION"}
    assert [r["submission_id"] for r in store.paused_crowns("pack")] == [
        _task(1),
        _task(2),
        _task(3),
    ]


def test_after_the_kings_regrade_exactly_the_earlier_challengers_are_filed_in_grading_order(
    tmp_path,
):
    root, store = _door(tmp_path)
    _row(store, KING, KEY)  # the king's uncounted regrade on the current pack
    _row(store, _task(4), KEY)  # graded after it: the live path contended it
    pool = root / "pool.sqlite3"
    planned = recontend.plan(root, pool, EXAM)
    assert [i["submission_id"] for i in planned["file"]] == [
        _task(1),
        _task(2),
        _task(3),
    ]
    assert planned["file"][0] == {
        "submission_id": _task(1),
        "evaluation_key": KEY,
        "entry_id": digest(["origin entry", _task(1)]),
        "pin": PIN,
        "state": "PAUSED",
    }
    assert store.paused_crowns() == []  # a plan writes nothing
    out = recontend.file(root, pool, EXAM, apply=True, clock=lambda: 7)
    assert out["filed"] == [_task(1), _task(2), _task(3)]
    filed = store.paused_crowns("pack")
    assert [r["submission_id"] for r in filed] == [_task(1), _task(2), _task(3)]
    assert {(r["exam"], r["pin"], r["evaluation_key"]) for r in filed} == {
        (EXAM, PIN, KEY)
    }
    log = (
        (root / "auto-grade" / "recontend" / "recontend.jsonl").read_text().splitlines()
    )
    assert [json.loads(line)["submission_id"] for line in log] == out["filed"]
    # filed once: a second run files nothing and says why
    again = recontend.file(root, pool, EXAM, apply=True)
    assert again["filed"] == [] and set(again["skipped"].values()) == {"already_filed"}


def test_the_receivers_own_sweep_decides_them_oldest_first_and_report_shows_it(
    tmp_path,
):
    root, store = _door(tmp_path)
    _row(store, KING, KEY)
    pool = root / "pool.sqlite3"
    recontend.file(root, pool, EXAM, apply=True)
    decided = []

    def reconsider(record):  # the receiver's reconsider_paused_pack, in the live sweep
        decided.append(record["submission_id"])
        return {"outcome": bp.INCUMBENT_KEEPS, "reason": "kept", "evaluation_key": KEY}

    assert [
        sid
        for sid, _ in sweeper.sweep(store, reconsider, kind="pack", current_exam=EXAM)
    ] == [
        _task(1),
        _task(2),
        _task(3),
    ]
    assert decided == [_task(1), _task(2), _task(3)]
    assert (
        sweeper.sweep(store, reconsider, kind="pack", current_exam=EXAM) == []
    )  # once each
    assert [r["resolution"] for r in recontend.report(pool)] == [
        "INCUMBENT_KEEPS:kept"
    ] * 3


def test_a_king_who_won_on_the_current_key_strands_nobody_so_nothing_is_contended_twice(
    tmp_path,
):
    """A king crowned on this exam (his first grade is on its key): every earlier challenger met the king of its moment."""
    root = tmp_path / "state"
    for name in ("artifacts", "entries"):
        (root / "auto-grade" / name).mkdir(parents=True, mode=0o700)
    store = PoolStore(root / "pool.sqlite3")
    _row(store, _task(1), KEY)  # graded against the previous king
    _row(store, KING, KEY)  # the new king's own winning grade
    _row(store, _task(2), KEY)  # graded against him, live
    store.set_incumbent(KING, bp.SEALED_TESTNET_PROMOTION)
    planned = recontend.plan(root, root / "pool.sqlite3", EXAM)
    assert planned["file"] == [] and planned["skipped"] == {}


def test_an_unresolved_entry_or_a_bad_exam_is_reported_never_guessed(tmp_path):
    root, store = _door(tmp_path)
    _row(store, KING, KEY)
    (
        root
        / "auto-grade"
        / "artifacts"
        / ("rtsk_" + f"{102:064x}" + ".evaluation")
        / "regrade-provenance.json"
    ).unlink()
    planned = recontend.plan(root, root / "pool.sqlite3", EXAM)
    assert planned["skipped"] == {_task(2): "origin_entry_unresolved"}
    with pytest.raises(recontend.RecontendRefused, match="exam_digest_invalid"):
        recontend.plan(root, root / "pool.sqlite3", "latest")
    with pytest.raises(recontend.RecontendRefused, match="pool_store_unavailable"):
        recontend.plan(root, root / "missing.sqlite3", EXAM)


def test_the_command_prints_the_plan_and_files_only_with_apply(tmp_path, capsys):
    root, store = _door(tmp_path)
    _row(store, KING, KEY)
    args = [
        "--root",
        str(root),
        "--pool-store",
        str(root / "pool.sqlite3"),
        "--exam",
        EXAM,
    ]
    assert recontend.main(["plan", *args]) == 0
    assert json.loads(capsys.readouterr().out)["file"] == [_task(1), _task(2), _task(3)]
    assert recontend.main(["file", *args]) == 0
    assert (
        json.loads(capsys.readouterr().out)["apply"] is False
        and store.paused_crowns() == []
    )
    assert recontend.main(["file", *args, "--apply"]) == 0
    assert len(store.paused_crowns()) == 3
    assert recontend.main(["report", "--pool-store", str(root / "pool.sqlite3")]) == 0
    assert [
        r["resolution"] for r in json.loads(capsys.readouterr().out.splitlines()[-1])
    ] == [None] * 3
