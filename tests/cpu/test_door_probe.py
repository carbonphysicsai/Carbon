"""door_probe.py: the rehearsal client's own evidence rules (no door, no chain)."""

from __future__ import annotations

import hashlib
import http.server
import json
import threading
from pathlib import Path
from typing import ClassVar

import pytest

from carbon.miner_agent import MINER_USER_AGENT
from scripts.dev.miner_launchpad import door_probe as dp

ROOT = Path(__file__).resolve().parents[2]


class _Door(http.server.BaseHTTPRequestHandler):
    status = 200
    agents: ClassVar[list] = []

    def do_GET(self):
        type(self).agents.append(self.headers.get("User-Agent"))
        body = json.dumps({"schema": "x.v1", "path": self.path}).encode()
        self.send_response(type(self).status)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


@pytest.fixture()
def door():
    _Door.status, _Door.agents = 200, []
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), _Door)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_port}"
    server.shutdown()


def _probe(door, out, *extra):
    return dp.main(
        [
            "probe",
            "--door",
            door,
            "--challenge",
            "c1",
            "--rate",
            "20",
            "--baseline-s",
            "0.5",
            "--duration-s",
            "0.5",
            "--out",
            str(out),
            *extra,
        ]
    )


def test_user_agent_matches_the_miner_agent():
    assert dp.user_agent() == MINER_USER_AGENT


def test_routes_cover_every_public_read():
    assert [p for _, p in dp.routes("c1")] == [
        "/carbon/v1/feed/c1",
        "/carbon/v1/koth/c1",
        "/carbon/v1/koth/c1/v2",
        "/carbon/v1/construction/intake",
        "/carbon/v1/queue/c1",
    ]
    assert "queue" not in dict(dp.routes("c1", queue=False))


def test_pass_run_writes_sealed_evidence_without_bodies(door, tmp_path):
    out = tmp_path / "run"
    assert _probe(door, out) == 0
    summary = json.loads((out / "summary.json").read_text())
    assert summary["verdict"] == "PASS" and summary["non_200"] == {}
    assert summary["baseline"]["requests"] > 0 and summary["window"]["requests"] > 0
    assert (out / dp.BASELINE_OK).exists()
    rows = [json.loads(x) for x in (out / "requests.jsonl").read_text().splitlines()]
    assert {r["route"] for r in rows} == {"feed", "koth", "koth_v2", "intake", "queue"}
    assert all(
        "path" not in json.dumps(r) for r in rows
    )  # schema + digest only, never the body
    assert all(r["schema"] == "x.v1" and len(r["body_sha256"]) == 64 for r in rows)
    sums = dict(
        reversed(line.split("  "))
        for line in (out / "SHA256SUMS").read_text().splitlines()
    )
    for name, digest in sums.items():
        assert hashlib.sha256((out / name).read_bytes()).hexdigest() == digest
    assert (
        summary["probe_sha256"]
        == hashlib.sha256(Path(dp.__file__).read_bytes()).hexdigest()
    )
    assert set(_Door.agents) == {MINER_USER_AGENT}


def test_non_200_at_baseline_aborts_before_the_swap(door, tmp_path):
    _Door.status = 503
    out = tmp_path / "run"
    assert _probe(door, out) == 3
    summary = json.loads((out / "summary.json").read_text())
    assert summary["verdict"] == "ABORTED_BASELINE" and "window" not in summary
    assert not (out / dp.BASELINE_OK).exists()


def test_window_counts_gaps_and_non_200():
    rows = [
        {"route": "feed", "status": 200, "latency_ms": 5, "done_s": 0.4},
        {"route": "koth", "status": 503, "latency_ms": 9, "done_s": 0.9},
        {"route": "feed", "status": 200, "latency_ms": 7, "done_s": 2.6},
    ]
    stats = dp.window_stats(rows, 0.0, 3.0)
    assert stats["non_200"] == {"koth": 1}
    assert [g["seconds"] for g in stats["gaps_over_1s"]] == [2.2]
    assert stats["max_latency_ms"] == 9 and stats["statuses"] == {"200": 2, "503": 1}


def test_no_success_at_all_is_one_whole_window_gap():
    assert dp.window_stats([], 0.0, 5.0)["max_gap_s"] == 5.0


def test_stop_file_ends_the_window(door, tmp_path):
    out = tmp_path / "run"
    seen = []

    def stop():
        seen.append(1)
        return len(seen) > 3

    stats = dp.run_phase(
        door, dp.routes("c1"), 50, 60, dp.Recorder(tmp_path / "r.jsonl"), "w", stop=stop
    )
    assert stats["requests"] <= 4
    assert not out.exists()


def test_limits_are_read_from_the_served_code_not_typed():
    pytest.importorskip("fcntl")  # carbon.battery.intake is Linux-only
    limits = dp.served_limits(ROOT)
    from carbon.battery import intake

    assert (limits["peer_burst"], limits["peer_rate_per_s"], limits["in_flight"]) == (
        intake.PEER_BURST,
        intake.PEER_RATE,
        intake.IN_FLIGHT,
    )
    assert limits["local_hop_gets_uncharged"] is True
    assert set(limits["source"]) == {
        "carbon/battery/intake.py",
        "carbon/challenge_validator/direct_intake.py",
    }


def test_signed_modes_refuse_off_localnet(monkeypatch):
    monkeypatch.delenv("CARBON_CHAIN_NETWORK", raising=False)
    with pytest.raises(SystemExit):
        dp._require_localnet()
    assert dp._require_localnet(live_door=True) == "testnet"
    monkeypatch.setenv("CARBON_CHAIN_NETWORK", "localnet")
    assert dp._require_localnet() == "localnet"


def test_r13_needs_both_hotkeys(tmp_path):
    with pytest.raises(SystemExit):
        dp.main(
            [
                "probe",
                "--door",
                "http://127.0.0.1:1",
                "--challenge",
                "c",
                "--out",
                str(tmp_path / "o"),
                "--r13-recipe",
                "x.json",
            ]
        )


def test_synthetic_document_is_named_by_its_digest():
    name, body = dp.synthetic_document("a", 20000)
    assert len(body) == 20000
    assert name == "level4-doc-" + hashlib.sha256(body).hexdigest() + ".json"
    from carbon.level4 import staging

    assert name.startswith(staging.WORKSPACE_PREFIX)
    assert dp.synthetic_document("a", 20000) == (name, body)
    assert dp.synthetic_document("b", 20000)[1] != body


def test_r13_outcomes_are_closed(monkeypatch):
    from carbon.development_session import direct_submission as ds

    class _R:
        digest = "sha256:" + "0" * 64

    seen = {}

    def fake(url, signer, *, read, **kw):
        seen["facts"] = read(url)
        raise outcome

    monkeypatch.setattr(ds, "submit_and_wait", fake)
    for outcome, want in (
        (ds.DirectConstructionPending("t1"), {"outcome": "admitted", "code": None}),
        (
            ds.DirectSameRecipeSubmitted({}),
            {"outcome": "same_recipe_already_submitted", "code": None},
        ),
        (
            ds.DirectIntakeRefusal("snapshot_unknown"),
            {"outcome": "refused", "code": "snapshot_unknown"},
        ),
    ):
        got = dp.r13_resubmit(
            "http://127.0.0.1:1",
            None,
            recipe=_R(),
            contract_digest="d",
            receiver="r",
            context=None,
            facts_before={"old": 1},
            root=Path("."),
            send=None,
        )
        assert got == want
        assert seen["facts"] == {"old": 1}  # the body is built from OLD's facts


def _client(tmp_path, name, role, rate, posts, start, end):
    d = tmp_path / name
    d.mkdir()
    (d / "requests.jsonl").write_text(
        "".join(json.dumps({"route": "post", **p}) + "\n" for p in posts)
    )
    (d / "summary.json").write_text(
        json.dumps(
            {
                "client": name,
                "role": role,
                "rate": rate,
                "start_utc": dp.utc(start),
                "end_utc": dp.utc(end),
                "status_429": sum(p["status"] == 429 for p in posts),
                "status_503": 0,
                "spoofed_header": None,
                "result": {},
            }
        )
    )
    return d


def test_merge_attributes_429s_to_the_upload_window(tmp_path):
    up = _client(
        tmp_path, "up", "upload", None, [{"status": 200, "done_s": 101.0}], 100.0, 200.0
    )
    a = _client(
        tmp_path,
        "a",
        "feedback",
        0.5,
        [{"status": 429, "done_s": 150.0}, {"status": 200, "done_s": 250.0}],
        90.0,
        260.0,
    )
    b = _client(
        tmp_path, "b", "feedback", 0.5, [{"status": 200, "done_s": 150.0}], 90.0, 260.0
    )
    merged = dp.merge([up, a, b])
    assert merged["clients"]["a"]["status_429_during_upload"] == 1
    assert merged["honest_client_429_during_upload"] is True
    assert merged["honest_clients_zero_429"] is False
    fixed = dp.merge([up, b])
    assert (
        fixed["honest_client_429_during_upload"] is False
        and fixed["honest_clients_zero_429"] is True
    )
