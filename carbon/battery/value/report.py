"""A readable owner report of an EV1 results document."""

from __future__ import annotations


def _f(value, digits=3):
    if value is None:
        return "—"
    if isinstance(value, str):
        return value
    return f"{value:.{digits}f}"


def render(results):
    summary = results["summary"]
    lines = [
        "# EV1: does Carbon's scoring prefer models that make better engineering decisions?",
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
            "- The model panel is small, and reconstruction seeds are repetitions of a "
            "recipe, not independent models."
        ),
        "",
    ]
    return "\n".join(lines)
