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
from carbon.challenge_validator import scoring as challenge_scoring
from carbon.development_session.research_tools import PREFIX
from carbon.reconstruction.capability_registry import (
    BATTERY_CHALLENGE,
    COLD_PLATE_CHALLENGE,
    MOTOR_CHALLENGE,
)

REPOSITORY = Path(__file__).resolve().parents[2]
#: Battery's phase-4 grant, as the registry names it (`phase4.PHASE4_GRANTS`).
BATTERY_GRANT_FILE = phase4.PHASE4_GRANTS[BATTERY_CHALLENGE].grant_file
COOLING_GRANT_FILE = phase4.PHASE4_GRANTS[COLD_PLATE_CHALLENGE].grant_file
GRANT_FILE = REPOSITORY / BATTERY_GRANT_FILE
CID = BATTERY_CHALLENGE
SCORING = challenge_scoring.scoring_for(CID)
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


@pytest.fixture(autouse=True)
def _stand_in_material(monkeypatch):
    """The stand-in Challenges' published material. A session checks out only
    its own Challenge's registered material (VALIDATOR-05); these synthetic
    Challenges reuse battery's files, which every Attacker received before."""
    from carbon.agent_campaign import boundaries

    for challenge in (StandIn.challenge_id, "another-challenge-v1", SYNTHETIC):
        monkeypatch.setitem(
            boundaries.PUBLISHED_MATERIAL, challenge, boundaries._PUBLISHED_CHALLENGE
        )


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
        scoring=SCORING,
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
        code = phase4.main(
            [
                "run",
                "--root",
                str(tmp_path / "root"),
                "--challenge",
                CID,
                "--dry-run",
            ]
        )
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
        (_verdict("INFRA", reason="infra:FAILED_INFRA"), "FAILED_INFRA"),
        (_verdict("INFRA", reason="oracle_no_answer:FAILED_INFRA"), "FAILED_INFRA"),
        (_verdict("INFRA", reason="infra:dispatch_unresolved"), "FAILED_INFRA"),
        (_verdict("INFRA", reason="infra:result_missing"), "CRASH"),
        (_verdict("INFRA", reason="rebuild_crashed:OSError"), "CRASH"),
        (_verdict("INFRA", reason="oracle_no_answer:TIMEOUT"), "TIMEOUT"),
        (_verdict("HELD", rebuild="UNREBUILDABLE"), "UNREBUILDABLE"),
        (_verdict("UNDETERMINED"), "NOT_RUN"),
        (_verdict("NOT_APPLICABLE"), "NOT_RUN"),
    ],
)
def test_the_store_outcome_is_never_a_hold_for_what_was_not_judged(verdict, outcome):
    """A timeout, crash, unrebuildable construction or Graphite's own refusal
    is never stored as a hold (counting FAILED_INFRA as a pass turns this
    red), and an infrastructure failure is stored FAILED_INFRA, never folded
    into CRASH."""
    assert phase4.store_outcome(verdict, VERIFY) == outcome


# -- the runner ----------------------------------------------------------------------------
def test_run_requires_an_explicit_challenge(tmp_path, capsys):
    """The neutral runner never falls back to Battery when selection is absent."""
    with pytest.raises(SystemExit) as stopped:
        phase4.main(["run", "--root", str(tmp_path / "r"), "--dry-run"])
    assert stopped.value.code == 2
    error = capsys.readouterr().err
    assert "--challenge" in error and "required" in error


def test_the_live_run_requires_the_phase4_grant_and_credentials(
    capsys, tmp_path, monkeypatch
):
    modules = stand_in_modules(StandIn())
    monkeypatch.setattr(phase4, "attack_modules", lambda: modules)
    code = _refusal(
        capsys,
        lambda: phase4.main(["run", "--root", str(tmp_path / "r"), "--challenge", CID]),
    )
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
        "--challenge",
        CID,
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


# -- the per-check view ---------------------------------------------------------------------
def _rows(names, *, check=None):
    return {name: {"check": check, "status": "NOT_RUN"} for name in names}


def test_the_check_view_names_every_track_a_check_from_the_adapter():
    """A seam's check comes from the adapter's declaration, so a report row
    that lost it neither hides the check nor passes it; the lost check is
    listed. A check nothing declares is `undeclared`, never covered."""
    adapter = StandIn()
    names = ["recipe_fields", "mandatory_cases", "participant_code"]
    report = {"families": _rows(names)}
    view = phase4.check_view(adapter, report, {"families": _rows(names)})
    assert tuple(view["checks"]) == phase4.TRACK_A_CHECKS
    assert len(phase4.TRACK_A_CHECKS) == 8
    assert view["checks"]["fresh_attack_confirmation"] == {
        "participant_code": {"kind": "seam", "status": "NOT_RUN"}
    }
    assert set(view["checks"]["artifact_and_dependency_attacks"]) == {
        "recipe_fields",
        "mandatory_cases",
    }
    assert sorted(view["undeclared"]) == sorted(
        set(phase4.TRACK_A_CHECKS)
        - {"fresh_attack_confirmation", "artifact_and_dependency_attacks"}
    )
    assert {(r["report"], r["family"]) for r in view["report_rows_without_check"]} == {
        (source, name) for source in ("families", "benchmark_b2") for name in names
    }
    seam_row = next(
        r
        for r in view["report_rows_without_check"]
        if r["family"] == "participant_code"
    )
    assert seam_row["declared"] == "fresh_attack_confirmation"


def test_the_check_view_refuses_a_report_check_that_disagrees(capsys):
    adapter = StandIn()
    report = {
        "families": _rows(
            ["participant_code"], check="score_exploitation_and_tail_failures"
        )
    }
    code = _refusal(
        capsys, lambda: phase4.check_view(adapter, report, {"families": {}})
    )
    assert code == "report_check_disagrees_with_adapter: families:participant_code"
    rows = {"families": _rows(["participant_code"], check="fresh_attack_confirmation")}
    view = phase4.check_view(adapter, rows, rows)
    assert view["report_rows_without_check"] == []


# == Carbon's side through the real engine ==================================================
SYNTHETIC = "synthetic-heat-sink-v1"
ALLOWED = frozenset({"model_family", "width"})
ATTACK = {"model_family": "mlp", "width": 8, "extra": 1}


def _synthetic_adapter(*, weak, narrow=False):
    """A second Challenge, with no battery code: one family run here
    (undeclared recipe fields), every other Track A check a declared seam.
    `narrow` makes the real boundary refuse widths over 16, which wrongly
    refuses the held-out control (width 32) while the trained one passes."""
    from carbon.agent_campaign.attack import adapter as core
    from carbon.agent_campaign.attack import engine

    def compile_doc(doc, *, checked=True):
        if type(doc) is not dict:
            return {"accepted": False, "unknown": False}
        unknown = bool(set(doc) - ALLOWED)
        ok = doc.get("model_family") == "mlp" and (not unknown or not checked)
        return {"accepted": ok, "unknown": unknown}

    def boundary(doc):
        if narrow and type(doc) is dict and doc.get("width", 0) > 16:
            return {"accepted": False, "unknown": False}
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


def _assert_every_check_named(coverage):
    """All eight Track A checks appear in the coverage report, each declared
    by a run family or a seam, and no report or B2 row lost its check."""
    view = coverage["checks"]
    assert set(view["checks"]) == set(phase4.TRACK_A_CHECKS)
    assert view["undeclared"] == []
    assert view["report_rows_without_check"] == []
    named = {
        line["check"]
        for rows in (
            coverage["families"]["families"],
            coverage["benchmark_b2"]["families"],
        )
        for line in rows.values()
    }
    assert named == set(phase4.TRACK_A_CHECKS)


def _validate_script(construction):
    # compile_strategy is an AUTHORITATIVE tool: a breach the oracle finds on
    # its boundary is recorded as a finding (dry_validate is advisory, so its
    # divergence would be a usability record, not a finding).
    return [
        tool(PREFIX + "compile_strategy", {"strategy_json": json.dumps(construction)}),
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
        assert finding["strategy"] == "graphite-attacker:compile_strategy"
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
        _assert_every_check_named(coverage)
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
        # The session's infrastructure failure is no finding; the weak
        # boundary's deterministic baseline breach is one, recorded apart.
        assert verdict["outcome"] == "INFRA"
        assert coverage["findings_by_source"]["attacker"] == []
        assert (
            entry["findings"]
            == coverage["findings_by_source"]["deterministic_baseline"]
        )
        line = coverage["families"]["families"]["recipe_fields"]
        assert line["timeouts_crashes"] == 1
        assert line["completed"] == 0 and line["held"] == 0
        assert line["status"] == "INCONCLUSIVE"
        assert [a["outcome"] for a in kstore.attempts(SYNTHETIC, 0)] == ["FAILED_INFRA"]
        assert kstore.near_misses(SYNTHETIC, 0) == []
    finally:
        control.close()


@needs_engine
def test_a_wrongly_refused_held_out_control_blocks_the_next_expansion(tmp_path):
    """A held-out control the real boundary wrongly refuses is a finding that
    reaches the controller through the same record path as an Attacker
    finding, bound to the control's identity, input digest and outcome, and
    every later expansion is refused."""
    from carbon.agent_campaign.attack import engine

    adapter = _synthetic_adapter(weak=False, narrow=True)
    (held,) = adapter.controls("held_out")
    miner = RecordingMiner({"status": "REFUSED", "accepted": False})
    control, _kstore, entry, coverage, _brief = _attack(
        tmp_path, adapter, _validate_script(ATTACK), miner
    )
    try:
        by_source = coverage["findings_by_source"]
        assert by_source["attacker"] == []
        assert by_source["deterministic_baseline"] == []
        (finding_id,) = by_source["held_out_controls"]
        assert entry["findings"] == [finding_id] == coverage["findings"]
        assert _blocked(control)
        (line,) = coverage["families"]["findings"]
        assert line["role"] == "held_out_control"
        assert line["control_identity"] == held.identity
        (ledger,) = control.admission_ledgers()["findings"]
        body = json.loads((control.root / ledger["evidence"]["path"]).read_bytes())
        assert body["control_identity"] == held.identity
        assert body["input_digest"] == engine.digest(held.value)
        assert body["outcome"] == "WRONGLY_REFUSED"
        rate = coverage["wrongful_rejection_held_out"]["recipe_fields"]
        assert (rate["status"], rate["rate"]) == ("MEASURED", 1.0)
    finally:
        control.close()


@needs_engine
def test_a_deterministic_baseline_breach_reaches_the_controller(tmp_path):
    """A breach in the adapter's deterministic baseline run (B2's other side)
    is recorded and stops expansion too, even when the session found none."""
    adapter = _synthetic_adapter(weak=True)
    control, _kstore, _entry, coverage, _brief = _attack(
        tmp_path, adapter, [text("done")], RecordingMiner()
    )
    try:
        by_source = coverage["findings_by_source"]
        assert by_source["attacker"] == [] and by_source["held_out_controls"] == []
        assert len(by_source["deterministic_baseline"]) == 1
        assert _blocked(control)
    finally:
        control.close()


def test_a_resume_refuses_a_missing_or_malformed_pin(tmp_path, capsys):
    """A resume reuses its recorded pin and never re-snapshots: a deleted
    pin, or one with the wrong schema, session or digest, is refused."""
    store = tmp_path / "store"
    store.mkdir()
    kstore = FakeStore(store)
    view = phase4.pin_session(store, 1, kstore)
    assert phase4.read_pin(store, 1)["attack_knowledge_digest"] == view.digest
    assert phase4.pin_session(store, 1, kstore, resume=True).digest == view.digest
    path = phase4.pin_path(store, 1)
    good = json.loads(path.read_bytes())
    path.unlink()
    code = _refusal(capsys, lambda: phase4.pin_session(store, 1, kstore, resume=True))
    assert code == "session_pin_missing"
    for bad in (
        {**good, "session": 2},
        {**good, "schema": "carbon.graphite.attacker-store-pin.v0"},
        {**good, "attack_knowledge_digest": "sha256:short"},
        {**good, "extra": True},
    ):
        path.write_text(json.dumps(bad))
        for resume in (True, False):
            code = _refusal(
                capsys,
                lambda resume=resume: phase4.pin_session(
                    store, 1, kstore, resume=resume
                ),
            )
            assert code == "session_pin_malformed"
        path.unlink()
    path.write_text("{not json")
    code = _refusal(capsys, lambda: phase4.read_pin(store, 1))
    assert code == "session_pin_malformed"


@needs_engine
def test_a_view_under_another_digest_than_the_recorded_pin_is_refused(tmp_path, capsys):
    """The replay guard compares the view with the session's recorded pin,
    never with itself."""
    atk = phase4.attack_modules()
    store = tmp_path / "attacker"
    store.mkdir()
    kstore = phase4.open_store(store, atk)
    view = phase4.pin_session(store, 1, kstore)
    assert phase4.replay_guard(store, 1, view, atk) is view
    kstore.add_attempt(
        challenge_id=SYNTHETIC,
        level=0,
        contract_digest="sha256:" + "c" * 64,
        check="artifact_and_dependency_attacks",
        family="recipe_fields",
        boundary="the recipe field allow-list",
        strategy="graphite-attacker:dry_validate",
        attempt_id="epoch-1-attack-tool-001",
        attempt={"recipe": {"width": 8}},
        outcome="HELD",
    )
    other = kstore.pin(kstore.snapshot())
    assert other.digest != view.digest
    code = _refusal(capsys, lambda: phase4.replay_guard(store, 1, other, atk))
    assert code == "attack_knowledge_replay_under_another_digest"
    phase4.pin_path(store, 1).unlink()
    code = _refusal(capsys, lambda: phase4.replay_guard(store, 1, view, atk))
    assert code == "session_pin_missing"


def test_a_tampered_copy_of_the_committed_grant_is_refused(
    capsys, tmp_path, monkeypatch
):
    """A live run's grant must equal the committed GRAPHITE-GRANT-PHASE4 by
    canonical digest: a local copy with its ceiling raised to 100 is refused
    before the credential is even looked at."""
    modules = stand_in_modules(StandIn())
    monkeypatch.setattr(phase4, "attack_modules", lambda: modules)
    committed = json.loads(GRANT_FILE.read_bytes())
    credential = tmp_path / "engy"
    credential.write_text("x")
    credential.chmod(0o600)
    for change in (
        {"monetary_ceiling": "100"},
        {"cleanup_allowance": "0.10"},
        {"account": "another-account"},
    ):
        tampered = tmp_path / "grant.json"
        tampered.write_text(json.dumps({**committed, **change}))
        argv = [
            "run",
            "--root",
            str(tmp_path / "r"),
            "--challenge",
            CID,
            "--grant",
            str(tampered),
            "--credential-file",
            str(credential),
            "--miner-profile",
            "p.json",
            "--miner-campaign",
            "c",
        ]
        code = _refusal(capsys, lambda argv=argv: phase4.main(argv))
        assert code == "grant_differs_from_the_committed_phase4_grant", change


def _no_network(monkeypatch):
    """A socket guard of the test's own: any connect or name lookup fails
    the test, whatever the code under test does with the error."""
    import socket

    used = []

    def refuse(*args, **kwargs):
        used.append(repr(args[:2]))
        raise AssertionError("network use in a run that must send nothing")

    monkeypatch.setattr(socket.socket, "connect", refuse)
    monkeypatch.setattr(socket.socket, "connect_ex", refuse)
    monkeypatch.setattr(socket, "create_connection", refuse)
    monkeypatch.setattr(socket, "getaddrinfo", refuse)
    return used


@needs_engine
def test_the_battery_dry_run_produces_coverage_and_b2_with_no_spend(
    tmp_path, monkeypatch
):
    used = _no_network(monkeypatch)
    out = io.StringIO()
    with redirect_stdout(out):
        code = phase4.main(
            [
                "run",
                "--root",
                str(tmp_path / "root"),
                "--challenge",
                CID,
                "--dry-run",
            ]
        )
    assert code == 0 and used == []
    body = out.getvalue()
    printed = json.loads(body[body.index('{\n "coverage"') :])
    entry, coverage = printed["session"], printed["coverage"]
    assert entry["provider_state"] == "succeeded"
    # Nothing is spent: the settled amount is exactly zero, not merely small.
    assert Decimal(entry["settled_usd"]) == 0
    assert printed["dry_run"]["settled_is_zero"] is True
    assert printed["dry_run"]["network_attempts"] == []
    assert coverage["challenge"] == CID and coverage["construction_level"] == 0
    assert coverage["claims"] == {"security_acceptance": False, "graded": False}
    assert coverage["benchmark_b2"]["store_snapshot"] == entry["store_pinned"]
    # With no miner path nothing reached the path: no finding is invented.
    assert coverage["findings"] == []
    assert all(v["refused_by"] == "graphite" for v in coverage["verdicts"])
    # Battery's higher-level families are declared seams, reported NOT_RUN.
    assert coverage["families"]["not_run"]
    # Every Track A check is accounted for, fresh_attack_confirmation included
    # (it is covered only by seams), and every report and B2 row names it.
    _assert_every_check_named(coverage)
    assert any(
        line["kind"] == "seam"
        for line in coverage["checks"]["checks"]["fresh_attack_confirmation"].values()
    )
    root = tmp_path / "root"
    assert (root / "attacker-dry-run" / "iteration-log.jsonl").is_file()
    assert not (root / "attacker").exists()


# -- L1: the grant check never trusts the working tree ------------------------------------------
def _git(cwd, *args):
    import os
    import subprocess

    env = {
        **os.environ,
        "GIT_AUTHOR_NAME": "t",
        "GIT_AUTHOR_EMAIL": "t@example.invalid",
        "GIT_COMMITTER_NAME": "t",
        "GIT_COMMITTER_EMAIL": "t@example.invalid",
        "GIT_CONFIG_GLOBAL": "/dev/null",
        "GIT_CONFIG_NOSYSTEM": "1",
    }
    return subprocess.run(
        ["git", *args], cwd=cwd, env=env, check=True, capture_output=True
    )


def _grant_repo(tmp_path, challenges=(CID,)):
    """A repository holding the committed phase-4 grants of `challenges` on
    main, pushed to a bare remote: what `check_committed_grant` reads, apart
    from this checkout. Returns the repository and the first Challenge's
    grant file."""
    remote, repo = tmp_path / "remote.git", tmp_path / "repo"
    _git(tmp_path, "init", "-q", "--bare", "-b", "main", str(remote))
    _git(tmp_path, "init", "-q", "-b", "main", str(repo))
    files = []
    for challenge in challenges:
        name = phase4.PHASE4_GRANTS[challenge].grant_file
        grant = repo / name
        grant.parent.mkdir(parents=True, exist_ok=True)
        grant.write_bytes((REPOSITORY / name).read_bytes())
        files.append(grant)
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "grant")
    _git(repo, "remote", "add", "origin", str(remote))
    _git(repo, "push", "-q", "-u", "origin", "main")
    return repo, files[0]


PHASE4_CHALLENGES = (CID, COLD_PLATE_CHALLENGE)


@pytest.mark.parametrize("challenge", PHASE4_CHALLENGES)
def test_the_committed_grant_is_read_from_head_not_the_working_tree(
    tmp_path, capsys, challenge
):
    """L1, for each Challenge's grant. The committed blob at a pushed HEAD is
    the grant: an operator who edits the working-tree grant and passes it (or
    an identical copy) is refused; so is a clean copy while the grants
    directory differs from HEAD, an unpushed HEAD, and a HEAD with no grant
    committed. Mutation: read the grant file from disk again, and the edited
    working-tree grant passes."""
    repo, grant = _grant_repo(tmp_path, (challenge,))
    name = phase4.PHASE4_GRANTS[challenge].grant_file
    committed = json.loads(grant.read_bytes())

    def check(path):
        return phase4.check_committed_grant(path, repo, challenge=challenge)

    copy = tmp_path / "copy.json"
    copy.write_bytes(grant.read_bytes())
    assert check(copy) == phase4.grant_digest(committed)
    assert check(grant) == phase4.grant_digest(committed)

    def refusal(path):
        return _refusal(capsys, lambda: check(path))

    # The operator edits the working-tree grant and hands it in, or an
    # identical copy of it: refused against HEAD's blob.
    raised = {**committed, "monetary_ceiling": "100.00"}
    grant.write_text(json.dumps(raised))
    edited_copy = tmp_path / "edited-copy.json"
    edited_copy.write_text(json.dumps(raised))
    for path in (grant, edited_copy):
        assert refusal(path) == "grant_differs_from_the_committed_phase4_grant"
    # A clean copy while the grants directory differs from HEAD.
    assert refusal(copy) == "grants_directory_has_uncommitted_changes"
    _git(repo, "checkout", "--", name)
    (grant.parent / "NOTE.txt").write_text("untracked")
    assert refusal(copy) == "grants_directory_has_uncommitted_changes"
    (grant.parent / "NOTE.txt").unlink()
    assert check(copy)
    # A HEAD that is not on a remote branch.
    (repo / "other.txt").write_text("x")
    _git(repo, "add", "other.txt")
    _git(repo, "commit", "-q", "-m", "local only")
    assert refusal(copy) == "grant_commit_not_pushed"
    # A HEAD with no grant committed.
    _git(repo, "rm", "-q", name)
    _git(repo, "commit", "-q", "-m", "no grant")
    assert refusal(copy) == "phase4_grant_not_committed"


@pytest.mark.parametrize("challenge", PHASE4_CHALLENGES)
def test_a_pushed_branch_carrying_an_edited_grant_is_refused(
    tmp_path, capsys, challenge
):
    """C1, for each Challenge's grant. The grant binds to main, which is what
    the owner approved: a feature branch that commits and pushes a raised
    ceiling, run with a copy of its own committed grant, is refused; so is a
    checkout whose remote has no main grant. Back on main the same check
    passes."""
    repo, grant = _grant_repo(tmp_path, (challenge,))
    committed = json.loads(grant.read_bytes())
    raised = {**committed, "monetary_ceiling": "100.00"}
    _git(repo, "checkout", "-q", "-b", "feature")
    grant.write_text(json.dumps(raised))
    _git(repo, "commit", "-q", "-am", "raise the ceiling")
    _git(repo, "push", "-q", "-u", "origin", "feature")
    copy = tmp_path / "copy.json"
    copy.write_text(json.dumps(raised))

    def check(path, repository=repo):
        return phase4.check_committed_grant(path, repository, challenge=challenge)

    def refusal(path, repository=repo):
        return _refusal(capsys, lambda: check(path, repository))

    assert refusal(copy) == "grant_differs_from_main"
    # A remote with no main to read the approved grant from.
    elsewhere = tmp_path / "elsewhere.git"
    _git(tmp_path, "init", "-q", "--bare", "-b", "main", str(elsewhere))
    _git(repo, "remote", "set-url", "origin", str(elsewhere))
    _git(repo, "push", "-q", "origin", "feature")
    assert refusal(copy) == "main_grant_unavailable"
    # Main itself passes.
    _git(repo, "remote", "set-url", "origin", str(tmp_path / "remote.git"))
    _git(repo, "checkout", "-q", "main")
    copy.write_bytes(grant.read_bytes())
    assert check(copy) == phase4.grant_digest(committed)


def test_a_branch_only_cooling_grant_is_refused_until_it_is_on_main(tmp_path, capsys):
    """WAVE-05 §2: the cooling grant counts only as the committed blob on
    main. Committed and pushed on a feature branch (this pull request's
    state), it is refused `main_grant_unavailable`; once main carries the
    same blob, the same checkout passes, while battery's grant passes
    throughout."""
    repo, battery = _grant_repo(tmp_path, (CID,))
    _git(repo, "checkout", "-q", "-b", "cooling-grant")
    cooling = repo / COOLING_GRANT_FILE
    cooling.write_bytes((REPOSITORY / COOLING_GRANT_FILE).read_bytes())
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "cooling grant")
    _git(repo, "push", "-q", "-u", "origin", "cooling-grant")
    copy = tmp_path / "cooling.json"
    copy.write_bytes(cooling.read_bytes())

    def check(path, challenge):
        return phase4.check_committed_grant(path, repo, challenge=challenge)

    code = _refusal(capsys, lambda: check(copy, COLD_PLATE_CHALLENGE))
    assert code == "main_grant_unavailable"
    assert check(battery, CID)
    # The pull request merges: main now holds the same blob.
    _git(repo, "push", "-q", "origin", "cooling-grant:main")
    expected = phase4.grant_digest(json.loads(copy.read_bytes()))
    assert check(copy, COLD_PLATE_CHALLENGE) == expected
    assert check(battery, CID)


def test_a_grant_for_another_challenge_is_refused(tmp_path, capsys):
    """Each Challenge accepts only its own grant, even with both committed on
    main: battery's grant with `--challenge chip-cold-plate` and cooling's
    with battery are `grant_is_for_another_challenge`, an unregistered id is
    `grant_is_not_the_phase4_grant`."""
    repo, _ = _grant_repo(tmp_path, PHASE4_CHALLENGES)
    grants = {c: repo / phase4.PHASE4_GRANTS[c].grant_file for c in PHASE4_CHALLENGES}

    def refusal(path, challenge):
        return _refusal(
            capsys,
            lambda: phase4.check_committed_grant(path, repo, challenge=challenge),
        )

    for challenge, own in grants.items():
        assert phase4.check_committed_grant(own, repo, challenge=challenge)
        for other, path in grants.items():
            if other != challenge:
                assert refusal(path, challenge) == "grant_is_for_another_challenge"
    unknown = tmp_path / "unknown.json"
    unknown.write_text(
        json.dumps({**json.loads(grants[CID].read_bytes()), "grant_id": "OTHER"})
    )
    for challenge in PHASE4_CHALLENGES:
        assert refusal(unknown, challenge) == "grant_is_not_the_phase4_grant"


@needs_engine
@pytest.mark.parametrize(
    "challenge, grant_of",
    [(COLD_PLATE_CHALLENGE, CID), (CID, COLD_PLATE_CHALLENGE)],
)
def test_the_live_run_refuses_another_challenges_grant(
    tmp_path, capsys, challenge, grant_of
):
    """Through `phase4 run`: the committed grant of the other Challenge is
    refused before the credential is looked at or anything opens."""
    credential = tmp_path / "engy"
    credential.write_text("x")
    credential.chmod(0o600)
    argv = [
        "run",
        "--root",
        str(tmp_path / "r"),
        "--challenge",
        challenge,
        "--grant",
        str(REPOSITORY / phase4.PHASE4_GRANTS[grant_of].grant_file),
        "--credential-file",
        str(credential),
        "--miner-profile",
        "p.json",
        "--miner-campaign",
        "c",
    ]
    code = _refusal(capsys, lambda: phase4.main(argv))
    assert code == "grant_is_for_another_challenge"
    assert not (tmp_path / "r" / "attacker").exists()


def test_a_challenge_with_no_registered_grant_is_refused(tmp_path, capsys):
    """Motor has no phase-4 grant until its scorer exists (WAVE-05 §2): every
    grant path refuses it typed, whichever committed grant is handed in."""
    repo, _ = _grant_repo(tmp_path, PHASE4_CHALLENGES)
    assert MOTOR_CHALLENGE not in phase4.PHASE4_GRANTS
    for challenge in (MOTOR_CHALLENGE, None, "", "stand-in-challenge-v1"):
        assert _refusal(capsys, lambda c=challenge: phase4.phase4_grant(c)) == (
            "no_phase4_grant_for_challenge"
        )
    for owner in PHASE4_CHALLENGES:
        path = repo / phase4.PHASE4_GRANTS[owner].grant_file
        for call in (
            lambda p=path: phase4.check_committed_grant(
                p, repo, challenge=MOTOR_CHALLENGE
            ),
            lambda p=path: phase4.live_checks(p, repo, challenge=MOTOR_CHALLENGE),
            lambda: phase4.dry_run_grant(MOTOR_CHALLENGE),
        ):
            assert _refusal(capsys, call) == "no_phase4_grant_for_challenge"


def test_the_prelive_grant_default_follows_the_challenge(tmp_path, monkeypatch):
    """`phase4 prelive` without `--grant` checks the grant registered for
    `--challenge`, and binds the gate to that Challenge."""
    from carbon.agent_campaign.graphite import phase4_prelive

    seen = []

    def record(
        root,
        adapter,
        atk,
        *,
        grant_path,
        challenge,
        scoring=None,
        analysis_image_manifest=None,
    ):
        assert analysis_image_manifest is None  # not given on this command line
        seen.append((grant_path, challenge, adapter.challenge_id))
        return 0

    monkeypatch.setattr(phase4_prelive, "prelive", record)
    for challenge in PHASE4_CHALLENGES:
        root = str(tmp_path / challenge)
        assert phase4.main(["prelive", "--root", root, "--challenge", challenge]) == 0
    assert seen == [
        (str(REPOSITORY / phase4.PHASE4_GRANTS[c].grant_file), c, c)
        for c in PHASE4_CHALLENGES
    ]


def test_the_prelive_gate_refuses_motor_typed_once_its_scoring_exists(
    tmp_path, capsys, monkeypatch
):
    """When a motor scorer registers (WAVE-05 §1) motor still has no grant:
    the prelive default refuses `no_phase4_grant_for_challenge` instead of
    borrowing battery's."""
    monkeypatch.setattr(
        challenge_scoring, "scoring_for", lambda challenge_id=None: SCORING
    )
    root = str(tmp_path / "r")
    code = _refusal(
        capsys,
        lambda: phase4.main(
            ["prelive", "--root", root, "--challenge", MOTOR_CHALLENGE]
        ),
    )
    assert code == "no_phase4_grant_for_challenge"


# -- mutations: each new grant guard, disabled, lets the wrong grant through ------------------------
def test_mutation_one_grant_for_every_challenge_lets_battery_s_run_cooling(
    tmp_path, capsys, monkeypatch
):
    """The registry lookup is the binding: answer battery's entry for every
    Challenge, and battery's committed grant passes for cooling and motor."""
    repo, battery = _grant_repo(tmp_path, PHASE4_CHALLENGES)
    real = phase4.phase4_grant
    monkeypatch.setattr(phase4, "phase4_grant", lambda c: real(CID))
    for challenge in (COLD_PLATE_CHALLENGE, MOTOR_CHALLENGE):
        assert phase4.check_committed_grant(battery, repo, challenge=challenge)
    monkeypatch.setattr(phase4, "phase4_grant", real)
    for challenge, code in (
        (COLD_PLATE_CHALLENGE, "grant_is_for_another_challenge"),
        (MOTOR_CHALLENGE, "no_phase4_grant_for_challenge"),
    ):
        assert (
            _refusal(
                capsys,
                lambda c=challenge: phase4.check_committed_grant(
                    battery, repo, challenge=c
                ),
            )
            == code
        )


def test_mutation_without_the_id_binding_the_refusal_loses_its_type(
    tmp_path, capsys, monkeypatch
):
    """`bind_grant_to_challenge` types a wrong pairing; with it disabled the
    digest still refuses, but as an untyped difference."""
    repo, battery = _grant_repo(tmp_path, PHASE4_CHALLENGES)

    def refusal():
        return _refusal(
            capsys,
            lambda: phase4.check_committed_grant(
                battery, repo, challenge=COLD_PLATE_CHALLENGE
            ),
        )

    assert refusal() == "grant_is_for_another_challenge"
    monkeypatch.setattr(phase4, "bind_grant_to_challenge", lambda d, e: e)
    assert refusal() == "grant_differs_from_the_committed_phase4_grant"


def test_mutation_reading_the_working_tree_grant_lets_an_edit_through(
    tmp_path, capsys, monkeypatch
):
    repo, grant = _grant_repo(tmp_path)
    raised = {**json.loads(grant.read_bytes()), "monetary_ceiling": "100.00"}
    grant.write_text(json.dumps(raised))

    def from_disk(path, repository=phase4.REPOSITORY):
        given = json.loads(Path(path).read_bytes())
        on_disk = json.loads((Path(repository) / BATTERY_GRANT_FILE).read_bytes())
        if phase4.grant_digest(given) != phase4.grant_digest(on_disk):
            raise phase4.RunnerRefused("grant_differs_from_the_committed_phase4_grant")
        return phase4.grant_digest(on_disk)

    assert from_disk(grant, repo)  # the old check: the edit passes
    code = _refusal(
        capsys, lambda: phase4.check_committed_grant(grant, repo, challenge=CID)
    )
    assert code == "grant_differs_from_the_committed_phase4_grant"


# -- one code-run rule ----------------------------------------------------------------------------
@needs_engine
def test_the_dispatcher_calls_the_adapters_own_code_run_rule(monkeypatch):
    """`AttackerTools` refuses a code run by the adapter's own
    `code_run_refusal`, the function battery's `resource_accounting` family
    attacks: for every one of that family's code-run attacks the dispatcher
    and the family's rule agree, and lifting battery's rule lifts the
    dispatcher's (no copy)."""
    from carbon.agent_campaign.attack.adapters import battery

    adapter = battery.ADAPTER
    seconds = phase4.adapter_code_run_seconds(adapter)
    rule = phase4.code_run_rule(adapter, seconds)
    attacks = dict(battery.ADAPTER.family_spec("resource_accounting").attacks())
    code_runs = {k: v for k, v in attacks.items() if v["kind"] == "code_run"}
    assert code_runs

    def dispatch(inner):
        miner = RecordingMiner()
        tools = phase4.AttackerTools(
            miner=miner, emit=lambda *a: None, code_run_seconds=seconds, refusal=rule
        )
        arguments = {
            "kind": "workspace",
            "strategy_json": None,
            "action": "run_python",
            "arguments_json": json.dumps(inner, allow_nan=True),
        }
        result = asyncio.run(tools.call(PREFIX + "start_research_task", arguments, "i"))
        return result.get("reason_code") if not miner.calls else None

    for name, value in code_runs.items():
        inner = value["arguments"]
        if not isinstance(inner, dict):
            continue  # not JSON an agent could send as arguments_json
        assert dispatch(inner) == battery.code_run_refusal(inner), name
        assert dispatch(inner) is not None, name
    monkeypatch.setattr(battery, "code_run_refusal", lambda arguments: None)
    assert dispatch({"seconds": seconds + 1}) is None
    # An adapter without its own rule gets the core's at its allowance.
    core = phase4.code_run_rule(StandIn(), 600)
    assert core({"seconds": 601}) == "code_run_needs_seconds_up_to_600"
    assert core({"seconds": 600}) is None
