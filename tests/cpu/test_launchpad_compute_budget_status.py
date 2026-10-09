"""LAUNCHPAD-COMPUTE-BUDGET-STATUS-01: miners see whether a recipe is inside
the Challenge's submission compute budget, by admission's own rule.

`challenge_contracts.budget_status` is the one status; `check_compute_budget`
admits by it, and every Launchpad door shows it: the free `budget_status`
read on both doors, each practice result, and freeze, commit and submit,
which refuse an over-budget recipe with its numbers before anything is signed.

No real contract declares a budget, so every real Challenge is NOT_SET with
no numbers. A declared budget is exercised only through a test-only contract
stand-in, here.
"""

from __future__ import annotations

import asyncio
import json
import shutil
import subprocess
import threading
from pathlib import Path
from types import SimpleNamespace

import pytest

from carbon.reconstruction import capability_registry as cr
from carbon.reconstruction import challenge_contracts as cc
from carbon.training_budget import cost
from carbon.training_budget.adapter import NoAdapter
from scripts.dev.miner_launchpad import budget_view
from scripts.dev.miner_launchpad.controller import Rejected

ROOT = Path(__file__).resolve().parents[2]
BATTERY = cr.BATTERY_CHALLENGE
NUMBERS = ("unit", "used", "allowed", "within")


def strategy(challenge=BATTERY, **parameters):
    return {
        "schema_version": "1.0",
        "challenge_id": challenge,
        "backbone": "mlp",
        "parameters": parameters,
    }


class Declared:
    """A test-only contract: the real one, with `budget` declared in its
    envelope. Never registered; it replaces the lookup for one test."""

    def __init__(self, budget, base):
        self.budget, self._base = budget, base

    def __getattr__(self, name):
        return getattr(self._base, name)

    def document(self):
        document = dict(self._base.document())
        document["envelope"] = {
            **dict(document["envelope"]),
            cc.COMPUTE_BUDGET: self.budget,
        }
        return document


@pytest.fixture(autouse=True)
def _fresh_cache():
    budget_view._status.cache_clear()
    yield
    budget_view._status.cache_clear()


@pytest.fixture
def declared(monkeypatch):
    """Give the battery contract a test-only declared budget, and the
    calculator a fixed report, for this test only."""

    real = cr.CONTRACTS[BATTERY]

    def declare(budget, report):
        monkeypatch.setattr(
            cc, "CONTRACTS", {**cr.CONTRACTS, BATTERY: Declared(budget, real)}
        )
        if isinstance(report, Exception):

            def refuse(challenge, s, **kw):
                raise report

            monkeypatch.setattr(cost, "cost", refuse)
        else:
            monkeypatch.setattr(cost, "cost", lambda challenge, s, **kw: report)

    return declare


# ---- The one status.


def test_every_real_challenge_is_not_set_with_no_numbers(monkeypatch):
    def never(*args, **kwargs):
        raise AssertionError("no cost is computed without a declared budget")

    monkeypatch.setattr(cost, "cost", never)
    assert cr.CONTRACTS
    for challenge in cr.CONTRACTS:
        value = cc.budget_status(challenge, strategy(challenge))
        assert value == {
            "schema": cc.BUDGET_STATUS_SCHEMA,
            "status": "NOT_SET",
            "unit": None,
            "used": None,
            "allowed": None,
            "within": None,
        }
        assert budget_view.status(strategy(challenge)) == value
        assert budget_view.refusal(value) is None
    # A Challenge with no construction contract declares no budget either.
    assert cc.budget_status("no-such-challenge-v1", strategy())["status"] == "NOT_SET"


def test_within_and_over_carry_the_numbers(declared):
    declared({"unit": "F1", "value": 1000}, {"F1": 400})
    within = cc.budget_status(BATTERY, strategy())
    assert {k: within[k] for k in ("status", *NUMBERS)} == {
        "status": "SET",
        "unit": "F1",
        "used": 400,
        "allowed": 1000,
        "within": True,
    }
    declared({"unit": "F1", "value": 1000}, {"F1": 1000})
    assert cc.budget_status(BATTERY, strategy())["within"] is True  # a ceiling
    declared({"unit": "F4_flops", "value": 1.0e9}, {"F4_flops": 2.5e9})
    over = cc.budget_status(BATTERY, strategy())
    assert {k: over[k] for k in ("status", *NUMBERS)} == {
        "status": "SET",
        "unit": "F4_flops",
        "used": 2.5e9,
        "allowed": 1.0e9,
        "within": False,
    }


@pytest.mark.parametrize(
    "budget",
    [
        {"unit": "F1"},
        {"unit": 4, "value": 1},
        {"unit": "F1", "value": -1},
        {"unit": "F1", "value": 0},
        {"unit": "F1", "value": True},
        {"unit": "F1", "value": float("inf")},
        "F1",
    ],
)
def test_a_malformed_declaration_shows_no_numbers(declared, budget):
    declared(budget, {"F1": 1})
    value = cc.budget_status(BATTERY, strategy())
    assert value["status"] == "MALFORMED"
    assert all(value[k] is None for k in NUMBERS)


def test_an_uncalibrated_unit_and_the_unmeasurable_cases(declared):
    declared({"unit": "F2", "value": 10.0}, {"F1": 3, "F2": cost.HUMAN_INPUT})
    value = cc.budget_status(BATTERY, strategy())
    assert value["status"] == "UNIT_NOT_CALIBRATED"
    assert (value["unit"], value["allowed"], value["used"]) == ("F2", 10.0, None)
    declared({"unit": "F1", "value": 10}, NoAdapter(BATTERY))
    assert cc.budget_status(BATTERY, strategy())["status"] == "NO_ADAPTER"
    declared({"unit": "F1", "value": 10}, cost.CostRefused("cost_unbounded_loop"))
    assert cc.budget_status(BATTERY, strategy())["status"] == "UNMEASURABLE"
    for report in ({}, {"F1": "x"}, {"F1": float("nan")}):
        declared({"unit": "F1", "value": 10}, report)
        assert cc.budget_status(BATTERY, strategy())["status"] == "UNMEASURABLE"


# ---- Admission and the display agree.


CASES = [
    ({"unit": "F1", "value": 1000}, {"F1": 400}),
    ({"unit": "F1", "value": 1000}, {"F1": 1000}),
    ({"unit": "F1", "value": 1000}, {"F1": 1001}),
    ({"unit": "F2", "value": 10.0}, {"F2": cost.HUMAN_INPUT}),
    ({"unit": "F1", "value": 10}, {}),
    ({"unit": "F1", "value": 10}, {"F1": float("nan")}),
    ({"unit": "F1", "value": 10}, cost.CostRefused("cost_unbounded_loop")),
    ({"unit": "F1", "value": 10}, NoAdapter(BATTERY)),
    ({"unit": "F1", "value": -1}, {"F1": 1}),
]


@pytest.mark.parametrize(("budget", "report"), CASES)
def test_check_compute_budget_refuses_exactly_what_the_status_shows(
    declared, budget, report
):
    declared(budget, report)
    item = cc.CONTRACTS[BATTERY]
    value = cc.budget_status(item, strategy())
    assert cc.budget_status(BATTERY, strategy()) == value
    if value["status"] == "MALFORMED":
        with pytest.raises(RuntimeError):
            cc.check_compute_budget(item, strategy())
        return
    if value["status"] == "SET" and value["within"]:
        assert cc.check_compute_budget(item, strategy()) == report
        assert budget_view.refusal(budget_view.status(strategy())) is None
        return
    with pytest.raises(cc.SubmissionRefused) as refused:
        cc.check_compute_budget(item, strategy())
    expected = (
        "budget.over_compute_budget"
        if value["status"] == "SET"
        else "budget.cost_unmeasurable"
    )
    assert [i.code for i in refused.value.issues] == [expected]
    assert refused.value.budget == {k: value[k] for k in ("unit", "used", "allowed")}
    door = budget_view.refusal(budget_view.status(strategy()))
    assert door.code == expected.removeprefix("budget.")
    assert door.budget == refused.value.budget
    # The submission compile refuses it the same way.
    with pytest.raises(cc.SubmissionRefused) as compiled:
        cc.compile_submission(strategy())
    assert [i.code for i in compiled.value.issues] == [expected]


def test_the_over_budget_refusal_names_the_numbers(declared):
    declared({"unit": "F1", "value": 1_000_000}, {"F1": 2_500_000})
    refused = budget_view.refusal(budget_view.status(strategy()))
    assert refused.code == "over_compute_budget" and refused.status == 409
    assert refused.budget == {"unit": "F1", "used": 2_500_000, "allowed": 1_000_000}
    assert "2,500,000 F1" in refused.next_step and "1,000,000 F1" in refused.next_step
    from scripts.dev.miner_launchpad.controller import error_body
    from scripts.dev.miner_launchpad.operations import refusal

    body = error_body(refused.code, refused)
    assert body["budget"] == refused.budget and body["next_step"] == refused.next_step
    assert refusal(refused.code, refused.next_step, refused.budget) == {
        "error": "over_compute_budget",
        "next_step": refused.next_step,
        "budget": refused.budget,
    }


# ---- The operation, on both doors.


def test_the_operation_reads_only():
    from scripts.dev.miner_launchpad.operations import OPERATIONS

    op = OPERATIONS["budget_status"]
    assert op.admits_work is False
    assert op.gates == OPERATIONS["ladder"].gates == ("request", "profile")
    assert op.required == {"challenge", "strategy"} and op.optional == frozenset()


def test_the_operation_refuses_by_name():
    for request, code in (
        (
            {"challenge": "no-such-challenge-v1", "strategy": strategy()},
            "challenge_unknown",
        ),
        ({"challenge": 4, "strategy": strategy()}, "challenge_required"),
        ({"challenge": BATTERY, "strategy": "not json"}, "strategy_json_invalid"),
        (
            {"challenge": BATTERY, "strategy": strategy("another-v1")},
            "strategy_names_another_challenge",
        ),
    ):
        with pytest.raises(Rejected) as refused:
            budget_view.for_request(request)
        assert refused.value.code == code
    # Strategy as the JSON text an MCP client may send.
    value = budget_view.for_request(
        {"challenge": BATTERY, "strategy": json.dumps(strategy())}
    )
    assert value["status"] == "NOT_SET"


@pytest.fixture
def browser(tmp_path):
    from scripts.dev.miner_launchpad import controller as launchpad

    def serve(host):
        server = launchpad.Server(
            launchpad.Controller(tmp_path / "launchpad.sqlite3"),
            "x" * 40,
            port=0,
            research_runner=host,
        )
        threading.Thread(target=server.serve_forever, daemon=True).start()
        servers.append(server)
        return server

    servers = []
    yield serve
    for server in servers:
        server.shutdown()
        server.server_close()


def _both_doors(server, host, body):
    from test_miner_launchpad import auth, request

    from carbon.miner_mcp.mcp_operations import make_operation_tools
    from scripts.dev.miner_launchpad.operations import perform

    code, _, content = request(
        server, "/api/v1/operations/budget_status", "POST", body, auth()
    )
    assert code == 200, content
    tool = {t.name: t for t in make_operation_tools(host)}["carbon_budget_status"]
    mcp = asyncio.run(tool.fn(**body)).payload
    assert json.loads(content) == mcp == perform(host, "budget_status", body)
    return mcp


def test_both_doors_give_the_same_status(browser, declared):
    from scripts.dev.miner_launchpad.research_fixture import FixtureRunner

    host = FixtureRunner()
    server = browser(host)
    body = {"challenge": BATTERY, "strategy": strategy(width=32)}
    assert _both_doors(server, host, body)["status"] == "NOT_SET"
    budget_view._status.cache_clear()
    declared({"unit": "F1", "value": 1000}, {"F1": 1500})
    over = _both_doors(server, host, body)
    assert (over["status"], over["used"], over["allowed"], over["within"]) == (
        "SET",
        1500,
        1000,
        False,
    )


# ---- Practice shows it; practice is never refused by it.


def test_each_practice_row_carries_its_recipes_status(declared):
    from scripts.dev.miner_launchpad.campaign_view import experiment_rows

    own = {"experiments": [{"id": "t1", "recipe": strategy()}, {"id": "t2"}]}
    rows = experiment_rows(own, None)
    assert rows[0]["budget_status"]["status"] == "NOT_SET"
    assert rows[1]["budget_status"] is None  # no recipe, no status
    budget_view._status.cache_clear()
    declared({"unit": "F1", "value": 1000}, {"F1": 1500})
    over = experiment_rows(own, None)[0]["budget_status"]
    assert (over["used"], over["allowed"], over["within"]) == (1500, 1000, False)


def test_practice_is_never_refused_by_the_budget(declared, tmp_path):
    from scripts.dev.miner_launchpad.runner import RunnerAdapter

    declared({"unit": "F1", "value": 1}, {"F1": 10**9})
    host = RunnerAdapter.__new__(RunnerAdapter)
    started = []
    host._design_refusal = lambda s: None
    host._background = lambda *args, **kw: started.append(args[1]) or {"state": "x"}
    admitted = SimpleNamespace(campaign={"id": "c", "root": str(tmp_path)})
    host.practice_admitted(admitted, {"strategy": strategy(), "hypothesis": "h"})
    assert started == ["practice"]


BUDGET_LINE = """
const src = require("node:fs").readFileSync(process.argv[1], "utf8");
const grab = name => src.slice(src.indexOf("function " + name + "("), src.indexOf("\\n  }\\n", src.indexOf("function " + name + "(")) + 4);
eval(grab("budgetNumber") + grab("budgetLine"));
console.log(JSON.stringify(JSON.parse(process.argv[2]).map(budgetLine)));
"""


def test_the_page_renders_one_line_per_status():
    node = shutil.which("node")
    if node is None:
        pytest.skip("node is not installed")
    statuses = [
        {"status": "SET", "unit": "F1", "used": 400, "allowed": 1000, "within": True},
        {"status": "SET", "unit": "F1", "used": 1500, "allowed": 1000, "within": False},
        {
            "status": "NOT_SET",
            "unit": None,
            "used": None,
            "allowed": None,
            "within": None,
        },
        {
            "status": "UNIT_NOT_CALIBRATED",
            "unit": "F2",
            "used": None,
            "allowed": 9,
            "within": None,
        },
        None,
    ]
    out = subprocess.run(
        [
            node,
            "-e",
            BUDGET_LINE,
            str(ROOT / "scripts/dev/miner_launchpad/app.js"),
            json.dumps(statuses),
        ],
        capture_output=True,
        text=True,
        check=True,
        timeout=60,
    )
    assert json.loads(out.stdout) == [
        "Within budget: 400 of 1,000 F1",
        "Over budget: 1,500 of 1,000 F1",
        "Budget not set for this Challenge",
        "Budget unit not calibrated yet",
        None,
    ]
    page = (ROOT / "scripts/dev/miner_launchpad/app.js").read_text(encoding="utf-8")
    training = page.index('" s training · backend "')
    assert page.index("budgetLine(experiment.budget_status)") > training


# ---- Freeze, commit and submit: shown, and refused over budget before signing.


def _host(tmp_path, monkeypatch):
    from carbon.development_session import research_campaign
    from scripts.dev.miner_launchpad.runner import RunnerAdapter

    monkeypatch.setattr(research_campaign, "freeze_refusal", lambda root, s: None)
    host = RunnerAdapter.__new__(RunnerAdapter)
    host.calls = []
    host._design_refusal = lambda s: None
    host._admissible = lambda admitted: None
    host._require_frozen = lambda admitted: None
    host._background = lambda *args, **kw: host.calls.append(args[1]) or {"state": "x"}

    def never(*args, **kwargs):
        raise AssertionError("nothing is signed or sent over budget")

    host._require_evaluation = never
    host._require_commitment = never
    host._poster = never
    host._candidate_digest = lambda root: (1, "d" * 64)
    (tmp_path / "campaign-manifest.json").write_text("{}", encoding="utf-8")
    (tmp_path / "epoch-1").mkdir()
    (tmp_path / "epoch-1" / "selected-recipe.json").write_text(
        json.dumps({"strategy": strategy()}), encoding="utf-8"
    )
    return host, SimpleNamespace(campaign={"id": "c", "root": str(tmp_path)})


def test_freeze_is_refused_over_budget_with_the_numbers(
    declared, tmp_path, monkeypatch
):
    host, admitted = _host(tmp_path, monkeypatch)
    declared({"unit": "F1", "value": 1000}, {"F1": 1500})
    request = {"strategy": strategy(), "reason": "best practice run"}
    with pytest.raises(Rejected) as refused:
        host.freeze_candidate_admitted(admitted, request)
    assert refused.value.code == "over_compute_budget"
    assert refused.value.budget == {"unit": "F1", "used": 1500, "allowed": 1000}
    assert "1,500 F1" in refused.value.next_step
    assert host.calls == []
    budget_view._status.cache_clear()
    declared({"unit": "F1", "value": 1000}, {"F1": 500})
    value = host.freeze_candidate_admitted(admitted, request)
    assert host.calls == ["freeze_candidate"]
    assert (value["budget_status"]["used"], value["budget_status"]["within"]) == (
        500,
        True,
    )


def test_freeze_without_a_budget_shows_not_set(tmp_path, monkeypatch):
    host, admitted = _host(tmp_path, monkeypatch)
    value = host.freeze_candidate_admitted(
        admitted, {"strategy": strategy(), "reason": "best practice run"}
    )
    assert value["budget_status"]["status"] == "NOT_SET"


@pytest.mark.parametrize("operation", ["submit", "commit"])
def test_submit_and_commit_refuse_over_budget_before_signing(
    declared, tmp_path, monkeypatch, operation
):
    host, admitted = _host(tmp_path, monkeypatch)
    declared({"unit": "F1", "value": 1000}, {"F1": 1500})
    with pytest.raises(Rejected) as refused:
        getattr(host, operation + "_admitted")(admitted, {})
    assert refused.value.code == "over_compute_budget"
    assert refused.value.budget["used"] == 1500
    assert host.calls == []
    # An unmeasurable cost under a declared budget is refused too, never sent.
    budget_view._status.cache_clear()
    declared({"unit": "F2", "value": 10.0}, {"F2": cost.HUMAN_INPUT})
    with pytest.raises(Rejected) as refused:
        getattr(host, operation + "_admitted")(admitted, {})
    assert refused.value.code == "cost_unmeasurable"


def test_submit_shows_the_status_when_within(declared, tmp_path, monkeypatch):
    host, admitted = _host(tmp_path, monkeypatch)
    host._require_evaluation = lambda admitted: None
    host._require_commitment = lambda admitted: None
    declared({"unit": "F1", "value": 1000}, {"F1": 500})
    value = host.submit_admitted(admitted, {})
    assert host.calls == ["submit"]
    assert value["budget_status"]["within"] is True
