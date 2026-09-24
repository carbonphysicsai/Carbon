"""Exam machinery for the exam-design campaign: pools, rotation, final comparison.

Numpy-only and challenge-agnostic above the per-case evaluator, so the same
pool/rotation/comparison code runs on the battery challenge and on replayed
Burgers development evidence.

Concepts, as the campaign tests them:

* **Prediction bank** - a stored model's predictions keyed by case. A pool
  change never retrains anything: a model already in the bank is *inferred* on
  an incoming batch and the new predictions are appended.
* **Screening pool** - ``n_active`` (three) active batches. Every screening
  score is over the whole active pool and is recorded with ``pool_version``.
* **Rotation** - after ``rotate_after`` admitted submissions, the oldest batch
  retires (becomes public) and the next prepared batch enters. Retired data
  enters official TRAIN only through a named ``TrainVersions.publish`` call.
* **Final comparison** - a frozen rule over paired per-case differences on
  fresh cases, with five possible outcomes; none is forced.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

import numpy as np

from scripts.dev.exam_design import gates, scoring

IMPROVEMENT, REGRESSION, TRADE_OFF, NO_IMPROVEMENT, INSUFFICIENT = (
    "IMPROVEMENT", "REGRESSION", "TRADE_OFF", "NO_IMPROVEMENT", "INSUFFICIENT_EVIDENCE")


@dataclass
class CaseStore:
    """Reference records and the per-case context gates need."""

    refs: dict[str, dict]
    ocv: dict[str, float]
    tol: gates.Tolerances
    scales: dict
    shapes: dict
    twins: dict[str, str] = field(default_factory=dict)  # duplicate case id -> original case id

    def important(self, cid: str) -> bool:
        r = self.refs[cid]
        return r.get("status") == "OK" and scoring.is_important(r)


def evaluate(preds: dict[str, dict | None], case_ids: list[str], store: CaseStore,
             infra_failed: set[str] | None = None) -> tuple[list[dict], dict]:
    """Gate and score one model on ``case_ids`` from stored predictions."""
    infra_failed = infra_failed or set()
    inverse = {}
    for dup, orig in store.twins.items():
        inverse.setdefault(orig, dup)
    rows = []
    for cid in case_ids:
        ref = store.refs[cid]
        twin = store.twins.get(cid) or inverse.get(cid)
        twin_pred = preds.get(twin) if twin and twin in case_ids else None
        row = gates.evaluate_case(preds.get(cid), ref, ref.get("inputs", {}), store.ocv.get(cid, np.nan), store.tol,
                                  store.shapes, twin_pred=twin_pred, infra_failed=cid in infra_failed)
        row["case_id"] = cid
        if row["state"] == gates.SCORABLE:
            comp = scoring.case_components(preds[cid], ref, store.scales)
            row["components"], row["error"] = comp, scoring.case_error(comp)
            row["important"] = store.important(cid)
        rows.append(row)
    return rows, scoring.aggregate(rows)


class PredictionBank:
    """Stored predictions per model; inference on demand, never retraining."""

    def __init__(self, predictors: dict[str, Callable[[list[str]], dict[str, dict]]] | None = None):
        self.preds: dict[str, dict[str, dict]] = {}
        self.predictors = predictors or {}
        self.inference_calls: dict[str, int] = {}
        self.inferred_cases: dict[str, int] = {}

    def add(self, model_id: str, preds: dict[str, dict]) -> None:
        self.preds.setdefault(model_id, {}).update(preds)

    def ensure(self, model_id: str, case_ids: list[str]) -> dict[str, dict]:
        have = self.preds.setdefault(model_id, {})
        missing = [c for c in case_ids if c not in have]
        if missing:
            if model_id not in self.predictors:
                raise KeyError(f"{model_id}: no stored predictions for {len(missing)} cases and no predictor")
            have.update(self.predictors[model_id](missing))
            self.inference_calls[model_id] = self.inference_calls.get(model_id, 0) + 1
            self.inferred_cases[model_id] = self.inferred_cases.get(model_id, 0) + len(missing)
        return {c: have[c] for c in case_ids}


class TrainVersions:
    """Official TRAIN changes only by a named version update."""

    def __init__(self, version: str, case_ids: list[str]):
        self.versions = {version: list(case_ids)}
        self.current = version

    def publish(self, new_version: str, added_case_ids: list[str], reason: str) -> None:
        if new_version in self.versions:
            raise ValueError(f"TRAIN version {new_version} already exists")
        self.versions[new_version] = self.versions[self.current] + list(added_case_ids)
        self.current = new_version
        self.__dict__.setdefault("log", []).append({"version": new_version, "added": len(added_case_ids), "reason": reason})


@dataclass
class ScreeningPool:
    batches: list[list[str]]          # every prepared batch, in entry order
    rotate_after: int                 # admitted submissions per rotation
    n_active: int = 3
    batch_size: int | None = None     # nested prefix of each batch, if smaller
    _next: int = 0
    pool_version: int = 0
    admitted_since_rotation: int = 0
    retired: list[int] = field(default_factory=list)
    history: list[dict] = field(default_factory=list)

    def __post_init__(self):
        if len(self.batches) < self.n_active:
            raise ValueError("not enough batches to fill the active pool")
        self.active = list(range(self.n_active))
        self._next = self.n_active

    def _ids(self, b: int) -> list[str]:
        ids = self.batches[b]
        return ids[: self.batch_size] if self.batch_size else ids

    def active_case_ids(self) -> list[str]:
        return [c for b in self.active for c in self._ids(b)]

    def can_rotate(self) -> bool:
        return self._next < len(self.batches)

    def score(self, model_id: str, bank: PredictionBank, store: CaseStore) -> dict:
        ids = self.active_case_ids()
        _, agg = evaluate(bank.ensure(model_id, ids), ids, store)
        rec = {"model_id": model_id, "pool_version": self.pool_version, "active_batches": list(self.active), **agg}
        self.history.append(rec)
        self.admitted_since_rotation += 1
        if self.admitted_since_rotation >= self.rotate_after and self.can_rotate():
            self.rotate()
        return rec

    def rotate(self) -> int:
        old = self.active.pop(0)
        self.retired.append(old)
        self.active.append(self._next)
        self._next += 1
        self.pool_version += 1
        self.admitted_since_rotation = 0
        return old


@dataclass(frozen=True)
class ComparisonRule:
    """Frozen before final inputs reach prediction workers."""

    equivalence_margin: float  # relative to the incumbent's mean case error
    n_min: int = 30
    n_boot: int = 4000
    alpha: float = 0.05
    important_min: int = 10
    seed: int = 20260924


def _classify(d: np.ndarray, base: float, rule: ComparisonRule, rng) -> tuple[str, list[float]]:
    boots = rng.choice(d, size=(rule.n_boot, d.size), replace=True).mean(axis=1)
    lo, hi = np.quantile(boots, [rule.alpha / 2, 1 - rule.alpha / 2])
    m = rule.equivalence_margin * base
    # Significant (interval excludes zero) AND practically relevant (mean beyond the margin).
    if hi < 0 and d.mean() < -m:
        c = "better"
    elif lo > 0 and d.mean() > m:
        c = "worse"
    elif lo >= -m and hi <= m:
        c = "equivalent"
    else:
        c = "unresolved"
    return c, [float(lo), float(hi)]


def final_compare(inc_err: dict[str, float], chal_err: dict[str, float], important: dict[str, bool],
                  rule: ComparisonRule, chal_eligible: bool = True, inc_components=None, chal_components=None) -> dict:
    """Paired comparison on the same fresh cases. Positive d means the challenger is worse."""
    rng = np.random.default_rng(rule.seed)
    ids = sorted(set(inc_err) & set(chal_err))
    out = {"n": len(ids), "rule": rule.__dict__}
    if not chal_eligible:
        return out | {"outcome": REGRESSION, "reason": "challenger failed a mandatory gate on final cases"}
    if len(ids) < rule.n_min:
        return out | {"outcome": INSUFFICIENT, "reason": f"{len(ids)} scorable paired cases < {rule.n_min}"}
    d = np.array([chal_err[c] - inc_err[c] for c in ids])
    base = float(np.mean([inc_err[c] for c in ids]))
    overall, ci = _classify(d, base, rule, rng)
    imp_ids = [c for c in ids if important.get(c)]
    if len(imp_ids) >= rule.important_min:
        di = np.array([chal_err[c] - inc_err[c] for c in imp_ids])
        imp, ci_i = _classify(di, float(np.mean([inc_err[c] for c in imp_ids])), rule, rng)
    else:
        imp, ci_i = "insufficient", None
    comp = {}
    if inc_components and chal_components:
        for k in scoring.COMPONENTS:
            dk = np.array([chal_components[c][k] - inc_components[c][k] for c in ids])
            comp[k], _ = _classify(dk, float(np.mean([inc_components[c][k] for c in ids])), rule, rng)
    out |= {"mean_delta": float(d.mean()), "ci": ci, "incumbent_mean": base, "overall": overall,
            "important": imp, "important_ci": ci_i, "n_important": len(imp_ids), "components": comp}
    if overall == "worse":
        o, why = REGRESSION, "overall error significantly higher"
    elif imp == "worse" and overall != "better":
        o, why = REGRESSION, "important region significantly worse without an overall gain"
    elif overall == "better" and imp == "worse":
        o, why = TRADE_OFF, "overall better but important region worse"
    elif overall == "better" and imp == "insufficient":
        o, why = INSUFFICIENT, "overall better but too few important-region cases to show no regression"
    elif overall == "better":
        o, why = IMPROVEMENT, "overall better; important region not worse"
    elif overall == "equivalent" and imp == "better":
        o, why = TRADE_OFF, "overall equivalent; important region better"
    elif overall == "equivalent" and "worse" in comp.values() and "better" in comp.values():
        o, why = TRADE_OFF, "overall equivalent; components move in opposite directions"
    elif overall == "equivalent":
        o, why = NO_IMPROVEMENT, "within the equivalence margin"
    else:
        o, why = INSUFFICIENT, "confidence interval neither excludes nor fits inside the margin"
    # Eligibility, not just reporting: only an IMPROVEMENT may be promoted. A significant important-region
    # regression blocks promotion even when the overall score improved (TRADE_OFF), and "equivalent" is only
    # ever concluded when the whole interval sits inside the margin - never from a failure to detect a
    # difference, which is INSUFFICIENT_EVIDENCE.
    return out | {"outcome": o, "reason": why, "promotable": o == IMPROVEMENT,
                  "regional_block": imp == "worse", "existing_disposition": EXISTING_DISPOSITION[o]}


# The repository's DEVELOPMENT comparison (carbon.scoring.development.compare) names its dispositions
# differently; the adapter reports both so results read against existing machinery.
EXISTING_DISPOSITION = {
    IMPROVEMENT: "ACCEPTED_DEVELOPMENT_IMPROVEMENT",
    REGRESSION: "DEVELOPMENT_REGRESSION",
    TRADE_OFF: "DEVELOPMENT_TRADEOFF",
    NO_IMPROVEMENT: "DEVELOPMENT_EQUIVALENT",
    INSUFFICIENT: "INDETERMINATE_REPLICA_OR_EFFECT_RESOLUTION",
}


def nominate(record: dict, incumbent: dict | None, margin: float) -> tuple[bool, str]:
    """Screening nomination rule: eligible, better overall, and no serious important-region regression.

    ``record``/``incumbent`` are pool score records on the same ``pool_version``.
    """
    if not record["eligible"]:
        return False, "gate failure"
    if incumbent is None:
        return True, "no incumbent"
    if record["pool_version"] != incumbent["pool_version"]:
        return False, "incumbent not scored on this pool version"
    if record["score"] >= incumbent["score"] * (1 - margin):
        return False, "not better than the incumbent by the margin"
    ri, ii = record.get("important_score"), incumbent.get("important_score")
    if ri is not None and ii is not None and ri > ii * (1 + margin):
        return False, "important-region regression beyond the margin"
    return True, "nominated"
