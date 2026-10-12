"""Public EV4 Level 1 decision study and readiness Q1 handoff.

No solver or trainer is invoked. Prediction bundles and score records are
inputs from the Graphite Test executor. Missing evidence is a refusal.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import math
from pathlib import Path

from carbon.battery.value import contract as ev
from carbon.battery.value import level_compile
from carbon.battery.value import panel as pn
from carbon.battery.value.experiment import Experiment
from carbon.challenge_pipeline.readiness import q1

ROOT = Path(__file__).resolve().parents[3]
CONTRACT = ROOT / "carbon/battery/value/contracts/ev4-dev-proof-l1-v1.json"
REFERENCE = (
    ROOT / "docs/development/evidence/ev4-2026-10-01/decision-references.jsonl.gz"
)
REFERENCE_SHA = "sha256:" + hashlib.sha256(REFERENCE.read_bytes()).hexdigest()
CHALLENGE = pn.CHALLENGE_ID
MEMBERS = "ev4-dev-proof-l1"
ABSTAIN = {"CORRECT_ABSTENTION", "MISSED_OPPORTUNITY", "ABSTENTION_UNRESOLVED"}
UNRESOLVED = {"SELECTED_UNRESOLVED", "ABSTENTION_UNRESOLVED", "REFERENCE_UNAVAILABLE"}


def registration():
    """Digest every exact member and both source files before freeze."""
    return ev.proof_l1_registration()


def estimate():
    """Planning estimate, not measured L1 cost; based on existing CPU priors."""
    from scripts.dev.battery.score_proof_run import estimate_seconds

    rows = pn.members(MEMBERS)
    by_level = {0: 0.0, 1: 0.0}
    levels = pn.levels(MEMBERS)
    for member, _label, strategy, _seed in rows:
        by_level[levels[member][0]] += estimate_seconds(strategy)
    return {
        "members": len(rows),
        "level_0": sum(levels[m][0] == 0 for m, *_ in rows),
        "level_1": sum(levels[m][0] == 1 for m, *_ in rows),
        "rebuild_cpu_hours_planning_only": round(sum(by_level.values()) / 3600, 3),
        "level_0_cpu_hours": round(by_level[0] / 3600, 3),
        "level_1_cpu_hours_level_0_proxy": round(by_level[1] / 3600, 3),
        "prediction_and_import_cpu_hours": "UNMEASURED",
        "peak_memory_gb": "UNMEASURED",
    }


def public_ev4_scoring_set(repository):
    """Only the digest-pinned public EV4 references, never the old private role."""
    import numpy as np

    from carbon.battery import exam
    from carbon.battery.calibration import SHAPES, frozen_calibration
    from carbon.battery.challenge import PublicMaterial

    if Path(repository).resolve() != ROOT.resolve():
        raise ValueError("public EV4 scoring set requires this repository")
    body = REFERENCE.read_bytes()
    if "sha256:" + hashlib.sha256(body).hexdigest() != REFERENCE_SHA:
        raise ValueError("public EV4 reference digest changed")
    refs = {
        record["case_id"]: record
        for line in gzip.decompress(body).splitlines()
        if line.strip()
        for record in (json.loads(line),)
        if not record.get("refined")
    }
    material = PublicMaterial.load(repository)
    ocv = {
        case: float(np.interp(row["inputs"]["soc0"], material.ocv_soc, material.ocv_v))
        for case, row in refs.items()
        if row.get("inputs")
    }
    tol, scales = frozen_calibration(repository)
    store = exam.CaseStore(refs, ocv, tol, scales, SHAPES, {})
    return (
        store,
        sorted(refs),
        {
            "path": str(REFERENCE.relative_to(ROOT)).replace("\\", "/"),
            "sha256": REFERENCE_SHA,
            "cases": len(refs),
            "classification": "PUBLIC_SYNTHETIC_DEVELOPMENT",
        },
    )


def _require_inputs(predictions: Path, scores: Path):
    expected = {m for m, *_ in pn.members(MEMBERS)}
    supplied = {p.name[: -len(".json.gz")] for p in predictions.glob("*.json.gz")}
    if supplied != expected:
        raise ValueError(
            f"prediction bundles: missing {sorted(expected - supplied)}, "
            f"unexpected {sorted(supplied - expected)}"
        )
    document = json.loads(scores.read_bytes())
    if (
        document.get("classification") != "PUBLIC_SYNTHETIC_DEVELOPMENT"
        or document.get("score_direction") != "higher_is_better"
        or document.get("scoring_rule_digest") != q1.current_rule_digest(CHALLENGE)
    ):
        raise ValueError("score records lack current public rule provenance")
    rows = document["members"]
    if set(rows) != expected:
        raise ValueError(
            f"score records: missing {sorted(expected - set(rows))}, "
            f"unexpected {sorted(set(rows) - expected)}"
        )
    if any(
        type(row) is not dict
        or type(row.get("eligible")) is not bool
        or "score" not in row
        for row in rows.values()
    ):
        raise ValueError("score records require eligible and score per member")
    return rows


def _outcome(entry):
    outcome = entry["outcome"]
    if outcome["selected"] is not None:
        return outcome["selected"]
    if outcome["kind"] in ABSTAIN:
        return "ABSTAIN"
    if outcome["kind"] == "MODEL_OUTPUT_MISSING":
        return "MISSING_OUTPUT"
    raise ValueError(f"unmapped outcome {outcome['kind']}")


def q1_panel(results, scores):
    """Map the experiment to Q1 on a common resolved development mask."""
    expected = {m for m, *_ in pn.members(MEMBERS)}
    members = results["summary"]["members"]
    decisions = results["decisions"]
    if not expected.issubset(members) or not expected.issubset(decisions):
        raise ValueError("experiment is missing registered members")
    scenarios = {
        name
        for name, row in results["references"].items()
        if row["split"] == "development"
    }
    resolved = {
        name
        for name in scenarios
        if all(
            name in decisions[member]
            and decisions[member][name]["outcome"]["kind"] not in UNRESOLVED
            for member in expected
        )
    }
    if not resolved:
        raise ValueError("no common resolved development scenario")
    out = {}
    digests = registration()["member_sha256"]
    for member in sorted(expected):
        score = scores[member]["score"]
        if score is not None and (
            not isinstance(score, (int, float))
            or isinstance(score, bool)
            or not math.isfinite(score)
        ):
            raise ValueError(f"non-numeric score for {member}")
        summary = members[member]
        losses = [
            decisions[member][name]["outcome"].get("decision_loss")
            for name in sorted(resolved)
        ]
        if any(
            not isinstance(loss, (int, float))
            or isinstance(loss, bool)
            or not math.isfinite(loss)
            for loss in losses
        ):
            raise ValueError(f"unscored resolved decision for {member}")
        value = sum(losses) / len(losses)
        out[member] = {
            "score": score,
            "value": value,
            "eligible": (
                bool(summary["eligible"])
                and bool(scores[member]["eligible"])
                and score is not None
            ),
            "recipe": digests[member],
            "kind": summary["kind"],
            "decision_outcome": {
                name: _outcome(decisions[member][name]) for name in sorted(resolved)
            },
        }
    return {
        "reference": {
            "provenance": "EV4_REFERENCE",
            "ref": str(REFERENCE.relative_to(ROOT)).replace("\\", "/"),
        },
        "decision_study": (
            f"{CONTRACT.relative_to(ROOT).as_posix()}; "
            f"common resolved EV4 development scenarios {len(resolved)}/{len(scenarios)}; "
            f"reference {REFERENCE_SHA}; experiment {results.get('manifest_digest', 'UNRECORDED')}"
        ),
        "members": out,
    }


def run(root: Path, predictions: Path, scores: Path, panel_out: Path, report_out: Path):
    """Import public evidence, evaluate, then write only the L1 Q1 report."""
    if report_out.name != "q1_report.L1.json":
        raise ValueError("the only permitted readiness output is q1_report.L1.json")
    rows = _require_inputs(predictions, scores)
    contract, _digest = ev.load(CONTRACT)
    if contract.get("public_reference_sha256") != REFERENCE_SHA:
        raise ValueError("public EV4 reference digest changed")
    experiment = Experiment(
        root,
        repository=ROOT,
        level_compiler=level_compile,
        scoring_set=public_ev4_scoring_set,
    )
    with experiment.lock():
        experiment.freeze(CONTRACT)
        reference_input = root / "public-ev4-references.jsonl"
        if not reference_input.exists():
            reference_input.write_bytes(gzip.decompress(REFERENCE.read_bytes()))
        experiment.import_references(reference_input)
        experiment.import_predictions(predictions)
        results = experiment.evaluate()
    panel = q1_panel(results, rows)
    panel_out.parent.mkdir(parents=True, exist_ok=True)
    panel_out.write_text(
        json.dumps(panel, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    if (
        q1.main(
            [
                "build",
                "--challenge",
                CHALLENGE,
                "--level",
                "1",
                "--panel",
                str(panel_out),
                "--out",
                str(report_out),
            ]
        )
        != 0
    ):
        raise ValueError("L1 Q1 build refused")
    return {"report": str(report_out), "members": len(panel["members"])}


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="python -m scripts.dev.battery.l1_decision_q1"
    )
    parser.add_argument("--root", type=Path)
    parser.add_argument("--predictions", type=Path)
    parser.add_argument("--scores", type=Path)
    parser.add_argument("--panel-out", type=Path)
    parser.add_argument("--report-out", type=Path)
    args = parser.parse_args(argv)
    print(json.dumps({"estimate": estimate()}, sort_keys=True), flush=True)
    if args.root is None:
        return 0
    if any(
        x is None
        for x in (args.predictions, args.scores, args.panel_out, args.report_out)
    ):
        parser.error("run requires predictions, scores, panel-out and report-out")
    try:
        result = run(
            args.root, args.predictions, args.scores, args.panel_out, args.report_out
        )
    except (ValueError, ev.ContractError) as refused:
        parser.exit(2, f"REFUSED: {refused}\n")
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
