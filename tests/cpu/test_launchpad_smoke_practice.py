"""A bounded smoke practice the freeze accepts (LAUNCHPAD-SMOKE-PRACTICE-01).

Claims tested:

1. A smoke practice runs the exact recipe through the campaign's own practice
   callback with its training steps truncated (battery: `parameters.steps`
   capped at `SMOKE_STEPS`, split evenly over ensemble members), and records
   the truncation, its runtime and outcome SMOKE.
2. Its `recipe` is the ORIGINAL strategy, so the freeze's equality holds; it
   carries no score, metrics or diagnostics, and the trial file the practice
   put in the miner's workspace holds the smoke result, never the full one
   (invariant 12).
3. The freeze accepts a PASSED smoke practice of the same strategy at Levels
   0, 1, 2 and 3, a heavy Level 2 recipe among them, and refuses after a
   FAILED one or one that raised.
4. The default practice is unchanged: no mode records nothing, sends the same
   research request and returns the practice's own result.
5. A Challenge without the hook refuses smoke `smoke_practice_unavailable`,
   at the Launchpad's door and in the campaign's practice path.
6. A full practice that ends FAILED_INFRA at its time budget is refused
   `practice_time_budget_reached`, whose next step is a smoke practice.
7. Both doors take `mode` from the one operations table.

The training run is a fixture: these tests run no real training.
"""

from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace

import pytest

from carbon.battery import smoke_practice as battery_smoke
from carbon.battery.compile import compile_recipe
from carbon.challenge_registry import campaigns
from carbon.development_session import construction_level as cl
from carbon.development_session import research_campaign as rc
from carbon.development_session import smoke_practice as smoke
from carbon.development_session.profile import canonical, digest
from carbon.development_session.research_ledger import CampaignLedger
from carbon.development_session.research_tasks import PublicResearchExecutor
from carbon.development_session.research_workspace import ResearchWorkspace
from carbon.reconstruction import capability_registry as cr
from carbon.research import PracticeTaskSpec
from scripts.dev.miner_launchpad import operations, supervisor
from scripts.dev.miner_launchpad.controller import Rejected
from scripts.dev.miner_launchpad.runner import (
    PRACTICE_PARAMS,
    SMOKE_PRACTICE_PARAMS,
    RunnerAdapter,
)

BATTERY = cr.BATTERY_CHALLENGE
URL = "http://127.0.0.1:9/carbon/v1/battery/intake"
OWNER = "miner"
LIGHT = {
    "schema_version": "1.0",
    "challenge_id": BATTERY,
    "backbone": "mlp",
    "parameters": {"width": 16, "depth": 1, "steps": 48, "optimizer_family": "muon"},
}
#: The lane E shape: an MLP of width 256, a 4-member ensemble, 20,000 steps.
HEAVY = {
    "schema_version": "1.0",
    "challenge_id": BATTERY,
    "backbone": "mlp",
    "parameters": {
        "width": 256,
        "ensemble_members": 4,
        "steps": 20000,
        "optimizer_family": "muon",
    },
}


def challenge():
    return campaigns.challenge_ref(BATTERY)


def bound(level, arm=None):
    return cl.with_target(cl.resolve(BATTERY, level, arm), URL)


def ladder_facts():
    served = [{"level": 0, "digest": cr.contract_digest(BATTERY)}]
    for level in (1, 2, 3):
        found = cl.resolve(BATTERY, level)
        served.append(
            {
                "level": found["level"],
                "variant": found["variant"],
                "digest": found["digest"],
            }
        )
    return {"challenge": {"id": BATTERY}, "served_contracts": served}


@pytest.fixture(autouse=True)
def fresh_cache(monkeypatch):
    cl._compiled.cache_clear()
    monkeypatch.setattr(cl, "READ_TARGET", lambda challenge, url: ladder_facts())
    yield
    cl._compiled.cache_clear()


def full_result(strategy, *, finite=True, cases=12):
    """A battery-shaped full practice result, with a score the smoke result
    must never carry."""
    return {
        "schema": "carbon.battery.practice-feedback.v3",
        "provenance": "BATTERY_PUBLIC_PRACTICE",
        "recipe": strategy,
        "summary": {
            "n_cases": cases,
            "n_scored": cases,
            "n_failed_infra": 0,
            "eligible": True,
            "score": 0.123,
            "components": {"voltage": 0.1},
            "gate_failures": {} if finite else {"schema_finite": cases},
        },
        "fit": {"final_loss": 0.01 if finite else None, "train_s": 9.5},
        "safety": {"decision": "x"},
    }


class FixturePractice:
    """The campaign's practice callback, with a fixture training run: the
    real compile (at the campaign's level), no real training."""

    seconds = 600

    def __init__(self, ledger, *, level=None, outcome=full_result, raises=None):
        self.ledger, self.level = ledger, level
        self.outcome, self.raises = outcome, raises
        self.sent = []

    def compile(self, strategy):
        if self.level is None:
            return compile_recipe(strategy)
        return cl.level_compiler(self.level, compile_recipe)(strategy)

    def __call__(self, identity, strategy):
        self.compile(strategy)
        self.sent.append(strategy)
        if self.raises is not None:
            raise self.raises
        result = self.outcome(strategy)
        if self.level is not None:
            result["construction_level"] = cl.practice_label(self.level)
        ResearchWorkspace(self.ledger, OWNER).put(
            "trial-" + digest(identity.encode())[7:23] + "-battery-practice.json",
            canonical(result),
        )
        return result


def ledger_at(tmp_path, level=None):
    tmp_path.mkdir(parents=True, exist_ok=True)
    tmp_path.chmod(0o700)
    ledger = CampaignLedger(tmp_path / "campaign", clock=lambda: 1000)
    with ledger.db() as db:
        # As the campaign's research service creates it.
        db.execute(
            "CREATE TABLE IF NOT EXISTS research_results(owner TEXT NOT NULL,task TEXT NOT NULL,body BLOB NOT NULL,digest TEXT NOT NULL,PRIMARY KEY(owner,task))"
        )
    manifest = {"owner": OWNER, "agent": "none", "challenge": challenge()}
    if level is not None:
        manifest["construction_level"] = level
    (ledger.root / "campaign-manifest.json").write_bytes(canonical(manifest))
    return ledger, manifest


def execute(ledger, practice, strategy, identity, *, smoke_mode):
    """One practice task through the research executor, as the campaign's
    research service runs it; `smoke_mode` records the request first, as
    `practice_recipe` does."""
    if smoke_mode:
        smoke.record_request(ledger, OWNER, identity, strategy, challenge())
    executor = PublicResearchExecutor(
        ledger=ledger, owner=OWNER, image=None, public_material=None, practice=practice
    )
    task = "rtsk_" + digest(identity.encode())[7:71]
    executor.request_resolver = lambda _task: SimpleNamespace(
        task_spec=PracticeTaskSpec(strategy, None), idempotency_key=identity
    )
    executor._execute(SimpleNamespace(task_id=SimpleNamespace(value=task)))
    with ledger.db() as db:
        body = db.execute(
            "SELECT body FROM research_results WHERE owner=? AND task=?",
            (OWNER, task),
        ).fetchone()[0]
    return task, json.loads(body)


def prepared(ledger, manifest, practice=None):
    return rc.PreparedCampaign(
        args=SimpleNamespace(),
        ledger=ledger,
        owner=OWNER,
        manifest=manifest,
        seeds={},
        role_root=None,
        data=None,
        image=None,
        key=None,
        config=None,
        composition=SimpleNamespace(executor=SimpleNamespace(practice=practice)),
        sdk=None,
        task=None,
        grant=None,
        agent_policy=None,
        campaign=campaigns.campaign_for(challenge()),
    )


def freeze(ledger, manifest, strategy, monkeypatch):
    monkeypatch.setattr(rc, "report", lambda *_, **__: None)
    return asyncio.run(
        rc.freeze_candidate(
            prepared(ledger, manifest), strategy=strategy, reason="smoke passed"
        )
    )


# ---- 1, 2. The truncation and the result.


def test_battery_truncates_the_heavy_recipes_steps_and_records_the_cut():
    truncated, cut = battery_smoke.truncate(HEAVY, compile_recipe)
    assert cut == {
        "field": "parameters.steps",
        "steps_requested": 20000,
        "steps_run": battery_smoke.SMOKE_STEPS,
    }
    # Only the step budget changed; the cut compiles to exactly it.
    assert truncated["parameters"] == {
        **HEAVY["parameters"],
        "steps": battery_smoke.SMOKE_STEPS,
    }
    assert HEAVY["parameters"]["steps"] == 20000
    _c, recipe = compile_recipe(truncated)
    assert recipe.settings["steps"] == battery_smoke.SMOKE_STEPS
    assert recipe.settings["steps"] % recipe.settings["ensemble_members"] == 0


def test_a_recipe_within_the_cap_runs_its_own_steps():
    truncated, cut = battery_smoke.truncate(LIGHT, compile_recipe)
    assert truncated == LIGHT
    assert cut["steps_requested"] == cut["steps_run"] == 48


def test_the_cut_keeps_the_compiles_member_rules():
    from carbon.battery import compile as battery_compile

    assert battery_smoke.MIN_MEMBER_STEPS == battery_compile.MIN_MEMBER_STEPS
    heavy = json.loads(json.dumps(HEAVY))
    # Polish takes 600 of each member's steps: the cut leaves each member
    # the compile's minimum beyond it, above the cap's even share.
    heavy["parameters"].update(steps=16000, polish_steps=600)
    truncated, cut = battery_smoke.truncate(heavy, compile_recipe)
    _c, recipe = compile_recipe(truncated)
    settings = recipe.settings
    member = settings["steps"] // settings["ensemble_members"]
    assert settings["steps"] == cut["steps_run"] == 4 * (600 + 16) < 16000
    assert member - settings["polish_steps"] >= battery_compile.MIN_MEMBER_STEPS


def test_a_smoke_result_carries_no_score_and_its_recipe_is_the_original(tmp_path):
    ledger, _ = ledger_at(tmp_path)
    practice = FixturePractice(ledger)
    identity = "miner-practice-0000000000000001"
    _task, result = execute(ledger, practice, HEAVY, identity, smoke_mode=True)
    # The practice ran the cut recipe; the result records the original.
    assert practice.sent[0]["parameters"]["steps"] == battery_smoke.SMOKE_STEPS
    assert result["recipe"] == HEAVY
    assert result["provenance"] == smoke.SMOKE_PROVENANCE
    assert (result["outcome"], result["status"], result["failure"]) == (
        "SMOKE",
        "PASSED",
        None,
    )
    assert result["smoke"] == {
        "field": "parameters.steps",
        "steps_requested": 20000,
        "steps_run": battery_smoke.SMOKE_STEPS,
        "truncated": True,
    }
    assert type(result["runtime_seconds"]) is float
    assert set(result) <= smoke.RESULT_FIELDS
    text = json.dumps(result)
    for withheld in ("score", "summary", "fit", "components", "safety", "loss"):
        assert withheld not in text
    # The trial file the practice wrote holds the smoke result only.
    workspace = ResearchWorkspace(ledger, OWNER)
    trials = [i["name"] for i in workspace.inventory()]
    assert len(trials) == 1
    assert json.loads(workspace.get(trials[0])) == result


def test_the_default_practice_is_unchanged(tmp_path):
    ledger, _ = ledger_at(tmp_path)
    practice = FixturePractice(ledger)
    identity = "miner-practice-0000000000000002"
    _task, result = execute(ledger, practice, HEAVY, identity, smoke_mode=False)
    assert practice.sent == [HEAVY]
    assert result == full_result(HEAVY)
    assert smoke.requested(ledger, OWNER, identity) is None


def test_the_campaign_practice_path_records_smoke_and_sends_the_same_request(
    tmp_path,
):
    ledger, manifest = ledger_at(tmp_path)
    calls = []

    async def call(name, args, identity):
        calls.append((name, args, identity))
        return {"terminal_task": {"state": "SUCCEEDED"}}

    value = prepared(ledger, manifest, FixturePractice(ledger))
    value.sdk = SimpleNamespace(call=call)
    asked = {"hypothesis": "h", "expected_effect": "e"}
    asyncio.run(rc.practice_recipe(value, strategy=HEAVY, identity="full-1", **asked))
    asyncio.run(
        rc.practice_recipe(
            value, strategy=HEAVY, identity="smoke-1", mode="smoke", **asked
        )
    )
    # The research request itself is the same for both modes.
    assert calls[0][:2] == calls[1][:2]
    assert json.loads(calls[0][1]["strategy_json"]) == HEAVY
    assert smoke.requested(ledger, OWNER, "full-1") is None
    assert smoke.requested(ledger, OWNER, "smoke-1")["strategy_digest"] == digest(
        canonical(HEAVY)
    )


# ---- 3. The freeze, at every level.


@pytest.mark.parametrize("level", [None, 1, 2, 3])
def test_the_freeze_accepts_a_passed_smoke_practice(tmp_path, monkeypatch, level):
    found = None if level is None else bound(level)
    ledger, manifest = ledger_at(tmp_path, found)
    practice = FixturePractice(ledger, level=found)
    strategy = HEAVY if level == 2 else LIGHT
    assert rc.freeze_refusal(ledger.root, strategy) == "practice_result_required"
    identity = "miner-practice-l" + str(level)
    execute(ledger, practice, strategy, identity, smoke_mode=True)
    assert rc.freeze_refusal(ledger.root, strategy) is None
    answer = freeze(ledger, manifest, strategy, monkeypatch)
    record = json.loads((ledger.root / "epoch-1" / "selected-recipe.json").read_bytes())
    assert answer["selection"] == record and record["strategy"] == strategy
    if found is not None:
        assert record["contract_digest"] == found["digest"]


def test_the_heavy_level_2_recipe_is_cut_at_its_level(tmp_path):
    found = bound(2)
    ledger, _ = ledger_at(tmp_path, found)
    practice = FixturePractice(ledger, level=found)
    widened = json.loads(json.dumps(HEAVY))
    widened["parameters"]["muon_spectral"] = True
    _task, result = execute(
        ledger, practice, widened, "miner-practice-w2", smoke_mode=True
    )
    assert result["status"] == "PASSED" and result["recipe"] == widened
    # The level's own field is kept; only the step budget was cut.
    assert practice.sent[0]["parameters"] == {
        **widened["parameters"],
        "steps": battery_smoke.SMOKE_STEPS,
    }
    assert result["construction_level"]["digest"] == found["digest"]


def test_the_freeze_refuses_after_a_failed_smoke_practice(tmp_path, monkeypatch):
    ledger, manifest = ledger_at(tmp_path)
    practice = FixturePractice(
        ledger, outcome=lambda strategy: full_result(strategy, finite=False)
    )
    _task, result = execute(
        ledger, practice, HEAVY, "miner-practice-bad", smoke_mode=True
    )
    assert (result["status"], result["failure"]) == ("FAILED", "outputs_not_finite")
    assert "score" not in json.dumps(result)
    assert rc.freeze_refusal(ledger.root, HEAVY) == "practice_result_required"
    with pytest.raises(rc.OperationRefused, match="practice_result_required"):
        freeze(ledger, manifest, HEAVY, monkeypatch)


def test_a_smoke_practice_that_raises_records_nothing(tmp_path):
    ledger, _ = ledger_at(tmp_path)
    practice = FixturePractice(ledger, raises=RuntimeError("worker lost"))
    with pytest.raises(RuntimeError):
        execute(ledger, practice, HEAVY, "miner-practice-lost", smoke_mode=True)
    assert rc.freeze_refusal(ledger.root, HEAVY) == "practice_result_required"


def test_a_smoke_practice_of_another_recipe_does_not_freeze_this_one(tmp_path):
    ledger, _ = ledger_at(tmp_path)
    execute(ledger, FixturePractice(ledger), LIGHT, "miner-practice-o", smoke_mode=True)
    assert rc.freeze_refusal(ledger.root, LIGHT) is None
    assert rc.freeze_refusal(ledger.root, HEAVY) == "practice_result_required"


def test_only_a_passed_smoke_result_supports_selection():
    passed = {
        "schema": smoke.SMOKE_RESULT_SCHEMA,
        "provenance": smoke.SMOKE_PROVENANCE,
        "outcome": "SMOKE",
        "status": "PASSED",
        "failure": None,
    }
    assert smoke.is_passed(passed)
    for change in (
        {"status": "FAILED"},
        {"failure": "outputs_missing"},
        {"outcome": "FULL"},
        {"provenance": "BATTERY_PUBLIC_PRACTICE"},
        {"schema": "other"},
    ):
        assert not smoke.is_passed({**passed, **change})
    # A smoke result never counts as a scored practice anywhere.
    assert smoke.SMOKE_PROVENANCE not in rc.practice_provenances()


# ---- 5. A Challenge without the hook.


def test_a_challenge_without_the_hook_refuses_smoke(tmp_path):
    cold_plate = campaigns._campaigns()[cr.COLD_PLATE_CHALLENGE]()
    assert cold_plate.smoke_practice is None
    with pytest.raises(smoke.SmokeUnavailable) as refused:
        smoke.hook_of(cold_plate)
    assert refused.value.code == "smoke_practice_unavailable"
    ledger, manifest = ledger_at(tmp_path)
    value = prepared(ledger, manifest)
    value.campaign = cold_plate
    value.sdk = SimpleNamespace(call=None)
    with pytest.raises(rc.OperationRefused, match="smoke_practice_unavailable"):
        asyncio.run(
            rc.practice_recipe(
                value,
                strategy=LIGHT,
                hypothesis="h",
                expected_effect="e",
                identity="smoke-2",
                mode="smoke",
            )
        )
    assert smoke.requested(ledger, OWNER, "smoke-2") is None


def test_the_launchpad_door_refuses_smoke_where_there_is_no_hook(tmp_path):
    root = tmp_path / "c"
    root.mkdir()
    admitted = SimpleNamespace(campaign={"root": str(root)}, profile={})
    for manifest in (
        {"challenge": campaigns.challenge_ref(cr.COLD_PLATE_CHALLENGE)},
        {"challenge": {"id": "no-such-challenge", "version": "1"}},
    ):
        (root / "campaign-manifest.json").write_bytes(canonical(manifest))
        with pytest.raises(Rejected) as refused:
            RunnerAdapter._practice_mode(admitted, {"mode": "smoke"})
        assert refused.value.code == "smoke_practice_unavailable"
        # Full practice never reads the hook.
        assert RunnerAdapter._practice_mode(admitted, {}) == "full"
    (root / "campaign-manifest.json").write_bytes(canonical({"challenge": challenge()}))
    assert RunnerAdapter._practice_mode(admitted, {"mode": "smoke"}) == "smoke"
    with pytest.raises(Rejected) as refused:
        RunnerAdapter._practice_mode(admitted, {"mode": "SMOKE"})
    assert (refused.value.code, refused.value.status) == ("practice_mode_invalid", 400)


# ---- 6. The next step on a full practice that reached its budget.


@pytest.mark.parametrize(
    ("mode", "state", "refused"),
    [
        (None, "FAILED_INFRA", "practice_time_budget_reached"),
        (None, "SUCCEEDED", None),
        # A smoke practice never reaches the budget refusal; its infrastructure failure
        # is said as practice_could_not_run.
        ("smoke", "FAILED_INFRA", "practice_could_not_run"),
    ],
)
def test_a_full_practice_at_its_budget_names_smoke_as_its_next_step(
    tmp_path, mode, state, refused
):
    ledger, manifest = ledger_at(tmp_path)
    practice = FixturePractice(ledger)
    # A zero budget: any elapsed time is at it.
    practice.seconds = 0

    async def call(name, args, identity):
        return {"terminal_task": {"state": state}}

    value = prepared(ledger, manifest, practice)
    value.sdk = SimpleNamespace(call=call)
    run = rc.practice_recipe(
        value,
        strategy=HEAVY,
        hypothesis="h",
        expected_effect="e",
        identity="budget-" + str(mode),
        mode=mode,
    )
    if refused:
        with pytest.raises(rc.OperationRefused, match=refused):
            asyncio.run(run)
    else:
        assert asyncio.run(run)["terminal_task"]["state"] == state
    step = supervisor.next_action("practice_time_budget_reached")
    assert "mode: smoke" in step and "carbon_practice" in step


def test_a_failed_full_practice_short_of_its_budget_is_not_read_as_reaching_it():
    answer = {"terminal_task": {"state": "FAILED_INFRA"}}
    assert not smoke.reached_time_budget(answer, 30.0, 600)
    assert smoke.reached_time_budget(answer, 560.0, 600)
    assert not smoke.reached_time_budget(answer, 560.0, None)


# ---- 7. The doors.


def test_both_doors_take_mode_from_the_one_table():
    practice = operations.OPERATIONS["practice"]
    assert "mode" in practice.optional and "mode" not in practice.required
    assert operations.CHOICES["mode"] == ("full", "smoke")
    for code in ("smoke_practice_unavailable", "practice_mode_invalid"):
        assert operations.refusal(code)["field"] == "mode"
    for code in (
        "smoke_practice_unavailable",
        "practice_mode_invalid",
        "practice_time_budget_reached",
    ):
        assert code in supervisor.NEXT_ACTIONS
    # No other operation takes it.
    assert [n for n, op in operations.OPERATIONS.items() if "mode" in op.optional] == [
        "practice"
    ]


def test_an_interrupted_smoke_practice_is_sent_again_as_smoke():
    assert SMOKE_PRACTICE_PARAMS == PRACTICE_PARAMS | {"mode"}
    item = {
        "params": json.dumps(
            {
                "strategy": HEAVY,
                "hypothesis": "h",
                "expected_effect": "e",
                "identity": "miner-practice-1",
                "mode": "smoke",
            }
        )
    }
    again = RunnerAdapter._retried_params(item)
    assert again["mode"] == "smoke" and again["identity"] != "miner-practice-1"
    # A full practice records no mode, and is sent again without one.
    full = {
        "params": json.dumps(
            {
                "strategy": HEAVY,
                "hypothesis": "h",
                "expected_effect": "e",
                "identity": "miner-practice-2",
            }
        )
    }
    assert set(RunnerAdapter._retried_params(full)) == PRACTICE_PARAMS


def test_observe_lists_a_smoke_result_apart_with_its_own_fields():
    result = {
        "schema": smoke.SMOKE_RESULT_SCHEMA,
        "provenance": smoke.SMOKE_PROVENANCE,
        "outcome": "SMOKE",
        "status": "PASSED",
        "failure": None,
        "recipe": HEAVY,
        "runtime_seconds": 12.5,
        "smoke": {"truncated": True},
        "summary": {"score": 1.0},
    }
    view = smoke.public_view("rtsk_1", result)
    assert view["id"] == "rtsk_1" and "summary" not in view
    assert set(view) - {"id"} <= smoke.RESULT_FIELDS


@pytest.mark.parametrize("state", ["FAILED_INFRA", "UNRESOLVED"])
@pytest.mark.parametrize("mode", [None, "smoke"])
def test_a_practice_that_ran_nothing_says_so_with_a_code_and_a_next_step(
    tmp_path, mode, state
):
    """M1 rc38: a practice whose host-readiness stage failed was answered READY with no
    experiment and no refusal. A task that ended FAILED_INFRA or UNRESOLVED is now refused
    practice_could_not_run, whose next step is plain."""
    ledger, manifest = ledger_at(tmp_path)
    practice = FixturePractice(ledger)
    practice.seconds = 10**6  # well inside the budget: not the time-budget refusal

    async def call(name, args, identity):
        return {"terminal_task": {"state": state}}

    value = prepared(ledger, manifest, practice)
    value.sdk = SimpleNamespace(call=call)
    with pytest.raises(rc.OperationRefused, match="practice_could_not_run"):
        asyncio.run(
            rc.practice_recipe(
                value,
                strategy=HEAVY,
                hypothesis="h",
                expected_effect="e",
                identity="nothing-" + str(mode) + state,
                mode=mode,
            )
        )
    step = supervisor.next_action("practice_could_not_run")
    assert "infrastructure problem" in step and "carbon_setup_status" in step
    assert "practice_could_not_run" in supervisor.NEXT_ACTIONS


def test_a_practice_that_produced_a_result_is_returned_unchanged(tmp_path):
    ledger, manifest = ledger_at(tmp_path)
    practice = FixturePractice(ledger)
    practice.seconds = 10**6
    answer = {"terminal_task": {"state": "SUCCEEDED"}, "experiments": [1]}

    async def call(name, args, identity):
        return answer

    value = prepared(ledger, manifest, practice)
    value.sdk = SimpleNamespace(call=call)
    assert (
        asyncio.run(
            rc.practice_recipe(
                value,
                strategy=HEAVY,
                hypothesis="h",
                expected_effect="e",
                identity="ok-run",
                mode=None,
            )
        )
        is answer
    )
