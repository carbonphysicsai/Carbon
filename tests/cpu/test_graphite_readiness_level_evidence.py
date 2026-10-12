"""PLT-09 batch 1: public fixtures, scripted roles and no inference/pod spend."""

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
from carbon.development_session import research_loop
from carbon.reconstruction import development_variants as dv

CID = p3f.SCORING.challenge_id


def evidence(item, level, **values):
    print(
        "\nREADINESS_LEVEL_EVIDENCE "
        + json.dumps(
            {"item": item, "challenge": CID, "level": level, **values}, sort_keys=True
        )
    )


@pytest.mark.parametrize("level", [2, 3, 4])
def test_phase3_dry_run_at_the_named_level(tmp_path, capsys, monkeypatch, level):
    containment_double.install(monkeypatch)
    assert (
        phase3.main(
            [
                "run",
                "--root",
                str(tmp_path),
                "--challenge",
                CID,
                "--level",
                str(level),
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
    opened = json.loads((folder / "session-open.json").read_bytes())
    recipe = json.loads((folder / "delivery/recipe.json").read_bytes())
    assert recipe["development"]["variant_digest"] == dv.variant(CID, level).digest
    assert recipe["development"]["level"] == level
    # Read the brief from the provider's persisted registry, not a fabricated summary.
    provider_briefs = list((tmp_path / "dry-run/graphite/briefs").glob("*.json"))
    brief = next(
        json.loads(path.read_bytes())
        for path in provider_briefs
        if json.loads(path.read_bytes())["initial_observation"]["level"] == level
    )
    assert brief["initial_observation"]["level_domain"]["level"] == level
    assert opened["brief"]["digest"]
    if level == 4:
        assert (folder / "delivery/level4-envelope.json").is_file()
        strategy = json.loads((folder / "delivery/strategy.json").read_bytes())
        assert strategy["parameters"]["composition_graphs"]
    evidence(
        "P3",
        level,
        provider_state=result["provider_state"],
        clean_rebuild="REBUILT",
        real_pod_path="OK",
        pod_failure_path="OK",
        pods_alive=[],
        variant_digest=recipe["development"]["variant_digest"],
    )


@pytest.mark.parametrize("level", [1, 2, 3, 4])
@pytest.mark.parametrize("role", [RoleName.CONSTRUCTOR, RoleName.ATTACKER])
def test_each_roles_turn_text_matches_its_scripted_ledger(
    tmp_path, monkeypatch, level, role
):
    adapter = adapters.load(CID, level)
    script = [tool("carbon_research_v2__get_challenge_info", {}), text("done")]
    if role is RoleName.CONSTRUCTOR:
        provider = p3f.provider(tmp_path, script, p3f.ScriptedPods())
    else:
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
            provider_attempts=len(seen) + 2,
            provider_nanodollars=(len(seen) + 1) * 1_000_000_000,
            research_trials=0,
        )
        source_rows.append(row)
        return row

    def checked_status(root, turn, **kw):
        # Deterministic, non-production ledger values, supplied independently of rendering.
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
            scoring=p3f.SCORING,
            variant=dv.variant(CID, level),
            level_domain_text=True,
        )
        control = p3f.controller(tmp_path, provider)
        try:
            phase3.run_session(control, provider, brief, 1, dv.variant(CID, level))
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
    evidence("R7", level, role=role.value, turns=len(seen))


@pytest.mark.parametrize("level", [1, 2, 3, 4])
def test_the_level_provider_records_its_rule_and_withholds_finish(
    tmp_path, monkeypatch, level
):
    adapter = adapters.load(CID, level)
    families = adapter.families()

    class Snapshot:
        def families(self):
            return families

        def __getattr__(self, name):
            return getattr(adapter, name)

    adapter = Snapshot()
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
        level,
        schema=schema,
        k=record["k"],
        unreachable=[row["family"] for row in complete["unreachable"]],
    )


@pytest.mark.parametrize("level", [2, 3, 4])
def test_graphite_filters_gate_failures_before_ranking(level):
    # Graphite ranks error ascending after eligibility; EV5 ranks -error descending.
    # They enforce the same admissibility invariant through distinct existing paths.
    from carbon.battery.value import ev5_run

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
    assert dv.variant(CID, level).level == level
    assert delivery.best_improvement(records)["proposal_id"] == "good"
    negative = {
        row["proposal_id"]: -abs(row["frozen_rule"]["score"]) for row in records
    }
    ranked = ev5_run.ranked_last(negative, {"failed": "FAIL"})
    assert ranked["failed"] < min(ranked["good"], ranked["other"])
