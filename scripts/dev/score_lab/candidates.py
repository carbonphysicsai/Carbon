"""Adapt the Validator's read-only Score Lab candidates to toy panels.

The candidate file stays outside the repository. Its Python functions are
trusted developer input, like ``--function``; they receive score-side data
only. Battery registry rules use the exact scorer on public replay instead.
"""

from __future__ import annotations

import hashlib
import importlib.util
from pathlib import Path

from .core import LabRefused, registry_rule


def load(path):
    path = Path(path)
    spec = importlib.util.spec_from_file_location("score_lab_candidates", path)
    if spec is None or spec.loader is None:
        raise LabRefused("candidates_unavailable")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    rules = getattr(module, "RULES", None)
    if not isinstance(rules, dict) or len(rules) != 10:
        raise LabRefused("candidates_contract_mismatch")
    return rules, hashlib.sha256(path.read_bytes()).hexdigest()


def adapt_synthetic(panel, member):
    """Convert only the synthetic scoring half to the candidate contract."""
    if panel["scope"] != "SYNTHETIC_DEVELOPMENT":
        raise LabRefused("candidate_proxy_requires_synthetic_panel")
    references = {}
    predictions = {}
    questions = {}
    probes = []
    for qid, question in panel["score_questions"].items():
        references[qid] = {
            aid: {
                "status": ref["status"],
                "objective": ref["objective"],
                "margins": {
                    "coupled_a": ref["margins"][0],
                    "coupled_b": ref["margins"][1],
                },
            }
            for aid, ref in question["actions"].items()
        }
        predictions[qid] = {
            aid: {
                "objective": pred["objective"],
                "margins": {
                    "coupled_a": pred["margins"][0],
                    "coupled_b": pred["margins"][1],
                },
            }
            for aid, pred in member["score_predictions"][qid].items()
        }
        questions[qid] = {
            "fallback": question["fallback"],
            "conditions": 1,
            "u": 1.0,  # explicit toy benefit unit, not a Challenge registration
            "actions": sorted(question["actions"]),
        }
        ids = questions[qid]["actions"]
        lo, hi = ids[0], ids[-1]
        delta = references[qid][hi]["objective"] - references[qid][lo]["objective"]
        if delta:
            probes.append((qid, lo, hi, 1 if delta > 0 else -1))
    metadata = {
        "sense": "min",
        "questions": questions,
        "scale": {"objective": 1.0, "coupled_a": 1.0, "coupled_b": 1.0},
        "near_band": 0.12,
        "probes": probes,
        "knobs": {"optimum_band": 0.12, "miss_penalty": 1.0, "top_fraction": 0.2},
    }
    return predictions, references, metadata


def rule_from_spec(
    candidate_id,
    spec,
    *,
    path_digest,
    panel,
    registry_v5=None,
    registry_v9=None,
    registry_v10=None,
):
    """Use exact battery registry code on real data; toy proxies otherwise."""
    if panel["scope"] == "PUBLIC_DEVELOPMENT":
        registry = (
            registry_v5
            if candidate_id.startswith("INFORCE-")
            else (
                registry_v9
                if candidate_id.startswith("V9-")
                else registry_v10 if candidate_id.startswith("V10-") else None
            )
        )
        if registry is None or spec.get("tier2_registry_id") is None:
            return None
        # The caller supplies the exact registered id, not the proxy's prose
        # suffix. A missing id returns an explicit unmeasured result.
        registered_id = spec["tier2_registry_id"].split(" (registry ", 1)[0]
        if candidate_id == "INFORCE-G-FEAS/A-Q>@0.05":
            # Registry v5 stores the cutoff inside the candidate gate, not
            # in the id. Keep the source id exact rather than guessing one.
            registered_id = "G-FEAS/A-Q>"
        try:
            return registry_rule(registry, registered_id)
        except LabRefused:
            return None

    candidate = spec.get("rule")
    if not callable(candidate):
        raise LabRefused("candidate_rule_missing")

    def score(predictions, references, metadata):
        # analyze passes the scoring references and member predictions only.
        synthetic_panel = {"scope": panel["scope"], "score_questions": references}
        synthetic_member = {"score_predictions": predictions}
        cp, cr, cm = adapt_synthetic(synthetic_panel, synthetic_member)
        result = candidate(cp, cr, cm)
        if not isinstance(result, dict) or result.get("gate") not in (
            None,
            "PASS",
            "FAIL",
        ):
            raise LabRefused("candidate_result_malformed")
        if result.get("score") is None:
            return None
        return {"score": result["score"], "admissible": result["gate"] != "FAIL"}

    score.rule_identity = {
        "kind": "validator_candidate_toy_proxy",
        "candidate": candidate_id,
        "candidates_sha256": path_digest,
    }
    return score
