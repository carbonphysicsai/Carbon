"""GRAPHITE-RUNNER-USABILITY-01: the operator findings B6, B9, B11, C7, C8, C9.

Nothing here launches a session, a pod or a network call: ledgers are written
by hand, the phase-4 reports are written from a fixture, and `run-checked` is
driven with `--plan` or a scripted step caller.
"""

from __future__ import annotations

import json
import os
from decimal import Decimal

import pytest
from graphite_phase3_fixtures import GRANT_FILE, SCORING, snapshot_file

from carbon.agent_campaign.graphite import cli_usage, phase3, phase4, run_checked
from carbon.agent_campaign.graphite import experiment as ex
from carbon.challenge_validator import scoring as challenge_scoring
from carbon.development_session.profile import canonical

TOKENS = challenge_scoring.registered()


def _ledger(path, rows):
    ledger = ex.PodLedger(path, clock=lambda: 0.0)
    for row in rows:
        event, at, body = row
        ledger.clock = lambda at=at: at
        ledger.append(event, **body)
    return ledger


def _pod_rows(intent, *, settle=None, unresolved=False, terminate=True):
    rows = [
        ("pod_reserved", 0.0, {"intent_id": intent, "reserved_usd": "1.20"}),
        ("pod_launch_requested", 1.0, {"intent_id": intent}),
        (
            "pod_created",
            10.0,
            {"intent_id": intent, "pod_id": "pod-" + intent, "rate_usd_per_hr": "0.60"},
        ),
    ]
    if terminate:
        rows.append(("pod_terminated_verified", 10.0 + 1800, {"intent_id": intent}))
    if unresolved:
        rows.append(("pod_charge_unresolved", 1820.0, {"intent_id": intent}))
    if settle is not None:
        rows.append(
            (
                "pod_settled",
                1820.0,
                {
                    "intent_id": intent,
                    "charge_usd": settle,
                    "basis": "provider_reported",
                },
            )
        )
    return rows


# -- B6: booked versus charged or estimated, with the basis ---------------------------------
def test_each_pod_shows_what_was_booked_and_on_what_basis(tmp_path):
    ledger = _ledger(
        tmp_path / "pod-ledger.jsonl",
        [
            *_pod_rows("a-reported", settle="0.31"),
            *_pod_rows("b-no-charge", unresolved=True),
            *_pod_rows("c-live", terminate=False),
            ("pod_reserved", 0.0, {"intent_id": "d-never", "reserved_usd": "1.20"}),
            (
                "pod_settled",
                0.0,
                {
                    "intent_id": "d-never",
                    "charge_usd": "0",
                    "basis": "reserved_never_dispatched",
                },
            ),
        ],
    )
    pods = {p["intent_id"]: p for p in ledger.charges()}
    reported, no_charge, live, never = (
        pods[k] for k in ("a-reported", "b-no-charge", "c-live", "d-never")
    )
    assert (reported["basis"], reported["booked_usd"], reported["charged_usd"]) == (
        "provider_reported",
        "0.31",
        "0.31",
    )
    # RunPod reported nothing: the full reservation is booked, never a charge.
    assert (no_charge["basis"], no_charge["booked_usd"], no_charge["charged_usd"]) == (
        "reservation",
        "1.20",
        None,
    )
    # 30 minutes at 0.60/h: an estimate for reading, never booked.
    assert Decimal(no_charge["estimated_usd"]) == Decimal("0.30")
    assert (live["basis"], live["booked_usd"], live["estimated_usd"]) == (
        "unresolved",
        "1.20",
        None,
    )
    assert (never["basis"], never["booked_usd"], never["settled_basis"]) == (
        "released",
        "0",
        "reserved_never_dispatched",
    )
    report = ex.pod_charge_report(ledger)
    # Booked equals what the run counts against its cap.
    settled, pending = ledger.committed()
    assert Decimal(report["booked_usd"]) == settled + pending
    assert report["charged_usd"] == "0.31"
    assert report["booked_at_reservation"] == 2
    assert set(report["bases"]) == {
        "provider_reported",
        "reservation",
        "unresolved",
        "released",
    }


def _run_dir(root, name, state, rows):
    run = root / "graphite" / "runs" / name
    (run / "experiment").mkdir(parents=True)
    (run / "state.json").write_text(json.dumps(state))
    _ledger(run / "experiment" / "pod-ledger.jsonl", rows)
    return run


# -- B9: a terminal reconciliation_required session names its next step ---------------------
def test_status_names_reconcile_for_a_reconciliation_required_session(tmp_path, capsys):
    _run_dir(
        tmp_path,
        "graphite-0000000000000001",
        {"state": "failed", "failure": {"code": "reconciliation_required"}},
        _pod_rows("x", unresolved=True),
    )
    _run_dir(
        tmp_path,
        "graphite-0000000000000002",
        {"state": "succeeded", "failure": None},
        _pod_rows("y", settle="0.10"),
    )
    assert phase3.main(["status", "--root", str(tmp_path)]) == 0
    out = json.loads(capsys.readouterr().out)
    failed, done = out["graphite-0000000000000001"], out["graphite-0000000000000002"]
    step = failed["next_step"]
    assert step["failure_code"] == "reconciliation_required"
    assert step["terminal"] is True and step["resumable"] is False
    assert any("reconcile" in line for line in step["do"])
    assert any("new session number" in line for line in step["do"])
    assert done["next_step"] is None
    assert failed["pod_charges"]["pods"][0]["basis"] == "reservation"
    assert done["pod_charges"]["pods"][0]["basis"] == "provider_reported"


def test_next_step_is_only_for_a_failed_session_with_a_known_code():
    assert cli_usage.next_step("succeeded", None) is None
    assert cli_usage.next_step("failed", {"code": "harness_error"}) is None
    assert cli_usage.next_step("failed", None) is None
    assert cli_usage.next_step("failed", {"code": "reconciliation_required"})


# -- B11: phase 4's coverage report and B2 are written once under the run root ------------
def _coverage(b2=None):
    return {"schema": phase4.COVERAGE_SCHEMA, "benchmark_b2": b2 or {"families": {}}}


def test_the_coverage_report_and_b2_are_written_once_as_canonical_json(
    tmp_path, capsys
):
    entry = {"run_id": "graphite-0000000000000003"}
    coverage = _coverage()
    record = phase4.write_reports(tmp_path, entry, coverage)
    captured = capsys.readouterr()
    assert captured.out == ""  # stdout is unchanged
    assert json.loads(captured.err) == record
    directory = tmp_path / "reports" / entry["run_id"]
    assert (directory / "coverage.json").read_bytes() == canonical(coverage)
    assert (directory / "benchmark-b2.json").read_bytes() == canonical(
        coverage["benchmark_b2"]
    )
    assert record["files"] == {
        "coverage.json": "written",
        "benchmark-b2.json": "written",
    }
    assert oct((directory / "coverage.json").stat().st_mode & 0o777) == "0o600"
    # The same report again is idempotent; a different one keeps the first.
    assert phase4.write_reports(tmp_path, entry, coverage)["files"][
        "coverage.json"
    ] == ("written")
    other = _coverage({"families": {"x": 1}})
    kept = phase4.write_reports(tmp_path, entry, other)
    assert kept["files"] == {
        "coverage.json": "kept_first",
        "benchmark-b2.json": "kept_first",
    }
    assert (directory / "coverage.json").read_bytes() == canonical(coverage)
    assert phase4.write_reports(tmp_path, entry, None) is None


# -- C7: one credential option, a key file, checked the same way in both phases -----------
def test_phase3_takes_the_engy_key_file_under_phase4s_owner_only_rule(tmp_path, capsys):
    document = json.loads(GRANT_FILE.read_bytes())
    document["expires_at"] = "2099-01-01T00:00:00Z"
    grant = tmp_path / "grant.json"
    grant.write_text(json.dumps(document))
    snapshot = snapshot_file(tmp_path / "lit", count=1, verdicts={1: "CORRECT"})
    key = tmp_path / "engy-key"
    key.write_text("fixture-not-a-key")
    os.chmod(key, 0o644)
    argv = [
        "run",
        "--root",
        str(tmp_path / "root"),
        "--challenge",
        SCORING.challenge_id,
        "--grant",
        str(grant),
        "--credential-file",
        str(key),
        "--runpod-key-file",
        str(key),
        "--code-ref",
        "0" * 40,
        "--miner-profile",
        "p",
        "--miner-campaign",
        "c",
        "--literature-snapshot",
        str(snapshot),
    ]
    with pytest.raises(SystemExit):
        phase3.main(argv)
    out = capsys.readouterr().out
    assert json.loads(out.strip().splitlines()[-1])["reason_code"] == (
        "credential_file_must_be_owner_only"
    )
    assert "fixture-not-a-key" not in out


# -- C8: --challenge stays required, and the usage error lists the accepted tokens --------
@pytest.mark.parametrize(
    "main, argv",
    [
        (phase3.main, ["run", "--root", "r", "--dry-run"]),
        (phase4.main, ["run", "--root", "r", "--dry-run"]),
        (phase4.main, ["prelive", "--root", "r"]),
    ],
)
def test_a_missing_challenge_names_the_accepted_tokens_and_no_default(
    main, argv, capsys
):
    with pytest.raises(SystemExit) as stopped:
        main(argv)
    assert stopped.value.code == 2
    error = capsys.readouterr().err
    assert "--challenge" in error and "required" in error
    assert all(token in error for token in TOKENS)
    assert "no default" in error


def test_the_help_lists_the_accepted_tokens(capsys):
    with pytest.raises(SystemExit):
        phase3.main(["run", "--help"])
    text = "".join(capsys.readouterr().out.split())  # argparse wraps at hyphens
    assert all(token in text for token in TOKENS)


# -- C9: run-checked composes the gates, the launch and the post-run checks ---------------
COMMON = [
    "run-checked",
    "--root",
    "/private/root",
    "--challenge",
    TOKENS[0],
    "--grant",
    "grant.json",
    "--credential-file",
    "/keys/engy",
    "--miner-profile",
    "profile.json",
    "--miner-campaign",
    "campaign",
]
PHASE3 = [
    *COMMON,
    "--phase",
    "3",
    "--code-ref",
    "1" * 40,
    "--literature-snapshot",
    "snap.json",
    "--runpod-key-file",
    "/keys/runpod",
]


def _never(step):
    raise AssertionError("a plan runs nothing: " + step["step"])


def test_the_plan_lists_the_steps_in_order_and_runs_nothing(capsys):
    assert run_checked.main([*PHASE3, "--plan"], call=_never) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["ran"] is False
    assert [s["step"] for s in out["plan"]] == [
        "gate.grant_and_code_ref",
        "gate.dry_run",
        "launch",
        "post.reconcile",
        "post.status",
    ]
    launch = out["plan"][2]["argv"]
    assert launch[0] == "run" and "--dry-run" not in launch
    assert "--credential-file" in launch and "--credential-env" not in launch
    assert "--runpod-key-file" in launch and "--runpod-key-env" not in launch
    assert "--dry-run" in out["plan"][1]["argv"]
    assert run_checked.main([*COMMON, "--phase", "4", "--plan"], call=_never) == 0
    four = json.loads(capsys.readouterr().out)["plan"]
    assert [s["step"] for s in four] == ["gate.prelive", "launch", "post.status"]
    assert four[0]["argv"][0] == "prelive"


def test_the_carrier_lane_has_no_reconcile_step(capsys):
    argv = [a for a in PHASE3 if a not in ("--runpod-key-file", "/keys/runpod")]
    argv += ["--compute", "carrier", "--image-manifest", "image.json"]
    assert run_checked.main([*argv, "--plan"], call=_never) == 0
    steps = [s["step"] for s in json.loads(capsys.readouterr().out)["plan"]]
    assert "post.reconcile" not in steps and steps[-1] == "post.status"


def _scripted(codes):
    seen = []

    def call(step):
        seen.append(step["step"])
        return codes.get(step["step"], 0)

    return seen, call


def test_a_refused_gate_stops_before_the_launch(capsys):
    seen, call = _scripted({"gate.dry_run": 4})
    assert run_checked.main(PHASE3, call=call) == 4
    assert seen == ["gate.grant_and_code_ref", "gate.dry_run"]
    record = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert record["run_checked"]["stopped_at"] == "gate.dry_run"
    assert record["run_checked"]["launched"] is False


def test_the_post_run_checks_run_whatever_the_launch_exit(capsys):
    seen, call = _scripted({"launch": 4})
    assert run_checked.main(PHASE3, call=call) == 4
    assert seen[-2:] == ["post.reconcile", "post.status"]
    seen, call = _scripted({"post.reconcile": 4})
    assert run_checked.main(PHASE3, call=call) == 4  # a pod still live
    seen, call = _scripted({})
    assert run_checked.main([*COMMON, "--phase", "4"], call=call) == 0
    assert seen == ["gate.prelive", "launch", "post.status"]


def test_options_are_checked_per_phase_before_any_step(capsys):
    with pytest.raises(SystemExit) as stopped:
        run_checked.main([*COMMON, "--phase", "4", "--code-ref", "1" * 40], call=_never)
    assert stopped.value.code == 2
    assert "phase_4_takes_no: --code-ref" in capsys.readouterr().out
    with pytest.raises(SystemExit):
        run_checked.main([*COMMON, "--phase", "3"], call=_never)
    reason = json.loads(capsys.readouterr().out)["reason_code"]
    assert reason.startswith("required: --code-ref, --literature-snapshot")
    with pytest.raises(SystemExit):
        run_checked.main(["run-checked", "--phase", "3", "--root", "r"], call=_never)
    error = capsys.readouterr().err
    assert all(token in error for token in TOKENS)


def test_a_step_that_exits_is_recorded_with_its_code(monkeypatch):
    def refuse(_argv):
        raise SystemExit(2)

    monkeypatch.setattr(run_checked, "phase3_gate", refuse)
    step = run_checked.plan(run_checked.parser().parse_args(PHASE3))[0]
    assert step["call"] == "phase3.gate"
    assert run_checked.call_step(step) == 2
