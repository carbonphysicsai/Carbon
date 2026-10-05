"""Challenge-neutral run plans for Launchpad construction campaigns.

The plan describes the miner's model-provider and Graphite budgets.  Physics,
construction vocabularies, reference material and scoring never enter it.
"""

from __future__ import annotations

AGENT_BUDGET_KEYS = ("provider_attempts", "provider_nanodollars")


def provider_plan(agent, budget, selection=None, graphite=None):
    """Return the finite, evaluator-blind plan for a named campaign agent."""
    if agent == "none":
        from carbon.development_session.research_tools import (
            ARGUMENT_NORMALISATION_V2,
        )

        # The miner's own agent calls the miner MCP door, which reads this
        # rule too (AGENT-DOOR-USABILITY-01 A1): a new plan freezes v2. A
        # plan frozen before names none and replays unchanged.
        return {
            "agent": "none",
            "model_calls": 0,
            "argument_normalisation": ARGUMENT_NORMALISATION_V2,
        }
    if agent == "graphite":
        return graphite_plan(budget, selection, graphite)
    if graphite is not None:
        raise ValueError("only a Graphite campaign freezes a Graphite block")
    from carbon.development_session import miner_guidance
    from carbon.development_session.model_provider import (
        DEFAULT_SELECTION,
        check_budget,
    )
    from carbon.development_session.research_agent_policy import (
        AUTONOMOUS,
        PARALLEL_CALLS_V2,
    )
    from carbon.development_session.research_campaign import FINAL_EPOCHS
    from carbon.development_session.research_tools import (
        ARGUMENT_NORMALISATION_V2,
        TOOLS_RULE,
    )

    ceilings = (budget or {}).get("ceilings") or {}
    if any(type(ceilings.get(key)) is not int for key in AGENT_BUDGET_KEYS):
        raise ValueError(
            "an autonomous campaign needs finite provider_attempts and "
            "provider_nanodollars ceilings"
        )
    selection = DEFAULT_SELECTION if selection is None else selection
    check_budget(selection, ceilings)
    plan = {
        "agent": "autonomous",
        "policy": AUTONOMOUS,
        "model": selection.model_id,
        "epochs": len(FINAL_EPOCHS),
        "max_provider_calls_per_epoch": 48,
        "max_research_trials_per_epoch": 8,
        "ceilings": {key: ceilings[key] for key in AGENT_BUDGET_KEYS},
        "evaluator_access": False,
        "parallel_calls": PARALLEL_CALLS_V2,
        "miner_guidance": miner_guidance.RULE,
        "research_tools": TOOLS_RULE,
        # AGENT-DOOR-USABILITY-01 A1: every new plan freezes v2; a plan
        # frozen before names no rule and replays unchanged.
        "argument_normalisation": ARGUMENT_NORMALISATION_V2,
    }
    if not selection.is_historical_default:
        plan["model_selection"] = selection.record()
    return plan


def graphite_plan(budget, selection, graphite):
    """Return Graphite's finite, evaluator-blind miner-edition plan."""
    from carbon.agent_campaign.graphite.miner import driver, edition
    from carbon.development_session import miner_guidance
    from carbon.development_session.model_provider import (
        DEFAULT_SELECTION,
        check_budget,
    )
    from carbon.development_session.research_agent_policy import PARALLEL_CALLS_V2
    from carbon.development_session.research_campaign import FINAL_EPOCHS
    from carbon.development_session.research_tools import (
        ARGUMENT_NORMALISATION_V2,
        TOOLS_RULE,
    )

    ceilings = (budget or {}).get("ceilings") or {}
    if any(type(ceilings.get(key)) is not int for key in AGENT_BUDGET_KEYS):
        raise ValueError(
            "a Graphite campaign needs finite provider_attempts and "
            "provider_nanodollars ceilings"
        )
    if graphite is None:
        raise ValueError("a Graphite plan freezes its launch block")
    block = edition.check_block(graphite)
    edition.resolve(block["edition"], block["edition_digest"])
    selection = DEFAULT_SELECTION if selection is None else selection
    check_budget(selection, ceilings)
    driver.check_research_share(block, ceilings, selection)
    limits = block["limits"]
    plan = {
        "agent": "graphite",
        "policy": edition.agent_policy(),
        "model": selection.model_id,
        "epochs": len(FINAL_EPOCHS),
        "ceilings": {key: ceilings[key] for key in AGENT_BUDGET_KEYS},
        "evaluator_access": False,
        "parallel_calls": PARALLEL_CALLS_V2,
        "miner_guidance": miner_guidance.RULE,
        "research_tools": TOOLS_RULE,
        # RESEARCH-TOOL-USABILITY-01: new plans freeze v2; a plan that froze
        # v1 (or no rule) keeps it.
        "argument_normalisation": ARGUMENT_NORMALISATION_V2,
        "limits": {
            "plan": edition.limits_rule(
                limits.get("planner_calls"), limits.get("trials_per_epoch")
            ),
            "build": edition.limits_rule(
                limits.get("calls_per_epoch"), limits.get("trials_per_epoch")
            ),
        },
        "compaction": edition.compaction_rule(),
        "graphite": block,
    }
    if not selection.is_historical_default:
        plan["model_selection"] = selection.record()
    return plan


def agent_policies(agent):
    """The controller policies allowed for a campaign agent."""
    from carbon.development_session.research_agent_policy import AUTONOMOUS

    if agent == "graphite":
        from carbon.agent_campaign.graphite.miner.edition import AGENT_POLICY

        return (AUTONOMOUS, AGENT_POLICY)
    return (AUTONOMOUS,)


def plan_selection(args, plan):
    """Resolve a frozen run plan's model selection without changing it."""
    from carbon.development_session.model_provider import DEFAULT_SELECTION
    from carbon.development_session.research_campaign import resolve_selection

    record = plan.get("model_selection")
    if record is None:
        if plan.get("model") != DEFAULT_SELECTION.model_id:
            raise ValueError("the frozen run plan names no usable model")
        record = DEFAULT_SELECTION.manifest_record()
    return resolve_selection(args, record)
