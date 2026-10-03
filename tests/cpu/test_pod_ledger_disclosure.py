"""Pod ledgers and limits: the repository is public, so it carries provenance only.

Balances, committed spend, the cap and rates live in the operator's private
ledger under ``~/.runpod/accounting/``; each campaign's ceiling and the balance
floor in ``~/.runpod/campaigns.json``. No test reaches RunPod; the figures
below are synthetic.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

REPOSITORY = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "pod_control_disclosure",
    REPOSITORY / "scripts/dev/exam_design/runpod/pod_control.py",
)
pc = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(pc)

ACCOUNTING = {"balance_usd", "committed_before_usd", "cap_usd", "cost_usd", "rule"}


def _allowed(event):
    return {"utc", "event"} | pc.PUBLIC_FIELDS.get(event, set())


def test_every_committed_ledger_carries_only_public_fields():
    ledgers = sorted(REPOSITORY.glob("docs/development/evidence/*/accounting/*.jsonl"))
    for path in ledgers:
        for n, line in enumerate(path.read_text().splitlines(), 1):
            row = json.loads(line)
            extra = set(row) - _allowed(row["event"])
            assert (
                not extra
            ), f"{path.relative_to(REPOSITORY)}:{n} carries {sorted(extra)}"


@pytest.fixture
def campaign(tmp_path, monkeypatch):
    for name in (
        "CAMPAIGN",
        "EVID",
        "LEDGER",
        "PRIVATE_LEDGER",
        "ACTIVE",
        "TOKEN_FILE",
    ):
        monkeypatch.setattr(pc, name, getattr(pc, name))
    monkeypatch.setattr(pc, "STATE_DIR", str(tmp_path / "state"))
    monkeypatch.setattr(pc, "REPO", str(tmp_path / "repo"))
    pc.use_campaign("ev4")
    return tmp_path


def _configure(campaign, text):
    (campaign / "state").mkdir(exist_ok=True)
    (campaign / "state" / pc.OPERATOR_CONFIG).write_text(text)


def _rows(path):
    return [json.loads(l) for l in Path(path).read_text().splitlines() if l.strip()]


def test_the_full_record_stays_private_and_the_projection_is_committed(campaign):
    assert Path(pc.PRIVATE_LEDGER).is_relative_to(campaign / "state")
    pc.ledger(
        "campaign_start",
        campaign="ev4",
        balance_usd=123.0,
        cap_usd=9.0,
        max_pods=3,
        rule="r",
    )
    pc.ledger(
        "dispatch_requested",
        campaign="ev4",
        ref="abc",
        minutes=60.0,
        balance_usd=122.0,
        committed_before_usd=0.5,
    )
    pc.ledger(
        "created",
        pod_id="p1",
        rate=0.4,
        created_epoch=1.0,
        deadline_epoch=3601.0,
        machine_id="m",
        ref="abc",
    )
    pc.ledger("a_future_event", pod_id="p1", balance_usd=1.0)
    public, private = _rows(pc.LEDGER), _rows(pc.PRIVATE_LEDGER)
    assert len(public) == len(private) == 4
    for row in public:
        assert not set(row) & (ACCOUNTING | {"rate", "machine_id"}), row
    assert set(public[3]) == {"utc", "event"}  # an unlisted event: time and name only
    assert private[0]["balance_usd"] == 123.0 and private[2]["rate"] == 0.4
    assert public[2]["pod_id"] == "p1" and public[1]["ref"] == "abc"
    # The budget reads the private ledger.
    assert pc.campaign_cap() == 9.0
    assert pc.committed_spend() > 0


def test_rates_and_machine_ids_stay_private(campaign):
    # Owner decision 2026-10-02: a rate with the pod's times recomputes its spend.
    assert "rate" not in pc.PUBLIC_FIELDS["created"]
    assert "machine_id" not in pc.PUBLIC_FIELDS["created"]
    pc.ledger("created", pod_id="p1", rate=0.4, machine_id="m", created_epoch=1.0)
    assert _rows(pc.LEDGER)[0] == {
        "utc": _rows(pc.LEDGER)[0]["utc"],
        "event": "created",
        "pod_id": "p1",
        "created_epoch": 1.0,
    }


def test_the_budget_refuses_a_repository_ledger_without_its_private_ledger(campaign):
    # A projected ledger on a host without the private one: figures elsewhere.
    Path(pc.LEDGER).parent.mkdir(parents=True)
    Path(pc.LEDGER).write_text(
        json.dumps({"utc": "t", "event": "campaign_start"}) + "\n"
    )
    with pytest.raises(SystemExit, match="migrate-ledger"):
        pc.committed_spend()
    pc.ledger("terminate_requested", pod_id="p1")  # termination is never refused
    with pytest.raises(SystemExit, match="migrate-ledger"):
        pc.committed_spend()


#: A full ledger as committed before the split.
FULL = [
    {
        "utc": "t0",
        "event": "campaign_start",
        "campaign": "ev4",
        "balance_usd": 50.0,
        "cap_usd": 9.0,
        "max_pods": 3,
    },
    {
        "utc": "t1",
        "event": "created",
        "pod_id": "p1",
        "rate": 0.4,
        "created_epoch": 1.0,
        "deadline_epoch": 7201.0,
    },
    {"utc": "t2", "event": "terminate_requested", "pod_id": "p1"},
    {
        "utc": "t3",
        "event": "terminated_verified",
        "pod_id": "p1",
        "verified_epoch": 7201.0,
    },
]


def _write_full():
    Path(pc.LEDGER).parent.mkdir(parents=True)
    Path(pc.LEDGER).write_text("".join(json.dumps(r) + "\n" for r in FULL))


def test_migration_moves_the_full_ledger_out_once(campaign):
    _write_full()
    pc.migrate_ledger()
    assert _rows(pc.PRIVATE_LEDGER) == FULL
    once = Path(pc.LEDGER).read_text()
    assert _rows(pc.LEDGER) == [pc.public_record(r) for r in FULL]
    pc.migrate_ledger()  # idempotent
    assert Path(pc.LEDGER).read_text() == once and _rows(pc.PRIVATE_LEDGER) == FULL
    assert pc.campaign_cap() == 9.0
    with open(pc.LEDGER, "a") as f:  # a projected row from another host
        f.write(json.dumps({"utc": "x", "event": "created", "pod_id": "p2"}) + "\n")
    with pytest.raises(SystemExit, match="lacks"):
        pc.migrate_ledger()


def test_a_changed_allow_list_keeps_committed_rows_matched(campaign, monkeypatch):
    _write_full()
    pc.migrate_ledger()
    grown = {**pc.PUBLIC_FIELDS, "created": pc.PUBLIC_FIELDS["created"] | {"rate"}}
    monkeypatch.setattr(pc, "PUBLIC_FIELDS", grown)
    assert pc.committed_spend() == pytest.approx(pc.pod_cost_usd(120, 0.4))
    shrunk = {**pc.PUBLIC_FIELDS, "created": {"pod_id"}}
    monkeypatch.setattr(pc, "PUBLIC_FIELDS", shrunk)
    assert pc.campaign_cap() == 9.0


def test_a_write_before_migration_keeps_the_budget_whole(campaign):
    _write_full()
    spent = pc.pod_cost_usd(120, 0.4)
    pc.ledger("terminate_requested", pod_id="p2")  # e.g. reconcile, unmigrated
    assert _rows(pc.PRIVATE_LEDGER) == FULL + [_rows(pc.PRIVATE_LEDGER)[-1]]
    assert pc.committed_spend() == pytest.approx(spent)
    assert pc.campaign_cap() == 9.0


def test_terminal_output_carries_no_accounting_by_default(
    campaign, monkeypatch, capsys
):
    pc.ledger(
        "campaign_start", campaign="ev4", balance_usd=50.0, cap_usd=9.0, max_pods=3
    )
    monkeypatch.setattr(pc, "pods", list)
    monkeypatch.setattr(pc, "account", lambda: pytest.fail("status read the balance"))
    pc.cmd_status(None)
    out = json.loads(capsys.readouterr().out)
    assert not set(out) & {
        "balance_usd",
        "spend_per_hr",
        "committed_spend_usd",
        "cap_usd",
    }
    assert out["within_cap"] is True
    with pytest.raises(SystemExit) as refused:
        pc.check_budget(8.0, 2.0, 9.0)
    assert not any(ch.isdigit() for ch in str(refused.value))


# --- operator limits: each campaign's ceiling and the balance floor ---------


def test_the_source_carries_no_ceiling_or_balance_floor():
    for spec in pc.CAMPAIGNS.values():
        assert not {k for k in spec if "ceiling" in k or "floor" in k}, spec
    for name in ("CEILING_USD", "BALANCE_FLOOR"):
        assert not hasattr(pc, name), name


def test_limits_come_from_the_operator_configuration(campaign):
    _configure(
        campaign,
        json.dumps({"balance_floor_usd": 3.0, "ceilings_usd": {"ev4": 12.0}}),
    )
    limits = pc.operator_limits()
    assert (limits.ceiling_usd, limits.balance_floor_usd) == (12.0, 3.0)
    assert pc.start_cap(100.0, None, limits) == 12.0
    assert pc.start_cap(100.0, 50.0, limits) == 12.0
    assert pc.start_cap(10.0, None, limits) == 7.0
    with pytest.raises(TypeError):
        pc.Limits(12.0, 3.0)  # valid values, but not through the configuration


@pytest.mark.parametrize(
    "text, refusal",
    [
        (None, "no operator configuration"),
        ("{", "not JSON"),
        ("[]", "not a JSON object"),
        ('{"balance_floor_usd": 3, "ceilings_usd": {"exam-design": 5}}', "ev4"),
        ('{"balance_floor_usd": 3, "ceilings_usd": {"ev4": 0}}', "ev4"),
        ('{"balance_floor_usd": 3, "ceilings_usd": {"ev4": Infinity}}', "ev4"),
        ('{"balance_floor_usd": 3, "ceilings_usd": {"ev4": true}}', "ev4"),
        ('{"balance_floor_usd": NaN, "ceilings_usd": {"ev4": 5}}', "balance_floor"),
        ('{"balance_floor_usd": -1, "ceilings_usd": {"ev4": 5}}', "balance_floor"),
        ('{"ceilings_usd": {"ev4": 5}}', "balance_floor"),
    ],
)
def test_missing_or_invalid_limits_refuse(campaign, text, refusal):
    if text is not None:
        _configure(campaign, text)
    with pytest.raises(SystemExit, match=refusal):
        pc.operator_limits()


@pytest.mark.parametrize("command", ["cmd_dispatch", "cmd_dispatch_cpu"])
def test_nothing_is_requested_without_the_operator_limits(
    campaign, monkeypatch, command
):
    for remote in ("pods", "account", "rest", "gql"):
        monkeypatch.setattr(pc, remote, lambda *a, r=remote: pytest.fail(f"{r} called"))

    class Args:
        kind = "motor"
        max_pods = 1

    with pytest.raises(SystemExit, match="no operator configuration"):
        getattr(pc, command)(Args())
