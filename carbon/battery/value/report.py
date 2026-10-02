# Copyright (c) 2026 Carbon Physics AI, Inc.
# SPDX-License-Identifier: MIT
# Full license text: see LICENSE at the repository root.

"""A readable owner report of an engineering-value results document."""

from __future__ import annotations


def _f(value, digits=3):
    if value is None:
        return "—"
    if isinstance(value, str):
        return value
    return f"{value:.{digits}f}"


def two_rankings(results):
    """The deciding rule and the proposed rule, side by side.

    OWNER-BATTERY-DECISION-AWARE-PROPOSAL-01: every report from here on shows
    both rankings with both halves of the evidence on the same row, and
    neither leads. Empty when a result does not carry both rules.
    """
    from .proposal import DECIDING_RULE, PROFILE_ID

    deciding, proposed = DECIDING_RULE["value_rule_id"], PROFILE_ID
    comparison = results.get("comparison", {})
    if deciding not in comparison or proposed not in comparison:
        return []
    check = results["summary"].get("boundary_optimist_check") or {}

    def optimist(rule):
        row = check.get(rule)
        if not row:
            return "not measured"
        return (
            f"{row['members_scored_below_it']} of {row['eligible_members']} members "
            f"at or below it ({'caught' if row['below_every_eligible_member'] else 'not caught'})"
        )

    def row(label, rule):
        c = comparison[rule]
        return (
            f"| {label} `{rule}` | {_f(c['tau_verification'])} "
            f"| {_f(c['tau_development'])} | {optimist(rule)} |"
        )

    return [
        "",
        "## The deciding rule and the proposed rule, side by side",
        "",
        (
            "The deciding rule is the frozen exam rule. The proposed rule is a "
            "prospective proposal and decides nothing until its own approval. "
            "Read both columns: ranking real models and catching optimism at the "
            "safety limits are separate questions, and a rule can win one and "
            "lose the other."
        ),
        "",
        "| Rule | τ verification (ranking real models) | τ development | Boundary-optimist control |",
        "|---|---|---|---|",
        row("deciding", deciding),
        row("proposed", proposed),
        "",
        (
            "Basis: `comparison.<rule>.tau_verification` and "
            "`summary.boundary_optimist_check` in this run's results. With a small "
            "panel, τ differences are indicative only."
        ),
    ]


def hypotheses(results):
    """EV4's pre-registered H1-H3, when the result carries them."""
    h = results.get("hypotheses")
    if not h:
        return []
    h1, h3 = h["H1"], h["H3"]
    low, high = h1["interval"]
    lines = [
        "",
        "## Pre-registered hypotheses",
        "",
        (
            f"**H1 (primary, paired).** Δτ = τ(`{h1['proposed_rule']}`) − "
            f"τ(`{h1['deciding_rule']}`) = {_f(h1['delta_tau'])} "
            f"({_f(h1['tau_proposed'])} − {_f(h1['tau_deciding'])}), "
            f"{round(h1['level'] * 100)} % paired bootstrap interval "
            f"[{_f(low)}, {_f(high)}] over {h1['members']} eligible members and "
            f"{h1['conditions']} verification conditions "
            f"(B = {h1['replicates']}, seed {h1['rng_seed']}, "
            f"{h1['replicates_skipped']} replicates undefined). "
            f"Decision: **{h1['decision']}**."
        ),
        "",
        (
            "An interval that includes 0 is UNRESOLVED: it does not show that the "
            "rules rank models equally well."
        ),
        "",
        "**H2 (boundary-optimist control).**",
        "",
    ]
    for rule, row in h["H2"].items():
        if not row:
            lines.append(f"- `{rule}`: not measured")
            continue
        lines.append(
            f"- `{rule}`: below every eligible member: "
            f"{row['below_every_eligible_member']} ({row['members_scored_below_it']} "
            f"of {row['eligible_members']} at or below it)"
        )
    lines += [
        "",
        (
            f"**H3 (real-model blind spot).** {h3['members_with_false_acceptance']} of "
            f"{h3['eligible_members']} eligible real members select a protocol the "
            "reference verifies INFEASIBLE on at least one verification condition."
        ),
        "",
    ]
    if h3["members"]:
        rules = list(h3["members"][0]["rank"])
        lines += [
            "| Member | Conditions | "
            + " | ".join(f"Rank `{r}`" for r in rules)
            + " |",
            "|---|---|" + "---|" * len(rules),
        ]
        for row in h3["members"]:
            ranks = " | ".join(str(row["rank"][r]) for r in rules)
            conditions = ", ".join(row["false_acceptance_conditions"])
            lines.append(f"| {row['member']} | {conditions} | {ranks} |")
    families = results.get("families")
    if families:
        lines += [
            "",
            "## Panel families",
            "",
            "| Family | Members | Eligible | Verification loss range |",
            "|---|---|---|---|",
        ]
        for family, row in sorted(families.items()):
            lines.append(
                f"| {family} | {row['members']} | {row['eligible']} "
                f"| {_f(row['loss_verification_min'])} – "
                f"{_f(row['loss_verification_max'])} |"
            )
    return lines


def render(results, experiment="EV1"):
    """`experiment` titles the report: the contract's case prefix, so an EV2
    report is never headed EV1."""
    summary = results["summary"]
    lines = [
        f"# {experiment}: does Carbon's scoring prefer models that make better engineering decisions?",
        "",
        (
            "Public synthetic DEVELOPMENT evidence. It changes no testnet rule and "
            'claims no qualification. "Best" means best in the tested candidate '
            "set, not a global optimum. No optimal weight ratio is claimed."
        ),
        "",
        f"- Contract: `{results['contract_digest']}`",
        (
            f"- Scoring set: `{results['scoring_set']['path']}` "
            f"({results['scoring_set']['cases']} cases, "
            f"sha256 `{results['scoring_set']['sha256'][:16]}…`)"
        ),
        (
            f"- Rule chosen on development scenarios: "
            f"**{summary['chosen_rule_on_development'] or 'none measurable'}**"
        ),
        (
            f"- Kendall τ (rule score vs. decision quality) on the verification "
            f"scenarios: chosen rule {_f(summary['chosen_rule_tau_verification'])}, "
            f"control {_f(summary['control_tau_verification'])}"
        ),
        *two_rankings(results),
        *hypotheses(results),
        "",
        "## Reference outcomes per scenario",
        "",
        "| Scenario | Split | Best in tested set | Baseline | Feasible / infeasible / unresolved / unavailable |",
        "|---|---|---|---|---|",
    ]
    for scenario, info in results["references"].items():
        counts = info["status_counts"]
        lines.append(
            f"| {scenario} | {info['split']} | {info['best_in_tested_set'] or 'none'} "
            f"| {info['baseline_status']} | {counts['FEASIBLE']} / {counts['INFEASIBLE']}"
            f" / {counts['UNRESOLVED']} / {counts['REFERENCE_UNAVAILABLE']} |"
        )
    lines += [
        "",
        "## Scoring rules against decision quality",
        "",
        (
            "τ > 0 means the rule prefers the models whose selections lose less. "
            "The panel is small, so treat these values as indicative."
        ),
        "",
        "| Rule | Measurable | τ development | τ verification | τ dev incl. controls | Top member (LOBO stable) |",
        "|---|---|---|---|---|---|",
    ]
    for rule, row in results["comparison"].items():
        stable = results["stability"].get(rule)
        top = (
            "—"
            if stable is None
            else f"{stable['top_member']} ({stable['leave_one_batch_out_same_top']}/{stable['batches']})"
        )
        lines.append(
            f"| {rule} | {'yes' if row['measurable'] else 'no: ' + ','.join(row['not_measurable'])} "
            f"| {_f(row['tau_development'])} | {_f(row['tau_verification'])} "
            f"| {_f(row['tau_development_with_controls'])} | {top} |"
        )
    check = summary.get("boundary_optimist_check")
    if check:
        lines += [
            "",
            "## Does each rule rank the boundary-optimist control below every eligible model?",
            "",
            (
                "The control is accurate almost everywhere and optimistic exactly "
                "near the plating and temperature limits, so it tends to select "
                "unsafe protocols."
            ),
            "",
            "| Rule | Below every eligible member | Members scored at or below it |",
            "|---|---|---|",
        ]
        for rule, row in check.items():
            if row is None:
                lines.append(f"| {rule} | not measurable | — |")
            else:
                lines.append(
                    f"| {rule} | {'yes' if row['below_every_eligible_member'] else 'no'} "
                    f"| {row['members_scored_below_it']} of {row['eligible_members']} |"
                )
    lines += [
        "",
        "## Members",
        "",
        (
            "Decision loss is measured in multiples of the minimum useful improvement; "
            "a false acceptance costs 10 and a missed opportunity costs 1 "
            "(provisional DEVELOPMENT costs)."
        ),
        "",
        "| Member | Kind | Eligible | Mean loss (dev) | Mean loss (verify) | Control score | p0-r30-a70 |",
        "|---|---|---|---|---|---|---|",
    ]
    for member, row in sorted(summary["members"].items()):
        scores = results["rule_scores"][member]
        lines.append(
            f"| {member} | {row['kind']} | {row['eligible']} | {_f(row['loss_development'])} "
            f"| {_f(row['loss_verification'])} | {_f(scores.get('control-exam-v1'), 4)} "
            f"| {_f(scores.get('p0-r30-a70'), 4)} |"
        )
    lines += [
        "",
        "## Decisions",
        "",
        "| Member | Scenario | Outcome | Selected | Gap to best (s) | vs baseline (s) | False acc. | False rej. | τ ranking |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for member in sorted(results["decisions"]):
        for scenario, row in results["decisions"][member].items():
            out, agree = row["outcome"], row["agreement"] or {}
            lines.append(
                f"| {member} | {scenario} | {out['kind']} | {out.get('selected') or '—'} "
                f"| {_f(out.get('gap_to_best_in_set_s'), 1)} "
                f"| {_f(out.get('improvement_vs_baseline_s'), 1)} "
                f"| {agree.get('false_acceptances', '—')} | {agree.get('false_rejections', '—')} "
                f"| {_f(agree.get('rank_tau_among_feasible'))} |"
            )
    lines += [
        "",
        "## Limitations",
        "",
        (
            "- Charging speed is time to constant-voltage onset (the 4.19 V crossing), "
            "not time to a target state of charge. The reference keeps no SOC or "
            "current trajectory."
        ),
        (
            "- The physics leg is not measurable for battery, so profiles that weight "
            "it are reported, not computed."
        ),
        (
            "- The scoring set omits hidden duplicates, so the paired-repeat gate is not "
            "exercised."
        ),
        (
            (
                "- The model panel is small, and reconstruction seeds are repetitions "
                "of a recipe, not independent models."
            )
            if "hypotheses" not in results
            else (
                "- Reconstruction seeds are repetitions of a recipe, not independent "
                "models; the bootstrap treats members as exchangeable."
            )
        ),
        "",
    ]
    return "\n".join(lines)
