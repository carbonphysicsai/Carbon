"""Read-only audit of public Graphite caps and grants; never dispatches a call."""

from __future__ import annotations

import argparse
import hashlib
import json
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

from carbon.agent_campaign.grant import GrantError, SpendingGrant
from carbon.agent_campaign.graphite import (
    experiment,
    grant_binding,
    level_planner,
    model_providers,
    phase4,
    provider,
    roles,
    score_lab_research,
    triage,
)
from carbon.challenge_validator import scoring as challenge_scoring

NANO = Decimal(10) ** 9
ROOT = Path(__file__).resolve().parents[2]
SOURCES = (
    "carbon/development_session/model_provider.py",
    "carbon/agent_campaign/graphite/roles.py",
    "carbon/agent_campaign/graphite/provider.py",
    "carbon/agent_campaign/graphite/model_providers.py",
    "carbon/agent_campaign/graphite/grant_binding.py",
    "carbon/agent_campaign/graphite/experiment.py",
    "carbon/agent_campaign/graphite/phase3.py",
    "carbon/agent_campaign/graphite/phase4.py",
    "carbon/agent_campaign/graphite/level_planner.py",
    "carbon/agent_campaign/graphite/score_lab_research.py",
    "carbon/agent_campaign/graphite/triage.py",
)


def selection(role, model_id, chosen=model_providers.ENGY):
    """Use the session's real selector; no provider instance or credential read."""
    host = SimpleNamespace(
        model_provider=chosen,
        adapter_id=chosen.default_adapter,
        model=SimpleNamespace(credential_reference="/audit/no-credential"),
    )
    return provider.GraphiteProvider._selection(host, model_id, role)


def call_record(selected):
    settings = selected.settings
    return {
        "model": selected.model_id,
        "max_input_tokens": settings.max_input_tokens,
        "max_output_tokens_including_reasoning": settings.max_output_tokens,
        "reservation_nano": selected.reservation_nano,
        "reservation_usd": str(Decimal(selected.reservation_nano) / NANO),
        "pricing": selected.pricing.record(),
    }


def capacity(selected, allowance):
    """Full-price reservations, without cached input or assumed cheap replies."""
    cost = Decimal(selected.reservation_nano) / NANO
    return {
        "model": selected.model_id,
        "reservation_usd": str(cost),
        "token_allowance_usd": str(allowance),
        "calls_at_full_reservation": int(allowance // cost),
        "reservation_fits": cost <= allowance,
    }


def workload(grant):
    """Only source-registered mappings. Unknown/historical mappings stay unknown."""
    entry = grant_binding.entry_of(grant)
    if entry is not None:
        scoring = challenge_scoring.scoring_for(entry.challenge)
        budget = (
            phase4.attacker_budget(grant, scoring)
            if entry.runner == "phase4"
            else experiment.phase3_budget(grant, scoring)
        )
        names = (
            [roles.RoleName.ATTACKER]
            if entry.runner == "phase4"
            else [roles.RoleName.CONSTRUCTOR, roles.RoleName.PLANNER]
        )
        return names, budget.token_allowance_usd, entry.replaced_by
    for entry in phase4.PHASE4_GRANTS.values():
        if entry.grant_id == grant.grant_id:
            budget = phase4.attacker_budget(
                grant, challenge_scoring.scoring_for(entry.challenge)
            )
            return [roles.RoleName.ATTACKER], budget.token_allowance_usd, None
    for entry in grant_binding.STUDY_GRANTS.values():
        if entry.grant_id == grant.grant_id:
            budget = experiment.phase3_budget(
                grant, challenge_scoring.scoring_for(entry.challenge)
            )
            return [roles.RoleName.CONSTRUCTOR], budget.token_allowance_usd, None
    return None


def closed_workload(grant):
    if grant.grant_id in level_planner.PLANNER_GRANTS:
        return "level_planner", level_planner.SETTINGS, level_planner.MAX_CALLS
    if grant.grant_id in score_lab_research.RESEARCH_GRANTS:
        return "score_lab", score_lab_research.SETTINGS, score_lab_research.MAX_CALLS
    if grant.grant_id in {
        "GRAPHITE-GRANT-PHASE2",
        "GRAPHITE-GRANT-LITERATURE-COOLING-MOTOR",
    }:
        return "literature_triage", triage.TRIAGE_SETTINGS, triage.MAX_CALLS_PER_RUN
    return None


def audit(root=ROOT):
    grant_dir = root / grant_binding.GRANTS_DIR
    paths = sorted(grant_dir.glob("*.json"))
    if not paths:
        raise ValueError("public_grant_inventory_empty")
    profiles = []
    for chosen in model_providers.MODEL_PROVIDERS.values():
        for role in roles.ROLES:
            models = [
                call_record(selection(role, model, chosen)) for model in chosen.ladder
            ]
            profiles.append(
                {
                    "provider": chosen.name,
                    "role": role.value,
                    "status": "PRICED" if models else "RATE_UNRECORDED",
                    "models": models,
                }
            )
    grants = []
    for path in paths:
        raw = path.read_bytes()
        row = {
            "file": path.relative_to(root).as_posix(),
            "sha256": hashlib.sha256(raw).hexdigest(),
        }
        try:
            grant = SpendingGrant.from_document(json.loads(raw))
            row.update(
                grant_id=grant.grant_id,
                worst_case_run_cost_usd=str(grant.worst_case_run_cost),
                monetary_ceiling_usd=str(grant.monetary_ceiling),
                cleanup_allowance_usd=str(grant.cleanup_allowance),
                permitted_runs=grant.permitted_runs,
            )
            if grant.zero_spend:
                row["status"] = "NO_INFERENCE"
            else:
                chosen = model_providers.resolve(grant_binding.model_provider_of(grant))
                row["model_provider"] = chosen.name
                mapped, closed = workload(grant), closed_workload(grant)
                if not chosen.ladder:
                    row["status"] = "RATE_UNRECORDED"
                elif mapped is not None:
                    names, allowance, replaced_by = mapped
                    row["status"] = "REPLACED" if replaced_by else "MAPPED"
                    row["replaced_by"] = replaced_by
                    row["roles"] = {
                        role.value: [
                            capacity(selection(role, model, chosen), allowance)
                            for model in chosen.ladder
                        ]
                        for role in names
                    }
                elif closed is not None:
                    name, settings, calls = closed
                    rows = []
                    for model in chosen.ladder:
                        selected = chosen.select(
                            adapter_id=chosen.default_adapter,
                            model_id=model,
                            credential_reference="/audit/no-credential",
                            settings=settings,
                        )
                        record = capacity(selected, grant.worst_case_run_cost)
                        record["maximum_call_count"] = calls
                        record["all_full_calls_usd"] = str(
                            Decimal(selected.reservation_nano) * calls / NANO
                        )
                        record["all_full_calls_fit"] = (
                            Decimal(selected.reservation_nano) * calls / NANO
                            <= grant.worst_case_run_cost
                        )
                        rows.append(record)
                    row.update(
                        status="MAPPED",
                        roles={name: rows},
                        closed_settings=settings,
                    )
                else:
                    row["status"] = "WORKLOAD_UNMAPPED"
        except (GrantError, ValueError) as refused:
            row.update(status="UNRESOLVED", reason=str(refused))
        grants.append(row)
    return {
        "schema": "carbon.graphite.role-grant-cap-audit.v1",
        "scope": "DEVELOPMENT_READ_ONLY_NO_SPEND_AUTHORITY",
        "basis": "CURRENT_REGISTERED_SELECTIONS_AND_PUBLIC_GRANT_FILES",
        "grant_count": len(grants),
        "source_sha256": {
            path: hashlib.sha256((ROOT / path).read_bytes()).hexdigest()
            for path in SOURCES
        },
        "profiles": profiles,
        "grants": grants,
        "amount_changes": "HUMAN_INPUT",
    }


def main():
    argparse.ArgumentParser(description=__doc__).parse_args()
    print(json.dumps(audit(), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
