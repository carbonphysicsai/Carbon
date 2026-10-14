"""Read-only evidence readiness and score-family capacity diagnostics.

Readiness validates a registered research plan's available public receipts. It
does not approve a scientific contract, execute collection/fitting, or read a
final holdout. The manifest records supplier-owned gaps without guessing them.
"""

from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import math
import statistics
from pathlib import Path

from carbon.battery.value import score_proof

from . import physics
from .core import LabRefused, canonical_sha

SCHEMA = "carbon.dev.score-lab-finish-line.v1"
PUBLIC_ROOTS = (
    "Business/research/",
    "docs/development/evidence/",
    "docs/development/challenge_pipeline/question-laws/",
    "scripts/dev/score_lab/",
)
REQUIRED_STAGES = frozenset(
    {
        "job_contract",
        "cohort",
        "paired_score_inputs",
        "references",
        "value_traces",
        "matched_controls",
        "interactions",
        "weight_search",
        "measurement",
        "goodhart",
        "competition",
        "budget",
        "independent_validation",
        "final_holdout",
        "real_replay",
    }
)


def _pointer(value, pointer):
    for key in pointer:
        if isinstance(value, dict) or isinstance(value, list) and type(key) is int:
            value = value[key]
        else:
            raise KeyError(key)
    return value


def _predicate(actual, check):
    op = check["op"]
    expected = check.get("expected")
    if op == "equals":
        return type(actual) is type(expected) and actual == expected
    if op == "length_at_least":
        return (
            type(expected) is int
            and expected > 0
            and isinstance(actual, (list, dict))
            and len(actual) >= expected
        )
    if op == "nonempty":

        def present(value):
            if value is None:
                return False
            if isinstance(value, str):
                tag = value.strip().upper().split(":", 1)[0]
                return bool(value.strip()) and tag not in {
                    "HUMAN_INPUT",
                    "UNKNOWN",
                    "UNMEASURED",
                    "MISSING",
                    "TBD",
                }
            if isinstance(value, dict):
                return bool(value) and all(present(v) for v in value.values())
            if isinstance(value, list):
                return bool(value) and all(present(v) for v in value)
            return (
                type(value) is bool
                or type(value) in (int, float)
                and math.isfinite(value)
            )

        return isinstance(actual, (str, list, dict)) and present(actual)
    if op == "finite":
        return type(actual) in (int, float) and math.isfinite(actual)
    raise LabRefused("readiness_predicate_unknown")


def _artifact(root, spec):
    relative = spec.get("path")
    if (
        type(relative) is not str
        or "\\" in relative
        or not relative.startswith(PUBLIC_ROOTS)
        or ".." in Path(relative).parts
    ):
        raise LabRefused("readiness_public_receipt_path")
    # Only small JSON receipts are read. Code and raw model/reference bundles,
    # arbitrary external paths, and custody-only holdout content are not inputs.
    path = (root / relative).resolve()
    if not path.is_relative_to(root) or path.suffix != ".json":
        raise LabRefused("readiness_public_receipt_path")
    if not path.exists():
        return None, "MISSING_ARTIFACT"
    if path.stat().st_size > 4 * 1024 * 1024:
        raise LabRefused("readiness_receipt_size")
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    if hashlib.sha256(raw).hexdigest() != spec["sha256"]:
        return None, "ARTIFACT_DIGEST_MISMATCH"
    value = json.loads(raw)
    if value.get("schema") != spec["schema"]:
        return None, "ARTIFACT_SCHEMA_MISMATCH"
    return value, None


def assess(manifest, root):
    """No supplied readiness flags are trusted; evaluate every bound predicate."""
    root = Path(root).resolve()
    if (
        manifest.get("schema") != SCHEMA
        or manifest.get("scope") != "PUBLIC_AND_SYNTHETIC_DEVELOPMENT"
    ):
        raise LabRefused("readiness_manifest_scope")
    custody = manifest.get("final_holdout", {})
    if set(custody) != {"custodian", "commitment_sha256", "reveal_policy"}:
        raise LabRefused("readiness_custody_only_no_content")
    digest = custody["commitment_sha256"]
    if (
        type(digest) is not str
        or len(digest) != 64
        or any(c not in "0123456789abcdef" for c in digest)
    ):
        raise LabRefused("readiness_holdout_commitment")
    artifacts = {}
    for name, spec in manifest["artifacts"].items():
        artifacts[name] = _artifact(root, spec)
    stages = manifest.get("stages", [])
    ids = [stage["id"] for stage in stages]
    if set(ids) != REQUIRED_STAGES or len(ids) != len(set(ids)):
        raise LabRefused("readiness_stage_identity")
    results = {}
    for stage in stages:
        if not all(
            stage.get(key)
            for key in (
                "owner",
                "owner_ticket",
                "minimum_action",
                "validation",
                "readiness_predicate",
            )
        ):
            raise LabRefused("readiness_unowned_gap")
        dependencies = stage.get("depends_on", [])
        if any(dep not in results for dep in dependencies):
            raise LabRefused("readiness_dependency_order")
        blockers = [
            "dependency:" + dep for dep in dependencies if not results[dep]["ready"]
        ]
        checked = []
        if not stage.get("checks"):
            blockers.append("NO_REGISTERED_EVIDENCE_PREDICATE")
        for check in stage.get("checks", []):
            source = check.get("artifact")
            actual, reason = None, None
            if source is None:
                reason = "HUMAN_INPUT_OR_SUPPLIER_ARTIFACT_REQUIRED"
            elif source not in artifacts:
                raise LabRefused("readiness_unbound_artifact")
            else:
                data, reason = artifacts[source]
                if reason is None:
                    try:
                        actual = _pointer(data, check["pointer"])
                    except (KeyError, IndexError):
                        reason = "REQUIRED_FIELD_MISSING"
                    if reason is None and not _predicate(actual, check):
                        reason = "EVIDENCE_PREDICATE_NOT_MET"
            checked.append(
                {
                    "artifact": source,
                    "pointer": check.get("pointer"),
                    "observed": actual,
                    "predicate": {
                        key: check[key] for key in ("op", "expected") if key in check
                    },
                    "reason": reason,
                }
            )
            if reason:
                blockers.append(reason)
        results[stage["id"]] = {
            "ready": not blockers,
            "status": "EVIDENCE_PRESENT" if not blockers else "BLOCKED",
            "owner": stage["owner"],
            "owner_ticket": stage["owner_ticket"],
            "minimum_action": stage["minimum_action"],
            "checks": checked,
            "blockers": blockers,
            "execution": stage.get("execution"),
        }
    return {
        "schema": "carbon.dev.score-lab-finish-line-status.v1",
        "manifest_sha256": canonical_sha(manifest),
        "stages": results,
        "status": (
            "REGISTERED_RESEARCH_INPUTS_PRESENT"
            if all(r["ready"] for r in results.values())
            else "INSUFFICIENT_EVIDENCE"
        ),
        "scientific_qualification": False,
        "rule_selection": None,
        "final_holdout_content_read": False,
        "interpretation": "Receipt predicates only; scientific adequacy and owner-reserved adoption are not conferred.",
    }


def capacity_witnesses(features, values):
    """Counterexamples for any coordinatewise nondecreasing feature-only score.

    Features must all be oriented higher-is-better and compared at identical
    eligibility. This is a necessary representational test, not a fitted upper
    bound on tau; extra features, gates or nonmonotone families are outside it.
    """
    if set(features) != set(values) or len(features) < 2:
        raise LabRefused("capacity_members")
    dimensions = {len(row) for row in features.values()}
    if (
        len(dimensions) != 1
        or next(iter(dimensions)) < 1
        or any(
            type(v) not in (int, float) or not math.isfinite(v)
            for row in features.values()
            for v in row
        )
        or any(
            type(v) not in (int, float) or not math.isfinite(v) for v in values.values()
        )
    ):
        raise LabRefused("capacity_finite_complete_features")
    aliases, reversals = [], []
    for a, b in itertools.combinations(sorted(features), 2):
        if values[a] == values[b]:
            continue
        better, worse = (a, b) if values[a] > values[b] else (b, a)
        pair = {
            "higher_value_member": better,
            "lower_value_member": worse,
            "value_difference": values[better] - values[worse],
        }
        if features[a] == features[b]:
            aliases.append(pair)
        elif all(
            x >= y for x, y in zip(features[worse], features[better], strict=True)
        ):
            reversals.append(pair)
    return {
        "schema": "carbon.dev.score-lab-capacity-witnesses.v1",
        "members": len(features),
        "feature_count": next(iter(dimensions)),
        "exact_feature_aliases": aliases,
        "monotone_order_reversals": reversals,
        "fitted": False,
        "claim": "Witnesses prevent perfect value ordering in this feature-only monotone family; no witnesses does not prove capacity.",
    }


def measurement_ceiling(losses, *, bootstrap, seed):
    if type(bootstrap) is not int or bootstrap < 1 or type(seed) is not int or seed < 0:
        raise LabRefused("ceiling_explicit_bootstrap")
    if (
        not losses
        or len({len(row) for row in losses}) != 1
        or any(
            type(v) not in (int, float) or not math.isfinite(v)
            for row in losses
            for v in row
        )
    ):
        raise LabRefused("ceiling_common_complete_mask")
    return {
        "estimate": score_proof.value_ceiling(losses, n_boot=bootstrap, seed=seed),
        "interpretation": "SCORE-CEILING-01 reliability diagnostic with its Spearman-Brown/bivariate-normal assumptions; not a universal mathematical tau bound or score-family capacity proof.",
    }


def combined_diagnostics(registration, baseline_cells, *, seed):
    """Replay fixed analytic value; inspect A/Q capacity without fitting a rule."""
    expected = set(range(len(registration["profiles"])))
    supplied = [cell["profile_index"] for cell in baseline_cells]
    if len(supplied) != len(set(supplied)) or set(supplied) != expected:
        raise LabRefused("combined_diagnostic_profile_coverage")
    rows = []
    for cell in baseline_cells:
        if (
            cell["plan_sha256"] != canonical_sha(registration)
            or cell["component_index"] != 0
        ):
            raise LabRefused("combined_diagnostic_binding")
        config = registration["profiles"][cell["profile_index"]]["config"]
        panel = physics.build(config)
        if canonical_sha(panel) != cell["panel_sha256"]:
            raise LabRefused("combined_diagnostic_panel_identity")
        off = {
            row["candidate"]: row for row in cell["rows"] if row["physics_index"] == 0
        }
        primary = [m["id"] for m in panel["members"] if m["kind"] == "MODEL"]
        features = {}
        for member in primary:
            pair = [
                off[f"TOY-ABLATION/{leg}/NO-GATE"]["scores"][member]
                for leg in ("A", "Q")
            ]
            if any(p is None or not p["admissible"] or p["tier"] != 0 for p in pair):
                features = None
                break
            features[member] = [p["score"] for p in pair]
        for scope in registration["value_scopes"]:
            view = physics.value_view(
                panel, scope, config["neighbourhood"]["value_weight"]
            )
            common = sorted(
                q
                for q in view["value_questions"]
                if all(m["value_losses"][q] is not None for m in view["members"])
            )
            saved = off["TOY-ABLATION/A/NO-GATE"]["outcomes"][scope]
            if not common or features is None:
                rows.append(
                    {
                        "profile": cell["profile_index"],
                        "scope": scope,
                        "status": "INSUFFICIENT_EVIDENCE",
                        "reason": "no_common_mask_or_eligible_features",
                        "measurement_ceiling": None,
                        "monotone_a_q_capacity": None,
                    }
                )
                continue
            if canonical_sha(common) != saved.get("common_mask_sha256"):
                raise LabRefused("combined_diagnostic_mask_identity")
            losses = [
                [m["value_losses"][q] for q in common]
                for m in view["members"]
                if m["kind"] == "MODEL"
            ]
            values = {
                name: -statistics.fmean(row)
                for name, row in zip(primary, losses, strict=True)
            }
            if any(
                values[name] != saved["value_by_member"].get(name) for name in primary
            ):
                raise LabRefused("combined_diagnostic_value_identity")
            rows.append(
                {
                    "profile": cell["profile_index"],
                    "scope": scope,
                    "features": "A and Q toy scores, existing neighbourhood blend, physics OFF, no gates/components",
                    "measurement_ceiling": measurement_ceiling(
                        losses, bootstrap=config["bootstrap"], seed=seed
                    ),
                    "monotone_a_q_capacity": capacity_witnesses(features, values),
                }
            )
    return {
        "schema": "carbon.dev.score-lab-combined-diagnostics.v1",
        "scope": "SYNTHETIC_DEVELOPMENT",
        "plan_sha256": canonical_sha(registration),
        "bootstrap_seed": seed,
        "rows": rows,
        "selection": None,
        "direct_v2_utility": "Separate objective family; must match buyer job, cost and abstention/unsafe semantics, not assumed identical here.",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    result = assess(json.loads(args.manifest.read_text(encoding="utf-8")), args.root)
    args.out.write_bytes(
        (json.dumps(result, indent=2, allow_nan=False) + "\n").encode()
    )
    print(result["status"])
    return 0 if result["status"] == "REGISTERED_RESEARCH_INPUTS_PRESENT" else 2


if __name__ == "__main__":
    raise SystemExit(main())
