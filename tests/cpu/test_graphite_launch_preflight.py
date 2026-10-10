"""GRAPHITE-LAUNCH-PREFLIGHT-01: the launch preflight, the run heartbeat and
the stall rule. Fixtures only: no network, no pod, no spend."""

from __future__ import annotations

import json
import os
import types
import urllib.error
from decimal import Decimal
from pathlib import Path

import pytest

from carbon.agent_campaign.grant import SpendingGrant
from carbon.agent_campaign.graphite import heartbeat, preflight
from carbon.agent_campaign.graphite.experiment import PodLedger
from carbon.development_session.profile import canonical

REPOSITORY = Path(__file__).resolve().parents[2]
GRANTS = REPOSITORY / "docs/development/graphite/grants"
SHA = "a" * 40


class _Response:
    def __init__(self, status):
        self.status = status

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def opener(up):
    def open_(url, timeout):
        if url not in up:
            raise urllib.error.URLError("refused")
        return _Response(200)

    return open_


def connect(open_ports):
    def connect_(address, timeout):
        if address[1] not in open_ports:
            raise ConnectionRefusedError
        return types.SimpleNamespace(close=lambda: None)

    return connect_


LANE = {
    "schema": preflight.LANE_SCHEMA,
    "signer": {"url": "http://127.0.0.1:9001/health"},
    "control_center": {"url": "http://127.0.0.1:9002/"},
    "tunnels": [{"name": "validator", "host": "127.0.0.1", "port": 9003}],
}


def _grant(name="GRAPHITE-GRANT-STAGE-A-CONSTRUCTOR", **changes):
    document = json.loads((GRANTS / (name + ".json")).read_text())
    return SpendingGrant.from_document(
        {**document, "expires_at": "2099-01-01T00:00:00Z", **changes}
    )


# -- the lane -------------------------------------------------------------------------------
def test_a_live_lane_passes():
    checks = preflight.check_lane(
        LANE,
        opener=opener({LANE["signer"]["url"], LANE["control_center"]["url"]}),
        connect=connect({9003}),
    )
    assert [c.status for c in checks] == [preflight.OK] * 3


def test_a_down_signer_is_an_owner_need_and_every_failure_is_listed():
    checks = preflight.check_lane(LANE, opener=opener(set()), connect=connect(set()))
    by_name = {c.name: c for c in checks}
    assert by_name["lane_signer"].status == preflight.FAIL
    assert by_name["lane_signer"].owner is True
    assert by_name["control_center"].status == preflight.FAIL
    assert by_name["tunnel:validator"].status == preflight.FAIL
    assert all(c.fix for c in checks)


def test_a_lane_file_of_another_shape_is_refused():
    (check,) = preflight.check_lane({"signer": {}})
    assert check.name == "lane_file" and check.status == preflight.FAIL


# -- the keys --------------------------------------------------------------------------------
def test_keys_are_checked_by_path_and_mode_only(tmp_path):
    good, loose = tmp_path / "good", tmp_path / "loose"
    good.write_text("x")
    good.chmod(0o600)
    loose.write_text("x")
    loose.chmod(0o644)
    checks = preflight.check_keys(
        [
            {"name": "good", "path": str(good)},
            {"name": "loose", "path": str(loose)},
            {"name": "gone", "path": str(tmp_path / "gone")},
        ]
    )
    status = {c.name: (c.status, c.owner) for c in checks}
    assert status == {
        "key:good": (preflight.OK, False),
        "key:loose": (preflight.FAIL, True),
        "key:gone": (preflight.FAIL, True),
    }
    assert "chmod 600" in checks[1].fix
    assert all("x" not in c.detail.split("/")[-1:] for c in checks)


# -- the revision, the roots and the grant ------------------------------------------------------
@pytest.mark.parametrize(
    ("profile", "status"),
    [
        ({"accepted_revision": SHA}, "OK"),
        ({"accepted_revision": "b" * 40}, "FAIL"),
        ({}, "FAIL"),
    ],
)
def test_the_checkout_must_be_the_accepted_revision(profile, status):
    assert preflight.check_revision(profile, SHA).status == status


def test_one_controller_root_per_concurrent_run(tmp_path):
    grant = _grant()  # max_concurrency 2
    a, b = tmp_path / "a", tmp_path / "b"
    assert preflight.check_roots([a, b], grant).status == preflight.OK
    for roots in (
        [a, a],
        [a, a / "inner"],
        [a, b, tmp_path / "c"],
        [REPOSITORY / "x"],
        [],
    ):
        assert preflight.check_roots(roots, grant).status == preflight.FAIL, roots


def test_the_grant_arithmetic_is_checked():
    assert preflight.check_grant(_grant()).status == preflight.OK
    over = _grant(permitted_runs=9)  # 9 x 14.91 + 0.12 > 74.67
    check = preflight.check_grant(over)
    assert check.status == preflight.FAIL and check.owner


# -- the pod probe ----------------------------------------------------------------------------
class FakePods:
    CAMPAIGN = "graphite-phase3"

    def __init__(self, *, stock=True, refuse=False, runs=True, stays=False):
        self.economics = {
            "gpu": "NVIDIA A40",
            "image": "image@sha256:" + "0" * 64,
            "rate_ceiling_usd_per_hr": Decimal("0.49"),
            "disk_gb": 20,
            "disk_usd_per_gb_month": Decimal("0.1"),
        }
        self.cuda_versions = ("12.4",)
        self.events, self.refuse, self.runs, self.stays = [], refuse, runs, stays
        self.balance = 100.0
        self.balance_floor = lambda: Decimal(5)
        self.economics["hourly_usd"] = Decimal("0.50")
        offer = types.SimpleNamespace(
            usd_per_hr=0.44, stock_status="High" if stock else None
        )
        self.adapter = types.SimpleNamespace(
            offers=lambda gpus, gpu_count: [offer],
            list_resources=lambda: (
                [types.SimpleNamespace(resource_id="pod-1")]
                if self.stays or "terminated" not in self.events
                else []
            ),
        )
        self.service = self

    def observe_balance(self, campaign):
        self.events.append("balance")
        return self.balance, 0.0

    def provision(self, request):
        from scripts.dev.exam_design.runpod.operator_compute import (
            ComputeError,
            Execution,
        )

        if self.refuse:
            raise ComputeError(
                operation="provision",
                failed="provider_refused",
                execution=Execution.NOT_EXECUTED,
                resources_may_remain=False,
                retry_safe=True,
                next_action="retry",
            )
        self.events.append("created")
        return types.SimpleNamespace(resource_id="pod-1")

    def refresh(self, campaign, intent):
        from scripts.dev.exam_design.runpod.operator_compute import ResourceState

        state = ResourceState.RUNNING if self.runs else ResourceState.STARTING
        return [types.SimpleNamespace(state=state)]

    def terminate(self, campaign, intent, resource_id):
        self.events.append("terminated")


def _clock():
    now = [1000.0]

    def clock():
        now[0] += 5
        return now[0]

    return clock


def test_the_probe_creates_runs_terminates_and_verifies(monkeypatch):
    pods = FakePods()
    check = preflight.probe_pod(pods, clock=_clock(), sleep=lambda s: None)
    assert check.status == preflight.OK, check.detail
    assert pods.events == ["balance", "created", "terminated"]


@pytest.mark.parametrize(
    ("pods", "owner"),
    [
        (FakePods(stock=False), True),
        (FakePods(refuse=True), False),
        (FakePods(runs=False), False),
        (FakePods(stays=True), True),
    ],
)
def test_a_failing_probe_is_named_and_the_pod_never_left_running(pods, owner):
    check = preflight.probe_pod(pods, clock=_clock(), sleep=lambda s: None)
    assert check.status == preflight.FAIL and check.owner is owner
    if "created" in pods.events:
        assert pods.events[-1] == "terminated"


# -- the command --------------------------------------------------------------------------------
def test_the_command_lists_every_owner_need_at_once(tmp_path, monkeypatch):
    from scripts.dev.exam_design.runpod import pod_control

    monkeypatch.setattr(pod_control, "STATE_DIR", str(tmp_path / "no-runpod"))
    lane = tmp_path / "lane.json"
    lane.write_text(
        json.dumps({**LANE, "keys": [{"name": "wallet", "path": str(tmp_path / "w")}]})
    )
    profile = tmp_path / "profile.json"
    profile.write_bytes(canonical({"accepted_revision": SHA}))
    profile.chmod(0o600)
    args = types.SimpleNamespace(
        lane=str(lane),
        profile=str(profile),
        grant=str(GRANTS / "GRAPHITE-GRANT-STAGE-A-CONSTRUCTOR.json"),
        root=[str(tmp_path / "r1"), str(tmp_path / "r1")],
        probe=True,
        key_file=str(tmp_path / "k"),
        code_ref=SHA,
    )
    report = preflight.run(
        args,
        opener=opener(set()),
        connect=connect(set()),
        checkout=SHA,
        make_pods=lambda **k: pytest.fail("no probe while checks fail"),
    )
    document = report.document()
    assert document["ok"] is False
    needs = {n["check"] for n in document["owner_needs"]}
    assert {"lane_signer", "key:wallet", "key:runpod"} <= needs
    failed = {c["name"] for c in document["checks"] if c["status"] == "FAIL"}
    assert {"controller_roots", "pod_probe", "control_center"} <= failed


# -- the heartbeat -------------------------------------------------------------------------------
def _run_dir(tmp_path, *, state="running", refused=0, created=1):
    run = tmp_path / "run"
    (run / "experiment").mkdir(parents=True)
    (run / "state.json").write_text(json.dumps({"state": state}))
    (run / "events.jsonl").write_text(
        json.dumps({"event_id": "e1", "kind": "tool_answered"}) + "\n"
    )
    ledger = PodLedger(run / "experiment" / "pod-ledger.jsonl", lambda: 1.0)
    for i in range(refused):
        ledger.append("pod_launch_refused", intent_id=f"r{i}")
    for i in range(created):
        ledger.append("pod_created", intent_id=f"c{i}", pod_id=f"p{i}")
        ledger.append("pod_settled", intent_id=f"c{i}", charge_usd="0.10")
    return run


def test_the_heartbeat_reads_the_run_and_is_shared(tmp_path):
    run, shared = _run_dir(tmp_path), tmp_path / "shared"
    document = heartbeat.write(
        run,
        "graphite-x",
        clock=lambda: 2000.0,
        environ={heartbeat.SHARED_DIR_ENV: str(shared)},
    )
    assert document["alive"] is True and document["phase"] == "running"
    assert document["pods"] == {"launched": 1, "refused": 0, "settled": 1}
    assert document["booked_usd"] == "0.10"
    assert document["last_event"] == "tool_answered"
    assert document["status"] == heartbeat.ALIVE
    assert json.loads((shared / "graphite-x.json").read_text()) == document
    assert os.stat(run / heartbeat.NAME).st_mode & 0o777 == 0o644


def test_a_heartbeat_older_than_15_minutes_reads_stalled(tmp_path):
    run = _run_dir(tmp_path)
    heartbeat.write(run, "graphite-x", clock=lambda: 2000.0, environ={})
    fresh = heartbeat.read(run / heartbeat.NAME, now=2000.0 + 60)
    old = heartbeat.read(run / heartbeat.NAME, now=2000.0 + heartbeat.STALL_S + 1)
    assert fresh["status"] == heartbeat.ALIVE
    assert old["status"] == heartbeat.STALLED and "no heartbeat" in old["status_reason"]


def test_an_all_refused_pod_record_is_stalled(tmp_path):
    run = _run_dir(tmp_path, refused=3, created=0)
    document = heartbeat.write(run, "graphite-x", clock=lambda: 2000.0, environ={})
    assert document["status"] == heartbeat.STALLED
    assert "refused" in document["status_reason"]


def test_a_finished_run_is_finished_and_a_missing_one_is_stalled(tmp_path):
    run = _run_dir(tmp_path, state="succeeded")
    document = heartbeat.write(run, "graphite-x", clock=lambda: 2000.0, environ={})
    assert document["status"] == heartbeat.FINISHED
    assert heartbeat.read(tmp_path / "nope.json")["status"] == heartbeat.STALLED


def test_beating_writes_while_the_block_runs(tmp_path):
    run = _run_dir(tmp_path)
    with heartbeat.beating(run, "graphite-x", interval=0.01):
        pass
    assert json.loads((run / heartbeat.NAME).read_text())["run_id"] == "graphite-x"


# -- GRANT-POD-CEILING-01 --------------------------------------------------------------------
def test_an_offer_above_the_grants_ceiling_is_the_owners_decision():
    pods = FakePods()
    pods.economics["rate_ceiling_usd_per_hr"] = Decimal("0.40")
    check = preflight.check_offer(pods)
    assert check.status == preflight.FAIL and check.owner
    assert check.detail == "owner decision: offer 0.44/h > grant ceiling 0.40/h"
    pods.economics["rate_ceiling_usd_per_hr"] = Decimal("0.44")
    assert preflight.check_offer(pods).status == preflight.OK


@pytest.mark.parametrize(
    ("body", "status"),
    [
        (None, "FAIL"),
        ("{}", "FAIL"),
        ('{"balance_floor_usd": "x"}', "FAIL"),
        ('{"balance_floor_usd": 5}', "OK"),
    ],
)
def test_the_balance_floor_file_must_exist_and_name_a_floor(tmp_path, body, status):
    if body is not None:
        (tmp_path / "campaigns.json").write_text(body)
    check = preflight.check_balance_floor(tmp_path, "campaigns.json")
    assert check.status == status
    assert "5" not in check.detail.replace(str(tmp_path), "")


def test_the_probe_observes_the_balance_before_it_provisions():
    """The executor's bug: without a balance observation the operator layer
    refuses every probe ("no account balance observation")."""
    pods = FakePods()
    preflight.probe_pod(pods, clock=_clock(), sleep=lambda s: None)
    assert pods.events.index("balance") < pods.events.index("created")


def test_a_probe_that_would_breach_the_floor_creates_nothing():
    pods = FakePods()
    pods.balance = 5.01
    check = preflight.probe_pod(pods, clock=_clock(), sleep=lambda s: None)
    assert check.status == preflight.FAIL and check.owner
    assert "created" not in pods.events
    assert "5.01" not in check.detail
