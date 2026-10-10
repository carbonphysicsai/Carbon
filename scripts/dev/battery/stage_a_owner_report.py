"""Combine Stage A aggregate alignment, capability refusals and grant spend.

This consumes development summaries only. It does not open operator records,
predictions, reference banks, hidden cases or raw campaign logs.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import statistics
from collections import Counter
from decimal import Decimal, InvalidOperation
from pathlib import Path

from scripts.dev.battery import stage_a_alignment

ROOT = Path(__file__).resolve().parents[3]
GRANTS = ROOT / "docs/development/graphite/grants"
SCOPE = "DEVELOPMENT_SUMMARY_ONLY"
REFUSALS_SCHEMA = "carbon.graphite.refused-capability-summary.v1"
SPEND_SCHEMA = "carbon.graphite.stage-a-spend-summary.v1"
REPORT_SCHEMA = "carbon.graphite.stage-a-owner-report.v1"
TOKEN = re.compile(r"[a-z][a-z0-9._-]{0,79}\Z")
SHA = re.compile(r"sha256:[0-9a-f]{64}\Z")


class Refused(ValueError):
    """An input is incomplete or outside the development-summary contract."""


def _closed(value, fields, code):
    if type(value) is not dict or set(value) != set(fields):
        raise Refused(code)


def _token(value, code):
    if type(value) is not str or not TOKEN.fullmatch(value):
        raise Refused(code)


def _sha(value, code):
    if type(value) is not str or not SHA.fullmatch(value):
        raise Refused(code)


def _read(path):
    body = Path(path).read_bytes()
    try:
        value = json.loads(body)
    except (UnicodeError, ValueError) as error:
        raise Refused("invalid_json") from error
    return value, "sha256:" + hashlib.sha256(body).hexdigest()


def _refusals(path):
    value, digest = _read(path)
    _closed(
        value,
        {"schema", "scope", "source_sha256", "complete", "levels_covered", "records"},
        "refusals_shape",
    )
    if value["schema"] != REFUSALS_SCHEMA or value["scope"] != SCOPE:
        raise Refused("refusals_development_summary_required")
    _sha(value["source_sha256"], "refusals_source_digest")
    if type(value["complete"]) is not bool:
        raise Refused("refusals_complete_invalid")
    levels = value["levels_covered"]
    if (
        type(levels) is not list
        or not levels
        or any(type(x) is not int or x not in range(6) for x in levels)
        or levels != sorted(set(levels))
    ):
        raise Refused("refusals_levels_invalid")
    if type(value["records"]) is not list:
        raise Refused("refusals_records_invalid")
    counts = Counter()
    for row in value["records"]:
        _closed(row, {"capability_id", "level", "refusal_code"}, "refusal_record_shape")
        _token(row["capability_id"], "capability_id_invalid")
        _token(row["refusal_code"], "refusal_code_invalid")
        if type(row["level"]) is not int or row["level"] not in levels:
            raise Refused("refusal_level_uncovered")
        counts[(row["capability_id"], row["level"], row["refusal_code"])] += 1
    ranked = [
        {
            "capability_id": capability,
            "level": level,
            "refusal_code": code,
            "count": count,
        }
        for (capability, level, code), count in sorted(
            counts.items(), key=lambda item: (-item[1], item[0])
        )
    ]
    return {
        "summary_sha256": digest,
        "source_sha256": value["source_sha256"],
        "complete_claim": value["complete"],
        "levels_covered": levels,
        "total_refusals": len(value["records"]),
        "ranked_level5_investigation_candidates": ranked,
    }


def _money(value, code):
    if type(value) is not str or not re.fullmatch(
        r"(?:0|[1-9][0-9]*)(?:\.[0-9]{1,2})?", value
    ):
        raise Refused(code)
    try:
        return Decimal(value)
    except InvalidOperation as error:
        raise Refused(code) from error


def _spend(path):
    value, digest = _read(path)
    _closed(value, {"schema", "scope", "grants"}, "spend_shape")
    if value["schema"] != SPEND_SCHEMA or value["scope"] != SCOPE:
        raise Refused("spend_development_summary_required")
    if type(value["grants"]) is not list or not value["grants"]:
        raise Refused("spend_grants_empty")
    out, seen = [], set()
    for row in value["grants"]:
        _closed(
            row,
            {
                "grant_id",
                "grant_sha256",
                "observed_spend_usd",
                "source_sha256",
                "state",
            },
            "spend_grant_shape",
        )
        grant_id = row["grant_id"]
        if (
            type(grant_id) is not str
            or not re.fullmatch(r"GRAPHITE-GRANT-STAGE-A-[A-Z-]+", grant_id)
            or grant_id in seen
        ):
            raise Refused("grant_id_invalid")
        seen.add(grant_id)
        for key in ("grant_sha256", "source_sha256"):
            _sha(row[key], "spend_" + key)
        if row["state"] not in ("SETTLED", "ESTIMATED", "UNRESOLVED"):
            raise Refused("spend_state_invalid")
        grant_path = GRANTS / (grant_id + ".json")
        grant_body = grant_path.read_bytes()
        if row["grant_sha256"] != "sha256:" + hashlib.sha256(grant_body).hexdigest():
            raise Refused("grant_digest_mismatch")
        grant = json.loads(grant_body)
        if grant["grant_id"] != grant_id or grant["currency"] != "USD":
            raise Refused("grant_document_invalid")
        cap = _money(grant["monetary_ceiling"], "grant_cap_invalid")
        spent = (
            _money(row["observed_spend_usd"], "observed_spend_invalid")
            if row["state"] != "UNRESOLVED"
            else None
        )
        if row["state"] == "UNRESOLVED" and row["observed_spend_usd"] is not None:
            raise Refused("unresolved_spend_has_value")
        out.append(
            {
                "grant_id": grant_id,
                "cap_usd": str(cap),
                "observed_spend_usd": None if spent is None else str(spent),
                "state": row["state"],
                "over_cap": None if spent is None else spent > cap,
                "source_sha256": row["source_sha256"],
            }
        )
    return {
        "summary_sha256": digest,
        "grants": sorted(out, key=lambda item: item["grant_id"]),
    }


def build(alignment_input, refusals_input, spend_input, *, draws=500, seed=20261009):
    return {
        "schema": REPORT_SCHEMA,
        "scope": SCOPE,
        "alignment": stage_a_alignment.analyze(alignment_input, draws=draws, seed=seed),
        "refusals": _refusals(refusals_input),
        "spend": _spend(spend_input),
        "interpretation": "development owner summary; refusal rank is demand evidence, not Level 5 approval",
    }


def _metric(value):
    return "UNMEASURED" if value is None else f"{value:.3f}"


def render(report):
    lines = [
        "# Graphite Stage A — owner one-pager",
        "",
        "**Development summary only.** No score-rule change or Level 5 approval.",
        f"Alignment input: `{report['alignment']['input_sha256']}`; refusal summary: `{report['refusals']['summary_sha256']}`; spend summary: `{report['spend']['summary_sha256']}`.",
        "",
        "## Scores and decision value",
        "",
        "| Cohort | Members | v2 τ/ρ | v3 τ/ρ | Practice→exam τ/ρ |",
        "| --- | ---: | --- | --- | --- |",
    ]
    for cohort in report["alignment"]["cohorts"]:
        name = f"L{cohort['cohort']['level']} / pool {cohort['cohort']['pool_version']} / {cohort['cohort']['device_class']}"
        v2 = cohort["v2"]
        v3 = cohort["v3"]
        practice = cohort["practice_vs_exam"]

        def pair(metrics):
            return (
                "UNMEASURED"
                if metrics is None
                else _metric(metrics["tau_b"]) + "/" + _metric(metrics["rho"])
            )

        lines.append(
            f"| {name} | {cohort['planned_members']} ({cohort['status']}) | "
            f"{pair(None if v2 is None else v2['alignment'])} | "
            f"{pair(None if v3 is None else v3['alignment'])} | "
            f"{pair(None if practice is None else practice['rank_association'])} |"
        )
        if practice is not None:
            recipes = practice["per_recipe"]
            exam_means = [
                row["mean_exam_score"]
                for row in recipes
                if row["mean_exam_score"] is not None
            ]
            lines.append("")
            lines.append(
                f"Practice/exam lower-is-better recipe means: "
                f"practice median {_metric(statistics.median([r['mean_practice_score'] for r in recipes])) if recipes else 'UNMEASURED'}, "
                f"exam median {_metric(statistics.median(exam_means)) if exam_means and len(exam_means) == len(recipes) else 'UNMEASURED'} "
                f"({practice['rank_association_status']})."
            )
        if v2 is not None:
            band = v2["bootstrap_95_descriptive"]["tau_b"]
            lines.append(
                f"V2 τ descriptive 95% recipe-bootstrap band: "
                f"[{_metric(band['low'])}, {_metric(band['high'])}] "
                f"({band['defined_draws']} defined draws)."
            )
        if v3 is not None:
            band = v3["bootstrap_95_descriptive"]["tau_b"]
            lines.append(
                f"V3 τ descriptive 95% recipe-bootstrap band: "
                f"[{_metric(band['low'])}, {_metric(band['high'])}] "
                f"({band['defined_draws']} defined draws)."
            )
        if v3 is not None:
            terms = v3["term_alignment"]
            lines.append("")
            lines.append(
                f"  - V3 terms τ/ρ: accuracy {pair(terms['accuracy_a'])}; "
                f"Q3 {pair(terms['q3_q'])}; G-FEAS {pair(terms['g_feas_lower_better'])}. "
                f"Divergent members: {len(v3['divergent_members'])}; v2: {len(v2['divergent_members'])}."
            )
        if cohort["unmeasured_members"]:
            lines.append("")
            lines.append(
                f"  - Missing member inputs: {len(cohort['unmeasured_members'])}; see aggregate JSON for causes."
            )
    lines += [
        "",
        "## Refused capabilities for Level 5 investigation",
        "",
        f"{report['refusals']['total_refusals']} refusal events across levels {report['refusals']['levels_covered']}; producer completeness claim: {report['refusals']['complete_claim']}.",
        "| Rank | Capability | Level | Refusal code | Events |",
        "| ---: | --- | ---: | --- | ---: |",
    ]
    for rank, row in enumerate(
        report["refusals"]["ranked_level5_investigation_candidates"][:10], 1
    ):
        lines.append(
            f"| {rank} | `{row['capability_id']}` | {row['level']} | `{row['refusal_code']}` | {row['count']} |"
        )
    lines += [
        "",
        "## Spend against committed caps",
        "",
        "| Grant | Observed USD | Cap USD | State |",
        "| --- | ---: | ---: | --- |",
    ]
    for grant in report["spend"]["grants"]:
        marker = " OVER CAP" if grant["over_cap"] else ""
        lines.append(
            f"| `{grant['grant_id']}` | {grant['observed_spend_usd'] or 'UNMEASURED'} | {grant['cap_usd']} | {grant['state']}{marker} |"
        )
    lines += [
        "",
        "**Owner decision:** HUMAN_INPUT. Compare cohorts only within their registered identities. Bootstrap bands and per-recipe practice/exam rows remain in the #942 aggregate JSON. Refusal counts are demand signals, not evidence that a capability is safe or ready. The interim refusal summary's source digest and completeness claim are producer assertions, not authenticated by this script.",
    ]
    return "\n".join(lines) + "\n"


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--alignment-input", required=True, type=Path)
    parser.add_argument("--refusals", required=True, type=Path)
    parser.add_argument("--spend", required=True, type=Path)
    parser.add_argument("--markdown-out", required=True, type=Path)
    parser.add_argument("--json-out", required=True, type=Path)
    parser.add_argument("--draws", type=int, default=500)
    parser.add_argument("--seed", type=int, default=20261009)
    args = parser.parse_args(argv)
    result = build(
        args.alignment_input,
        args.refusals,
        args.spend,
        draws=args.draws,
        seed=args.seed,
    )
    args.markdown_out.write_text(render(result), encoding="utf-8")
    args.json_out.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    main()
