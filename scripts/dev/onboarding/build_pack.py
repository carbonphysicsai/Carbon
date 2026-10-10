"""Carbon evidence pack generator (ONBOARDING-PIPELINE-01, extension).

Renders one page per Challenge and one cross-Challenge page from the brief-to-product
ledger (`build_ledger.py`). Every number on a page is a ledger field and carries the
artefact it came from. A field the ledger could not fill is printed as UNMEASURED with its
owner and question, never blank or smoothed. The pages are measurements read from
repository artefacts. They make no traction, customer, qualification or LIVE claim.

    python scripts/dev/onboarding/build_pack.py --out-dir DIR CHALLENGE [CHALLENGE ...]
"""

import argparse
import importlib.util
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location(
    "onboarding_build_ledger", HERE / "build_ledger.py"
)
ledger_module = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ledger_module)

UNMEASURED = ledger_module.UNMEASURED
DISCLAIMER = (
    "> DISCLAIMER: These pages are measurements read from repository artefacts. They are "
    "not traction, customer, qualification or LIVE claims, and not a statement that any "
    "Challenge is production-ready."
)
FRAMING = "Models never beat the solver on accuracy; the solver is the reference."
CONDITIONS = (
    "a_real_buyer_decision_two_sources",
    "b_regret_below_cheap_baseline_paired_bootstrap_ci",
    "c_speed_up_100x_per_decision_query",
    "d_value_and_volume_ranges",
    "e_equal_budget_screen_then_verify_beats_solver",
)


def _compact(value):
    if isinstance(value, str):
        return value
    return json.dumps(value, sort_keys=True, ensure_ascii=False)


def line(label, field):
    """One bullet: a measured value with its source, or UNMEASURED with owner and question."""
    if field["value"] == UNMEASURED:
        text = f"- {label}: UNMEASURED (owner: {field['owner']}; question: {field['question']})"
        if field.get("flag"):
            text += f" [{field['flag']}]"
        if field.get("source"):
            text += f" [source: {field['source']}]"
        return text
    return f"- {label}: {_compact(field['value'])} [source: {field['source']}]"


def challenge_page(ledger):
    brief, out, proc = ledger["brief"], ledger["outputs"], ledger["process"]
    value = out["passes_value"]
    lines = [
        f"# Evidence page: {ledger['challenge']}",
        "",
        DISCLAIMER,
        "",
        f"Generated from the brief-to-product ledger for `{ledger['challenge']}`.",
        f"Framing: {FRAMING}",
        "",
        "## Decision",
        line("Current decision", brief["current_decision"]),
    ]
    for key in ("unresolved_or_adverse_evidence", "scorecard_disposition"):
        if key in brief:
            lines.append(line(key.replace("_", " ").capitalize(), brief[key]))
    lines += [
        "",
        "## Value",
        line("A real buyer decision with at least two sources", value[CONDITIONS[0]]),
        line("Value and volume ranges", value[CONDITIONS[3]]),
        "",
        "## Model against reference and cheap baseline",
        line("Model agreement with the reference (accuracy)", out["model_accuracy"]),
        line(
            "Decision quality against the strongest cheap baseline (V4)",
            out["decision_quality_vs_cheap_baseline"],
        ),
        line(
            "Regret against the cheap baseline, paired bootstrap interval",
            value[CONDITIONS[1]],
        ),
        line("Score-value alignment", out["score_value_alignment"]),
        "",
        "## Required: equal-budget screen-then-verify",
        (
            f"This page is required. {FRAMING} A model beats the solver only by "
            "finding a better design at equal time and compute."
        ),
        line("Screen-then-verify against the solver alone", value[CONDITIONS[4]]),
        "",
        "## Speed-up against the reference",
        line("Speed-up per decision query", value[CONDITIONS[2]]),
        line("Speed-up from the ledger outputs", out["speed_up_against_reference"]),
        "",
        "## Onboarding cost and time",
        line("Dated stage records", proc["dated_stage_records"]),
        line("Cycle days per stage", proc["cycle_days_per_stage"]),
        line("Cost per stage", proc["cost_per_stage"]),
    ]
    for key, label in (
        ("readiness_first_run", "Readiness, first gate run"),
        ("readiness_latest_by_level", "Readiness, latest by level"),
        ("lessons_entries", "Lessons entries"),
        ("grant_caps", "Grant caps (caps only)"),
    ):
        if key in proc:
            lines.append(line(label, proc[key]))
    lines += [
        "",
        "## Blockers",
        "The taxonomy is pipeline-wide and seeded with battery stage A.",
    ]
    blockers = proc["blockers"]
    for blocker in blockers["value"]:
        lines.append(
            f"- {blocker['id']} {blocker['name']}: fix {blocker['fix_status']}; "
            f"time lost {blocker['time_lost']} [source: {blockers['source']}]"
        )
    lines += ["", "## Network"]
    for key, field in sorted(ledger["network"].items()):
        lines.append(line(key.replace("_", " ").capitalize(), field))
    measured = sum(1 for key in CONDITIONS if value[key]["value"] != UNMEASURED)
    lines += [
        "",
        "## PASSES VALUE",
        (
            f"- Conditions measured: {measured} of {len(CONDITIONS)} "
            f"[source: ledger outputs.passes_value for {ledger['challenge']}]"
        ),
        f"- Set by: {value['set_by']} [source: ledger outputs.passes_value for {ledger['challenge']}]",
        "",
    ]
    return "\n".join(lines)


def cross_page(ledgers):
    lines = [
        "# Evidence pack: across Challenges",
        "",
        DISCLAIMER,
        "",
        f"Framing: {FRAMING}",
        "",
        "## Challenges covered",
    ]
    for ledger in ledgers:
        decision = ledger["brief"]["current_decision"]
        lines.append(line(ledger["challenge"], decision))
    lines += [
        "",
        "## Physics regimes covered",
        (
            "- Regime taxonomy: UNMEASURED (owner: Test Lead; question: which regime "
            "tags apply to each Challenge? No artefact records one.)"
        ),
        "",
        "## PASSES VALUE across Challenges",
        "| Challenge | " + " | ".join(key[0] for key in CONDITIONS) + " |",
        "|---|" + "---|" * len(CONDITIONS),
    ]
    for ledger in ledgers:
        value = ledger["outputs"]["passes_value"]
        cells = [
            "UNMEASURED" if value[key]["value"] == UNMEASURED else "measured"
            for key in CONDITIONS
        ]
        lines.append(f"| {ledger['challenge']} | " + " | ".join(cells) + " |")
    lines += ["", "## Per-stage cost and time", ""]
    for ledger in ledgers:
        proc = ledger["process"]
        lines.append(f"### {ledger['challenge']}")
        lines.append(line("Dated stage records", proc["dated_stage_records"]))
        lines.append(line("Cycle days per stage", proc["cycle_days_per_stage"]))
        lines.append(line("Cost per stage", proc["cost_per_stage"]))
        lines.append("")
    lines += ["## Network evidence", ""]
    for ledger in ledgers:
        lines.append(f"### {ledger['challenge']}")
        for key, field in sorted(ledger["network"].items()):
            lines.append(line(key.replace("_", " ").capitalize(), field))
        lines.append("")
    return "\n".join(lines)


def build(challenges):
    """`{file name: text}` for the pack. Deterministic."""
    ledgers = [ledger_module.build(c) for c in challenges]
    pages = {f"{ledger['challenge']}.md": challenge_page(ledger) for ledger in ledgers}
    pages["cross_challenge.md"] = cross_page(ledgers)
    return pages


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("challenges", nargs="+")
    parser.add_argument("--out-dir", required=True)
    args = parser.parse_args(argv)
    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    for name, text in build(args.challenges).items():
        (out / name).write_text(text, encoding="utf-8", newline="\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
