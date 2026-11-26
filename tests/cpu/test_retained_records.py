"""Retained records of the new exams (owner, 25 Nov 2026: every new exam version it names keeps ALL solver outputs of
every solve, scored or unscored, in its retained records, as bank 8319 to 8321 and door-code 8330 S3 and S4 specify).

Claims:
1. REGISTRATION: a crown row may carry ``"records": "all"``; any other value refuses. No public repository row carries
   it, the live 1.8 row included. `records_all` is true only for the served version under it.
2. S3 LEDGER: a version under it files the coldkey (read from the receiver's own snapshot) and the signed receipt block on
   every GRADED row it reserves; a regrade, or any other version, files neither; a coldkey the snapshot cannot give is
   NULL and the reservation is exactly as before; an older ledger gains both columns, NULL on its rows.
3. S3 CROWN: every decided confirmation (crowned, or not confirmed) files one private record with both open numbers,
   both confirmation numbers and the answer; a wait files none; the record is write-once.
4. S4 GATES: every grade's capture holds every gate verdict (PASS, FAIL, NOT_APPLICABLE) with the gate-set version (sha256
   of the sorted gate names); the sidecar is written only for a version under the line; it never raises.

Every value is a SYNTHETIC fixture, never a production value.
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

import test_crown_confirmation
from test_crown_confirmation import (
    CHALLENGE,
    KEY,
    RULED,
    _confirming_policies,
    _grade,
    _mine,
    _record,
    _registry,
    _Store,
)
from test_crown_confirmation import _consider as _consider_plain
from test_exam_cap import cadence
from test_pool_multiclass_regions import (  # noqa: F401  (a fixture)
    geometric_v1_stand_in,
)

from carbon.battery.pool_store import StateError
from carbon.challenge_validator import bank_promotion as bp
from carbon.challenge_validator import (
    crown_official,
    exam_cap,
    exam_rotation,
)
from carbon.challenge_validator import lean_recipe_retention as retention
from carbon.challenge_validator.ledger import AttemptLedger
from carbon.scoring import pool_exam

ROOT = Path(__file__).resolve().parents[2]
HOTKEY = "5GrwvaEF5zXb26Fz9rcQpDWS57CtERHpNehXCPcNoHGKutQY"
COLDKEY = "5FHneW46xGXgs5mUiveU4sbTyGBzmstUspZC92UhjJM694ty"
EXAM = "sha256:" + "1" * 64
SERVED = ("electric-motor-magnetics", "1.9")


@pytest.fixture(autouse=True)
def _nothing_installed(monkeypatch):
    monkeypatch.setattr(crown_official, "ACTIVE", None)
    monkeypatch.setattr(exam_cap, "COLDKEYS", None)
    monkeypatch.setattr(exam_cap, "GROUPING", None)


def _install(tmp_path, entry, pair=SERVED):
    path = _registry(tmp_path, {f"{pair[0]} {pair[1]}": entry})
    lines = []
    crown_official.install(*pair, path=path, log=lines.append)
    return lines


# ---------------------------------------------------------------- 1. registration


def test_a_row_may_keep_every_record_and_says_so_at_install(tmp_path):
    lines = _install(tmp_path, {"margin": 0.01, "records": "all"})
    assert lines == ["crown_official_score=true margin=0.01 records=all"]
    assert crown_official.records_all()
    assert crown_official.records_all(*SERVED)
    # another pair than the served one never reads the served row
    assert not crown_official.records_all("electric-motor-magnetics", "1.8")


@pytest.mark.parametrize("value", ["some", "", None, True, ["all"]])
def test_any_other_records_value_refuses(tmp_path, value):
    path = _registry(tmp_path, {"zz 1": {"margin": 0.01, "records": value}})
    with pytest.raises(crown_official.CrownOfficialInvalid, match="entry_malformed"):
        crown_official.registered("zz", "1", path=path)


def test_without_the_key_or_without_an_installed_rule_nothing_more_is_kept(tmp_path):
    assert not crown_official.records_all()
    _install(tmp_path, {"margin": 0.01})
    assert not crown_official.records_all()


def test_no_public_repository_row_keeps_every_record_and_the_live_row_is_unchanged():
    """The versions whose rows keep every record live on carbon-internal until they open (owner G-LEAD-122)."""
    rows = json.loads(Path(crown_official.REGISTRY).read_bytes())["versions"]
    assert {name for name, row in rows.items() if row.get("records") == "all"} == set()
    assert rows["electric-motor-magnetics 1.8"] == {"margin": 0.0129, "score": "A"}


# ---------------------------------------------------------------- 2. S3 ledger


LANE_HOURS = {"electric-motor-magnetics": 1.0}


def _cap(tmp_path):
    directory = tmp_path / "ledger"
    directory.mkdir(mode=0o700, exist_ok=True)
    return exam_cap.ExamCap(
        AttemptLedger(directory / "attempts.sqlite3"),
        clock=lambda: 1_000_000_000_000,
        cadence=cadence(134.4, LANE_HOURS),
    )


def _reserve(cap, submission_id="rtsk_1", *, block=7200, regrade=False, pair=SERVED):
    return cap.reserve(
        hotkey=HOTKEY,
        challenge_id=pair[0],
        challenge_version=pair[1],
        exam_key=EXAM,
        submission_id=submission_id,
        block=block,
        regrade=regrade,
    )


def _filed(cap, row):
    with cap.ledger._db() as db:
        return db.execute(
            "SELECT coldkey, receipt_block FROM exam_graded WHERE id=?", (row,)
        ).fetchone()


def test_a_version_under_the_line_files_the_coldkey_and_the_receipt_block(
    tmp_path, monkeypatch
):
    _install(tmp_path, {"margin": 0.01, "records": "all"})
    asked = []
    exam_cap.install_coldkeys(lambda hotkey: asked.append(hotkey) or COLDKEY)
    cap = _cap(tmp_path)
    row = _reserve(cap)
    assert _filed(cap, row) == (COLDKEY, 7200)
    assert asked == [HOTKEY]


def test_a_regrade_or_another_version_files_neither(tmp_path):
    _install(tmp_path, {"margin": 0.01, "records": "all"})
    exam_cap.install_coldkeys(lambda hotkey: COLDKEY)
    cap = _cap(tmp_path)
    assert _filed(cap, _reserve(cap, "rtsk_r", block=None, regrade=True)) == (
        None,
        None,
    )
    other = ("electric-motor-magnetics", "1.8")
    assert _filed(cap, _reserve(cap, "rtsk_o", block=7200 * 3, pair=other)) == (
        None,
        None,
    )


def test_a_version_without_the_key_files_neither(tmp_path):
    _install(tmp_path, {"margin": 0.01})
    exam_cap.install_coldkeys(lambda hotkey: COLDKEY)
    cap = _cap(tmp_path)
    assert _filed(cap, _reserve(cap)) == (None, None)


@pytest.mark.parametrize("reader", [None, lambda hotkey: None, lambda hotkey: 1 / 0])
def test_a_coldkey_the_snapshot_cannot_give_is_null_and_the_slot_is_taken(
    tmp_path, reader
):
    _install(tmp_path, {"margin": 0.01, "records": "all"})
    exam_cap.install_coldkeys(reader)
    cap = _cap(tmp_path)
    row = _reserve(cap)
    assert type(row) is int
    assert _filed(cap, row) == (None, 7200)


def test_an_older_ledger_gains_both_columns_null_on_its_rows(tmp_path):
    directory = tmp_path / "ledger"
    directory.mkdir(mode=0o700)
    ledger = AttemptLedger(directory / "attempts.sqlite3")
    with ledger._db() as db:
        # the table as an earlier release created it (no coldkey, no receipt_block)
        db.execute(
            "CREATE TABLE exam_graded(id INTEGER PRIMARY KEY AUTOINCREMENT, hotkey TEXT NOT NULL,"
            " challenge_id TEXT NOT NULL, challenge_version TEXT NOT NULL, exam_key TEXT NOT NULL,"
            " kind TEXT NOT NULL DEFAULT 'GRADED', epoch INTEGER NOT NULL, submission_id TEXT NOT NULL,"
            " state TEXT NOT NULL, status TEXT, reserved_ns INTEGER NOT NULL, settled_ns INTEGER,"
            " UNIQUE(challenge_id, challenge_version, exam_key, submission_id))"
        )
        db.execute(
            "INSERT INTO exam_graded(hotkey, challenge_id, challenge_version, exam_key, epoch,"
            " submission_id, state, reserved_ns) VALUES(?,?,?,?,?,?,'COUNTED',1)",
            (HOTKEY, *SERVED, EXAM, 0, "rtsk_old"),
        )
    exam_cap.ExamCap(ledger, cadence=cadence(134.4, LANE_HOURS))
    with ledger._db() as db:
        columns = {row[1] for row in db.execute("PRAGMA table_info(exam_graded)")}
        old = db.execute(
            "SELECT coldkey, receipt_block FROM exam_graded WHERE submission_id='rtsk_old'"
        ).fetchone()
    assert {"coldkey", "receipt_block"} <= columns
    assert old == (None, None)


def test_the_receiver_installs_the_snapshot_reader_beside_the_grouping():
    receiver = ROOT / "carbon/challenge_validator/direct_receiver.py"
    source = receiver.read_text(encoding="utf-8")
    grouping = source.index("exam_cap.install_grouping(")
    assert (
        "exam_cap.install_coldkeys(allowance_groups.coldkey_reader(window))"
        in source[grouping : grouping + 800]
    )


def test_the_coldkey_reader_reads_the_grading_snapshot(monkeypatch):
    from carbon.battery import intake
    from carbon.challenge_validator import allowance_groups

    members = {HOTKEY: SimpleNamespace(coldkey=COLDKEY)}
    snapshot = SimpleNamespace(resolve=members.get)
    monkeypatch.setattr(intake, "grading_snapshot", lambda window: snapshot)
    read = allowance_groups.coldkey_reader(object())
    assert read(HOTKEY) == COLDKEY
    assert read("5Unknown") is None
    monkeypatch.setattr(intake, "grading_snapshot", lambda window: None)
    assert read(HOTKEY) is None


# ---------------------------------------------------------------- 3. S3 crown decision


class _FilingStore(_Store):
    def __init__(self, king, records, fail=None):
        super().__init__(king, records)
        self.decisions, self.fail = {}, fail

    def record_confirmation_decision(self, submission_id, key, record):
        if self.fail is not None:
            raise self.fail
        if submission_id in self.decisions and self.decisions[submission_id] != record:
            raise StateError("confirmation_decision_changed")
        self.decisions[submission_id] = record


def _consider(
    tmp_path, monkeypatch, outcome, *, king="king", records=(), block=RULED, fail=None
):
    store = _FilingStore(king, dict(records), fail)
    monkeypatch.setattr(bp, "_scored", _open_number)
    monkeypatch.setattr(test_crown_confirmation, "_Store", lambda k, r: store)
    decided, _ = _consider_plain(
        tmp_path, monkeypatch, outcome, king=king, records=records, block=block
    )
    return decided, store


def _open_number(row):
    # the two ranked open numbers the decision compared (stand-ins: the rows carry no real evidence)
    return "SCORED", {"cand": 0.7, "king": 0.6}[row["submission_id"]]


def test_a_crowned_challenger_files_its_decision_with_every_number(
    tmp_path, monkeypatch
):
    decided, store = _consider(
        tmp_path, monkeypatch, CHALLENGE, records=[_mine(0.6), _mine(0.5, "king")]
    )
    assert decided["outcome"] == bp.CHALLENGER and store.set_to == "cand"
    record = store.decisions["cand"]
    assert record["schema"] == crown_official.DECISION_SCHEMA
    assert (record["verdict"], record["reason"], record["first"]) == (
        "CONFIRMED",
        None,
        False,
    )
    assert (record["candidate_open"], record["incumbent_open"]) == (0.7, 0.6)
    assert record["candidate_confirmation"]["value"] == 0.6
    assert record["incumbent_confirmation"]["value"] == 0.5
    assert record["rule"] == RULED
    # the decision itself still carries no confirmation number
    assert "0.5" not in json.dumps(decided)


def test_a_challenger_not_confirmed_files_its_decision_and_the_king_stays(
    tmp_path, monkeypatch
):
    decided, store = _consider(
        tmp_path, monkeypatch, CHALLENGE, records=[_mine(0.5), _mine(0.5, "king")]
    )
    assert decided["outcome"] == bp.INCUMBENT_KEEPS and store.set_to is None
    record = store.decisions["cand"]
    assert (record["verdict"], record["reason"]) == (
        "NOT_CONFIRMED",
        crown_official.CROWN_NOT_CONFIRMED,
    )


def test_a_gate_failed_king_dethroned_files_the_not_confirmed_decision(
    tmp_path, monkeypatch
):
    failed = {"outcome": bp.CHALLENGER, "reason": "incumbent_failed_mandatory_gate"}
    decided, store = _consider(
        tmp_path, monkeypatch, failed, records=[_mine(None, status="INVALID")]
    )
    assert decided["outcome"] == bp.DETHRONED and store.vacated == "king"
    record = store.decisions["cand"]
    assert (record["verdict"], record["first"]) == ("NOT_CONFIRMED", True)
    assert record["incumbent_confirmation"] is None


@pytest.mark.parametrize(
    "records,outcome",
    [
        ([_mine(0.6), _mine(0.5, "king")], bp.CHALLENGER),
        ([_mine(0.4), _mine(0.5, "king")], bp.INCUMBENT_KEEPS),
    ],
)
def test_a_record_that_cannot_be_filed_never_changes_the_decision(
    tmp_path, monkeypatch, capsys, records, outcome
):
    decided, store = _consider(
        tmp_path, monkeypatch, CHALLENGE, records=records, fail=OSError("disk full")
    )
    assert decided["outcome"] == outcome
    assert store.set_to == ("cand" if outcome == bp.CHALLENGER else None)
    assert store.decisions == {}
    line = capsys.readouterr().err
    assert "crown_confirmation_decision_unfiled" in line and "OSError" in line
    assert "disk full" not in line


def test_a_wait_files_no_decision(tmp_path, monkeypatch):
    decided, store = _consider(
        tmp_path, monkeypatch, CHALLENGE, records=[_mine(0.9)], block=RULED
    )
    assert decided["outcome"] == bp.UNAVAILABLE
    assert store.decisions == {}


def test_the_store_files_one_decision_record_per_crown(tmp_path):
    from carbon.battery.pool_store import PoolStore

    store = PoolStore(tmp_path / "pool.sqlite3", clock=lambda: 123.0)
    record = crown_official.decision_record(
        True, ("CONFIRMED", None), _record(0.5), None, (0.7, None)
    )
    store.record_confirmation_decision("rtsk_x", KEY, record)
    store.record_confirmation_decision("rtsk_x", KEY, record)
    assert store.confirmation_decision("rtsk_x", KEY) == record
    assert store.confirmation_decision("rtsk_y", KEY) is None
    with pytest.raises(StateError, match="changed"):
        store.record_confirmation_decision("rtsk_x", KEY, {**record, "first": False})
    with pytest.raises(StateError, match="invalid"):
        store.record_confirmation_decision("rtsk_x", KEY, {"schema": "other"})


# ---------------------------------------------------------------- 4. S4 gate verdicts


def _binding(*names):
    return SimpleNamespace(physics_gates=SimpleNamespace(gate_names=tuple(names)))


def test_every_gate_verdict_is_named_with_the_gate_set_version():
    gates = {"native": True, "physics_pool": False, "speed": True, "accuracy": True}
    found = pool_exam.gate_verdicts(
        _binding("bound", "sign"), gates, ["sign"], accuracy_registered=True
    )
    assert found["status"] == "MEASURED"
    assert found["measure"] == {
        "accuracy": "PASS",
        "native": "PASS",
        "physics_pool": "FAIL",
        "speed": "PASS",
    }
    assert found["pool"] == {
        pool_exam.AGEN_VALIDITY_GATE: "PASS",
        "bound": "PASS",
        "sign": "FAIL",
    }
    expected = hashlib.sha256(
        json.dumps(found["gate_set"], sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    assert found["gate_set_sha256"] == expected
    # the version names the gate list, not the verdicts
    passing = pool_exam.gate_verdicts(
        _binding("bound", "sign"), {**gates, "physics_pool": True}, [], True
    )
    assert passing["gate_set_sha256"] == found["gate_set_sha256"]
    more = pool_exam.gate_verdicts(_binding("bound", "sign", "new"), gates, [], True)
    assert more["gate_set_sha256"] != found["gate_set_sha256"]


def test_a_version_without_physics_scoring_reads_not_applicable_for_accuracy():
    found = pool_exam.gate_verdicts(
        _binding("bound"), {"physics_pool": True, "speed": True}, [], False
    )
    assert found["measure"][pool_exam.ACCURACY_GATE] == "NOT_APPLICABLE"


def test_gate_verdicts_never_raise():
    found = pool_exam.gate_verdicts(object(), {"speed": True}, [], True)
    assert found["status"] == "UNAVAILABLE" and "reason" in found


@pytest.mark.usefixtures("geometric_v1_stand_in")
def test_every_grade_keeps_its_gate_verdicts_in_the_capture():
    open_sets, _confirming, plain, _policies, material = _confirming_policies()
    result, capture = _grade(open_sets, plain, material)
    found = capture["gate_verdicts"]
    assert found["status"] == "MEASURED"
    assert set(found["measure"]) == set(result["gates"])
    assert all(
        found["measure"][name] == ("PASS" if ok else "FAIL")
        for name, ok in result["gates"].items()
    )
    # names and verdicts only: nothing of the grade's numbers
    assert set(found) == {
        "schema",
        "status",
        "gate_set",
        "gate_set_sha256",
        "measure",
        "pool",
    }


def test_the_sidecar_is_written_only_for_a_version_under_the_line(tmp_path):
    verdicts = {"schema": pool_exam.GATE_VERDICTS_SCHEMA, "status": "MEASURED"}
    assert retention._gate_verdict_sidecar(EXAM, verdicts) is None
    _install(tmp_path, {"margin": 0.01, "records": "all"})
    assert retention._gate_verdict_sidecar(EXAM, None) is None
    assert retention._gate_verdict_sidecar(EXAM, verdicts) == {
        "schema": exam_rotation.GATE_VERDICTS_SIDECAR_SCHEMA,
        "exam_key": EXAM,
        "record": verdicts,
    }


def test_both_sidecar_writers_and_the_se_report_carry_the_verdicts():
    written = ROOT / "carbon/challenge_validator/lean_recipe_retention.py"
    source = written.read_text(encoding="utf-8")
    assert source.count("_gate_verdict_sidecar(") == 3  # the helper and its two writers
    se = (ROOT / "carbon/scoring/pool_exam_se.py").read_text(encoding="utf-8")
    assert 'report["gate_verdicts"] = capture["gate_verdicts"]' in se
