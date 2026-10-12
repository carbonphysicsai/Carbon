"""PUBLIC-DEV-DECISIONS-01 launcher: the hard stop and the weekly ledger are
enforced before any pod exists (OWNER-PUBLIC-DEV-DECISIONS-GRANT-01)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.dev.battery import public_dev_launch as pl

ROOT = Path(__file__).resolve().parents[2]
NOW = 1_800_000_000.0


class FakeLedger:
    def __init__(self, calls, refuse=None):
        self.calls, self.refuse = calls, refuse

    def claim(self):
        self.calls.append("claim")
        if self.refuse:
            raise RuntimeError(self.refuse)

    def release(self):
        self.calls.append("release")

    def settle(self, usd):
        self.calls.append(f"settle {usd}")


def _body(deadline):
    return {"env": {} if deadline is None else {"PROBE_DEADLINE": str(deadline)}}


@pytest.mark.parametrize(
    "deadline",
    [None, "soon", int(NOW) - 1, int(NOW + pl.HOURS * 3600) + 1],
)
def test_the_hard_stop_must_be_in_the_body_and_inside_the_window(deadline):
    with pytest.raises(pl.Refused):
        pl.check_deadline(_body(deadline), now=NOW)


def test_the_worst_case_stays_inside_the_cap():
    worst = pl.check_deadline(
        _body(int(NOW + pl.HOURS * 3600 - pl.DEADLINE_MARGIN_S)), now=NOW
    )
    assert worst <= pl.CAP_USD and float(worst) == pytest.approx(
        float(pl.RATE_USD_H) * (pl.HOURS - 0.1), abs=0.01
    )
    with pytest.raises(pl.Refused):
        pl.check_deadline(_body(int(NOW + 3600)), now=NOW, cap=pl.Decimal("1.00"))


def test_the_shipped_files_are_tracked_and_carry_the_phase():
    paths = json.loads((ROOT / pl.SHIP_FILE).read_text())
    for need in (pl.BOOTSTRAP, pl.OVERLAY_LOCK, "scripts/dev/battery/public_dev_pod_phase.py",
                 "scripts/dev/battery/public_dev_questions.py", "carbon/battery/truth_env.py"):  # fmt: skip
        assert need in paths
    assert all((ROOT / p).is_file() for p in paths)


def test_the_body_holds_a_deadline_within_the_window_and_no_key():
    body = pl.build_body(ROOT, "HEAD", now=NOW, token="t", ca="c")
    pl.check_deadline(body, now=NOW)
    env = body["env"]
    assert env["PDD_QUESTIONS"] == "240" and "RUNPOD_API_KEY" not in env
    assert int(env["PDD_SOLVE_BUDGET_S"]) < int(env["PROBE_DEADLINE"]) - NOW
    assert body["imageName"].endswith(
        "@sha256:2d19b261e722fe67f20bee02e115f2277a799c448b90d54d2872361b341bd940"
    )


def test_nothing_is_created_when_the_ledger_refuses(tmp_path):
    calls = []

    def request(*a):
        calls.append("create")
        return 200, "{}"

    with pytest.raises(RuntimeError):
        pl.launch(ROOT, "HEAD", tmp_path, request=request, ledger=FakeLedger(calls, "weekly_budget_reached"),
                  clock=lambda: NOW, ca="c")  # fmt: skip
    assert calls == ["claim"]


def test_a_failed_create_releases_the_reservation_and_keeps_the_response(tmp_path):
    calls = []
    with pytest.raises(pl.Refused):
        pl.launch(ROOT, "HEAD", tmp_path, request=lambda *a: (500, "Internal Server Error"),
                  ledger=FakeLedger(calls), clock=lambda: NOW, ca="c")  # fmt: skip
    assert calls == ["claim", "release"]
    assert "Internal Server Error" in (tmp_path / "create-response.txt").read_text()
    assert not (tmp_path / "pod_id").exists()


def test_a_pod_at_another_rate_is_deleted_at_once(tmp_path):
    calls = []

    def request(method, path, body=None):
        calls.append(method)
        return 200, json.dumps({"id": "p1", "costPerHr": 3.52})

    with pytest.raises(pl.Refused):
        pl.launch(
            ROOT,
            "HEAD",
            tmp_path,
            request=request,
            ledger=FakeLedger(calls),
            clock=lambda: NOW,
            ca="c",
        )
    assert calls == ["claim", "POST", "DELETE", "settle 0.05"]


def test_an_approved_launch_reports_its_deadline_and_worst_case(tmp_path):
    calls = []

    def request(method, path, body=None):
        calls.append(method)
        return 200, json.dumps({"id": "p1", "costPerHr": 1.76})

    result = pl.launch(
        ROOT,
        "HEAD",
        tmp_path,
        request=request,
        ledger=FakeLedger(calls),
        clock=lambda: NOW,
        ca="c",
    )
    assert calls == ["claim", "POST"] and result["pod_id"] == "p1"
    assert pl.Decimal(result["worst_case_usd"]) <= pl.CAP_USD
    assert (tmp_path / "ledger_key").read_text().startswith(pl.RUN_KEY)
