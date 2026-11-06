"""OWNER-DASHBOARD-01: the Worker reads a launch board as launch.py does.

The public Cloudflare path projects the launch Challenges' signed standing in JavaScript
(carbon/dashboard/worker/feed.mjs, `projectLaunch`) so the board stays live without
redeploys. These tests hold it equal to `feed.project` / `board_v2.project` on every
accepted board and every refusal, in the bytes the operator uploads, and check the
Worker's fail-closed serving: a refused launch board keeps the last built board.
"""

from __future__ import annotations

import copy
import datetime
import json
import os
import shutil

import pytest

from carbon.challenge_validator import launch_board as lb
from carbon.challenge_validator.score_feed import FeedKey
from carbon.dashboard import board_v2, feed, launch
from tests.cpu import test_dashboard_worker as base

NODE = shutil.which("node")
pytestmark = pytest.mark.skipif(NODE is None, reason="node is not installed here")

KING = "5F3sa2TJAWMqDhXG6jhV4N8ko9SxwGy8TpaNS1repo5EYjQX"
OTHER = "5DAAnrj7VHTznn2AWBemMuyBwZWs6FNFjdyVXUeYum3PTXFy"
THIRD = "5HGjWAeFDfFCWGSSAdJNNnvVcMB5dAPa3QCVq4NJTfYfmfZZ"
NOW = 1_800_000_000
WHEN = datetime.datetime.fromtimestamp(NOW, datetime.UTC)


def _row(hotkey, total, status="IMPROVED", gates=()):
    def document(kind_status, shown):
        return {
            "schema": "carbon.private-exam.ladder-feedback.v2",
            "exam_version": "motor-exam-1",
            "status": kind_status,
            "total": shown,
            "gate_names": list(gates),
        }

    best = None if total is None else document("IMPROVED", total)
    return (hotkey, best, document(status, total))


def _king(king=True, margin=0.02):
    return {
        "schema": "carbon.koth.public.v1",
        "challenge_id": "electric-motor-magnetics",
        "challenge_version": "1.4",
        "exam_version_label": "motor-exam-1",
        "king": {"hotkey": KING, "total": 0.64, "since_epoch": 7} if king else None,
        "margin": margin,
        "to_beat": 0.66 if king else None,
        "baseline_total": None if king else 0.3,
    }


def _boards(signer):
    graded = [
        _row(KING, 0.64),
        _row(OTHER, 0.5, "NO_IMPROVEMENT"),
        _row(THIRD, None, "GATE_FAILED", gates=("native_motor_valid",)),
    ]
    out = {
        "empty": lb.build(
            king_document=_king(False),
            rows=[],
            network="testnet",
            key=signer,
            version=1,
            now=WHEN,
        ),
        "graded": lb.build(
            king_document=_king(),
            rows=graded,
            network="testnet",
            key=signer,
            version=2,
            now=WHEN,
        ),
        "no_king_but_scored": lb.build(
            king_document=_king(False, margin=None),
            rows=[_row(OTHER, 0.34)],
            network="testnet",
            key=signer,
            version=3,
            now=WHEN,
        ),
        "wide_steps": lb.build(
            king_document={**_king(), "margin": 0.037},
            rows=[_row(KING, 0.64), _row(OTHER, 0.607)],
            network="testnet",
            key=signer,
            version=4,
            now=WHEN,
        ),
    }
    return out


def _resign(signer, body):
    body = {k: v for k, v in body.items() if k != "signature"}
    return {**body, "signature": signer.sign(body)}


def _variants(signer, boards):
    out = [(name, board) for name, board in boards.items()]
    graded = boards["graded"]

    def edit(name, change):
        body = copy.deepcopy(graded)
        change(body)
        out.append((name, _resign(signer, body)))

    edit("extra_field", lambda b: b.__setitem__("operator_note", "x"))
    edit("extra_ladder_key", lambda b: b["ladder"][0].__setitem__("accuracy", 0.5))
    edit("extra_king_key", lambda b: b["king"].__setitem__("case_errors", [1]))
    edit("counts", lambda b: b["counts"].__setitem__("graded", 9))
    edit("labels_fixture", lambda b: b["labels"].append("FIXTURE"))
    edit("over_one", lambda b: b["ladder"][0].__setitem__("total", 1.5))
    edit("unrounded", lambda b: b["ladder"][0].__setitem__("total", 0.123456789123))
    edit("rank_float", lambda b: b["ladder"][0].__setitem__("rank", 1.0))
    edit("gates_on_scored", lambda b: b["ladder"][0].__setitem__("gate_names", ["x"]))
    edit("bad_hotkey", lambda b: b["ladder"][0].__setitem__("hotkey", "5short"))
    edit("duplicate_hotkey", lambda b: b["ladder"][1].__setitem__("hotkey", KING))
    edit("version_zero", lambda b: b.__setitem__("version", 0))
    edit("bad_time", lambda b: b.__setitem__("generated_at", "yesterday"))
    edit(
        "exam_label_markup",
        lambda b: b["challenge"].__setitem__("exam_version_label", "<b>x"),
    )
    edit("network", lambda b: b.__setitem__("network", "localnet"))

    def crown(to, frm, epoch, total):
        return {
            "from_hotkey": frm,
            "to_hotkey": to,
            "since_epoch": epoch,
            "total": total,
        }

    def v2(name, changes, *, signed_under=launch.DOMAIN_V2, mutate=None):
        body = {k: v for k, v in copy.deepcopy(graded).items() if k != "signature"}
        body["schema"] = launch.SCHEMA_V2
        body["king"]["to_beat_rule"] = launch.TO_BEAT_RULE
        if changes is not None:
            body["crown_changes"] = changes
        if mutate:
            mutate(body)
        signature = signer._key.sign(signed_under + lb._canonical(body).encode())
        out.append((name, {**body, "signature": signature.hex()}))

    two = [crown(KING, OTHER, 9, 0.64), crown(OTHER, None, 4, 0.5)]
    v2("v2_two", two)
    v2("v2_empty", [])
    v2("v2_five", [crown(KING, OTHER, 9 - i, 0.64) for i in range(5)])
    v2("v2_six", [crown(KING, OTHER, 9 - i, 0.64) for i in range(6)])
    v2("v2_missing_field", None)
    v2("v2_extra_entry_key", [{**two[0], "submission": "rtsk_x"}])
    v2("v2_bad_from", [crown(KING, "5short", 9, 0.64)])
    v2("v2_negative_epoch", [crown(KING, OTHER, -1, 0.64)])
    v2("v2_float_epoch", [crown(KING, OTHER, 9.0, 0.64)])
    v2("v2_total_over_one", [crown(KING, OTHER, 9, 1.5)])
    v2("v2_total_unrounded", [crown(KING, OTHER, 9, 0.123456789123)])
    v2("v2_signed_under_v1_domain", two, signed_under=launch.DOMAIN)
    v2("v2_no_rule", two, mutate=lambda b: b["king"].pop("to_beat_rule"))
    v2(
        "v2_wrong_rule",
        two,
        mutate=lambda b: b["king"].__setitem__("to_beat_rule", "ceil"),
    )

    def co_rank(b):  # a bit-equal challenger shares rank 1 with the king
        for row in b["ladder"]:
            row["rank"] = 1

    v2("v2_co_rank", two, mutate=co_rank)
    # crown averaging on (Lead 5 Nov): the averaged bar's own rule, read by both and passed to the page
    v2(
        "v2_averaged_rule",
        two,
        mutate=lambda b: b["king"].__setitem__(
            "to_beat_rule", launch.TO_BEAT_RULE_AVERAGED
        ),
    )

    def v3(name, stability, *, signed_under=launch.DOMAIN_V3, mutate=None):
        body = {k: v for k, v in copy.deepcopy(graded).items() if k != "signature"}
        body["schema"] = launch.SCHEMA_V3
        body["king"]["to_beat_rule"] = launch.TO_BEAT_RULE
        body["king"]["stability"] = stability
        body["crown_changes"] = two
        if mutate:
            mutate(body)
        signature = signer._key.sign(signed_under + lb._canonical(body).encode())
        out.append((name, {**body, "signature": signature.hex()}))

    v3("v3_unstable", "UNSTABLE")
    v3(
        "v3_averaged_rule",
        "STABLE",
        mutate=lambda b: b["king"].__setitem__(
            "to_beat_rule", launch.TO_BEAT_RULE_AVERAGED
        ),
    )
    v3("v3_stable", "STABLE")
    v3("v3_bad_value", "OTHER")
    v3("v3_king_without_stability", None)
    v3("v3_signed_under_v2_domain", "UNSTABLE", signed_under=launch.DOMAIN_V2)
    v3("v3_missing_field", "UNSTABLE", mutate=lambda b: b["king"].pop("stability"))
    v3(
        "v3_extra_king_key",
        "UNSTABLE",
        mutate=lambda b: b["king"].__setitem__("mean", 0.7),
    )
    measured = {"state": "MEASURED", "kept": 10, "n": 10}
    checks = [
        {
            "hotkey": OTHER,
            "state": "DECIDED",
            "outcome": "INCUMBENT_KEEPS",
            "note": "the king keeps the crown",
        },
        {
            "hotkey": THIRD,
            "state": "PENDING",
            "outcome": "UNAVAILABLE",
            "note": "waiting for the king's re-measure",
        },
    ]

    def v4(
        name,
        stability,
        measure,
        crown_checks,
        *,
        signed_under=launch.DOMAIN_V4,
        mutate=None,
    ):
        body = {k: v for k, v in copy.deepcopy(graded).items() if k != "signature"}
        body["schema"] = launch.SCHEMA_V4
        body["king"]["to_beat_rule"] = launch.TO_BEAT_RULE_AVERAGED
        body["king"]["stability"] = stability
        body["king"]["measure"] = measure
        body["crown_changes"] = two
        body["crown_checks"] = crown_checks
        if mutate:
            mutate(body)
        signature = signer._key.sign(signed_under + lb._canonical(body).encode())
        out.append((name, {**body, "signature": signature.hex()}))

    v4("v4_measured", "STABLE", measured, checks)
    v4("v4_in_progress", None, {"state": "IN_PROGRESS", "kept": 3, "n": 10}, checks)
    v4("v4_unmeasured", None, {"state": "UNMEASURED", "kept": 0, "n": 10}, [])
    v4("v4_unstable", "UNSTABLE", {"state": "UNSTABLE", "kept": 7, "n": 10}, checks)
    v4(
        "v4_stability_disagrees",
        "STABLE",
        {"state": "IN_PROGRESS", "kept": 3, "n": 10},
        checks,
    )
    v4("v4_kept_over_n", None, {"state": "IN_PROGRESS", "kept": 11, "n": 10}, checks)
    v4("v4_measure_with_mean", "STABLE", {**measured, "mean": 0.7}, checks)
    v4("v4_pending_decided", "STABLE", measured, [{**checks[0], "state": "PENDING"}])
    v4("v4_bad_outcome", "STABLE", measured, [{**checks[0], "outcome": "CROWNED"}])
    v4("v4_bad_reason", "STABLE", measured, [{**checks[0], "note": "Has Spaces"}])
    v4(
        "v4_raw_reason",
        "STABLE",
        measured,
        [{**checks[0], "reason": "mean_within_margin_or_tie"}],
    )
    v4("v4_check_extra_key", "STABLE", measured, [{**checks[0], "seed": 3}])
    v4("v4_duplicate_check", "STABLE", measured, [checks[0], checks[0]])
    v4(
        "v4_signed_under_v3_domain",
        "STABLE",
        measured,
        checks,
        signed_under=launch.DOMAIN_V3,
    )
    v4(
        "v4_missing_checks",
        "STABLE",
        measured,
        checks,
        mutate=lambda b: b.pop("crown_checks"),
    )
    body = {k: v for k, v in copy.deepcopy(graded).items() if k != "signature"}
    signature = signer._key.sign(launch.DOMAIN_V2 + lb._canonical(body).encode())
    out.append(("v1_signed_under_v2_domain", {**body, "signature": signature.hex()}))
    tampered = copy.deepcopy(graded)
    tampered["ladder"][0]["total"] = 0.99
    out.append(("tampered", tampered))
    wrong_domain = FeedKey(os.urandom(32))
    body = {k: v for k, v in graded.items() if k != "signature"}
    out.append(
        ("feed_domain_signature", {**body, "signature": wrong_domain.sign(body)})
    )
    return out


def test_worker_matches_launch_py_on_every_board_and_refusal(tmp_path):
    signer = lb.LaunchBoardKey(os.urandom(32))
    key = signer.public_key
    trust = feed.Trust(keys=frozenset({key}))
    items, items_v2, expected, expected_v2 = [], [], [], []
    for name, document in _variants(signer, _boards(signer)):
        for indent in (None, 1):
            text = json.dumps(document, indent=indent)
            item = {"text": text, "fixture": False, "keys": [key]}
            items.append(item)
            expected.append((name, base._python(text, trust)))
            items_v2.append({**item, "now": NOW, "card": None})
            expected_v2.append((name, base._python_v2(text, trust, NOW, None)))
    got = base._node({"mode": "project", "items": items}, tmp_path)
    for (name, want), have in zip(expected, got, strict=True):
        assert have == want, name
    got_v2 = base._node({"mode": "project_v2", "items": items_v2}, tmp_path)
    for (name, want), have in zip(expected_v2, got_v2, strict=True):
        assert have == want, name
    codes = {name: want.get("code") for name, want in expected}
    assert codes["empty"] is None and codes["graded"] is None
    assert codes["v2_averaged_rule"] is None and codes["v3_averaged_rule"] is None
    for name in ("v4_measured", "v4_in_progress", "v4_unmeasured", "v4_unstable"):
        assert codes[name] is None, name
    for name in (
        "v4_stability_disagrees",
        "v4_kept_over_n",
        "v4_measure_with_mean",
        "v4_pending_decided",
        "v4_bad_outcome",
        "v4_bad_reason",
        "v4_raw_reason",
        "v4_check_extra_key",
        "v4_duplicate_check",
        "v4_signed_under_v3_domain",
        "v4_missing_checks",
    ):
        assert codes[name] is not None, name
    page = dict(expected_v2)["v4_in_progress"]["board"]["launch"]
    assert page["king_measure"] == {"state": "IN_PROGRESS", "kept": 3, "n": 10}
    assert [c["state"] for c in page["crown_checks"]] == ["DECIDED", "PENDING"]
    assert "crown_checks" not in dict(expected_v2)["v3_stable"]["board"]["launch"]
    assert codes["v2_wrong_rule"] == "king_invalid"
    shown = dict(expected_v2)
    assert (
        shown["v2_averaged_rule"]["board"]["launch"]["to_beat_rule"]
        == launch.TO_BEAT_RULE_AVERAGED
    )
    assert (
        "to_beat_rule" not in shown["v2_two"]["board"]["launch"]
    )  # the single-grade page data is unchanged
    assert codes["tampered"] == "signature_invalid"
    assert codes["feed_domain_signature"] == "signature_invalid"
    assert codes["extra_field"] == "board_fields"
    assert codes["extra_ladder_key"] == "ladder_invalid"
    assert codes["unrounded"] == "total_unrounded"
    assert codes["counts"] == "counts_invalid"
    for ok in ("v2_two", "v2_empty", "v2_five"):
        assert codes[ok] is None, ok
    for bad in (
        "v2_six",
        "v2_extra_entry_key",
        "v2_bad_from",
        "v2_negative_epoch",
        "v2_float_epoch",
        "v2_total_over_one",
    ):
        assert codes[bad] == "crown_changes_invalid", bad
    assert codes["v2_missing_field"] == "board_fields"
    assert codes["v2_total_unrounded"] == "total_unrounded"
    assert codes["v2_signed_under_v1_domain"] == "signature_invalid"
    assert (
        codes["v2_no_rule"] == "board_fields" or codes["v2_no_rule"] == "king_invalid"
    )
    assert codes["v2_wrong_rule"] == "king_invalid"
    assert codes["v2_co_rank"] is None
    assert codes["v1_signed_under_v2_domain"] == "signature_invalid"
    for ok in ("v3_unstable", "v3_stable"):
        assert codes[ok] is None, ok
    for bad in (
        "v3_bad_value",
        "v3_king_without_stability",
        "v3_missing_field",
        "v3_extra_king_key",
    ):
        assert codes[bad] == "king_invalid", bad
    assert codes["v3_signed_under_v2_domain"] == "signature_invalid"
    flags = {
        n: w["board"]["launch"].get("king_stability")
        for n, w in expected_v2
        if "board" in w
    }
    assert (
        flags["v3_unstable"] == "UNSTABLE"
        and flags["v3_stable"] == "STABLE"
        and flags["v2_two"] is None
        and flags["graded"] is None
    )
    # a board that is accepted projects to the launch phases
    phases = {
        name: want["board"]["phase"] for name, want in expected_v2 if "board" in want
    }
    assert phases["empty"] == "PRE_FIRST_RELEASE" and phases["graded"] == "LIVE"
    graded = next(w["board"] for n, w in expected_v2 if n == "graded")
    assert graded["launch"]["counts"]["graded"] == 3
    # a v1 board carries no history; a v2 board carries it as the validator signed it, newest first
    assert "crown_changes" not in graded["launch"]
    two = next(w["board"] for n, w in expected_v2 if n == "v2_two")
    assert [c["since_epoch"] for c in two["launch"]["crown_changes"]] == [9, 4]
    assert two["launch"]["crown_changes"][1]["from_hotkey"] is None
    empty = next(w["board"] for n, w in expected_v2 if n == "v2_empty")
    assert empty["launch"]["crown_changes"] == []
    assert graded["eligible_leaderboard"]["label"] == board_v2.LAUNCH_LADDER_LABEL


def test_worker_refuses_the_wrong_key_and_a_fixture_trust_for_a_launch_board(tmp_path):
    signer = lb.LaunchBoardKey(os.urandom(32))
    document = _boards(signer)["graded"]
    text = json.dumps(document)
    other = FeedKey(os.urandom(32)).public_key
    fixture_key = feed.FIXTURE_PUBLIC_KEY
    items = [
        {"text": text, "fixture": False, "keys": [other]},
        {"text": text, "fixture": True, "keys": [fixture_key]},
    ]
    got = base._node({"mode": "project", "items": items}, tmp_path)
    assert got == [{"code": "signature_invalid"}, {"code": "fixture_launch_board"}]
    assert base._python(text, feed.Trust(keys=frozenset({other}))) == got[0]
    assert (
        base._python(text, feed.Trust(keys=frozenset({fixture_key}), fixture=True))
        == got[1]
    )


def test_worker_serves_a_launch_board_and_keeps_the_last_good_one(tmp_path):
    signer = lb.LaunchBoardKey(os.urandom(32))
    key = signer.public_key
    trust = feed.Trust(keys=frozenset({key}))
    boards = _boards(signer)
    site = base._site(tmp_path, [boards["graded"]], trust)
    slug = "electric-motor-magnetics--no-class"
    url = "https://validator.example/launch/motor"
    env = {"FEED_URLS": url, "FEED_KEYS": key, "CACHE_SECONDS": "0"}
    # the live board is the Worker's own projection of what the operator uploaded
    fresh = json.dumps(boards["wide_steps"])
    served = base._worker(
        tmp_path,
        site,
        env,
        {url: fresh},
        [f"/data/v2/{slug}.json", "/data/index.json"],
    )
    by_path = {r["path"]: r for r in served}
    v2 = json.loads(by_path[f"/data/v2/{slug}.json"]["body"])
    assert by_path[f"/data/v2/{slug}.json"]["status"] == 200
    assert v2["feed_state"]["state"] == "ACCEPTED" and v2["version"] == 4
    assert v2["launch"]["margin"] == 0.037
    # a refused newer board keeps the last built one, marked REFUSED with the reason
    (tmp_path / "kept").mkdir()
    broken = _resign(signer, {**boards["graded"], "operator_note": "x"})
    kept = base._worker(
        tmp_path / "kept",
        site,
        env,
        {url: json.dumps(broken)},
        [f"/data/v2/{slug}.json"],
    )
    (row,) = kept
    assert row["status"] == 200
    body = json.loads(row["body"])
    assert body["feed_state"] == {"state": "REFUSED", "code": "board_fields"}
    assert body["launch"]["counts"]["graded"] == 3
