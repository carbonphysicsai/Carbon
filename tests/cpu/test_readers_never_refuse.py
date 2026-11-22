"""Readers cut and count, never refuse a whole document (CAPS.md 3 items 2-8; owner: no cap without a named harm).

Claims: a GATE_FAILED row with more than `MAX_GATES` gates is cut to its first ones (producer) and read (readers); the
crown-average N may reach the registry's own bound (`crown_common.MAX_N`) on the producer and both readers; a crown history
or check list longer than its cap is cut (producer) and read, with the page showing the first ones (readers); one hotkey
shape everywhere, and a row, change or check whose hotkey is not that shape is left out (never a refused board); a
queue v3/v4 document over its byte bound keeps its first rows and counts the rest; the clients read a door reply up to
1 MiB; the pack check's read bounds follow the registered material. Synthetic hotkeys, rows and documents only.
"""

from __future__ import annotations

import datetime
import json
import os
import pathlib
import re

import pytest

from carbon.challenge_validator import crown_common, queue_public
from carbon.challenge_validator import launch_board as lb
from carbon.dashboard import feed, launch

ROOT = pathlib.Path(__file__).resolve().parents[2]
WORKER = (ROOT / "carbon" / "dashboard" / "worker" / "feed.mjs").read_text(
    encoding="utf-8"
)
_ALPHABET = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
NOW = datetime.datetime.fromtimestamp(1_800_000_000, datetime.UTC)


def _hotkey(i, length=48):
    digits = ""
    n = i
    for _ in range(6):
        digits = _ALPHABET[n % len(_ALPHABET)] + digits
        n //= len(_ALPHABET)
    return "5" + "D" * (length - 7) + digits


def _gates(count):
    return [f"gate_{i:02d}" for i in range(count)]


def _find(value, key):
    if isinstance(value, dict):
        if key in value:
            return value[key]
        for inner in value.values():
            found = _find(inner, key)
            if found is not None:
                return found
    return None


def _king_document():
    return {
        "schema": "carbon.koth.public.v1",
        "challenge_id": "electric-motor-magnetics",
        "challenge_version": "1.4",
        "exam_version_label": "motor-exam-1",
        "king": None,
        "margin": 0.02,
        "to_beat": None,
        "baseline_total": 0.3,
    }


def _signed(rows):
    signer = lb.LaunchBoardKey(os.urandom(32))
    board = lb.build(
        king_document=_king_document(),
        rows=rows,
        network="testnet",
        key=signer,
        version=1,
        now=NOW,
    )
    return board, signer, feed.Trust(keys=frozenset({signer.public_key}))


def _resign(board, signer):
    body = {k: v for k, v in board.items() if k != "signature"}
    board["signature"] = signer.sign(body)
    return board


# --- one constant per bound, held equal across the producer, the Python reader and the Worker ---


def test_one_hotkey_shape_and_one_measure_bound_everywhere():
    (worker_ss58,) = re.findall(r"const LAUNCH_SS58 = /\^(.+?)\$/u;", WORKER)
    assert worker_ss58 == lb._SS58.pattern == launch._SS58.pattern
    (worker_n,) = re.findall(r"const LAUNCH_MAX_MEASURE_N = (\d+);", WORKER)
    assert int(worker_n) == launch.MAX_MEASURE_N == crown_common.MAX_N
    assert lb._measure_max_n() == crown_common.MAX_N


# --- item 2: gate names ---


def test_the_producer_cuts_a_long_gate_list_and_the_readers_read_one():
    many = _gates(lb.MAX_GATES + 4)
    rows = [(_hotkey(1), None, {"status": "GATE_FAILED", "gate_names": many})]
    (row,) = lb.ladder_rows(rows)
    assert row["gate_names"] == many[: lb.MAX_GATES]
    board, signer, trust = _signed(rows)
    board["ladder"][0][
        "gate_names"
    ] = many  # a board signed with more names than the page shows
    projected = feed.project(_resign(board, signer), trust)
    assert _find(projected, "gate_names") == {_hotkey(1): many[: launch.MAX_GATES]}


# --- item 3: the crown-average N ---


@pytest.mark.parametrize(
    "n, ok", [(100, True), (101, True), (1000, True), (1001, False)]
)
def test_the_measure_n_runs_to_the_registry_bound(n, ok):
    measure = {"state": "IN_PROGRESS", "kept": 3, "n": n}
    king = {"hotkey": _hotkey(1), "total": 0.6, "since_epoch": 7}
    if ok:
        assert lb.measure_checked(measure, king=king) == measure
        launch._measure(measure, king)
    else:
        with pytest.raises(lb.BoardRefused):
            lb.measure_checked(measure, king=king)
        with pytest.raises(launch.LaunchRefused):
            launch._measure(measure, king)


# --- item 4: crown changes and checks ---


def _check(i):
    return {
        "hotkey": _hotkey(i),
        "state": "DECIDED",
        "outcome": "CHALLENGER",
        "note": "took the crown",
    }


def _change(i):
    return {
        "from_hotkey": _hotkey(i + 1),
        "to_hotkey": _hotkey(i),
        "since_epoch": 100 - i,
        "total": 0.6,
    }


def test_long_crown_lists_are_cut_by_the_producer_and_read_by_the_readers():
    checks = [_check(i) for i in range(lb.MAX_CROWN_CHECKS + 3)]
    changes = [_change(i) for i in range(lb.MAX_CROWN_CHANGES + 3)]
    assert lb.crown_checks_checked(checks) == checks[: lb.MAX_CROWN_CHECKS]
    assert [c["to_hotkey"] for c in lb.crown_changes_checked(changes)] == [
        c["to_hotkey"] for c in changes[: lb.MAX_CROWN_CHANGES]
    ]
    launch._crown_checks(checks)  # read, never refused
    launch._crown_changes(changes)
    assert "checks.length > LAUNCH_MAX_CROWN_CHECKS" not in WORKER
    assert "changes.length > LAUNCH_MAX_CROWN_CHANGES" not in WORKER
    assert "document.crown_checks.slice(0, LAUNCH_MAX_CROWN_CHECKS)" in WORKER
    assert "document.crown_changes.slice(0, LAUNCH_MAX_CROWN_CHANGES)" in WORKER


# --- item 5: the hotkey shape ---


def test_a_row_or_entry_with_an_odd_hotkey_is_left_out_never_a_refused_board():
    good = (_hotkey(1), {"total": 0.5}, {"status": "IMPROVED"})
    odd = ("5" + "<b>" * 15, {"total": 0.9}, {"status": "IMPROVED"})
    assert [r["hotkey"] for r in lb.ladder_rows([odd, good])] == [_hotkey(1)]
    assert lb.ladder_rows([(_hotkey(2, 46), {"total": 0.5}, {"status": "IMPROVED"})])
    bad_check = {**_check(3), "hotkey": "rtsk_" + "a" * 64}
    assert lb.crown_checks_checked([bad_check, _check(4)]) == [_check(4)]
    bad_change = {**_change(5), "to_hotkey": "<script>"}
    assert lb.crown_changes_checked([bad_change]) == []
    board, _signer, trust = _signed([odd, good])
    assert [r["hotkey"] for r in board["ladder"]] == [_hotkey(1)]
    feed.project(board, trust)


# --- item 6: the queue rows ---


class _View:
    def __init__(self, snapshot):
        self.value = snapshot

    def snapshot_v3(self):
        return self.value


def _queue_snapshot(count):
    from test_queue_rows import _row, _rows_snapshot

    return _rows_snapshot([_row(i + 1) for i in range(count)])


def test_a_long_queue_keeps_its_first_rows_and_counts_the_rest(monkeypatch):
    from test_queue_public import CHALLENGE

    full_status, full = queue_public.serve_v3(_View(_queue_snapshot(200)), CHALLENGE)
    assert full_status == 200 and len(full["rows"]) == 200
    size = len(json.dumps(full, sort_keys=True, separators=(",", ":")))
    limit = size // 2
    monkeypatch.setattr(queue_public, "MAX_BYTES_V3", limit)
    status, body = queue_public.serve_v3(_View(_queue_snapshot(200)), CHALLENGE)
    assert status == 200
    kept = len(body["rows"])
    assert 0 < kept < 200 and body["more_rows"] == 200 - kept
    assert body["rows"] == full["rows"][:kept]
    assert len(json.dumps(body, sort_keys=True, separators=(",", ":"))) <= limit
    one_more = {**body, "rows": full["rows"][: kept + 1], "more_rows": 199 - kept}
    assert len(json.dumps(one_more, sort_keys=True, separators=(",", ":"))) > limit
    # only a document that cannot fit even with no rows is still unavailable
    monkeypatch.setattr(queue_public, "MAX_BYTES_V3", 64)
    assert queue_public.serve_v3(_View(_queue_snapshot(200)), CHALLENGE)[0] == 503


# --- item 7: door replies in the clients ---


def test_the_clients_read_a_door_reply_up_to_one_mib():
    from carbon.battery import intake_client
    from carbon.challenge_validator import receiver_setup
    from carbon.development_session import direct_submission

    for module in (intake_client, receiver_setup, direct_submission):
        assert module.REPLY_READ_BYTES == 1024 * 1024
        source = pathlib.Path(module.__file__).read_text(encoding="utf-8")
        assert "read(65536)" not in source, module.__name__


# --- item 8: the pack check's read bounds ---


def test_the_pack_check_reads_to_the_registered_material_size():
    source = (ROOT / "carbon/challenge_validator/direct_receiver.py").read_text(
        encoding="utf-8"
    )
    assert 'max_bytes=max(1, len(material["train"]))' in source
    assert "max_bytes=max(65536, 8 * len(canonical(document)))" in source
    assert "max_bytes=16 * 1024 * 1024" not in source
