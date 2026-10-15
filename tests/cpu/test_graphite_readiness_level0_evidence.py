"""Level-0 readiness evidence for cooling and motor (P3, R7, A2, A3, S2).

The Level-0 counterpart of `test_graphite_readiness_level_evidence.py`, which
emits battery's evidence at Levels 1 to 4. Each test here runs once per
Challenge on the challenge's own registered Level-0 scoring and attack
adapter, and prints one `READINESS_LEVEL_EVIDENCE` line naming that
Challenge and Level 0, which the readiness gate requires
(`carbon.challenge_pipeline.readiness.checks.run_tests`).

Public fixtures, scripted roles, synthetic pod outputs: no inference, no
pod, no key, no network and no spend. Level 0 is the recorded miner-facing
contract: no development variant is named anywhere.
"""

from __future__ import annotations

import copy
import json
from types import SimpleNamespace

import containment_double
import graphite_phase3_fixtures as p3f
import pytest
from graphite_fixtures import RecordingMinerTools
from test_graphite_attacker_stop_rule_v3 import _door_attempts
from test_graphite_phase4 import _grant

from carbon.agent_campaign.attack import adapters
from carbon.agent_campaign.graphite import delivery, phase3, phase4
from carbon.agent_campaign.graphite.model import ScriptedModel, text, tool
from carbon.agent_campaign.graphite.roles import ROLES, RoleName
from carbon.challenge_validator import scoring as challenge_scoring
from carbon.development_session import research_loop

LEVEL = 0
CHALLENGES = ("chip-cold-plate", "electric-motor-magnetics")
BACKBONE = "kernel_ridge"


def evidence(item, challenge, **values):
    print(
        "\nREADINESS_LEVEL_EVIDENCE "
        + json.dumps(
            {"item": item, "challenge": challenge, "level": LEVEL, **values},
            sort_keys=True,
        )
    )


def _snapshot(adapter):
    """Take the families once; the same adapter still classifies every call."""
    families = adapter.families()

    class Snapshot:
        def families(self):
            return families

        def __getattr__(self, name):
            return getattr(adapter, name)

    return Snapshot()


@pytest.mark.parametrize("challenge", CHALLENGES)
def test_phase3_dry_run_at_level_zero(tmp_path, capsys, monkeypatch, challenge):
    containment_double.install(monkeypatch)
    assert (
        phase3.main(
            [
                "run",
                "--root",
                str(tmp_path),
                "--challenge",
                challenge,
                "--level",
                str(LEVEL),
                "--dry-run",
            ]
        )
        == 0
    )
    output = capsys.readouterr().out
    result = json.loads(output[output.index("{\n") :])
    assert result["provider_state"] == "succeeded"
    assert result["delivery"]["clean_rebuild"]["status"] == "REBUILT"
    checks = result["dry_run"]
    assert checks["pods_alive"] == []
    assert (
        checks["real_pod_path"]["status"]
        == checks["pod_failure_path"]["status"]
        == "OK"
    )
    folder = tmp_path / "dry-run/graphite/runs" / result["run_id"]
    for name in ("WRITEUP.md", "REBUILD.md", "manifest.json", "recipe.json"):
        assert (folder / "delivery" / name).is_file(), name
    # The bundle is this Challenge's own Level-0 recipe, not another's.
    strategy = json.loads((folder / "delivery/strategy.json").read_bytes())
    assert strategy["challenge_id"] == challenge
    assert strategy["backbone"] == BACKBONE
    recipe = json.loads((folder / "delivery/recipe.json").read_bytes())
    assert "development" not in recipe
    # The brief comes from the provider's persisted registry and names this
    # Challenge at Level 0, with no development variant.
    briefs = [
        json.loads(path.read_bytes())
        for path in (tmp_path / "dry-run/graphite/briefs").glob("*.json")
    ]
    brief = next(
        b
        for b in briefs
        if b["initial_observation"].get("challenge_id") == challenge
        or b["initial_observation"].get("challenge") == challenge
        or challenge in json.dumps(b["initial_observation"])
    )
    contract = brief["initial_observation"].get("construction_contract") or {}
    assert contract.get("development_variant") is None
    evidence(
        "P3",
        challenge,
        provider_state=result["provider_state"],
        clean_rebuild="REBUILT",
        real_pod_path="OK",
        pod_failure_path="OK",
        pods_alive=[],
        recipe_digest=result["delivery"]["clean_rebuild"]["recipe_digest"],
    )


@pytest.mark.parametrize("role", [RoleName.CONSTRUCTOR, RoleName.ATTACKER])
@pytest.mark.parametrize("challenge", CHALLENGES)
def test_each_roles_turn_text_matches_its_scripted_ledger_at_level_zero(
    tmp_path, monkeypatch, challenge, role
):
    scoring = challenge_scoring.scoring_for(challenge)
    script = [
        tool("carbon_research_v2__get_challenge_info", {}),
        (
            text("done")
            if role is RoleName.CONSTRUCTOR
            else tool(
                phase4.FINISH_TOOL_NAME, {"summary": "fixture budget is nearly used"}
            )
        ),
    ]
    if role is RoleName.CONSTRUCTOR:
        provider = p3f.provider(tmp_path, script, p3f.ScriptedPods(), scoring=scoring)
    else:
        adapter = adapters.load(challenge, LEVEL)
        families = adapter.families()
        monkeypatch.setattr(adapter, "families", lambda: families)
        provider = phase4.live_provider(
            tmp_path,
            grant=_grant(),
            model=ScriptedModel(script),
            adapter=adapter,
            miner_attach=None,
        )
        provider.miner_tools = RecordingMinerTools()
    seen = []
    real_status = research_loop.budget_status
    real_ledger_status = phase3.Phase3Ledger.status
    source_rows = []

    def scripted_status(self, *args, **kwargs):
        row = copy.deepcopy(real_ledger_status(self, *args, **kwargs))
        row["budget"].update(
            provider_attempts=13, provider_nanodollars=9_000_000_000, research_trials=0
        )
        row["used"].update(
            provider_attempts=len(seen) + (2 if role is RoleName.CONSTRUCTOR else 10),
            provider_nanodollars=(len(seen) + 1) * 1_000_000,
            research_trials=0,
        )
        source_rows.append(row)
        return row

    def checked_status(root, turn, **kw):
        # Deterministic, non-production ledger values, supplied independently
        # of rendering: the agent's text must be computed from the ledger.
        ledger = source_rows[-1]
        assert kw["ledger_status"] == ledger
        message = real_status(root, turn, **kw)
        value = message["content"]
        left = (
            ledger["budget"]["provider_attempts"] - ledger["used"]["provider_attempts"]
        )
        assert f"{left} of 13 provider calls left" in value
        money = (
            ledger["budget"]["provider_nanodollars"]
            - ledger["used"]["provider_nanodollars"]
        ) / 10**9
        assert f"USD {money:.4f} of USD 9.0000 provider spend left" in value
        assert f"USD {kw['provider'].reservation_nano / 10**9:.4f}" in value
        assert "0 of 0" not in value
        seen.append(message)
        return message

    monkeypatch.setattr(research_loop, "budget_status", checked_status)
    monkeypatch.setattr(phase3.Phase3Ledger, "status", scripted_status)
    if role is RoleName.CONSTRUCTOR:
        brief = phase3.session_brief(
            checkout_commit="1" * 40,
            budget=provider.budget,
            scoring=scoring,
            variant=None,
            level_domain_text=True,
        )
        control = p3f.controller(tmp_path, provider)
        try:
            phase3.run_session(control, provider, brief, 1, None)
        finally:
            control.close()
    else:
        brief = phase4.session_brief(
            adapter, checkout_commit="1" * 40, stop_rule=provider.stop_rule
        )
        control = phase4.controller_for(tmp_path, provider, provider.grant)
        try:
            phase4.ensure_campaign(
                control,
                checkout_digest=brief.checkout_manifest_digest,
                profile_digest=phase4.attacker_profile(adapter)[1],
            )
            from carbon.agent_campaign.provider import TaskSpec

            spec = TaskSpec(
                campaign_id=phase4.CAMPAIGN,
                role=ROLES[role].boundary.value,
                workspace_id=phase4.WORKSPACE,
                credential_ref=phase4.CREDENTIAL_REF,
                profile_digest=phase4.attacker_profile(adapter)[1],
                instructions_digest=provider.register_brief(brief),
                max_runtime_s=provider.grant.max_runtime_s,
            )
            control.launch(spec, phase4.session_key(1))
            provider.run(provider.run_id_for(phase4.session_key(1)))
        finally:
            control.close()
    assert len(seen) >= 2
    for status in seen:
        assert any(status in request["input"] for request in provider.model.requests)
    evidence("R7", challenge, role=role.value, turns=len(seen))


@pytest.mark.parametrize("challenge", CHALLENGES)
def test_every_reachable_family_is_an_adapter_family_at_level_zero(challenge):
    adapter = adapters.load(challenge, LEVEL)
    names = {f.name for f in adapter.families()}
    reachable = phase4.reachable_families(
        adapter, ROLES[RoleName.ATTACKER].tool_schemas(), declare=True
    )
    assert reachable
    assert set(reachable) <= names


@pytest.mark.parametrize("challenge", CHALLENGES)
def test_the_level_zero_provider_records_its_rule_and_withholds_finish(
    tmp_path, monkeypatch, challenge
):
    adapter = _snapshot(adapters.load(challenge, LEVEL))
    provider = phase4.live_provider(
        tmp_path,
        grant=_grant(),
        model=ScriptedModel([]),
        adapter=adapter,
        miner_attach=None,
    )
    schema = provider.stop_rule
    assert schema in phase4.STOP_RULES
    record = provider.session_limits_record(
        {"max_runtime_s": provider.grant.max_runtime_s}
    )["stop_rule"]
    assert record == phase4.stop_rule_record(schema)
    table = phase4.stop_rule_coverage(
        adapter, ROLES[RoleName.ATTACKER].tool_schemas(), schema=schema
    )
    assert table["families"], "no family is reachable at Level 0"
    assert phase4.finish_verdict(table, None)[0] is False
    attempts = []
    for row in table["families"]:
        attempts += _door_attempts(table, row["family"], len(attempts))[: record["k"]]
    complete = phase4.stop_rule_coverage(
        adapter, ROLES[RoleName.ATTACKER].tool_schemas(), attempts, schema=schema
    )
    assert all(row["attempts"] == record["k"] for row in complete["families"])
    assert phase4.finish_verdict(complete, None)[0] is True
    from carbon.agent_campaign.attack import analysis

    observed = []
    monkeypatch.setattr(analysis, "attempts", lambda directory: observed)
    ledger = SimpleNamespace(
        status=lambda **kwargs: {
            "budget": {"provider_attempts": 100},
            "used": {"provider_attempts": 0},
        }
    )
    finish = provider._finish_check(
        "fixture", ledger, ROLES[RoleName.ATTACKER], object(), schema
    )
    assert finish({"summary": "fixture"})[0] is False
    observed.extend(attempts)
    assert finish({"summary": "fixture"})[0] is True
    evidence(
        "A3",
        challenge,
        schema=schema,
        k=record["k"],
        reachable=sorted(row["family"] for row in complete["families"]),
        unreachable=sorted(row["family"] for row in complete["unreachable"]),
    )


@pytest.mark.parametrize("challenge", CHALLENGES)
def test_graphite_filters_gate_failures_before_ranking_at_level_zero(challenge):
    # A gate-failing proposal with the best raw score is never the delivered
    # improvement: Graphite selects only among frozen-rule-eligible proposals.
    # The Challenge's own scoring is resolved, so the selection runs under the
    # same named scoring a Level-0 session uses.
    scoring = challenge_scoring.scoring_for(challenge)
    assert scoring.challenge_id == challenge
    records = [
        {
            "proposal_id": name,
            "kind": "proposal",
            "status": "SCORED",
            "ordinal": index,
            "against_baseline": {"outcome": "IMPROVEMENT"},
            "frozen_rule": {"eligible": eligible, "score": score},
        }
        for index, (name, eligible, score) in enumerate(
            [("failed", False, -100.0), ("good", True, -2.0), ("other", True, -0.5)]
        )
    ]
    assert delivery.best_improvement(records)["proposal_id"] == "good"
    only_failed = [r for r in records if r["proposal_id"] == "failed"]
    assert delivery.best_improvement(only_failed) is None
