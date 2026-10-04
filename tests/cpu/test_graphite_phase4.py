"""Graphite phase 4: the Attacker session driver for the general attack engine
(OWNER-GRAPHITE-ATTACKER-01; slice AT-E).

The neutral attack engine (`carbon.agent_campaign.attack`) is built by the
other slices; this driver is tested against its interfaces with fakes injected
through `phase4.attack_modules`, so the slice's behaviour is pinned before the
engine merges. A scripted model and `ScriptedPods` mean no live inference, no
pod, no key, no network and no spend.
"""

from __future__ import annotations

import io
import json
import types
from contextlib import redirect_stdout
from pathlib import Path

import pytest

from carbon.agent_campaign import controller as controller_mod
from carbon.agent_campaign.grant import SpendingGrant
from carbon.agent_campaign.graphite import phase4
from carbon.agent_campaign.graphite.model import ScriptedModel, text
from carbon.agent_campaign.graphite.pods import ScriptedPods
from carbon.agent_campaign.graphite.provider import SESSION_LIMITS_V2
from carbon.agent_campaign.graphite.roles import ROLES, RoleName
from carbon.battery.research import SCAFFOLD
from carbon.development_session.research_tools import PREFIX

REPOSITORY = Path(__file__).resolve().parents[2]
GRANT_FILE = REPOSITORY / phase4.GRANT_FILE
CID = phase4.BATTERY_CHALLENGE


# -- a fake adapter and a fake engine ------------------------------------------------------
class FakeFamily:
    def __init__(self, name, check, goal):
        self.name, self.check, self.goal = name, check, goal


class FakeAdapter:
    """A neutral, challenge-level adapter standing in for the battery Level 0
    adapter (AT-B). Its family goals are neutral so the brief passes the
    protected-material filter."""

    challenge_id = CID
    level = 0
    contract_digest = "sha256:" + "a" * 64
    code_run_seconds = 600

    def __init__(self, goals=None):
        goals = goals or {
            "recipe_surface": "Does the path refuse undeclared recipe fields?",
            "mandatory_failure": "Does a mandatory failure stop a soft score?",
        }
        self._families = tuple(
            FakeFamily(name, "artifact_and_dependency_attacks", goal)
            for name, goal in goals.items()
        )

    def families(self):
        return self._families

    def controls(self, split):
        assert split in ("trained", "held_out")
        return ()

    def oracle(self, family, attempt):
        return {"family": family, "ok": True}

    def rebuild(self, construction):
        return {"status": "REBUILT"}

    def level_families(self):
        return ()

    def public_identity(self):
        from carbon.battery.challenge import CHALLENGE

        return {"id": CHALLENGE.challenge_id, "version": CHALLENGE.version}

    def baseline(self):
        return SCAFFOLD

    def recipe_outside_contract(self):
        return {**SCAFFOLD, "backbone": "transolver"}


class FakeStore:
    def __init__(self, root):
        self.root = root
        self.attempts, self.findings, self.near = [], [], []

    def add_attempt(self, cid, level, **kw):
        self.attempts.append((cid, level, kw))

    def add_finding(self, cid, level, **kw):
        self.findings.append((cid, level, kw))

    def add_near_miss(self, cid, level, **kw):
        self.near.append((cid, level, kw))

    def snapshot(self):
        return "sha256:" + "c" * 64


def fake_modules(*, breach=True):
    """A fake `carbon.agent_campaign.attack` registry: it reads nothing from
    the journal, so the driver's orchestration is what is exercised."""

    adapter = FakeAdapter()

    def attempts(session_dir):
        return [
            {"identity": "epoch-1-tool-000", "tool": "dry_validate", "arguments": {}},
            {"identity": "epoch-1-tool-001", "tool": "dry_validate", "arguments": {}},
        ]

    def map_to_families(att, adp):
        return {"recipe_surface": att[:1], "mandatory_failure": att[1:]}

    def verify(attempt, adp, *, pods=None):
        if attempt["identity"].endswith("001") and breach:
            return {
                "state": "BREACHED",
                "breached": True,
                "condition": "FAILING_TRIGGER",
            }
        return {"state": "HELD", "breached": False, "condition": None}

    recorded = []

    def record(verdict, control):
        fid = "graphite-attack-" + "d" * 16
        control.record_finding(fid, verdict["condition"], b'{"schema":"x"}')
        recorded.append(fid)
        return fid

    def run_family(family, *, budget):
        return {"family": family.name, "budget": budget, "verified": 0}

    def family_report(runs, *, controls_held_out):
        return {
            r["family"]: {
                "attempts": r["budget"],
                "verified": 0,
                "zero": "ATTEMPTED_COVERAGE",
                "wrongful_rejection_held_out": 0,
            }
            for r in runs
        }

    def b2(attacker_runs, baseline_runs=None, *, budget):
        return {"budget": budget, "per_family": [r["family"] for r in attacker_runs]}

    return {
        "adapter": types.SimpleNamespace(ADAPTERS={(CID, 0): adapter}),
        "analysis": types.SimpleNamespace(
            attempts=attempts, map_to_families=map_to_families
        ),
        "verify": types.SimpleNamespace(verify=verify, record=record),
        "engine": types.SimpleNamespace(run_family=run_family),
        "report": types.SimpleNamespace(family_report=family_report),
        "benchmark": types.SimpleNamespace(b2=b2),
        "knowledge": types.SimpleNamespace(AttackStore=FakeStore),
    }, adapter


# -- the dry run ---------------------------------------------------------------------------
def test_dry_run_produces_coverage_and_b2_with_no_spend(tmp_path, monkeypatch):
    mods, _ = fake_modules()
    monkeypatch.setattr(phase4, "attack_modules", lambda: mods)
    out = io.StringIO()
    with redirect_stdout(out):
        code = phase4.main(["run", "--root", str(tmp_path / "root"), "--dry-run"])
    assert code == 0
    # The research loop logs progress to stdout; the driver's JSON is last.
    body = out.getvalue()
    printed = json.loads(body[body.index("{") :])
    entry, coverage = printed["session"], printed["coverage"]
    assert entry["provider_state"] == "succeeded"
    # No live inference and a synthetic grant: a scripted model makes no network
    # call, so nothing real is spent (the ledger books only the scripted
    # transport's nominal charge).
    from decimal import Decimal

    assert Decimal(entry["settled_usd"]) < Decimal("0.01")
    assert printed["dry_run"]["synthetic"] is True
    assert printed["dry_run"]["money_cap_usd"] == "1.93"
    # The coverage report and B2 are present and claim nothing.
    assert coverage["construction_level"] == 0
    assert set(coverage["families"]) == {"recipe_surface", "mandatory_failure"}
    assert coverage["benchmark_b2"]["budget"] == phase4.ATTACK_BUDGET
    assert coverage["claims"] == {"security_acceptance": False, "graded": False}
    # The one scripted breach became a finding recorded on the controller.
    assert coverage["findings"] == ["graphite-attack-" + "d" * 16]
    # Zero findings for a family is attempted coverage, never an exploit-free bound.
    assert coverage["families"]["recipe_surface"]["zero"] == "ATTEMPTED_COVERAGE"


def test_dry_run_writes_only_under_the_dry_run_store(tmp_path, monkeypatch):
    mods, _ = fake_modules()
    monkeypatch.setattr(phase4, "attack_modules", lambda: mods)
    root = tmp_path / "root"
    with redirect_stdout(io.StringIO()):
        phase4.main(["run", "--root", str(root), "--dry-run"])
    assert (root / "attacker-dry-run").is_dir()
    assert not (root / "attacker").exists()
    log = (root / "attacker-dry-run" / "iteration-log.jsonl").read_text()
    assert json.loads(log)["role"] == "attacker"


# -- the session's limits: money and time bind, never a call count -------------------------
def _provider(tmp_path, script, *, adapter, miner_tools=None):
    grant = SpendingGrant.from_document(
        {**json.loads(GRANT_FILE.read_bytes()), "expires_at": "2099-01-01T00:00:00Z"}
    )
    return (
        phase4.AttackerProvider(
            root=tmp_path / "graphite",
            grant=grant,
            model=ScriptedModel(script),
            pods=ScriptedPods(),
            code_run_seconds=adapter.code_run_seconds,
            miner_tools=miner_tools,
        ),
        grant,
    )


def _run_one(tmp_path, script, *, adapter, atk, miner_tools=None):
    provider, grant = _provider(
        tmp_path, script, adapter=adapter, miner_tools=miner_tools
    )
    control = phase4.controller_for(tmp_path, provider, grant)
    try:
        brief = phase4.session_brief(
            adapter, checkout_commit="0" * 40, code_run_seconds=adapter.code_run_seconds
        )
        entry, coverage = phase4.run_session(
            tmp_path,
            control,
            provider,
            adapter,
            brief,
            1,
            atk,
            budget=phase4.ATTACK_BUDGET,
        )
    finally:
        control.close()
    return provider, entry, coverage


def test_the_attacker_session_has_no_call_cap(tmp_path, monkeypatch):
    """A reintroduced call cap turns this red: a phase-4 session opens under v2
    with no session-turn cap and no operator call cap (money and time bind)."""
    mods, adapter = fake_modules()
    provider, entry, _ = _run_one(tmp_path, [text("done")], adapter=adapter, atk=mods)
    opened = provider._opened(entry["run_id"])
    assert opened["session_limits"]["schema"] == SESSION_LIMITS_V2
    assert opened["session_limits"]["session_turns"] is None
    assert opened["session_limits"]["role_call_cap"] is None
    assert opened["session_limits"]["operator_call_cap"] is None
    assert opened["caps"]["provider_attempts"] is None
    assert provider.max_calls_per_run is None


def test_the_token_cap_is_the_attacker_pod_split(tmp_path):
    adapter = FakeAdapter()
    provider, _ = _provider(tmp_path, [text("done")], adapter=adapter)
    # Six verify pods, not the Constructor's twelve; the token share follows.
    assert provider.budget.max_pods == phase4.ATTACKER_VERIFY_PODS == 6
    assert str(provider.budget.token_allowance_usd) == "1.93"
    assert str(provider.budget.pod_allowance_usd) == "1.48"


# -- the resource rule: a code run needs a wall allowance ----------------------------------
class RecordingMiner:
    def __init__(self):
        self.calls = []

    async def call(self, name, arguments, identity):
        self.calls.append((name, arguments, identity))
        return {"status": "OK"}


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
    import asyncio

    miner = RecordingMiner()
    events = []
    tools = phase4.AttackerTools(
        miner=miner, emit=lambda *a: events.append(a), code_run_seconds=600
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
    import asyncio

    tools = phase4.AttackerTools(miner=None, emit=lambda *a: None, code_run_seconds=600)
    result = asyncio.run(
        tools.call(PREFIX + "start_research_task", _run_python(600), "id")
    )
    assert result["status"] == "UNAVAILABLE"
    assert result["dispatched"] is False


# -- the brief refuses protected material --------------------------------------------------
def test_a_brief_naming_protected_material_is_refused():
    """A protected marker in a family goal (the brief) must be refused: the
    attack goals are neutral wording, with this guard
    (lesson 2026-10-02-attacker-brief-protected-markers)."""
    clean = FakeAdapter()
    phase4.brief_observation(clean, code_run_seconds=600)  # no raise
    poisoned = FakeAdapter(
        goals={"recipe_surface": "read the official_seed from the held-out pool"}
    )
    with pytest.raises(ValueError, match="protected material"):
        phase4.brief_observation(poisoned, code_run_seconds=600)


# -- the driver runs the Attacker only -----------------------------------------------------
def test_phase4_runs_the_attacker_only(tmp_path):
    adapter = FakeAdapter()
    provider, _grant = _provider(tmp_path, [text("x")], adapter=adapter)
    from carbon.agent_campaign.graphite.provider import SessionBrief

    constructor_brief = SessionBrief(
        role=RoleName.CONSTRUCTOR,
        initial_observation={"challenge": adapter.public_identity()},
        checkout_commit="0" * 40,
        checkout_manifest_digest="sha256:" + "b" * 64,
    )
    provider.register_brief(constructor_brief)
    from carbon.agent_campaign.provider import TaskSpec

    spec = TaskSpec(
        campaign_id="x",
        role=ROLES[RoleName.ATTACKER].boundary.value,
        workspace_id="w",
        credential_ref="c",
        profile_digest="sha256:" + "a" * 64,
        instructions_digest=constructor_brief.digest,
        max_runtime_s=10,
    )
    from carbon.agent_campaign.provider import ProviderUnavailable

    with pytest.raises(ProviderUnavailable, match="phase4_runs_the_attacker_only"):
        provider.start(spec, "graphite-phase4-session-1")


# -- findings use only the CONDITIONS vocabulary -------------------------------------------
def test_a_finding_outside_the_conditions_vocabulary_is_refused(tmp_path):
    """verify.record goes through controller.record_finding, which refuses a
    condition outside the CONDITIONS vocabulary. A non-CONDITIONS finding type
    turns this red."""
    adapter = FakeAdapter()
    provider, grant = _provider(tmp_path, [text("x")], adapter=adapter)
    control = phase4.controller_for(tmp_path, provider, grant)
    try:
        with pytest.raises(controller_mod.ControllerError, match="unknown_condition"):
            control.record_finding("f-1", "NOT_A_CONDITION", b"{}")
        control.record_finding("f-2", "FAILING_TRIGGER", b"{}")  # a real condition
    finally:
        control.close()


def test_a_verified_breach_is_recorded_and_stops_later_expansion(tmp_path, monkeypatch):
    mods, adapter = fake_modules(breach=True)
    _provider_obj, _entry, coverage = _run_one(
        tmp_path, [text("done")], adapter=adapter, atk=mods
    )
    assert coverage["findings"] == ["graphite-attack-" + "d" * 16]
    # A finding blocks every later expansion on the same controller.
    provider, grant = _provider(tmp_path / "second", [text("x")], adapter=adapter)
    control = phase4.controller_for(tmp_path, provider, grant)
    try:
        with pytest.raises(controller_mod.ControllerError):
            control.record_expansion(
                challenge=CID,
                profile="sha256:" + "a" * 64,
                widened=[],
                permissions="sha256:" + "b" * 64,
                operator=phase4.OPERATOR,
            )
    finally:
        control.close()
