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

    koth_refusal: ClassVar[str | None] = None

    def do_GET(self):
        type(self).agents.append(self.headers.get("User-Agent"))
        status = type(self).status
        body = json.dumps({"schema": "x.v1", "path": self.path}).encode()
        if type(self).koth_refusal and self.path.startswith("/carbon/v1/koth/"):
            status, body = (
                404,
                json.dumps({"refused": type(self).koth_refusal}).encode(),
            )
        self.send_response(status)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


@pytest.fixture()
def door():
    _Door.status, _Door.agents, _Door.koth_refusal = 200, [], None
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


def test_r13_outcomes_are_closed(monkeypatch, tmp_path):
    from carbon.development_session import direct_submission as ds

    class _R:
        digest = "sha256:" + "0" * 64

    seen = {}

    def fake(url, signer, *, read, root, **kw):
        assert root.is_dir()  # the ledger exists before an admission writes into it
        seen["facts"] = [read(url), read(url)]  # a retry after a 429 reads again
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
        assert (
            seen["facts"] == [{"old": 1}] * 2
        )  # every attempt is built on OLD's facts


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


def test_only_the_earlier_grade_is_an_r13_pass():
    assert dp.ACCEPTED_R13 == ("same_recipe_already_submitted",)


def test_stop_during_the_baseline_does_not_end_it_or_pass(door, tmp_path, monkeypatch):
    out = tmp_path / "run"
    real = dp.run_phase

    def early_stop(*args, **kwargs):
        if args[5] == "baseline":
            (out / dp.STOP).write_text("")  # the operator writes STOP too early
        return real(*args, **kwargs)

    monkeypatch.setattr(dp, "run_phase", early_stop)
    assert _probe(door, out) == 1
    summary = json.loads((out / "summary.json").read_text())
    assert summary["baseline"]["requests"] > 0  # the baseline ran in full
    assert summary["window"]["requests"] == 0 and summary["verdict"] == "FAIL"


def test_an_r13_worker_that_records_nothing_is_a_failed_run(
    door, tmp_path, monkeypatch
):
    monkeypatch.setattr(
        dp, "_r13_thread", lambda *args: None
    )  # the worker ends without a result
    out = tmp_path / "run"
    argv = ["--r13-recipe", "r.json", "--hotkey", "h", "--receiver-hotkey", "r"]
    assert _probe(door, out, *argv) == 1
    summary = json.loads((out / "summary.json").read_text())
    assert summary["r13"] == {"outcome": "probe_error", "code": "no_result"}
    assert summary["verdict"] == "FAIL"


def test_a_door_with_no_king_yet_is_the_expected_state_not_a_fault(door, tmp_path):
    _Door.koth_refusal = "koth_unpublished"  # staging, or a new version's first start
    out = tmp_path / "run"
    assert _probe(door, out) == 0
    summary = json.loads((out / "summary.json").read_text())
    assert summary["verdict"] == "PASS" and summary["non_200"] == {}
    assert set(summary["window"]["expected"]) == {"koth", "koth_v2"}
    rows = [json.loads(x) for x in (out / "requests.jsonl").read_text().splitlines()]
    assert {r["refused"] for r in rows if r["route"] == "koth"} == {"koth_unpublished"}


def test_any_other_king_refusal_still_aborts(door, tmp_path):
    _Door.koth_refusal = "koth_unavailable"
    assert _probe(door, tmp_path / "run") == 3


def test_routes_picks_a_subset_and_refuses_unknown_names(door, tmp_path):
    out = tmp_path / "run"
    assert _probe(door, out, "--routes", "feed,intake") == 0
    rows = [json.loads(x) for x in (out / "requests.jsonl").read_text().splitlines()]
    assert {r["route"] for r in rows} == {"feed", "intake"}
    with pytest.raises(SystemExit):
        _probe(door, tmp_path / "bad", "--routes", "feed,kingdom")


# ---------------------------------------------------------------- fresh (S1)


def test_fresh_recipes_are_new_per_client_and_per_run_and_valid():
    from carbon.battery import direct_graph

    a, rate_a = dp.fresh_recipe(123456, 0)
    b, _ = dp.fresh_recipe(123456, 1)
    c, _ = dp.fresh_recipe(123457, 0)
    assert len({a.digest, b.digest, c.digest}) == 3
    assert dp.fresh_recipe(123456, 0)[0].digest == a.digest
    assert abs(rate_a / dp.FRESH_BASE_RATE - 1) <= 1e-4
    # Battery's own training check accepts it, at the moved rate.
    assert direct_graph.training_settings(a)["learning_rate"] == rate_a
    challenge = a.to_dict()["challenge"]
    assert (challenge["id"], challenge["version"]) == dp.FRESH_CHALLENGE


def test_fresh_needs_two_named_clients():
    for specs in (
        ["bob=5B"],
        ["bob=5B", "bob=5C"],
        ["Bob=5B", "c=5C"],
        ["bob", "c=5C"],
    ):
        with pytest.raises(SystemExit):
            dp.fresh_clients(specs)
    assert dp.fresh_clients(["bob=5B", "charlie=5C"]) == [
        ("bob", "5B"),
        ("charlie", "5C"),
    ]


class _Clock:
    def __init__(self):
        self.t = 1_000_000.0

    def __call__(self):
        return self.t

    def sleep(self, s):
        self.t += s


def _fresh(monkeypatch, tmp_path, *, built=None, raises=None, grades=(), wait_s=600):
    from carbon.development_session import direct_submission as ds

    clock = _Clock()
    calls = {"stage": 0, "go": 0, "feedback": 0}
    monkeypatch.setattr(
        dp,
        "stage_scaffold",
        lambda *a, **k: calls.__setitem__("stage", calls["stage"] + 1) or 3,
    )

    def submit(url, signer, *, root, wait_s, **kw):
        assert root.is_dir()
        assert calls["go"] == 1  # every client submits only after the shared start
        if raises is not None:
            raise raises
        return built

    def feedback(url, signer, *, submission_id, **kw):
        assert submission_id == built["task_id"]
        calls["feedback"] += 1
        reply = grades[min(calls["feedback"], len(grades)) - 1]
        return reply

    monkeypatch.setattr(ds, "submit_and_wait", submit)
    monkeypatch.setattr(ds, "read_exam_feedback", feedback)

    class _R:
        digest = "sha256:" + "ab" * 32

    row = dp.fresh_client(
        "http://127.0.0.1:1",
        None,
        recipe=_R(),
        contract="d",
        receiver="r",
        context=None,
        root=tmp_path / "ledger",
        read=None,
        send=None,
        wait_s=wait_s,
        poll_s=30,
        go=lambda: calls.__setitem__("go", calls["go"] + 1),
        clock=clock,
        sleep=clock.sleep,
    )
    return row, calls


def _sub(state, failure=None):
    reply = {"submission": {"submission_id": "t1", "grade_state": state}}
    if failure:
        reply["failure"] = {"code": failure}
    return reply


_BUILT = {"task_id": "t1", "state": "RECONSTRUCTED"}


def test_fresh_client_follows_the_build_then_the_grade(monkeypatch, tmp_path):
    row, calls = _fresh(
        monkeypatch,
        tmp_path,
        built=_BUILT,
        grades=[_sub("QUEUED"), _sub(None), _sub("GRADED")],
    )
    assert row["outcome"] == "graded" and row["grade_state"] == "GRADED"
    assert row["task_id"] == "t1" and row["build_state"] == "RECONSTRUCTED"
    assert calls == {"stage": 1, "go": 1, "feedback": 3}
    assert row["seconds"] == 60.0  # two 30 s polls


def test_fresh_crown_hold_counts_as_graded(monkeypatch, tmp_path):
    row, _ = _fresh(
        monkeypatch, tmp_path, built=_BUILT, grades=[_sub("CROWN_HELD_FOR_REVIEW")]
    )
    assert row["outcome"] == "graded"


@pytest.mark.parametrize(
    "grade, failure, code",
    [
        ("FAILED_INFRA", None, "FAILED_INFRA"),
        ("NOT_GRADED", None, "NOT_GRADED"),
        ("CANDIDATE_FAILED", "WORKER_WALL_LIMIT_REACHED", "WORKER_WALL_LIMIT_REACHED"),
    ],
)
def test_fresh_grade_failures_fail_with_their_code(
    monkeypatch, tmp_path, grade, failure, code
):
    row, _ = _fresh(monkeypatch, tmp_path, built=_BUILT, grades=[_sub(grade, failure)])
    assert row["outcome"] == "grade_failed"
    assert row["code"] == code and row["grade_state"] == grade


def test_fresh_build_failure_fails_with_its_code(monkeypatch, tmp_path):
    built = {"task_id": "t1", "state": "FAILED_INFRA", "failure": {"code": "x_infra"}}
    row, calls = _fresh(monkeypatch, tmp_path, built=built)
    assert row["outcome"] == "build_failed" and row["code"] == "x_infra"
    assert calls["feedback"] == 0


def test_fresh_no_grade_by_the_deadline_is_not_terminal(monkeypatch, tmp_path):
    row, calls = _fresh(
        monkeypatch, tmp_path, built=_BUILT, grades=[_sub("QUEUED")], wait_s=100
    )
    assert row["outcome"] == "not_terminal" and row["stage"] == "grade"
    assert calls["feedback"] == 4  # t = 0, 30, 60, 90; a fifth would pass 100 s


def test_fresh_a_receiver_without_the_per_submission_read_is_not_a_pass(
    monkeypatch, tmp_path
):
    row, _ = _fresh(
        monkeypatch, tmp_path, built=_BUILT, grades=[{"best": None, "latest": None}]
    )
    assert row["outcome"] == "grade_unreadable"


def test_fresh_refusals_are_closed(monkeypatch, tmp_path):
    from carbon.development_session import direct_submission as ds

    for raised, want in (
        (
            ds.DirectConstructionPending("t9"),
            {"outcome": "not_terminal", "task_id": "t9"},
        ),
        (
            ds.DirectSameRecipeSubmitted({}),
            {"outcome": "refused", "code": "same_recipe_already_submitted"},
        ),
        (
            ds.DirectIntakeRefusal("construction_intake_unavailable"),
            {"outcome": "refused", "code": "construction_intake_unavailable"},
        ),
        (RuntimeError("boom"), {"outcome": "probe_error", "code": "RuntimeError"}),
    ):
        row, _ = _fresh(monkeypatch, tmp_path, raises=raised)
        assert {k: row.get(k) for k in want} == want


def test_fresh_passes_only_when_every_client_is_graded_on_its_own_task():
    clients = [("bob", "5B"), ("charlie", "5C")]
    ok = {
        "bob": {"outcome": "graded", "task_id": "t1"},
        "charlie": {"outcome": "graded", "task_id": "t2"},
    }
    assert dp.fresh_verdict(clients, ok) == ("PASS", True)
    same = {**ok, "charlie": {"outcome": "graded", "task_id": "t1"}}
    assert dp.fresh_verdict(clients, same) == ("FAIL", False)
    failed = {**ok, "charlie": {"outcome": "grade_failed", "task_id": "t2"}}
    assert dp.fresh_verdict(clients, failed)[0] == "FAIL"
    assert dp.fresh_verdict(clients, {"bob": ok["bob"]})[0] == "FAIL"


def test_fresh_refuses_off_localnet(monkeypatch, tmp_path):
    monkeypatch.delenv("CARBON_CHAIN_NETWORK", raising=False)
    with pytest.raises(SystemExit):
        dp.main(
            [
                "fresh",
                "--door",
                "http://127.0.0.1:1",
                "--client",
                "bob=5B",
                "--client",
                "charlie=5C",
                "--receiver-hotkey",
                "5R",
                "--out",
                str(tmp_path / "o"),
            ]
        )
