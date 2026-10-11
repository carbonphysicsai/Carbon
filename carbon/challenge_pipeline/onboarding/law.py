"""Draft question laws; KEEP neutral export validation, never infer P from Q."""

from carbon.challenge_pipeline.onboarding import packet
from carbon.design_search import diversity, producer_panels, tasks

SOURCES = {
    "battery-v3": (
        "carbon.battery-ambient-question-law.proposal.round2.v1",
        {
            "P": "P_recommendation",
            "Q": "Q_recommendation",
            "w": "w",
            "action_set": "action_decision",
            "question": "question",
            "bank": "bank",
            "cost": "cost",
        },
    ),
    "motor": (
        "carbon.motor.question-law-proposal.v1",
        {
            "P": "P_job",
            "Q": "Q",
            "w": "w",
            "action_set": "action_space",
            "question": "requirements",
            "k": "k",
            "NONE_FEASIBLE": "NONE_FEASIBLE",
            "bank": "bank",
            "cost": "cost",
        },
    ),
    "f02": (
        "carbon.development.f02-question-law.v1",
        {
            "P": "p_job",
            "Q": "q_job",
            "w": "w_job",
            "action_set": "action_proposal",
            "question": "p_job",
            "k": "k",
            "NONE_FEASIBLE": "none_feasible",
            "bank": "bank_recommendation",
            "cost": "cost",
        },
    ),
}


def source_crosswalk(challenge, source):
    if challenge not in SOURCES or type(source) is not dict:
        raise packet.DraftError("known law proposal required for crosswalk")
    schema, mapping = SOURCES[challenge]
    if source.get("schema") != schema:
        raise packet.DraftError("law source family/schema mismatch")
    # Retain the prospective source, including its missing values and caveats.
    # Mapping is for drafting, never installation of the proposal's values.
    return {key: source.get(field) for key, field in mapping.items()}


def generate(draft, *, export=None, law_source=None):
    packet.validate_packet(draft)
    result = {
        "schema": "carbon.onboarding.question-law-draft.v1",
        "challenge": draft["challenge"],
        "maturity": "DRAFT_ONLY",
        "P": draft["fields"]["P"],
        "Q": draft["fields"]["Q"],
        "w": draft["fields"]["w"],
        "action_set": draft["fields"]["geometry"],
        "question": {
            "status": "HUMAN_INPUT",
            "recommendation": "One complete buyer decision, not one solver point; indexed decisions include every mandatory band",
            "buyer_decision": draft["fields"]["decision"],
        },
        "k": {
            "status": "HUMAN_INPUT",
            "recommendation": None,
            "basis": "Power and exposure owner selects; a panel's batch size is not approval",
        },
        "NONE_FEASIBLE": {
            "status": "HUMAN_INPUT",
            "recommendation": "VALID_FORWARD_NO_REDRAW only with a complete settled proof; missing/uncertain support stays UNRESOLVED",
        },
        "T2a": {
            "status": "TEST_LEAD_WORKING_VALUE",
            "near_refinement_bands": 2,
            "minimum_distinct_feasible": 5,
            "minimum_distinct_infeasible": 5,
            "measured": "NOT_ASSESSED_BY_DRAFTING",
            "band_widths": "HUMAN_INPUT",
            "rule": "Both sides near the limit; add frontier resolution, never widen bands",
        },
        "bank": {
            "status": "HUMAN_INPUT",
            "E": None,
            "B": None,
            "n": None,
            "threshold_variation_renews_exposure": False,
        },
        "startup_cost": {
            "status": "HUMAN_INPUT",
            "cpu_hours": None,
            "eur": None,
            "basis": "Requires unique new physical cases/rungs, measured CPU, throughput, overhead and quote; B is not a solve count",
        },
        "panel_basis": None,
        "diversity": None,
        "held_closed": "No law approval, bank draw, runtime registration, power acceptance or spend",
    }
    if law_source is not None:
        crosswalk = source_crosswalk(draft["challenge"], law_source)
        result["source_proposal_crosswalk"] = crosswalk
        result["source_proposal_digest"] = tasks.digest(law_source)
        result["source_proposal_status"] = "RETAINED_PROPOSAL_NOT_OWNER_ACCEPTANCE"
        k = crosswalk.get("k", {})
        if draft["challenge"] == "battery-v3":
            k = (crosswalk.get("question") or {}).get("k", {})
        if type(k) is dict:
            result["k"]["recommendation"] = k.get("recommendation")
    if export is not None:
        if type(export) is not dict or export.get("family") != draft["challenge"]:
            raise packet.DraftError("packet/panel family mismatch")
        try:
            bank, grid, continuous, _ = producer_panels.adapt_export(export)
            reports = [
                diversity.diversity_report(bank, law)
                for law in (grid, continuous)
                if law is not None
            ]
        except tasks.TaskError as error:
            raise packet.DraftError(
                "registered complete producer panel required"
            ) from error
        # Only existing aggregate views: no case IDs, task seeds, winners or curves.
        result["diversity"] = reports
        result["panel_basis"] = {
            "input_digest": tasks.digest(export),
            "questions_checked": len(bank["cases"]),
            "law_views_checked": len(reports),
            "reference_qualified_by_tool": False,
        }
        if result["k"]["recommendation"] is None:
            result["k"]["recommendation"] = reports[0]["batch_size"]
    return result
