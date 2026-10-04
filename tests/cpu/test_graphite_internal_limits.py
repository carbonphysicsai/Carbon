"""Internal Graphite's session limits: money and time, not call counts.

OWNER-GRAPHITE-MINER-01 §6 (2026-10-03): "I don't like that internal graphite
has limits like that". A NEW internal session runs under
`provider.SESSION_LIMITS_V2`: no session-turn cap (the 150 of GRAPHITE-D26)
and no per-role call cap. The grant's per-run money cap, the controller's
reservation for the run, and the task's runtime bind; stall detection and its
one-rung escalation stay; the loop gets the engine's count-free limits and
recorded compaction. A session recorded under the old caps resumes under them
and replays byte-identically.

Claims tested, with a scripted model, scripted pods and no spend:

- a new session freezes the v2 rule with the money cap and elapsed limit it
  binds, and the per-run worst case stays computable from money alone;
- the loop receives `LIMITS_V2` with no counts and `COMPACTION_V1`, never a
  call cap; a v1 session receives exactly the cap it had;
- a v1 plan is byte-identical to the plan the code before this change wrote
  (digests pinned from 9bfd9add), and a v1 record resumes under its own cap
  on a provider that opens v2 sessions, from every crash point;
- a resume under a changed or unknown rule is refused before any call;
- end to end, a v2 Constructor session runs past 150 calls until its money
  cap; a money stop still bundles the best improvement and applies the stall
  rule; an elapsed stop launches no new pod.

The end-to-end claims run on the engine's limits rule (`research_loop` with
`limits`/`compaction`, slice S1). Predictions are SYNTHETIC. Nothing here is
scientific, security or production qualification.
"""

from __future__ import annotations

import json
from decimal import Decimal

import pytest
from graphite_fixtures import RecordingMinerTools, reader_script, started
from graphite_fixtures import provider as harness_provider
from graphite_phase3_fixtures import (
    LEDGER_NOW,
    PREFIX,
    ScriptedPods,
    brief,
    controller,
    grant,
    propose,
    provider,
    run_id,
    session,
    steps,
    text,
    tool,
    variant,
)

from carbon.agent_campaign import controller as ctl
from carbon.agent_campaign.graphite import experiment as ex
from carbon.agent_campaign.graphite import phase3
from carbon.agent_campaign.graphite import provider as gp
from carbon.agent_campaign.graphite.model import ScriptedModel
from carbon.agent_campaign.graphite.roles import (
    CONSTRUCTOR_SESSION_TURNS,
    CONSTRUCTOR_STALL_ATTEMPTS,
    RoleName,
)
from carbon.agent_campaign.provider import RunState
from carbon.development_session.model_provider import ENGY_LADDER
from carbon.development_session.profile import canonical, digest
from carbon.development_session.research_agent_policy import (
    COMPACTION_V1,
    LIMITS_V2,
)

PROBE = tool(PREFIX + "get_challenge_info", {})
#: The epoch plans the code before this change (9bfd9add) wrote for the two
#: v1 scenarios below. A v1 session must still write these exact bytes.
V1_CONSTRUCTOR_PLAN = (
    "sha256:eee0290d80bc854a7af1526fcf84ff1673bf8c4882e0c000d8a8a9d6b492b08f"
)
V1_READER_PLAN = (
    "sha256:5c3d46bc02da2a7e0ad27d88c312b161b6fa2c8fc81766a24eb2dd1791f2c120"
)
CAPPED_ON_MONEY = {"code": "run_cap_reached", "dimension": "provider_nanodollars"}
CAPPED_ON_TIME = {"code": "run_cap_reached", "dimension": "elapsed_seconds"}


def _opened(graphite, number=1):
    path = graphite._dir(run_id(number)) / "session-open.json"
    return json.loads(path.read_bytes())


def _plan_bytes(run_dir):
    return (run_dir / "ledger" / "epoch-1" / "plan.json").read_bytes()


def _state(graphite):
    return json.loads((graphite._dir(run_id()) / "state.json").read_bytes())


class LoopRecorder:
    """Records the arguments each session passes to `run_epoch`, then runs
    the real loop with them."""

    def __init__(self, real):
        self.real, self.calls = real, []

    async def __call__(self, ledger, **kwargs):
        self.calls.append(kwargs)
        return await self.real(ledger, **kwargs)


@pytest.fixture
def recorded_loop(monkeypatch):
    recorder = LoopRecorder(gp.run_epoch)
    monkeypatch.setattr(gp, "run_epoch", recorder)
    monkeypatch.setattr(phase3, "run_epoch", recorder)
    return recorder


# -- the rule a new session freezes ------------------------------------------------------
def test_the_engine_rules_a_v2_session_passes_are_the_engines():
    assert LIMITS_V2["schema"] == "carbon.autoresearch.limits.v2"
    assert gp.LOOP_LIMITS == {
        **LIMITS_V2,
        "calls_per_epoch": None,
        "trials_per_epoch": None,
    }
    assert COMPACTION_V1["schema"] == "carbon.autoresearch.compaction.v1"
    assert gp.SESSION_LIMITS == (gp.SESSION_LIMITS_V1, gp.SESSION_LIMITS_V2)


def test_a_new_session_freezes_the_v2_rule_with_its_money_and_time_bounds(tmp_path):
    result, graphite, _ = session(tmp_path, [PROBE, text("done")], ScriptedPods())
    assert result["provider_state"] == "succeeded"
    opened = _opened(graphite)
    grant_ = graphite.grant
    assert opened["session_limits"] == {
        "schema": gp.SESSION_LIMITS_V2,
        "authority": "OWNER-GRAPHITE-MINER-01",
        "session_turns": None,
        "role_call_cap": None,
        "operator_call_cap": None,
        # The run's whole cap, tokens and pods: the controller's reservation.
        "money_cap_nanodollars": 4_910_000_000,
        # Of which model calls may take the token share.
        "model_spend_cap_nanodollars": 1_950_000_000,
        "elapsed_seconds": grant_.max_runtime_s,
        "binding": ["money_cap", "elapsed_seconds"],
        "loop_limits": gp.LOOP_LIMITS,
        "compaction": COMPACTION_V1,
        "money_cap_covers": "model_calls_and_pods",
        "pods_per_session": 12,
        "stall_attempts": CONSTRUCTOR_STALL_ATTEMPTS,
        "stall_escalation": "one_rung",
        "on_cap_stop": "bundle_best_improvement_and_escalate_on_stall",
        "on_elapsed_stop": "escalate_on_stall_without_new_pods",
    }
    # No count caps the run's ledger: only money and elapsed time.
    assert opened["caps"]["provider_attempts"] is None
    assert graphite.caps()["provider_attempts"] is None
    assert opened["caps"]["provider_nanodollars"] == 1_950_000_000
    # The money cap is the controller's per-run reservation, so its gate
    # "spent + run worst case + cleanup <= ceiling" is computed from money.
    cap = Decimal(opened["session_limits"]["money_cap_nanodollars"]) / 10**9
    assert cap == grant_.worst_case_run_cost == Decimal("4.91")
    runs = (grant_.monetary_ceiling - grant_.cleanup_allowance) // cap
    assert runs == grant_.permitted_runs == 3
    assert result["session_limits"] == opened["session_limits"]


def test_an_operator_call_cap_still_narrows_a_v2_run(tmp_path):
    """No call cap is Carbon's; an operator may still set one, recorded."""
    graphite = provider(tmp_path, [PROBE] * 3, ScriptedPods(), max_calls_per_run=2)
    assert graphite.caps()["provider_attempts"] == 2
    record = graphite.session_limits_record({"max_runtime_s": 60})
    assert record["operator_call_cap"] == 2
    assert record["session_turns"] is None and record["role_call_cap"] is None


def test_the_loop_gets_count_free_limits_and_compaction_never_a_call_cap(
    tmp_path, recorded_loop
):
    session(tmp_path / "p3", [PROBE, text("done")], ScriptedPods())
    reader, reader_run = started(tmp_path / "reader")
    assert reader.run(reader_run) == "succeeded"
    assert len(recorded_loop.calls) == 2
    for kwargs in recorded_loop.calls:
        assert "max_provider_calls" not in kwargs
        assert kwargs.get("limits") == gp.LOOP_LIMITS
        assert gp.LOOP_LIMITS["calls_per_epoch"] is None
        assert gp.LOOP_LIMITS["trials_per_epoch"] is None
        assert kwargs.get("compaction") == COMPACTION_V1


def test_a_v1_session_passes_exactly_the_cap_it_had(tmp_path, recorded_loop):
    session(
        tmp_path / "p3",
        [PROBE, text("done")],
        ScriptedPods(),
        session_limits=gp.SESSION_LIMITS_V1,
    )
    reader, reader_run = started(
        tmp_path / "reader", session_limits=gp.SESSION_LIMITS_V1
    )
    assert reader.run(reader_run) == "succeeded"
    constructor, harness = recorded_loop.calls
    # The Constructor's GRAPHITE-D26 cap; the harness role the loop's shared 48.
    assert constructor["max_provider_calls"] == CONSTRUCTOR_SESSION_TURNS == 150
    assert "max_provider_calls" not in harness
    for kwargs in (constructor, harness):
        assert "limits" not in kwargs and "compaction" not in kwargs


def test_an_unknown_rule_is_refused_before_anything_opens(tmp_path):
    with pytest.raises(ValueError, match="session-limits rule"):
        harness_provider(tmp_path / "graphite", session_limits="carbon.graphite.x")
    assert not (tmp_path / "graphite").exists()


# -- old records replay byte-identically ---------------------------------------------------
def test_a_v1_plan_is_byte_identical_to_the_one_written_before_the_change(tmp_path):
    result, graphite, _ = session(
        tmp_path / "p3",
        [PROBE, PROBE, text("done")],
        ScriptedPods(),
        session_limits=gp.SESSION_LIMITS_V1,
    )
    assert result["provider_state"] == "succeeded"
    assert digest(_plan_bytes(graphite._dir(run_id()))) == V1_CONSTRUCTOR_PLAN
    opened = _opened(graphite)
    # The record has exactly the shape it had: no session_limits block.
    assert "session_limits" not in opened
    assert opened["caps"]["provider_attempts"] == 150
    assert result["session_limits"]["schema"] == gp.SESSION_LIMITS_V1
    assert result["session_limits"]["session_turns"] == 150
    reader, reader_run = started(
        tmp_path / "reader", session_limits=gp.SESSION_LIMITS_V1
    )
    assert reader.run(reader_run) == "succeeded"
    assert digest(_plan_bytes(reader._dir(reader_run))) == V1_READER_PLAN
    assert json.loads(_plan_bytes(reader._dir(reader_run)))["max_provider_calls"] == 48
    assert "session_limits" not in reader.session_record(reader_run)


def test_a_v1_record_resumes_under_its_own_cap_from_every_crash_point(tmp_path):
    """A provider that opens v2 sessions resumes a v1 record under v1: the
    same plan bytes, no reply resent, the same session record."""
    reference, reference_run = started(
        tmp_path / "reference", session_limits=gp.SESSION_LIMITS_V1
    )
    assert reference.run(reference_run) == "succeeded"
    expected = reference.session_record_digest(reference_run)
    points = reference._checkpoints
    assert points >= 8
    for point in range(1, points + 1):
        root = tmp_path / f"crash-{point:02d}"
        model = ScriptedModel(reader_script())
        crashed, run = started(
            root,
            model,
            crash_at_checkpoint=point,
            session_limits=gp.SESSION_LIMITS_V1,
        )
        with pytest.raises(ctl.SimulatedCrash):
            crashed.run(run)
        resumed = harness_provider(root, model)  # opens v2 sessions
        assert resumed.session_limits == gp.SESSION_LIMITS_V2
        assert resumed.status(run).state is RunState.RUNNING
        assert resumed.run(run) == "succeeded", point
        assert len(model.requests) == 3, point
        assert resumed.session_record_digest(run) == expected, point
        assert digest(_plan_bytes(resumed._dir(run))) == V1_READER_PLAN, point


def test_a_v2_record_resumes_under_v2_from_a_provider_configured_for_v1(tmp_path):
    model = ScriptedModel(reader_script())
    crashed, run = started(tmp_path / "g", model, crash_at_checkpoint=3)
    with pytest.raises(ctl.SimulatedCrash):
        crashed.run(run)
    resumed = harness_provider(
        tmp_path / "g", model, session_limits=gp.SESSION_LIMITS_V1
    )
    assert resumed.run(run) == "succeeded"
    assert len(model.requests) == 3
    record = resumed.session_record(run)
    assert record["session_limits"]["schema"] == gp.SESSION_LIMITS_V2
    assert record["caps"]["provider_attempts"] is None


@pytest.mark.parametrize(
    "change, detail",
    [
        (
            lambda block: block["compaction"].update(trigger_fraction=0.5),
            "session_limits_changed",
        ),
        (
            lambda block: block["loop_limits"].update(calls_per_epoch=150),
            "session_limits_changed",
        ),
        (lambda block: block.update(session_turns=150), "session_limits_changed"),
        (lambda block: block.update(elapsed_seconds=1), "session_limits_changed"),
        (lambda block: block.update(schema="carbon.x"), "session_limits_unknown"),
    ],
)
def test_a_resume_under_a_changed_rule_is_refused(tmp_path, change, detail):
    model = ScriptedModel(reader_script())
    graphite, run = started(tmp_path / "graphite", model)
    path = graphite._dir(run) / "session-open.json"
    opened = json.loads(path.read_bytes())
    change(opened["session_limits"])
    path.write_bytes(canonical(opened))
    assert graphite.run(run) == "failed"
    failure = graphite.session_record(run)["outcome"]["failure"]
    assert failure == {"code": "session_record_mismatch", "detail": detail}
    assert model.requests == []


def _open_phase3(graphite, number=1):
    """Open (not run) a phase-3 session; returns its run id."""
    from carbon.agent_campaign.graphite.roles import ROLES
    from carbon.agent_campaign.provider import TaskSpec

    _document, profile = phase3.permission_profile()
    spec = TaskSpec(
        campaign_id=phase3.CAMPAIGN,
        role=ROLES[RoleName.CONSTRUCTOR].boundary.value,
        workspace_id=phase3.WORKSPACE,
        credential_ref=phase3.CREDENTIAL_REF,
        profile_digest=profile,
        instructions_digest=graphite.register_brief(brief(graphite)),
        max_runtime_s=graphite.grant.max_runtime_s,
    )
    return graphite.start(spec, phase3.session_key(number)).provider_run_id


def test_a_v2_constructor_record_cannot_be_turned_into_a_v1_one(tmp_path):
    """Dropping the block would resume under the 150 cap; the caps the record
    froze (no call cap) no longer match v1's, so nothing runs."""
    graphite = provider(tmp_path, [PROBE, text("done")], ScriptedPods())
    run = _open_phase3(graphite)
    path = graphite._dir(run) / "session-open.json"
    opened = json.loads(path.read_bytes())
    assert opened["caps"]["provider_attempts"] is None
    del opened["session_limits"]
    path.write_bytes(canonical(opened))
    assert graphite.run(run) == "failed"
    failure = graphite.session_record(run)["outcome"]["failure"]
    assert failure == {
        "code": "session_record_mismatch",
        "detail": "grant_or_caps_changed",
    }
    assert graphite.model.requests == []


# -- end to end: money and time bind, not counts ---------------------------------------------
def _money_capped(tmp_path, script, pods, *, run_cost):
    """A Constructor session whose token share is `run_cost` less the 2.96 of
    pods, and whose every call settles at all but 440 nanodollars of its
    reservation, so the token share binds after a known number of calls
    (returned with the result)."""
    graphite = provider(
        tmp_path, script, pods, grant_changes={"worst_case_run_cost": run_cost}
    )
    reservation = graphite._selection(ENGY_LADDER[0]).reservation_nano
    graphite.model.charged_micro = reservation // 1000
    settled = graphite.model.charged_micro * 1000
    share = ex.usd_to_nano(graphite.budget.token_allowance_usd)
    calls = 0
    while calls * settled + reservation <= share:
        calls += 1
    control = controller(tmp_path, graphite)
    try:
        result = phase3.run_session(control, graphite, brief(graphite), 1)
    finally:
        control.close()
    return result, graphite, calls


def test_a_v2_constructor_session_runs_past_150_until_its_money_cap(tmp_path):
    """A token share of 0.54 USD (a 3.50 run less 2.96 of pods) holds 172
    calls at this charge: past the old 150, and the money cap stops it."""
    script = [PROBE] * 200
    result, graphite, expected = _money_capped(
        tmp_path, script, ScriptedPods(), run_cost="3.50"
    )
    assert expected == 172 > CONSTRUCTOR_SESSION_TURNS
    assert len(graphite.model.requests) == expected
    assert graphite.model.remaining == 200 - expected
    assert result["provider_state"] == "failed"
    assert _state(graphite)["failure"] == CAPPED_ON_MONEY
    tokens = graphite._tokens_usd(run_id())
    assert tokens <= graphite.budget.token_allowance_usd == Decimal("0.54")
    # The stop still closed the session: no improvement to bundle here.
    assert result["delivery"] == {"status": "NO_IMPROVEMENT", "bundle": None}


def test_a_money_stop_still_bundles_the_best_improvement(tmp_path):
    """A 3.00 run leaves 0.04 USD of tokens: the money cap stops the agent
    after a dozen calls, and the session still bundles its improvement."""
    script = [propose(variant(width=128))] + [PROBE] * 20
    account = ScriptedPods(steps=steps(1.0, 0.4, 1.0))
    result, graphite, expected = _money_capped(
        tmp_path, script, account, run_cost="3.00"
    )
    assert len(graphite.model.requests) == expected == 12
    assert _state(graphite)["failure"] == CAPPED_ON_MONEY
    outcome = result["delivery"] or {}
    assert outcome.get("status") == "BUNDLED"
    assert outcome["clean_rebuild"]["status"] == "REBUILT"
    # The ablation pod ran inside the same run cap, after the model stopped.
    assert len(account.launched) == 3 and account.alive == {}
    spend = graphite._tokens_usd(run_id()) + sum(
        graphite.experiment(run_id()).ledger.committed()
    )
    assert spend <= Decimal("3.00")


def test_a_stall_then_a_money_stop_escalates_one_rung(tmp_path):
    attempts = [propose(variant(width=w)) for w in (32, 40, 48, 56, 72)]
    account = ScriptedPods(steps=steps(1.0, 1.0, 1.0, 1.0, 1.0, 1.0))
    result, graphite, expected = _money_capped(
        tmp_path, [*attempts, *[PROBE] * 20], account, run_cost="3.00"
    )
    assert len(graphite.model.requests) == expected == 12
    assert _state(graphite)["failure"] == CAPPED_ON_MONEY
    assert graphite.experiment(run_id()).stall_observation()["attempts"] == 5
    history = graphite.ladder.history()
    assert len(history) == 1
    assert history[0]["kind"] == "build_stalled_against_baseline"
    assert graphite.ladder.model(RoleName.CONSTRUCTOR) == ENGY_LADDER[1]
    assert result["delivery"] == {"status": "NO_IMPROVEMENT", "bundle": None}


class JumpClock:
    """The run ledger's clock; `jump` moves it to one minute before the run's
    elapsed limit, so the next model call cannot fit its 120 s timeout."""

    def __init__(self, limit):
        self.now, self.limit = LEDGER_NOW, limit

    def __call__(self):
        return self.now

    def jump(self):
        self.now = LEDGER_NOW + self.limit - 60


def _elapsed_session(tmp_path, script_before, account):
    clock = JumpClock(grant().max_runtime_s)
    script = [*script_before, dict(PROBE, hook=clock.jump), text("never sent")]
    graphite = phase3.Phase3Provider(
        root=tmp_path / "graphite",
        grant=grant(),
        model=ScriptedModel(script),
        pods=account,
        miner_tools=RecordingMinerTools(),
        clock=clock,
        randomness=lambda n: b"\x01" * n,
    )
    control = controller(tmp_path, graphite)
    try:
        result = phase3.run_session(control, graphite, brief(graphite), 1)
    finally:
        control.close()
    return result, graphite


def test_an_elapsed_stop_launches_no_new_pod(tmp_path):
    account = ScriptedPods(steps=steps(1.0, 0.4, 1.0))
    result, graphite = _elapsed_session(
        tmp_path, [propose(variant(width=128))], account
    )
    assert result["provider_state"] == "failed"
    assert _state(graphite)["failure"] == CAPPED_ON_TIME
    assert graphite.model.remaining == 1
    # The improvement is recorded, but no ablation pod ran past the limit.
    assert len(account.launched) == 2 and account.alive == {}
    assert result["delivery"] is None


def test_an_elapsed_stop_still_applies_the_stall_rule(tmp_path):
    attempts = [propose(variant(width=w)) for w in (32, 40, 48, 56, 72)]
    account = ScriptedPods(steps=steps(1.0, 1.0, 1.0, 1.0, 1.0, 1.0))
    result, graphite = _elapsed_session(tmp_path, attempts, account)
    assert _state(graphite)["failure"] == CAPPED_ON_TIME
    history = graphite.ladder.history()
    assert len(history) == 1
    assert history[0]["kind"] == "build_stalled_against_baseline"
    assert result["delivery"] is None


def test_a_v1_session_closes_nothing_at_a_cap_as_before(tmp_path):
    """The historical rule is unchanged: a capped v1 run neither bundles nor
    escalates (only the v2 rule closes a session a limit stopped)."""
    attempts = [propose(variant(width=w)) for w in (32, 40, 48, 56, 72)]
    account = ScriptedPods(steps=steps(1.0, 1.0, 1.0, 1.0, 1.0, 1.0))
    clock = JumpClock(grant().max_runtime_s)
    script = [*attempts, dict(PROBE, hook=clock.jump), text("never sent")]
    graphite = phase3.Phase3Provider(
        root=tmp_path / "graphite",
        grant=grant(),
        model=ScriptedModel(script),
        pods=account,
        miner_tools=RecordingMinerTools(),
        clock=clock,
        randomness=lambda n: b"\x01" * n,
        session_limits=gp.SESSION_LIMITS_V1,
    )
    control = controller(tmp_path, graphite)
    try:
        result = phase3.run_session(control, graphite, brief(graphite), 1)
    finally:
        control.close()
    assert _state(graphite)["failure"] == CAPPED_ON_TIME
    assert graphite.experiment(run_id()).stall_observation() is not None
    assert graphite.ladder.history() == []
    assert result["delivery"] is None


def test_a_v2_harness_role_runs_past_the_shared_48(tmp_path):
    """A Reader session, which the loop's shared 48 capped, ends when the
    agent stops; under v1 it still stops at 48."""
    script = [tool("lit_search", {"query": "operator"})] * 50 + [text("done")]
    model = ScriptedModel(script)
    graphite, run = started(tmp_path / "v2", model)
    assert graphite.run(run) == "succeeded"
    assert len(model.requests) == 51
    old = ScriptedModel(list(script))
    historical, old_run = started(
        tmp_path / "v1", old, session_limits=gp.SESSION_LIMITS_V1
    )
    assert historical.run(old_run) == "succeeded"
    assert len(old.requests) == 48
    outcome = historical._dir(old_run) / "ledger" / "epoch-1" / "outcome.json"
    assert json.loads(outcome.read_bytes())["reason"] == "epoch provider-call ceiling"


def test_the_dry_run_shows_no_call_cap_and_the_money_cap(tmp_path, capsys):
    assert phase3.main(["run", "--root", str(tmp_path), "--dry-run"]) == 0
    output = capsys.readouterr().out
    result = json.loads(output[output.index("{\n") :])
    dry = result["dry_run"]
    # It still proves the parallel-call behaviour (LP-PROD-A)...
    assert dry["parallel_calls_run"] == 3 and dry["parallel_calls_not_run"] == 0
    # ...and now shows the session's bounds: money and time, no call count.
    assert dry["session_limits_rule"] == gp.SESSION_LIMITS_V2
    assert dry["model_call_cap"] is None
    assert dry["money_cap_usd"] == "4.91"
    assert dry["elapsed_limit_s"] == 39600
    assert result["session_limits"]["loop_limits"] == gp.LOOP_LIMITS
    assert result["provider_state"] == "succeeded"
    assert phase3.main(["status", "--root", str(tmp_path / "dry-run")]) == 0
    status = json.loads(capsys.readouterr().out)
    [row] = status.values()
    assert row["session_limits"]["session_turns"] is None


def test_the_phase3_budget_split_is_unchanged():
    """Grant math is unchanged: the run cap splits into 2.96 of pods and
    1.95 of tokens, from money alone."""
    budget = ex.phase3_budget(grant())
    assert budget.run_cap_usd == Decimal("4.91")
    assert budget.pod_allowance_usd == Decimal("2.96")
    assert budget.token_allowance_usd == Decimal("1.95")
