"""Q1 report for the readiness gate (items V1 and V2).

V1 is a measurement gate, not a threshold: it passes when a score-to-value
alignment report for the challenge's registered panel EXISTS, is internally
consistent and is current against the scoring rule in force. V2 is a real
threshold: the panel's members must reach at least `MIN_DISTINCT_OUTCOMES`
distinct decision outcomes on the decision study.

The report is `readiness/<challenge>/q1_report.json`. It is built from the
panel Data Collection's Track B harness produced (`carbon.design_search.
track_b.alignment` and `score_value.alignment`):

    python -m carbon.challenge_pipeline.readiness.q1 build \
        --challenge ID --level 0 --panel PANEL.json --out REPORT.json

`PANEL.json` is `{"provenance": "REGISTERED_PANEL", "decision_study": REF,
"members": {name: {score, value, eligible, recipe, kind, decision_outcome}}}`,
exactly the `members` shape `score_value.alignment` takes plus each member's
`decision_outcome` (the design it chose, or ABSTAIN). The build recomputes the
alignment, so a recorded report cannot disagree with its members, and binds the
report to the digest of the scoring rule in force.

Nothing here chooses a value: no threshold other than the two-outcome floor the
gate document names, and no panel is produced. A FIXTURE panel is never
evidence (invariant 9) and fails V1.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .model import FAIL, PACKAGE, PASS, REPOSITORY, Result, digest

REPORT_SCHEMA = "carbon.challenge-pipeline.readiness-q1-report.v1"
#: The gate document's V2 floor: "at least two distinct decision outcomes".
MIN_DISTINCT_OUTCOMES = 2
PANEL_PROVENANCES = ("REGISTERED_PANEL", "FIXTURE")


def current_rule_digest(challenge, repository=REPOSITORY):
    """The digest of the registered scoring's frozen rule identity, or None
    when no scoring is registered for the challenge."""
    from carbon.challenge_validator import scoring

    try:
        rule = scoring.scoring_for(challenge).frozen_rule(Path(repository))
    except scoring.ScoringUnavailable:
        return None
    return digest(rule.identity)


def _alignment_of(members):
    """`score_value.alignment` over members whose JSON list values (class,
    number) are the tuples it expects, as plain JSON data for comparison."""
    from carbon.design_search import score_value

    fixed = {
        name: {
            **row,
            "value": tuple(row["value"])
            if isinstance(row.get("value"), list)
            else row.get("value"),
        }
        for name, row in members.items()
    }
    return json.loads(json.dumps(score_value.alignment(fixed)))


def build_report(challenge, level, panel, rule_digest):
    """The Q1 report for `panel`, with its alignment recomputed."""
    members = panel["members"]
    return {
        "schema": REPORT_SCHEMA,
        "challenge": challenge,
        "level": level,
        "scoring_rule_digest": rule_digest,
        "provenance": panel["provenance"],
        "decision_study": panel["decision_study"],
        "members": members,
        "alignment": _alignment_of(members),
    }


def load_report(challenge, root=None):
    path = Path(PACKAGE if root is None else root) / challenge / "q1_report.json"
    if not path.is_file():
        return None, path
    try:
        return json.loads(path.read_bytes()), path
    except ValueError:
        return False, path


def _problem(report, challenge, level):
    if not isinstance(report, dict) or report.get("schema") != REPORT_SCHEMA:
        return "not a readiness Q1 report"
    if report.get("challenge") != challenge or report.get("level") != level:
        return "names another challenge or level"
    if report.get("provenance") not in PANEL_PROVENANCES:
        return "provenance is not recorded"
    members = report.get("members")
    if not (isinstance(members, dict) and members):
        return "no panel members"
    if not isinstance(report.get("alignment"), dict):
        return "no alignment"
    return None


def v1_alignment_report(item, ctx):
    report, path = load_report(ctx.challenge)
    if report is None:
        return Result(
            FAIL,
            "no Q1 alignment report is recorded (readiness/<challenge>/q1_report.json); "
            "run the Track B alignment on the registered panel and build one with "
            "`readiness.q1 build`",
        )
    problem = _problem(report, ctx.challenge, ctx.level) if report else "unreadable"
    if problem:
        return Result(FAIL, f"q1_report.json is unusable: {problem}", (path.name,))
    if report["provenance"] != "REGISTERED_PANEL":
        return Result(
            FAIL,
            "the recorded panel is a FIXTURE; fixture panels are never evidence",
            (path.name,),
        )
    current = current_rule_digest(ctx.challenge, ctx.repository)
    if current is None:
        return Result(
            FAIL,
            "no scoring is registered for the challenge, so the report cannot be "
            "shown current against a scoring rule",
            (path.name,),
        )
    if report.get("scoring_rule_digest") != current:
        return Result(
            FAIL,
            "the report is stale: it was built under another scoring rule digest",
            (f"recorded {report.get('scoring_rule_digest')}", f"current {current}"),
        )
    if _alignment_of(report["members"]) != report["alignment"]:
        return Result(
            FAIL,
            "the recorded alignment does not follow from its members",
            (path.name,),
        )
    a = report["alignment"]
    band = a["tau_noise_band"]["band"]
    divergences = [
        c["member"]
        for c in a["conditions"]
        if c["condition"] == "SCORE_VALUE_DIVERGENCE"
    ]
    return Result(
        PASS,
        f"Q1 report recorded: tau {a['kendall_tau_b']} (band {band}), rho "
        f"{a['spearman_rho']}, {len(divergences)} divergences. A measurement, not a "
        "threshold: a negative or within-noise tau is recorded, and the first runs "
        "are framed as alignment measurements (review).",
        (
            f"report:{digest(report)}",
            f"tau:{a['kendall_tau_b']}",
            f"rho:{a['spearman_rho']}",
            f"tau_band:{band}",
            *[f"divergence:{m}" for m in divergences],
        ),
    )


def v2_panel_discrimination(item, ctx):
    report, path = load_report(ctx.challenge)
    if report is None:
        return Result(
            FAIL, "no Q1 report is recorded, so panel discrimination is unmeasured"
        )
    problem = _problem(report, ctx.challenge, ctx.level) if report else "unreadable"
    if problem:
        return Result(FAIL, f"q1_report.json is unusable: {problem}", (path.name,))
    outcomes = {}
    for name, row in sorted(report["members"].items()):
        if row.get("eligible") is not True:
            continue
        outcome = row.get("decision_outcome")
        if not (isinstance(outcome, str) and outcome):
            return Result(
                FAIL, f"member {name} records no decision outcome", (path.name,)
            )
        outcomes.setdefault(outcome, []).append(name)
    evidence = tuple(f"{o}:{','.join(m)}" for o, m in sorted(outcomes.items()))
    if report["provenance"] != "REGISTERED_PANEL":
        return Result(FAIL, "the recorded panel is a FIXTURE; not evidence", evidence)
    if len(outcomes) >= MIN_DISTINCT_OUTCOMES:
        return Result(
            PASS,
            f"{len(outcomes)} distinct decision outcomes among panel members",
            evidence,
        )
    return Result(
        FAIL,
        f"{len(outcomes)} distinct decision outcome(s), below {MIN_DISTINCT_OUTCOMES}: "
        "widen the construction families first (development variant)",
        evidence,
    )


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="python -m carbon.challenge_pipeline.readiness.q1"
    )
    sub = parser.add_subparsers(dest="command", required=True)
    b = sub.add_parser("build", help="build a Q1 report from a harness panel")
    b.add_argument("--challenge", required=True)
    b.add_argument("--level", type=int, default=0)
    b.add_argument("--panel", required=True)
    b.add_argument("--out", required=True)
    args = parser.parse_args(argv)
    panel = json.loads(Path(args.panel).read_bytes())
    for key in ("provenance", "decision_study", "members"):
        if key not in panel:
            print(f"panel is missing {key}")
            return 2
    rule = current_rule_digest(args.challenge)
    if rule is None:
        print("no scoring is registered for the challenge; cannot bind a rule digest")
        return 2
    report = build_report(args.challenge, args.level, panel, rule)
    with open(args.out, "w", encoding="utf-8", newline=chr(10)) as out:
        out.write(json.dumps(report, indent=1, sort_keys=True) + chr(10))
    return 0


if __name__ == "__main__":
    sys.exit(main())
