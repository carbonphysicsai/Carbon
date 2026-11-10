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


def test_fresh_recipes_are_new_per_client_and_per_run_and_bound_to_the_contract():
    from carbon.reconstruction.served_recipe_contract import registered

    a, rate_a, entry, contract = dp.fresh_recipe("f02", "2.5", 123456, 0)
    b = dp.fresh_recipe("f02", "2.5", 123456, 1)[0]
    c = dp.fresh_recipe("f02", "2.5", 123457, 0)[0]
    assert len({a.digest, b.digest, c.digest}) == 3
    assert dp.fresh_recipe("f02", "2.5", 123456, 0)[0].digest == a.digest
    assert abs(rate_a / dp.FRESH_BASE_RATE - 1) <= 1e-4
    doc = a.to_dict()
    assert doc["source"]["catalog_id"] == entry
    assert doc["procedure"]["configuration"]["learning_rate"] == rate_a
    # The client-side check that refused the Battery-dev 1.0 scaffold (9 Nov).
    assert doc["challenge"] == registered("f02", "2.5").construction_kit
    assert contract == registered("f02", "2.5").digest


def test_fresh_refuses_a_version_without_a_catalog_before_signing():
    with pytest.raises(SystemExit, match="no catalog entry"):
        dp.fresh_recipe("battery-fastcharge-ageing-development-v1", "1.0", 1, 0)
    with pytest.raises(SystemExit, match="no catalog entry"):
        dp.fresh_recipe("f02", "2.5", 1, 0, catalog_id="no.such.entry")


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
    calls = {"go": 0, "feedback": 0}

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
    assert calls == {"go": 1, "feedback": 3}
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
                "--challenge",
                "f02",
                "--version",
                "2.5",
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


# ---------------------------------------------------------------- fresh --canary


def _root(
    base, name, port, *, state="receiver/state", network=None, challenge="f02", hk="5R"
):
    root = base / name
    (root / "receiver" / "state").mkdir(parents=True)
    cfg = {
        "host": "127.0.0.1",
        "port": port,
        "root": state,
        "challenge": {"id": challenge, "version": "2.5"},
        "receiver_hotkey": hk,
    }
    if network is not None:
        cfg["chain_network"] = network
    (root / "receiver" / "receiver.json").write_text(json.dumps(cfg), "utf-8")
    return root


@pytest.fixture()
def roots(tmp_path):
    spare = _root(tmp_path, "spare", 18871)
    live = _root(tmp_path, "live", 18771)

    def show(unit, prop):
        assert prop == "ExecStart"
        return "{ path=/x ; argv[]=/x --config %s ; }" % (
            spare / "receiver" / "receiver.json"
        )

    return spare, live, show


def _target(roots, door="http://127.0.0.1:18871", unit="carbon-spare.service", **kw):
    spare, live, show = roots
    return dp.canary_target(
        door,
        kw.get("spare", spare),
        kw.get("live", live),
        unit,
        challenge=kw.get("challenge", "f02"),
        receiver=kw.get("receiver", "5R"),
        show=kw.get("show", show),
    )


def _refused(code, call):
    with pytest.raises(dp.CanaryRefused) as refused:
        call()
    assert refused.value.code == code


def test_canary_target_accepts_only_the_prepared_spare(roots):
    assert _target(roots) == 18871


@pytest.mark.parametrize(
    "door",
    [
        "http://localhost:18871",
        "http://10.0.0.5:18871",
        "https://127.0.0.1:18871",
        "http://door.carbonphysics.ai:18871",
        "http://127.0.0.1",
        "http://127.0.0.1:18871/carbon/v1/mcp",
        "http://u:p@127.0.0.1:18871",
        "http://127.0.0.1:18871?x=1",
        "http://127.0.0.1:notaport",
    ],
)
def test_canary_refuses_anything_but_a_bare_loopback_url(roots, door):
    _refused("canary_target_not_loopback_spare_url", lambda: _target(roots, door=door))


@pytest.mark.parametrize("port", sorted(dp.LIVE_FRONT_PORTS))
def test_canary_refuses_every_live_front_port(roots, port):
    _refused(
        "canary_target_live_port",
        lambda: _target(roots, door=f"http://127.0.0.1:{port}"),
    )


def test_canary_refuses_the_live_roots_own_receiver_port(roots):
    _refused(
        "canary_target_live_port", lambda: _target(roots, door="http://127.0.0.1:18771")
    )


def test_canary_refuses_missing_roots(roots):
    _refused("canary_roots_required", lambda: _target(roots, spare=None))
    _refused("canary_roots_required", lambda: _target(roots, live=""))


def test_canary_refuses_a_spare_that_is_in_or_holds_the_live_root(roots, tmp_path):
    spare, live, _ = roots
    _refused("canary_spare_is_live_root", lambda: _target(roots, spare=live))
    inner = _root(live, "inner", 18871)
    _refused("canary_spare_is_live_root", lambda: _target(roots, spare=inner))
    _refused(
        "canary_spare_is_live_root", lambda: _target(roots, live=spare / "receiver")
    )


def test_canary_refuses_an_unreadable_receiver_config(roots, tmp_path):
    empty = tmp_path / "empty"
    empty.mkdir()
    _refused("canary_receiver_config_unreadable", lambda: _target(roots, spare=empty))


def test_canary_refuses_a_spare_not_serving_that_port(roots):
    _refused(
        "canary_target_not_the_spare",
        lambda: _target(roots, door="http://127.0.0.1:18872"),
    )


def test_canary_refuses_a_spare_sharing_the_live_state(roots, tmp_path):
    _, live, show = roots
    shared = _root(
        tmp_path, "shared", 18871, state=str((live / "receiver" / "state").resolve())
    )
    _refused(
        "canary_spare_shares_live_state",
        lambda: _target(roots, spare=shared, show=show),
    )


def test_canary_refuses_a_spare_on_another_network(roots, tmp_path):
    main = _root(tmp_path, "main", 18871, network="finney")
    _refused("canary_network_not_testnet", lambda: _target(roots, spare=main))


@pytest.mark.parametrize("unit", ["", "x; rm -rf /", "carbon-spare", "a b.service"])
def test_canary_refuses_a_bad_unit_name(roots, unit):
    _refused("canary_unit_invalid", lambda: _target(roots, unit=unit))


def test_canary_refuses_a_unit_that_is_not_the_spare(roots):
    spare, live, _ = roots
    live_cfg = str(live / "receiver" / "receiver.json")
    spare_cfg = str(spare / "receiver" / "receiver.json")
    _refused(
        "canary_unit_not_the_spare",
        lambda: _target(roots, show=lambda u, p: "argv[]=x --config " + live_cfg),
    )
    _refused(
        "canary_unit_not_the_spare",
        lambda: _target(
            roots, show=lambda u, p: f"--config {spare_cfg} --config {live_cfg}"
        ),
    )

    def broken(unit, prop):
        raise OSError("no systemctl")

    _refused("canary_unit_unreadable", lambda: _target(roots, show=broken))


def _canary_main(tmp_path, *extra):
    return dp.main(
        [
            "fresh",
            "--canary",
            "--door",
            "http://127.0.0.1:18871",
            "--challenge",
            "f02",
            "--version",
            "2.5",
            "--receiver-hotkey",
            "5R",
            "--out",
            str(tmp_path / "o"),
            *extra,
        ]
    )


def test_canary_refuses_any_client_but_the_canary(tmp_path):
    with pytest.raises(dp.CanaryRefused) as refused:
        _canary_main(tmp_path, "--client", "bob=5B")
    assert refused.value.code == "canary_client_given"


@pytest.mark.parametrize("n", ["0", "3"])
def test_canary_refuses_more_than_two_submits(tmp_path, n):
    with pytest.raises(dp.CanaryRefused) as refused:
        _canary_main(tmp_path, "--submits", n)
    assert refused.value.code == "canary_too_many_submits"


def test_canary_refuses_a_wall_over_an_hour(tmp_path):
    with pytest.raises(dp.CanaryRefused) as refused:
        _canary_main(tmp_path, "--wait-s", "3601")
    assert refused.value.code == "canary_wall_over_cap"


def test_canary_refusals_come_before_anything_is_written(tmp_path):
    with pytest.raises(dp.CanaryRefused):
        _canary_main(tmp_path, "--spare-root", str(tmp_path / "nope"))
    assert not (tmp_path / "o").exists()


def test_canary_hotkey_is_the_registered_one_only():
    from carbon.challenge_validator.canary import CANARY_HOTKEYS

    assert len(CANARY_HOTKEYS) == 1


def test_canary_refuses_the_kings_recipe():
    pages = {
        "/koth/f02": '{"king": {"recipe": "sha256:' + "ab" * 32 + '"}}',
        "/koth/f02/v2": "{}",
    }

    def get(url):
        return next(v for k, v in pages.items() if url.endswith(k))

    _refused(
        "canary_recipe_is_kings",
        lambda: dp.canary_not_kings(
            "http://127.0.0.1:1", "f02", ["sha256:" + "ab" * 32], get=get
        ),
    )
    dp.canary_not_kings("http://127.0.0.1:1", "f02", ["sha256:" + "cd" * 32], get=get)


def test_canary_journal_counts_and_verdict():
    grade = '{"event": "direct_grade", "service": "x", "state": "GRADED"}\n'
    text = "ok\nx direct_grade_failure y\nsqlite3.OperationalError: locked\n" + grade
    assert dp.journal_counts(text) == {
        "direct_grade_failure": 1,
        "OperationalError": 1,
        "direct_grade": 1,
    }
    clients = [("canary_1", "5C"), ("canary_2", "5C")]
    graded = {
        "canary_1": {"outcome": "graded", "task_id": "t1"},
        "canary_2": {"outcome": "graded", "task_id": "t2"},
    }
    clean = {"direct_grade_failure": 0, "OperationalError": 0}
    assert dp.canary_verdict(clients, graded, clean, "0", "0")[0] == "PASS"
    assert dp.canary_verdict(clients, graded, clean, "0", "1")[0] == "FAIL"
    assert dp.canary_verdict(clients, graded, clean, None, None)[0] == "FAIL"
    dirty = {"direct_grade_failure": 0, "OperationalError": 2}
    assert dp.canary_verdict(clients, graded, dirty, "0", "0")[0] == "FAIL"
    unread = {"direct_grade_failure": None, "OperationalError": None}
    assert dp.canary_verdict(clients, graded, unread, "0", "0")[0] == "FAIL"


def test_canary_refuses_another_doors_spare(roots, tmp_path):
    _refused("canary_spare_of_another_door", lambda: _target(roots, challenge="f08"))
    other = _root(tmp_path, "other", 18871, challenge="f08-ribbed-bracket")
    _refused("canary_spare_of_another_door", lambda: _target(roots, spare=other))
    other_live = _root(tmp_path, "other_live", 18772, challenge="f08-ribbed-bracket")
    _refused("canary_spare_of_another_door", lambda: _target(roots, live=other_live))


def test_canary_refuses_another_receiver_hotkey(roots):
    _refused(
        "canary_receiver_hotkey_not_the_spares", lambda: _target(roots, receiver="5X")
    )


def test_canary_unit_reads_are_user_units(monkeypatch):
    """The receiver units are user units: every read names --user (V2B must-fix)."""
    seen = []

    class _Done:
        stdout = " 0 "

    def run(argv, **kw):
        assert kw["check"] is True and kw["timeout"] > 0
        seen.append(argv)
        return _Done()

    monkeypatch.setattr(dp.subprocess, "run", run)
    assert dp.systemctl_show("carbon-spare.service", "NRestarts") == "0"
    dp.journal_since("carbon-spare.service", 1_700_000_000.9)
    assert seen[0] == [
        "systemctl",
        "--user",
        "show",
        "-p",
        "NRestarts",
        "--value",
        "carbon-spare.service",
    ]
    assert seen[1][:4] == ["journalctl", "--user", "-u", "carbon-spare.service"]
    assert seen[1][4:6] == ["--since", "@1700000000"]


def test_canary_runs_one_submit_by_default():
    args = dp.parser().parse_args(
        [
            "fresh",
            "--canary",
            "--door",
            "http://127.0.0.1:1",
            "--challenge",
            "f02",
            "--version",
            "2.5",
            "--receiver-hotkey",
            "5R",
            "--out",
            "o",
        ]
    )
    assert args.submits == 1


@pytest.mark.parametrize(
    "text",
    [
        "",
        "-- No entries --\n",
        "No journal files were found.\n",
        '{"event": "direct_grade_failure", "type": "OperationalError"}\n',
        "direct_grade state=GRADED\n",  # not the receiver's JSON line
    ],
)
def test_canary_a_journal_without_this_runs_grade_is_unread_and_fails(text):
    counts = dp.journal_counts(text)
    assert counts["direct_grade_failure"] is None
    assert counts["OperationalError"] is None
    clients = [("canary_1", "5C")]
    graded = {"canary_1": {"outcome": "graded", "task_id": "t1"}}
    assert dp.canary_verdict(clients, graded, counts, "0", "0")[0] == "FAIL"


def test_canary_a_journal_with_the_grade_and_no_failures_passes():
    text = '{"event": "direct_grade", "service": "x", "state": "GRADED"}\n'
    counts = dp.journal_counts(text)
    assert counts == {
        "direct_grade_failure": 0,
        "OperationalError": 0,
        "direct_grade": 1,
    }
    clients = [("canary_1", "5C")]
    graded = {"canary_1": {"outcome": "graded", "task_id": "t1"}}
    assert dp.canary_verdict(clients, graded, counts, "0", "0")[0] == "PASS"


@pytest.mark.parametrize("hotkeys", [(), ("5A", "5B")])
def test_canary_refuses_unless_exactly_one_canary_is_registered(
    monkeypatch, tmp_path, hotkeys
):
    from carbon.challenge_validator import canary

    monkeypatch.setattr(dp, "canary_args", lambda args: 18871)
    monkeypatch.setattr(canary, "CANARY_HOTKEYS", hotkeys)
    with pytest.raises(dp.CanaryRefused) as refused:
        _canary_main(tmp_path)
    assert refused.value.code == "canary_hotkey_not_single"
    assert not (tmp_path / "o").exists()
