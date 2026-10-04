"""Graphite phase 4: the Attacker session driver for the general attack engine
(OWNER-GRAPHITE-ATTACKER-01; slice AT-E).

Two layers. The session-side tests (limits, tools, brief, neutrality, the
provider's guards, the store-outcome rule) use a small stand-in adapter and
stub Carbon's side, so they run before the engine merges. The engine tests
drive Carbon's side through the real `carbon.agent_campaign.attack` modules
(their published `Verdict`, `DeclaredAdapter`, `AttackStore`, report and B2)
with a synthetic second Challenge and battery's Level 0 adapter; they skip
until those modules are importable. A scripted model and scripted or no pods
mean no live inference, no pod, no key, no network and no spend.
"""

from __future__ import annotations

import asyncio
import importlib.util
import io
import json
import types
from contextlib import redirect_stdout
from decimal import Decimal
from pathlib import Path

import pytest

from carbon.agent_campaign import controller as controller_mod
from carbon.agent_campaign.grant import SpendingGrant
from carbon.agent_campaign.graphite import phase4
from carbon.agent_campaign.graphite.model import ScriptedModel, text, tool
from carbon.agent_campaign.graphite.pods import PodFailure, ScriptedPods
from carbon.agent_campaign.graphite.provider import SESSION_LIMITS_V2, SessionBrief
from carbon.agent_campaign.graphite.roles import ROLES, RoleName
from carbon.agent_campaign.provider import ProviderUnavailable, TaskSpec
from carbon.development_session.research_tools import PREFIX

REPOSITORY = Path(__file__).resolve().parents[2]
GRANT_FILE = REPOSITORY / phase4.GRANT_FILE
CID = phase4.BATTERY_CHALLENGE
ENGINE = importlib.util.find_spec("carbon.agent_campaign.attack") is not None
needs_engine = pytest.mark.skipif(
    not ENGINE, reason="the attack engine slices (AT-A..AT-D) are not merged here"
)


# -- a stand-in adapter (the core's FamilyDef / SeamFamily shapes) ------------------------
class Def(types.SimpleNamespace):
    """A family as the core's `FamilyDef` names it: name, check, boundary."""


class StandIn:
    """A neutral Challenge at Level 0 with the core protocol and the session
    surface. Not battery: the driver must take everything from it."""

    challenge_id = "stand-in-challenge-v1"
    level = 0
    contract_digest = "sha256:" + "a" * 64

    def __init__(self, boundaries=None, **surface):
        boundaries = boundaries or {
            "recipe_fields": "Does the path refuse undeclared recipe fields?",
            "mandatory_cases": "Does a mandatory failure stop a soft score?",
        }
        self._families = tuple(
            Def(name=name, check="artifact_and_dependency_attacks", boundary=text_)
            for name, text_ in boundaries.items()
        )
        self._surface = {
            "public_identity": lambda: {"id": "stand-in-challenge", "version": "1"},
            "code_run_seconds": lambda: 600,
            "recipe_outside_contract": lambda: {"model_family": "transolver"},
            **surface,
        }

    def __getattr__(self, name):
        try:
            return self.__dict__["_surface"][name]
        except KeyError:
            raise AttributeError(name) from None

    def families(self):
        return self._families

    def controls(self, split):
        return ()

    def level_families(self):
        return (Def(name="participant_code", check="fresh_attack_confirmation"),)


class FakeView:
    def __init__(self, value):
        self.digest = value

    def priors(self, challenge_id):
        return {"by_family": {"recipe_fields": {"attempts": 1, "boundaries": {}}}}

    def replay(self, value):
        assert value == self.digest
        return self


class FakeStore:
    def __init__(self, root):
        self.root = root

    def snapshot(self):
        return "sha256:" + "c" * 64

    def pin(self, value):
        return FakeView(value)


def stand_in_modules(adapter):
    return {
        "adapter": types.SimpleNamespace(ADAPTERS={(CID, 0): adapter}),
        "knowledge": types.SimpleNamespace(AttackStore=FakeStore),
    }


def _grant():
    return SpendingGrant.from_document(
        {**json.loads(GRANT_FILE.read_bytes()), "expires_at": "2099-01-01T00:00:00Z"}
    )


def _provider(tmp_path, script, *, adapter, miner_tools=None, pods=None):
    grant = _grant()
    provider = phase4.AttackerProvider(
        root=tmp_path / "graphite",
        grant=grant,
        model=ScriptedModel(script),
        pods=pods or ScriptedPods(),
        adapter=adapter,
        miner_tools=miner_tools,
    )
    return provider, grant


def _refusal(capsys, call):
    with pytest.raises(SystemExit):
        call()
    return json.loads(capsys.readouterr().out.strip().splitlines()[-1])["reason_code"]


# -- the session's limits: money and time bind, never a call count -------------------------
def test_the_dry_run_session_has_no_call_cap_and_freezes_the_attackers_limits(
    tmp_path, monkeypatch
):
    """A call cap reintroduced anywhere on the dry-run path turns this red: in
    `dry_run`/`command_run` (`max_calls_per_run`), or in `_epoch`'s loop
    arguments (`max_provider_calls`)."""
    adapter = StandIn()
    seen = {}
    real_run_epoch = phase4.run_epoch

    async def recording_run_epoch(*args, **kwargs):
        seen["kwargs"] = kwargs
        return await real_run_epoch(*args, **kwargs)

    def stub_side(store, control, provider, run_id, adapter, atk, **kw):
        seen["opened"] = provider._opened(run_id)
        seen["caps"] = provider.caps()
        return {"attack_knowledge": {"after": kw["view"].digest}}, {}, [], None

    monkeypatch.setattr(phase4, "run_epoch", recording_run_epoch)
    monkeypatch.setattr(phase4, "carbon_side", stub_side)
    monkeypatch.setattr(phase4, "attack_modules", lambda: stand_in_modules(adapter))
    out = io.StringIO()
    with redirect_stdout(out):
        code = phase4.main(["run", "--root", str(tmp_path / "root"), "--dry-run"])
    assert code == 0
    assert "max_provider_calls" not in seen["kwargs"]
    limits = seen["opened"]["session_limits"]
    assert limits["schema"] == SESSION_LIMITS_V2
    assert limits["session_turns"] is None and limits["role_call_cap"] is None
    assert limits["operator_call_cap"] is None
    assert seen["opened"]["caps"]["provider_attempts"] is None
    assert seen["caps"]["provider_attempts"] is None
    assert limits["binding"] == ["money_cap", "elapsed_seconds"]
    # What the Attacker does, not the Constructor's pod/delivery/stall rule.
    assert limits["on_limit_stop"] == "record_attempts_only"
    assert limits["pods_per_session"] == 0
    assert limits["verify_pod_rebuild"] == "NOT_RUN"
    assert limits["code_run_seconds_at_most"] == 600
    assert "stall_attempts" not in limits and "pod_admission" not in limits
    body = out.getvalue()
    printed = json.loads(body[body.index('{\n "coverage"') :])
    assert printed["dry_run"]["money_cap_usd"] == "1.93"
    assert Decimal(printed["session"]["settled_usd"]) < Decimal("0.01")
    assert printed["session"]["store_pinned"] == "sha256:" + "c" * 64


def test_the_token_cap_is_the_attacker_pod_split(tmp_path):
    provider, _ = _provider(tmp_path, [text("done")], adapter=StandIn())
    assert provider.budget.max_pods == phase4.ATTACKER_VERIFY_PODS == 6
    assert str(provider.budget.token_allowance_usd) == "1.93"
    assert str(provider.budget.pod_allowance_usd) == "1.48"


def test_a_live_attacker_launches_no_pod():
    """While Carbon's verify-pod rebuild is a declared seam, the live pod
    backend refuses a launch before any provider write and charges nothing."""
    pods = phase4.NoVerifyPods()
    with pytest.raises(PodFailure) as refused:
        pods.launch(None, None)
    assert refused.value.executed is False
    assert pods.recover("x", None) is None and pods.charge(None) == 0
    assert pods.describe()["seam"] == phase4.POD_REBUILD_SEAM["name"]


# -- the resource rule: a code run needs a wall allowance ----------------------------------
class RecordingMiner:
    def __init__(self, reply=None):
        self.calls = []
        self.reply = reply or {"status": "OK"}

    async def call(self, name, arguments, identity):
        self.calls.append((name, arguments, identity))
        return dict(self.reply)


def _run_python(seconds):
    inner = {"source": "print(1)", "files": []}
    if seconds is not None:
        inner["seconds"] = seconds
    return {
        "kind": "workspace",
        "strategy_json": None,
        "action": "run_python",
        "arguments_json": json.dumps(inner),
    }


@pytest.mark.parametrize(
    "seconds,dispatched",
    [(None, False), (0, False), (601, False), (600, True), (1, True)],
)
def test_a_code_run_needs_a_wall_allowance_within_the_adapter_ceiling(
    seconds, dispatched
):
    """Lifting `code_run_seconds` turns the 601 case green; it must stay a
    refusal before dispatch (family resource_and_failure_accounting)."""
    miner = RecordingMiner()
    tools = phase4.AttackerTools(
        miner=miner, emit=lambda *a: None, code_run_seconds=600
    )
    result = asyncio.run(
        tools.call(PREFIX + "start_research_task", _run_python(seconds), "id")
    )
    if dispatched:
        assert miner.calls and result["status"] == "OK"
    else:
        assert not miner.calls
        assert result["status"] == "REJECTED_BEFORE_DISPATCH"
        assert result["code_run_seconds_at_most"] == 600


def test_a_code_run_without_a_miner_path_is_unavailable_not_dispatched():
    tools = phase4.AttackerTools(miner=None, emit=lambda *a: None, code_run_seconds=600)
    result = asyncio.run(
        tools.call(PREFIX + "start_research_task", _run_python(600), "id")
    )
    assert result["status"] == "UNAVAILABLE"
    assert result["dispatched"] is False


# -- the brief: the adapter's own, never battery's ------------------------------------------
def test_the_brief_is_the_adapters_with_no_baseline():
    adapter = StandIn()
    knowledge = {"snapshot": "sha256:" + "c" * 64, "by_family": {}}
    observation = phase4.brief_observation(adapter, knowledge=knowledge)
    assert observation["challenge"] == {"id": "stand-in-challenge", "version": "1"}
    assert observation["challenge_id"] == adapter.challenge_id
    assert observation["contract_digest"] == adapter.contract_digest
    assert "baseline_strategy" not in observation
    assert [f["id"] for f in observation["families"]] == [
        "recipe_fields",
        "mandatory_cases",
    ]
    # Each family's goal is its boundary, in the adapter's neutral words.
    assert observation["families"][0]["goal"] == (
        "Does the path refuse undeclared recipe fields?"
    )
    assert observation["not_run"] == [{"id": "participant_code", "state": "NOT_RUN"}]
    assert observation["attack_knowledge"] == knowledge
    assert observation["limits"]["code_run_seconds_at_most"] == 600


def test_a_brief_naming_protected_material_is_refused():
    """A protected marker in a family boundary (the brief) must be refused
    (lesson 2026-10-02-attacker-brief-protected-markers)."""
    poisoned = StandIn(boundaries={"recipe_fields": "read the official_seed list"})
    with pytest.raises(ValueError, match="protected material"):
        phase4.brief_observation(poisoned)


@pytest.mark.parametrize("missing", ["public_identity", "code_run_seconds"])
def test_a_missing_session_surface_is_refused_never_battery(capsys, missing):
    """The driver substitutes no other Challenge's identity or limits."""
    adapter = StandIn(**{missing: None})
    code = _refusal(capsys, lambda: phase4.brief_observation(adapter))
    assert code == "adapter_session_surface_missing: " + missing


def test_the_dry_run_script_needs_the_adapters_refused_recipe(capsys):
    adapter = StandIn(recipe_outside_contract=None)
    code = _refusal(capsys, lambda: phase4.dry_run_script(adapter))
    assert code == "adapter_session_surface_missing: recipe_outside_contract"


# -- the provider runs the Attacker, on its adapter's brief only ---------------------------
def _spec(brief):
    return TaskSpec(
        campaign_id="x",
        role=ROLES[RoleName.ATTACKER].boundary.value,
        workspace_id="w",
        credential_ref="c",
        profile_digest="sha256:" + "a" * 64,
        instructions_digest=brief.digest,
        max_runtime_s=10,
    )


def test_phase4_runs_the_attacker_only(tmp_path):
    adapter = StandIn()
    provider, _ = _provider(tmp_path, [text("x")], adapter=adapter)
    constructor_brief = SessionBrief(
        role=RoleName.CONSTRUCTOR,
        initial_observation={"challenge": {"id": "stand-in-challenge"}},
        checkout_commit="0" * 40,
        checkout_manifest_digest="sha256:" + "b" * 64,
    )
    provider.register_brief(constructor_brief)
    with pytest.raises(ProviderUnavailable, match="phase4_runs_the_attacker_only"):
        provider.start(_spec(constructor_brief), "graphite-phase4-session-1")


def test_a_brief_for_another_challenge_is_refused(tmp_path):
    """A session never runs one Challenge's brief against another's adapter."""
    other = StandIn()
    other.challenge_id = "another-challenge-v1"
    provider, _ = _provider(tmp_path, [text("x")], adapter=StandIn())
    brief = phase4.session_brief(other, checkout_commit="0" * 40)
    provider.register_brief(brief)
    with pytest.raises(ProviderUnavailable, match="attacker_brief_challenge_id"):
        provider.start(_spec(brief), "graphite-phase4-session-1")


# -- verdicts: a finding is BREACHED with conditions, and never a near miss of infra ------
VERIFY = types.SimpleNamespace(
    BREACHED="BREACHED",
    HELD="HELD",
    INFRA="INFRA",
    UNREBUILDABLE="UNREBUILDABLE",
)


def _verdict(outcome, conditions=(), **rest):
    fields = {"rebuild": "NO_CONSTRUCTION", "refused_by": "path", "reason": None}
    return types.SimpleNamespace(
        outcome=outcome, conditions=conditions, **{**fields, **rest}
    )


def test_a_verdict_whose_breach_and_conditions_disagree_is_refused(capsys):
    assert phase4.is_finding(_verdict("BREACHED", ("FAILING_TRIGGER",)), VERIFY)
    assert not phase4.is_finding(_verdict("HELD"), VERIFY)
    for bad in (_verdict("BREACHED"), _verdict("HELD", ("OTHER_SIGNAL",))):
        code = _refusal(capsys, lambda bad=bad: phase4.is_finding(bad, VERIFY))
        assert code == "verdict_breach_and_conditions_disagree"


@pytest.mark.parametrize(
    "verdict,outcome",
    [
        (_verdict("BREACHED", ("FAILING_TRIGGER",)), "BREACHED"),
        (_verdict("HELD"), "HELD"),
        (_verdict("HELD", refused_by="graphite"), "NOT_RUN"),
        (_verdict("INFRA", reason="infra:FAILED_INFRA"), "CRASH"),
        (_verdict("INFRA", reason="oracle_no_answer:TIMEOUT"), "TIMEOUT"),
        (_verdict("HELD", rebuild="UNREBUILDABLE"), "UNREBUILDABLE"),
        (_verdict("UNDETERMINED"), "NOT_RUN"),
        (_verdict("NOT_APPLICABLE"), "NOT_RUN"),
    ],
)
def test_the_store_outcome_is_never_a_hold_for_what_was_not_judged(verdict, outcome):
    """A timeout, crash, unrebuildable construction or Graphite's own refusal
    is never stored as a hold (counting FAILED_INFRA as a pass turns this
    red)."""
    assert phase4.store_outcome(verdict, VERIFY) == outcome


# -- the runner ----------------------------------------------------------------------------
def test_the_live_run_requires_the_phase4_grant_and_credentials(
    capsys, tmp_path, monkeypatch
):
    modules = stand_in_modules(StandIn())
    monkeypatch.setattr(phase4, "attack_modules", lambda: modules)
    code = _refusal(capsys, lambda: phase4.main(["run", "--root", str(tmp_path / "r")]))
    assert code.startswith("required: --grant")
    other = tmp_path / "other-grant.json"
    other.write_text(
        json.dumps(
            {**json.loads(GRANT_FILE.read_bytes()), "grant_id": "SOMETHING-ELSE"}
        )
    )
    credential = tmp_path / "engy"
    credential.write_text("x")
    credential.chmod(0o600)
    argv = [
        "run",
        "--root",
        str(tmp_path / "r"),
        "--grant",
        str(other),
        "--credential-file",
        str(credential),
        "--miner-profile",
        "p.json",
        "--miner-campaign",
        "c",
    ]
    assert (
        _refusal(capsys, lambda: phase4.main(argv)) == "grant_is_not_the_phase4_grant"
    )


def test_cancel_asks_a_running_session_to_stop(tmp_path, capsys):
    run_id = phase4.GraphiteProvider.run_id_for(phase4.session_key(2))
    state = tmp_path / "attacker" / "graphite" / "runs" / run_id / "state.json"
    state.parent.mkdir(parents=True)
    state.write_text(json.dumps({"state": "running", "cancel_requested": False}))
    assert phase4.main(["cancel", "--root", str(tmp_path), "--session", "2"]) == 0
    assert json.loads(state.read_text())["cancel_requested"] is True
    assert _refusal(
        capsys,
        lambda: phase4.main(["cancel", "--root", str(tmp_path), "--session", "3"]),
    ) == ("unknown_session")


# == Carbon's side through the real engine ==================================================
SYNTHETIC = "synthetic-heat-sink-v1"
ALLOWED = frozenset({"model_family", "width"})
ATTACK = {"model_family": "mlp", "width": 8, "extra": 1}


def _synthetic_adapter(*, weak):
    """A second Challenge, with no battery code: one family run here
    (undeclared recipe fields), every other Track A check a declared seam."""
    from carbon.agent_campaign.attack import adapter as core
    from carbon.agent_campaign.attack import engine

    def compile_doc(doc, *, checked=True):
        if type(doc) is not dict:
            return {"accepted": False, "unknown": False}
        unknown = bool(set(doc) - ALLOWED)
        ok = doc.get("model_family") == "mlp" and (not unknown or not checked)
        return {"accepted": ok, "unknown": unknown}

    def boundary(doc):
        return compile_doc(doc, checked=not weak)

    family = engine.Family(
        name="recipe_fields",
        check="artifact_and_dependency_attacks",
        boundary=boundary,
        attacks=lambda: (("extra_field", ATTACK),),
        specimen=lambda doc: compile_doc(doc, checked=False),
        breached=lambda r: r["accepted"] and r["unknown"],
        control=lambda: True,
    )
    definition = core.FamilyDef(
        name="recipe_fields",
        check="artifact_and_dependency_attacks",
        boundary="Does the recipe compiler refuse a field the contract does not declare?",
        attack_example="extra_field",
        control_example="plain_recipe",
        family=family,
    )
    # Neutral seam names: a seam named after `fresh_attack_confirmation` would
    # trip the brief's protected filter (boundaries' denied paths).
    seams = tuple(
        core.SeamFamily(
            name=f"later_family_{index}", check=check, level=1, reason="not run here"
        )
        for index, check in enumerate(core.TRACK_A_CHECKS)
        if check != "artifact_and_dependency_attacks"
    )
    controls = (
        core.Control(
            "plain_recipe",
            "recipe_fields",
            "trained",
            "synthetic-v1",
            value={"model_family": "mlp", "width": 8},
        ),
        core.Control(
            "wide_recipe",
            "recipe_fields",
            "held_out",
            "synthetic-v1",
            value={"model_family": "mlp", "width": 32},
        ),
    )

    def rebuilder(construction):
        if type(construction) is not dict:
            return core.Unrebuildable("not_declarative")
        return core.Rebuilt(
            engine.digest(construction), engine.digest({"rebuilt": construction})
        )

    session = types.SimpleNamespace(
        permission_inventory=dict,
        public_identity=lambda: {"id": SYNTHETIC, "version": "1"},
        admission_refusals=lambda strategy: [],
        code_run_seconds=lambda: 60,
        recipe_outside_contract=lambda: {"model_family": "transolver"},
    )
    return core.DeclaredAdapter(
        challenge_id=SYNTHETIC,
        level=0,
        contract_digest=engine.digest({"synthetic": "contract-v1"}),
        family_defs=(definition,),
        control_set=controls,
        seams=seams,
        rebuilder=rebuilder,
        session=session,
    )


def _attack(tmp_path, adapter, script, miner):
    """One Attacker session on the real engine, as the dry run does, with a
    path that answers (`miner`)."""
    atk = phase4.attack_modules()
    store = tmp_path / "attacker"
    store.mkdir()
    provider, grant = _provider(store, script, adapter=adapter, miner_tools=miner)
    control = phase4.controller_for(store, provider, grant)
    kstore = phase4.open_store(store, atk)
    view = phase4.pin_session(store, 1, kstore)
    brief = phase4.session_brief(
        adapter,
        checkout_commit="0" * 40,
        knowledge=phase4.knowledge_brief(view, adapter),
    )
    try:
        entry, coverage = phase4.run_session(
            store,
            control,
            provider,
            adapter,
            brief,
            1,
            atk,
            budget=phase4.ATTACK_BUDGET,
            kstore=kstore,
            view=view,
        )
    except BaseException:
        control.close()
        raise
    return control, kstore, entry, coverage, brief


def _validate_script(construction):
    return [
        tool(PREFIX + "dry_validate", {"strategy_json": json.dumps(construction)}),
        text("done"),
    ]


def _blocked(control):
    """Whether the controller refuses expansion because of a finding."""
    try:
        control.record_expansion(
            challenge=CID,
            profile="sha256:" + "a" * 64,
            widened=["objective.loss_expressions"],
            permissions="sha256:" + "b" * 64,
            operator=phase4.OPERATOR,
        )
    except controller_mod.ControllerError as refused:
        return "admission_expansion_after_finding" in str(refused)
    except Exception:  # noqa: BLE001 - refused for another reason: not a finding
        return False
    return False


@needs_engine
def test_a_verified_breach_is_recorded_and_stops_expansion(tmp_path):
    """A weak boundary that accepts an undeclared field: the session's attempt
    is rebuilt, re-checked by the adapter's oracle, BREACHED with
    FAILING_TRIGGER, recorded through `controller.record_finding`, and every
    later expansion is refused. Allowing expansion after a finding, or
    reading a real Verdict as no finding, turns this red."""
    adapter = _synthetic_adapter(weak=True)
    miner = RecordingMiner({"status": "OK", "accepted": True})
    control, kstore, entry, coverage, _brief = _attack(
        tmp_path, adapter, _validate_script(ATTACK), miner
    )
    try:
        [verdict] = [v for v in coverage["verdicts"] if v["family"] == "recipe_fields"]
        assert verdict["outcome"] == "BREACHED" and verdict["rebuild"] == "REBUILT"
        assert verdict["conditions"] == ["FAILING_TRIGGER"]
        assert entry["findings"] and entry["findings"] == coverage["findings"]
        assert all(f.startswith("attack-failing-trigger-") for f in entry["findings"])
        assert _blocked(control)
        assert coverage["families"]["families"]["recipe_fields"]["status"] == "FINDING"
        # The store keeps the attempt and the finding with its specimen.
        [finding] = kstore.findings(SYNTHETIC, 0)
        assert finding["condition"] == "FAILING_TRIGGER"
        assert finding["specimen"] == ATTACK
        assert finding["strategy"] == "graphite-attacker:dry_validate"
        assert [a["outcome"] for a in kstore.attempts(SYNTHETIC, 0)] == ["BREACHED"]
    finally:
        control.close()


@needs_engine
def test_a_held_boundary_is_attempted_coverage_under_the_pinned_snapshot(tmp_path):
    adapter = _synthetic_adapter(weak=False)
    miner = RecordingMiner({"status": "REFUSED", "accepted": False})
    control, kstore, entry, coverage, brief = _attack(
        tmp_path, adapter, _validate_script(ATTACK), miner
    )
    try:
        assert entry["findings"] == [] and not _blocked(control)
        line = coverage["families"]["families"]["recipe_fields"]
        assert line["status"] == "ATTEMPTED_COVERAGE"
        assert coverage["families"]["zero_findings_reads_as"] == "ATTEMPTED_COVERAGE"
        # Held-out controls only measure wrongful rejection.
        assert line["wrongful_rejection_held_out"]["controls"] == 1
        # B2: the Attacker against the adapter's own deterministic runs, at an
        # equal budget, under the snapshot the session's brief was pinned to.
        b2 = coverage["benchmark_b2"]
        pinned = entry["store_pinned"]
        assert b2["store_snapshot"] == pinned == coverage["attack_knowledge"]["pinned"]
        assert brief.initial_observation["attack_knowledge"]["snapshot"] == pinned
        family = b2["families"]["recipe_fields"]
        assert family["budget"] == phase4.ATTACK_BUDGET
        assert family["baseline"]["attempts"] == 1
        # Every other check is a declared seam: NOT_RUN, never a pass.
        assert len(coverage["families"]["not_run"]) == 7
        assert coverage["seams"] == [phase4.POD_REBUILD_SEAM]
        assert [a["outcome"] for a in kstore.attempts(SYNTHETIC, 0)] == ["HELD"]
        assert kstore.findings(SYNTHETIC, 0) == []
        # Neutral: the brief is the synthetic Challenge's, never battery's.
        observation = brief.initial_observation
        assert observation["challenge"] == {"id": SYNTHETIC, "version": "1"}
        assert CID not in json.dumps(observation)
    finally:
        control.close()


@needs_engine
def test_an_infrastructure_failure_is_never_a_pass_or_a_near_miss(tmp_path):
    adapter = _synthetic_adapter(weak=True)
    miner = RecordingMiner({"status": "FAILED_INFRA"})
    control, kstore, entry, coverage, _brief = _attack(
        tmp_path, adapter, _validate_script(ATTACK), miner
    )
    try:
        [verdict] = [v for v in coverage["verdicts"] if v["family"] == "recipe_fields"]
        assert verdict["outcome"] == "INFRA" and entry["findings"] == []
        line = coverage["families"]["families"]["recipe_fields"]
        assert line["timeouts_crashes"] == 1
        assert line["completed"] == 0 and line["held"] == 0
        assert line["status"] == "INCONCLUSIVE"
        assert [a["outcome"] for a in kstore.attempts(SYNTHETIC, 0)] == ["CRASH"]
        assert kstore.near_misses(SYNTHETIC, 0) == []
    finally:
        control.close()


@needs_engine
def test_the_battery_dry_run_produces_coverage_and_b2_with_no_spend(tmp_path):
    out = io.StringIO()
    with redirect_stdout(out):
        code = phase4.main(["run", "--root", str(tmp_path / "root"), "--dry-run"])
    assert code == 0
    body = out.getvalue()
    printed = json.loads(body[body.index('{\n "coverage"') :])
    entry, coverage = printed["session"], printed["coverage"]
    assert entry["provider_state"] == "succeeded"
    assert Decimal(entry["settled_usd"]) < Decimal("0.01")
    assert coverage["challenge"] == CID and coverage["construction_level"] == 0
    assert coverage["claims"] == {"security_acceptance": False, "graded": False}
    assert coverage["benchmark_b2"]["store_snapshot"] == entry["store_pinned"]
    # With no miner path nothing reached the path: no finding is invented.
    assert coverage["findings"] == []
    assert all(v["refused_by"] == "graphite" for v in coverage["verdicts"])
    # Battery's higher-level families are declared seams, reported NOT_RUN.
    assert coverage["families"]["not_run"]
    root = tmp_path / "root"
    assert (root / "attacker-dry-run" / "iteration-log.jsonl").is_file()
    assert not (root / "attacker").exists()
