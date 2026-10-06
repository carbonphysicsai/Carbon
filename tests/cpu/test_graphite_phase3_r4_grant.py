"""GRAPHITE-GRANT-PHASE3-R4 (OWNER-GRAPHITE-PHASE3-R4-01): battery Level 1+
on the top Engy rung.

Claims tested:
- the grant is the owner's: R3's exact shape with only the approved fields
  changed, and its arithmetic holds (3 × 14.91 + 0.25 = 44.98 ≤ 45.00);
- a full-window kimi-k3 call at the Constructor's settings reserves exactly
  USD 2.0646912: five fit the run's USD 11.93 token share, four the approved
  USD 10 model allowance, none a Level 0 run's USD 1.95;
- the run's budget uses the registered USD 11.93 share, and its pods get the
  rest only while that covers them; every other grant's budget is unchanged;
- a Level 0 run under R4 is refused typed, at the CLI before anything opens
  and again before a session opens;
- a Level 1 session under R4 opens on kimi-k3, its first full-window call is
  admitted, its record carries the run conditions, and a stall at the top
  records `ladder_top`; a session that would open below kimi-k3 is refused;
- every other grant keeps its ladder, budget and record;
- each guard, disabled, lets the wrong thing through (mutations).

Scripted model, scripted pods: no live run, key, network or spend.
"""

from __future__ import annotations

import dataclasses
import json
import types
from decimal import Decimal
from pathlib import Path

import pytest

from carbon.agent_campaign.grant import SpendingGrant
from carbon.agent_campaign.graphite import experiment as ex
from carbon.agent_campaign.graphite import grant_binding, phase3, pods, roles
from carbon.agent_campaign.graphite.ladder import Ladder, LadderError
from carbon.agent_campaign.graphite.model import ScriptedModel, text, tool
from carbon.agent_campaign.graphite.roles import FailureKind, RoleName
from carbon.agent_campaign.provider import ProviderUnavailable, TaskSpec
from carbon.challenge_validator import scoring as challenge_scoring
from carbon.development_session.model_provider import ENGY_LADDER, select
from carbon.reconstruction.capability_registry import (
    BATTERY_CHALLENGE,
    COLD_PLATE_CHALLENGE,
)

REPOSITORY = Path(__file__).resolve().parents[2]
GRANTS = REPOSITORY / grant_binding.GRANTS_DIR
R4_ID = "GRAPHITE-GRANT-PHASE3-R4"
R4_NAME = R4_ID + ".json"
BATTERY = challenge_scoring.scoring_for(BATTERY_CHALLENGE)
#: kimi-k3's full-window reservation, nanodollars: 1,048,576 × 1,950 + 2,048 × 9,750.
KIMI_RESERVATION_NANO = 2064691200
NANO = Decimal(10) ** 9


def _document(name=R4_NAME, **changes):
    document = json.loads((GRANTS / name).read_bytes())
    assert "HUMAN_INPUT" not in json.dumps(document)
    return {**document, **changes}


def _grant(name=R4_NAME, **changes):
    return SpendingGrant.from_document(
        _document(name, **{"expires_at": "2099-01-01T00:00:00Z", **changes})
    )


def _refusal(capsys, call):
    with pytest.raises(SystemExit):
        call()
    return json.loads(capsys.readouterr().out.strip().splitlines()[-1])["reason_code"]


def _provider(tmp_path, grant, script=None, model=None):
    return phase3.Phase3Provider(
        root=tmp_path / "graphite",
        grant=grant,
        model=model or ScriptedModel(script or [text("done")]),
        pods=pods.ScriptedPods(),
        miner_tools=phase3.DryRunMiner(),
        randomness=lambda n: b"\x00" * n,
        scoring=BATTERY,
    )


def _level_1():
    return phase3.development_variant_for(1, BATTERY)


def _start(provider, variant):
    """Open one session under `provider` at `variant`'s level (None: 0)."""
    brief = phase3.session_brief(
        checkout_commit="0" * 40,
        budget=provider.budget,
        scoring=BATTERY,
        variant=variant,
    )
    profile = phase3.permission_profile(BATTERY, variant)[1]
    spec = TaskSpec(
        campaign_id=phase3.CAMPAIGN,
        role=roles.ROLES[RoleName.CONSTRUCTOR].boundary.value,
        workspace_id=phase3.WORKSPACE,
        credential_ref=phase3.CREDENTIAL_REF,
        profile_digest=profile,
        instructions_digest=provider.register_brief(brief),
        max_runtime_s=provider.grant.max_runtime_s,
    )
    provider.start(spec, phase3.session_key(1))
    return provider._opened(provider.run_id_for(phase3.session_key(1)))


def _run(tmp_path, grant, model=None):
    """One whole Level 1 session under the controller, as the runner runs it."""
    provider = _provider(tmp_path, grant, model=model)
    control = phase3.controller_for(tmp_path, provider, grant)
    try:
        brief = phase3.session_brief(
            checkout_commit="0" * 40,
            budget=provider.budget,
            scoring=BATTERY,
            variant=_level_1(),
        )
        result = phase3.run_session(control, provider, brief, 1, _level_1())
    finally:
        control.close()
    return provider, result


# -- the grant ----------------------------------------------------------------------------------
def test_the_r4_grant_is_r3_with_only_the_approved_fields_changed():
    r3, r4 = _document("GRAPHITE-GRANT-PHASE3-R3.json"), _document()
    assert list(r4) == list(r3)
    changed = {key for key in r3 if r3[key] != r4[key]}
    assert changed == {"grant_id", "monetary_ceiling", "worst_case_run_cost"}
    assert r4["grant_id"] == R4_ID
    assert r4["monetary_ceiling"] == "45.00"
    assert r4["worst_case_run_cost"] == "14.91"
    assert r4["permitted_runs"] == r4["max_submissions"] == 3
    assert (r4["expires_at"], r4["account"], r4["granted_by"]) == (
        r3["expires_at"],
        r3["account"],
        r3["granted_by"],
    )
    grant = SpendingGrant.from_document(r4)
    assert grant.provider == "graphite" and grant.currency == "USD"


def test_the_arithmetic_holds():
    grant = _grant()
    r3 = _grant("GRAPHITE-GRANT-PHASE3-R3.json")
    assert grant.worst_case_run_cost == r3.worst_case_run_cost + Decimal("10.00")
    total = grant.permitted_runs * grant.worst_case_run_cost + grant.cleanup_allowance
    assert total == Decimal("44.98") <= grant.monetary_ceiling == Decimal("45.00")
    headroom = grant.monetary_ceiling - grant.cleanup_allowance
    assert headroom // grant.worst_case_run_cost == grant.permitted_runs


def test_kimi_k3s_full_window_reservation_and_how_many_fit():
    settings = roles.MODEL_SETTINGS[RoleName.CONSTRUCTOR]["kimi-k3"]
    selection = select(
        provider_id=phase3.ADAPTER,
        model_id="kimi-k3",
        credential={"kind": "file", "reference": "unused"},
        settings=dict(settings),
    )
    assert selection.settings.max_input_tokens == 1048576
    assert selection.settings.max_output_tokens == 2048
    assert selection.reservation_nano == KIMI_RESERVATION_NANO
    reservation = Decimal(KIMI_RESERVATION_NANO) / NANO
    assert reservation == Decimal("2.0646912")
    assert Decimal("11.93") // reservation == 5
    assert Decimal("10.00") // reservation == 4
    # A Level 0 battery run's token share admits none.
    r3 = ex.phase3_budget(_grant("GRAPHITE-GRANT-PHASE3-R3.json"), BATTERY)
    assert r3.token_allowance_usd == Decimal("1.95") < reservation


def test_the_grant_cites_its_authority():
    readme = (GRANTS / "README.md").read_text()
    section = readme[readme.index("## GRAPHITE-GRANT-PHASE3-R4") :]
    section = section[: section.index("\n## ", 1)]
    assert "OWNER-GRAPHITE-PHASE3-R4-01" in section
    assert "= 44.98  ≤ 45.00" in section
    assert "USD 2.0646912" in section
    assert grant_binding.LEVEL_REFUSED in section
    assert grant_binding.START_MODEL_REFUSED in section
    record = REPOSITORY / ".agent/decisions/2026-10-05-OWNER-GRAPHITE-PHASE3-R4-01.md"
    assert "For 1 and up." in record.read_text()


# -- the registry and the budget ---------------------------------------------------------------
def test_the_registry_binds_r4_to_battery_main_level_1_and_the_top_rung():
    entry = grant_binding.PHASE3_GRANTS[R4_ID]
    assert entry.challenge == BATTERY_CHALLENGE and entry.main_blob is True
    assert entry.grant_file == grant_binding.GRANTS_DIR + "/" + R4_NAME
    assert entry.min_level == 1
    assert entry.start_model == "kimi-k3" == ENGY_LADDER[-1]
    assert entry.token_share_usd == Decimal("11.93")
    assert grant_binding.start_rungs(_grant()) == {
        RoleName.CONSTRUCTOR: len(ENGY_LADDER) - 1,
        RoleName.PLANNER: len(ENGY_LADDER) - 1,
    }
    for other_id, other in grant_binding.PHASE3_GRANTS.items():
        if other_id == R4_ID:
            continue
        assert (other.min_level, other.start_model, other.token_share_usd) == (
            0,
            None,
            None,
        )
        named = types.SimpleNamespace(grant_id=other_id)
        assert grant_binding.run_conditions(named) is None
        assert grant_binding.start_rungs(named) == {}
        assert grant_binding.level_refusal(named, 0) is None


def test_the_run_budget_uses_the_registered_token_share():
    budget = ex.phase3_budget(_grant(), BATTERY)
    assert budget.token_allowance_usd == Decimal("11.93")
    assert budget.pod_allowance_usd == Decimal("2.98") >= budget.pods_need_usd
    assert budget.pods_need_usd == Decimal("2.96") and budget.max_pods == 12
    assert budget.record()["token_share_usd"] == "11.93"
    assert ex.usd_to_nano(budget.token_allowance_usd) >= KIMI_RESERVATION_NANO


def test_other_grants_budgets_are_unchanged():
    for name in (
        "GRAPHITE-GRANT-PHASE3.json",
        "GRAPHITE-GRANT-PHASE3-R2.json",
        "GRAPHITE-GRANT-PHASE3-R3.json",
    ):
        budget = ex.phase3_budget(_grant(name), BATTERY)
        assert budget.token_share_usd is None
        assert "token_share_usd" not in budget.record()
        assert budget.pod_allowance_usd == Decimal("2.96")
        assert budget.token_allowance_usd == Decimal("1.95")


def test_a_share_that_starves_the_pods_is_refused(monkeypatch):
    entry = grant_binding.PHASE3_GRANTS[R4_ID]
    starved = dataclasses.replace(entry, token_share_usd=Decimal("12.00"))
    monkeypatch.setattr(
        grant_binding,
        "PHASE3_GRANTS",
        types.MappingProxyType({**grant_binding.PHASE3_GRANTS, R4_ID: starved}),
    )
    with pytest.raises(ex.BudgetRefused) as refused:
        ex.phase3_budget(_grant(), BATTERY)
    assert refused.value.code == "grant_token_share_leaves_too_little_for_pods"


# -- Level 0 is refused -------------------------------------------------------------------------
def test_level_0_under_r4_is_refused_before_git(tmp_path, capsys):
    """The level is checked before the main-blob read: `tmp_path` is no
    repository, so a Level 1 check goes on to refuse there instead."""
    grant = _grant()
    for level in (0, None, "1", -1):
        code = _refusal(
            capsys,
            lambda lv=level: grant_binding.check_phase3_grant(
                GRANTS / R4_NAME,
                grant,
                challenge=BATTERY_CHALLENGE,
                level=lv,
                repository=tmp_path,
            ),
        )
        assert code == grant_binding.LEVEL_REFUSED, level
    code = _refusal(
        capsys,
        lambda: grant_binding.check_phase3_grant(
            GRANTS / R4_NAME,
            grant,
            challenge=BATTERY_CHALLENGE,
            level=1,
            repository=tmp_path,
        ),
    )
    assert code == "phase3_grant_not_committed"
    code = _refusal(
        capsys,
        lambda: grant_binding.check_phase3_grant(
            GRANTS / R4_NAME, grant, challenge=COLD_PLATE_CHALLENGE, level=1
        ),
    )
    assert code == "grant_is_for_another_challenge"


def test_the_runner_refuses_a_level_0_r4_run_before_anything_opens(tmp_path, capsys):
    root = tmp_path / "root"
    argv = [
        "run",
        "--root",
        str(root),
        "--challenge",
        BATTERY_CHALLENGE,
        "--grant",
        str(GRANTS / R4_NAME),
        "--credential-env",
        "ENGY_API_KEY",
        "--runpod-key-env",
        "RUNPOD_API_KEY",
        "--code-ref",
        "0" * 40,
    ]
    assert _refusal(capsys, lambda: phase3.main(argv)) == grant_binding.LEVEL_REFUSED
    assert not any(root.iterdir())


def test_the_provider_refuses_a_level_0_session_under_r4(tmp_path):
    provider = _provider(tmp_path, _grant())
    with pytest.raises(ProviderUnavailable) as refused:
        _start(provider, None)
    assert str(refused.value) == grant_binding.LEVEL_REFUSED
    assert not list((tmp_path / "graphite" / "runs").iterdir())


# -- Level 1 opens on the top rung -------------------------------------------------------------
def test_a_level_1_session_opens_on_kimi_k3_and_its_first_call_is_admitted(tmp_path):
    provider, result = _run(tmp_path, _grant())
    assert result["provider_state"] == "succeeded"
    record = provider.session_record(result["run_id"])
    assert record["role"]["model"] == "kimi-k3"
    assert record["role"]["rung"] == len(ENGY_LADDER) - 1
    assert record["run_conditions"] == {
        "schema": grant_binding.RUN_CONDITIONS_SCHEMA,
        "authority": "OWNER-GRAPHITE-PHASE3-R4-01",
        "grant_id": R4_ID,
        "min_construction_level": 1,
        "start_model": "kimi-k3",
        "start_roles": ["constructor", "planner"],
        "token_share_usd": "11.93",
    }
    [call] = record["calls"]
    assert call["state"] == "SUCCEEDED" and call["provider_model"] == "kimi-k3"
    assert call["reservation"]["provider_nanodollars"] == KIMI_RESERVATION_NANO
    assert record["caps"]["provider_nanodollars"] == 11930000000


def test_there_is_no_rung_above_the_top(tmp_path):
    provider = _provider(tmp_path, _grant())
    ladder = provider.ladder
    assert ladder.model(RoleName.CONSTRUCTOR) == "kimi-k3"
    assert ladder.model(RoleName.PLANNER) == "kimi-k3"
    failure = ladder.record_failure(
        RoleName.CONSTRUCTOR, FailureKind.BUILD_FAILED_TO_COMPILE, "sha256:" + "a" * 64
    )
    with pytest.raises(LadderError) as refused:
        ladder.escalate(RoleName.CONSTRUCTOR, failure)
    assert refused.value.code == "ladder_top"
    # The other roles keep their own start rungs.
    assert ladder.model(RoleName.WRITER) == roles.ROLES[RoleName.WRITER].start_model


def test_a_session_below_the_start_rung_is_refused(tmp_path):
    provider = _provider(tmp_path, _grant())
    provider.ladder = Ladder(tmp_path / "plain-ladder")
    with pytest.raises(ProviderUnavailable) as refused:
        _start(provider, _level_1())
    assert str(refused.value) == grant_binding.START_MODEL_REFUSED


def test_other_grants_keep_their_ladder_and_record(tmp_path):
    grant = _grant("GRAPHITE-GRANT-PHASE3-R3.json")
    provider = _provider(tmp_path, grant)
    assert provider.ladder.start_rungs == {}
    opened = _start(provider, None)
    assert opened["role"]["model"] == roles.ROLES[RoleName.CONSTRUCTOR].start_model
    assert "run_conditions" not in opened
    assert "token_share_usd" not in opened["grant"]["phase3_budget"]


# -- a settled call frees its unused reservation -------------------------------------------------
#: Run 5 made 23 model calls. No per-call token record of it is committed, so
#: this is a stated conservative profile: each call charged as 30,000 input
#: tokens plus the whole 2,048-token output cap at kimi-k3's list prices,
#: 30,000 × 1,950 + 2,048 × 9,750 nanodollars = USD 0.078468, about 2.6 times
#: the ~USD 0.03 run 5's calls would cost on kimi-k3.
RUN5_CALLS = 23
RUN5_CHARGED_MICRO = 78468


def _run5_model():
    probe = tool("carbon_research_v2__get_challenge_info", {})
    return ScriptedModel(
        [probe] * (RUN5_CALLS - 1) + [text("done")],
        charged_micro=RUN5_CHARGED_MICRO,
        input_tokens=30000,
    )


def _succeeded(provider, result):
    calls = provider.session_record(result["run_id"])["calls"]
    return [call for call in calls if call["state"] == "SUCCEEDED"]


def test_23_settled_kimi_k3_calls_are_admitted_under_the_r4_share(tmp_path):
    """Each call is admitted against the share with its full USD 2.0646912
    reservation, then settles to its reported charge, which replaces the
    reservation in the research ledger (`CampaignLedger._usage`): run 5's
    23 calls fit, where full reservations alone would stop after 5."""
    provider, result = _run(tmp_path, _grant(), model=_run5_model())
    assert result["provider_state"] == "succeeded"
    calls = _succeeded(provider, result)
    assert len(calls) == RUN5_CALLS
    for call in calls:
        assert call["provider_model"] == "kimi-k3"
        assert call["reservation"]["provider_nanodollars"] == KIMI_RESERVATION_NANO
        assert call["settlement"]["provider_nanodollars"] == RUN5_CHARGED_MICRO * 1000
    spent = Decimal(RUN5_CALLS * RUN5_CHARGED_MICRO) / 10**6
    assert spent + Decimal(KIMI_RESERVATION_NANO) / NANO <= Decimal("11.93")


def test_mutation_keeping_each_full_reservation_stops_after_5_calls(
    tmp_path, monkeypatch
):
    from carbon.development_session import research_ledger

    def reserved_only(self, db):
        used = dict.fromkeys(research_ledger.DIMENSIONS, 0)
        for (reserved,) in db.execute("SELECT reservation FROM operations"):
            for key, value in json.loads(reserved).items():
                used[key] += value
        return used

    monkeypatch.setattr(research_ledger.CampaignLedger, "_usage", reserved_only)
    provider, result = _run(tmp_path, _grant(), model=_run5_model())
    assert result["provider_state"] != "succeeded"
    assert len(_succeeded(provider, result)) == 5


# -- mutations: each guard, disabled, lets the wrong thing through ------------------------------
def test_mutation_without_the_level_guard_level_0_opens_on_r4(tmp_path, monkeypatch):
    monkeypatch.setattr(grant_binding, "level_refusal", lambda grant, level: None)
    opened = _start(_provider(tmp_path, _grant()), None)
    assert opened["role"]["model"] == "kimi-k3"


def test_mutation_without_the_start_rung_level_1_cannot_open(tmp_path, monkeypatch):
    monkeypatch.setattr(grant_binding, "start_rungs", lambda grant: {})
    with pytest.raises(ProviderUnavailable) as refused:
        _start(_provider(tmp_path, _grant()), _level_1())
    assert str(refused.value) == grant_binding.START_MODEL_REFUSED


def test_mutation_without_both_rung_guards_level_1_opens_on_the_cheap_rung(
    tmp_path, monkeypatch
):
    monkeypatch.setattr(grant_binding, "start_rungs", lambda grant: {})
    monkeypatch.setattr(
        grant_binding, "start_model_refusal", lambda grant, role, model: None
    )
    opened = _start(_provider(tmp_path, _grant()), _level_1())
    assert opened["role"]["model"] == roles.ROLES[RoleName.CONSTRUCTOR].start_model


def test_mutation_r3s_token_share_admits_no_kimi_k3_call(tmp_path, monkeypatch):
    """Falling back to R3's token share (USD 1.95): the run stops at the cap
    before its first full-window kimi-k3 call."""
    entry = grant_binding.PHASE3_GRANTS[R4_ID]
    fallback = dataclasses.replace(entry, token_share_usd=Decimal("1.95"))
    monkeypatch.setattr(
        grant_binding,
        "PHASE3_GRANTS",
        types.MappingProxyType({**grant_binding.PHASE3_GRANTS, R4_ID: fallback}),
    )
    provider, result = _run(tmp_path, _grant())
    assert result["provider_state"] != "succeeded"
    record = provider.session_record(result["run_id"])
    assert not [call for call in record["calls"] if call["state"] == "SUCCEEDED"]
