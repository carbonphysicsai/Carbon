"""The battery DEVELOPMENT exam: gates, score, pools and the frozen comparison.

Promoted from `scripts/dev/exam_design/{gates,scoring,exam}.py` (KEEP the
code, WRAP it in the Carbon package). A test replays the campaign's retained
predictions through both and requires identical outputs, and reproduces every
recorded verification decision.

Owner decision OD-2 (OWNER-BATTERY-TESTNET-01) makes the campaign's frozen,
verified rule the **provisional DEVELOPMENT** exam rule for the testnet track:
TRAIN v1 = 400, screening batch 100 with 3 active, rotate after 3 admitted,
5.7 % equivalence margin, only IMPROVEMENT promotable, important-region
regressions block. These are non-paying development values, not production
values, and nothing here is scientifically qualified.

Gates, typed case states and the score, as published in the campaign
(`EXAM_DESIGN_CAMPAIGN_RESULT.md`):

* a case is typed first: ``REFERENCE_INVALID`` (withdrawn for every model),
  ``FAILED_INFRA`` (not scored, retryable, never a scientific failure), else
  the gates decide ``GATE_FAILED`` or ``SCORABLE``;
* mandatory gate failure is never compensated by score;
* the case error is the mean of four TRAIN-scale-normalized components, lower
  is better, bound to this Challenge version and not comparable across
  Challenges.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

import numpy as np

from .challenge import PLATING_BAND_V, T_IMPORTANT_C, is_important

#: OD-2: the provisional DEVELOPMENT exam rule (frozen in the campaign's
#: `freeze.json`, verified on 200 private cases). Not production values.
DEVELOPMENT_RULE = {
    "status": "PROVISIONAL_DEVELOPMENT_NON_PAYING",
    "authority": "OWNER-BATTERY-TESTNET-01 OD-2",
    "train_v1_cases": 400,
    "screening_batch_size": 100,
    "active_batches": 3,
    "rotate_after_admitted": 3,
    "equivalence_margin_rel": 0.056993107446249414,
    "comparison": {"n_min": 30, "n_boot": 4000, "alpha": 0.05, "important_min": 10},
    "important_region": {
        "plating_band_v": PLATING_BAND_V,
        "t_important_c": T_IMPORTANT_C,
    },
    "promotable": ["IMPROVEMENT"],
    "important_region_regression_blocks": True,
}

# --- Gates (scripts/dev/exam_design/gates.py) ---

F32_EPS = float(np.finfo(np.float32).eps)
ULP_FACTOR = (
    32  # the Burgers development rule's initial-condition resolution, 32 float32 ulp
)

PASS, FAIL, NOT_APPLICABLE = "PASS", "FAIL", "NOT_APPLICABLE"
SCORABLE, GATE_FAILED, REFERENCE_INVALID, FAILED_INFRA = (
    "SCORABLE",
    "GATE_FAILED",
    "REFERENCE_INVALID",
    "FAILED_INFRA",
)


@dataclass(frozen=True)
class Gate:
    gate_id: str
    formula: str
    required_outputs: tuple[str, ...]
    applicability: str
    tolerance_rule: str


GATES = (
    Gate(
        "schema_finite",
        "every required output present, of the declared shape, and finite",
        ("voltage_v", "temperature_c", "plating_margin_v", "capacity_ah"),
        "all cases",
        "exact",
    ),
    Gate(
        "initial_voltage",
        "|V_hat(0) - OCV(soc0)| <= tau_v0",
        ("voltage_v",),
        "all cases (cycle 1 begins with a zero-current rest at soc0)",
        "max(2 x max reference |V(0) - OCV| on calibration references, 32 float32 ulp at 4.2 V). The reference's "
        "V(0) is a zero-current rest voltage 0.003-0.44 mV below OCV (internal side-reaction currents), so this "
        "is a bounded-offset boundary probe, not an exact initial-value constraint",
    ),
    Gate(
        "initial_temperature",
        "|T_hat(0) - T_amb| <= tau_t0",
        ("temperature_c",),
        "all cases (initial temperature = ambient)",
        "max(2 x max reference |T(0) - T_amb|, 32 float32 ulp at 40 C)",
    ),
    Gate(
        "voltage_ceiling",
        "max_t V_hat(t) <= V_max + tau_vmax",
        ("voltage_v",),
        "all cases (the cycler holds V <= 4.2 V; this is protocol control, not a safety limit)",
        "max(2 x max reference overshoot of V_max, 32 float32 ulp at 4.2 V)",
    ),
    Gate(
        "voltage_floor",
        "min_t V_hat(t) >= V_min - tau_vmin",
        ("voltage_v",),
        "all cases (discharge stops at 2.5 V)",
        "max(2 x max reference undershoot of V_min, 32 float32 ulp at 2.5 V)",
    ),
    Gate(
        "capacity_bound",
        "0 < Q_hat_k <= Q_bound for every checkpoint k",
        ("capacity_ah",),
        "all cases",
        "Q_bound = min(negative, positive, lithium-inventory capacity) from the parameter set; no tolerance",
    ),
    Gate(
        "paired_repeat",
        "|y_hat(x) - y_hat(x')| <= 32 float32 ulp x max(1, |y|) when x' duplicates x",
        ("voltage_v", "temperature_c", "plating_margin_v", "capacity_ah"),
        "cases carrying a hidden duplicate in the same batch",
        "32 float32 ulp",
    ),
)


@dataclass
class Tolerances:
    tau_v0: float
    tau_t0: float
    tau_vmax: float
    tau_vmin: float
    q_bound: float
    v_max: float = 4.2
    v_min: float = 2.5
    evidence: dict = field(default_factory=dict)

    def as_dict(self) -> dict:
        return {
            k: getattr(self, k)
            for k in (
                "tau_v0",
                "tau_t0",
                "tau_vmax",
                "tau_vmin",
                "q_bound",
                "v_max",
                "v_min",
            )
        } | {"evidence": self.evidence}


def calibrate(
    references: list[dict], ocv: dict[str, float], q_bound: float, v_max=4.2, v_min=2.5
) -> Tolerances:
    """Derive tolerances from reference evidence only (never from model predictions).

    ``references`` are OK reference records on the calibration roles (TRAIN,
    PRACTICE and pilot refinements); ``ocv`` maps case_id to the parameter-set
    OCV at that case's initial state.
    """
    d_v0 = max(
        abs(r["outputs"]["voltage_v"][0] - ocv[r["case_id"]]) for r in references
    )
    d_t0 = max(
        abs(r["outputs"]["temperature_c"][0] - r["inputs"]["t_amb_c"])
        for r in references
    )
    over = max(max(r["outputs"]["voltage_v"]) - v_max for r in references)
    under = max(v_min - min(r["outputs"]["voltage_v"]) for r in references)
    ulp = lambda x: ULP_FACTOR * F32_EPS * x
    return Tolerances(
        tau_v0=max(2 * d_v0, ulp(v_max)),
        tau_t0=max(2 * d_t0, ulp(40.0)),
        tau_vmax=max(2 * max(over, 0.0), ulp(v_max)),
        tau_vmin=max(2 * max(under, 0.0), ulp(v_min)),
        q_bound=q_bound,
        v_max=v_max,
        v_min=v_min,
        evidence={
            "max_ref_v0_minus_ocv": d_v0,
            "max_ref_t0_minus_ambient": d_t0,
            "max_ref_overshoot_v": over,
            "max_ref_undershoot_v": under,
            "n_references": len(references),
        },
    )


def _finite_shape(pred: dict, shapes: dict) -> bool:
    try:
        for k, shp in shapes.items():
            a = np.asarray(pred[k], dtype=float)
            if a.shape != shp or not np.all(np.isfinite(a)):
                return False
        return True
    except Exception:  # noqa: BLE001 -- failure is typed
        return False


def evaluate_case(
    pred: dict | None,
    reference: dict,
    case_inputs: dict,
    ocv: float,
    tol: Tolerances,
    shapes: dict,
    twin_pred: dict | None = None,
    infra_failed: bool = False,
) -> dict:
    """Type one case for one model and run every applicable gate."""
    if reference.get("status") != "OK" or not reference.get("reference_valid", True):
        return {"state": REFERENCE_INVALID, "gates": {}}
    if infra_failed or pred is None:
        return {"state": FAILED_INFRA, "gates": {}}
    g: dict[str, str] = {}
    g["schema_finite"] = PASS if _finite_shape(pred, shapes) else FAIL
    if g["schema_finite"] == FAIL:
        # Nothing else can be evaluated on malformed output; the case fails.
        return {"state": GATE_FAILED, "gates": g}
    v = np.asarray(pred["voltage_v"], float)
    t = np.asarray(pred["temperature_c"], float)
    q = np.asarray(pred["capacity_ah"], float)
    g["initial_voltage"] = PASS if abs(v[0] - ocv) <= tol.tau_v0 else FAIL
    g["initial_temperature"] = (
        PASS if abs(t[0] - case_inputs["t_amb_c"]) <= tol.tau_t0 else FAIL
    )
    g["voltage_ceiling"] = PASS if v.max() <= tol.v_max + tol.tau_vmax else FAIL
    g["voltage_floor"] = PASS if v.min() >= tol.v_min - tol.tau_vmin else FAIL
    g["capacity_bound"] = PASS if np.all(q > 0) and np.all(q <= tol.q_bound) else FAIL
    if twin_pred is None:
        g["paired_repeat"] = NOT_APPLICABLE
    else:
        ok = _finite_shape(twin_pred, shapes)
        if ok:
            for k in shapes:
                a, b = np.asarray(pred[k], float), np.asarray(twin_pred[k], float)
                if np.any(
                    np.abs(a - b) > ULP_FACTOR * F32_EPS * np.maximum(1.0, np.abs(a))
                ):
                    ok = False
        g["paired_repeat"] = PASS if ok else FAIL
    state = GATE_FAILED if FAIL in g.values() else SCORABLE
    return {"state": state, "gates": g}


# --- Score (scripts/dev/exam_design/scoring.py) ---

COMPONENTS = ("voltage", "temperature", "plating", "capacity")


def scales_from_train(train_refs: list[dict], floors: dict | None = None) -> dict:
    """TRAIN spread per output, never below the output's reference-uncertainty floor."""
    v = np.array([r["outputs"]["voltage_v"] for r in train_refs])
    # Temperature is scaled by the spread of the *rise above ambient*: ambient is an input, so its 5-40 C
    # range would otherwise inflate the scale and make a 1 C thermal error nearly free.
    t = np.array(
        [
            np.asarray(r["outputs"]["temperature_c"]) - r["inputs"]["t_amb_c"]
            for r in train_refs
        ]
    )
    e = np.array([r["outputs"]["plating_margin_v"] for r in train_refs])
    q = np.array([r["outputs"]["capacity_ah"] for r in train_refs])
    fade = q[:, :1] - q[:, 1:]
    raw = {
        "s_v": float(v.std()),
        "s_t": float(t.std()),
        "s_eta": float(e.std()),
        "s_q1": float(q[:, 0].std()),
        "s_fade": float(fade.std()),
    }
    floors = floors or {}
    out = {k: max(val, float(floors.get(k, 0.0))) for k, val in raw.items()}
    return out | {"raw": raw, "floors": floors, "n_train": len(train_refs)}


def case_components(pred: dict, ref: dict, scales: dict) -> dict:
    o = ref["outputs"]
    rms = lambda a, b: float(
        np.sqrt(np.mean((np.asarray(a, float) - np.asarray(b, float)) ** 2))
    )
    return {
        "voltage": rms(pred["voltage_v"], o["voltage_v"]) / scales["s_v"],
        "temperature": rms(pred["temperature_c"], o["temperature_c"]) / scales["s_t"],
        "plating": abs(float(pred["plating_margin_v"]) - o["plating_margin_v"])
        / scales["s_eta"],
        "capacity": 0.5
        * (
            abs(float(pred["capacity_ah"][0]) - o["capacity_ah"][0]) / scales["s_q1"]
            + rms(
                np.asarray(pred["capacity_ah"][0])
                - np.asarray(pred["capacity_ah"][1:], float),
                o["capacity_ah"][0] - np.asarray(o["capacity_ah"][1:], float),
            )
            / scales["s_fade"]
        ),
    }


def case_error(components: dict) -> float:
    return float(np.mean([components[c] for c in COMPONENTS]))


def aggregate(case_rows: list[dict]) -> dict:
    """Summarize typed case rows from ``gates.evaluate_case`` plus errors.

    A single gate failure makes the submission ineligible: mandatory failure is
    not compensated by soft performance. Reference-invalid and infra cases are
    counted and excluded, never charged to the model.
    """
    states = [r["state"] for r in case_rows]
    scored = [r for r in case_rows if r["state"] == "SCORABLE"]
    imp = [r for r in scored if r.get("important")]
    out = {
        "n_cases": len(case_rows),
        "n_scored": len(scored),
        "n_gate_failed": states.count("GATE_FAILED"),
        "n_reference_invalid": states.count("REFERENCE_INVALID"),
        "n_failed_infra": states.count("FAILED_INFRA"),
        "eligible": states.count("GATE_FAILED") == 0 and len(scored) > 0,
        "score": float(np.mean([r["error"] for r in scored])) if scored else None,
        "important_score": float(np.mean([r["error"] for r in imp])) if imp else None,
        "n_important": len(imp),
        "components": (
            {
                c: float(np.mean([r["components"][c] for r in scored]))
                for c in COMPONENTS
            }
            if scored
            else None
        ),
    }
    fails: dict[str, int] = {}
    for r in case_rows:
        for g, v in r.get("gates", {}).items():
            if v == "FAIL":
                fails[g] = fails.get(g, 0) + 1
    out["gate_failures"] = fails
    return out


# --- Exam machinery (scripts/dev/exam_design/exam.py) ---

IMPROVEMENT, REGRESSION, TRADE_OFF, NO_IMPROVEMENT, INSUFFICIENT = (
    "IMPROVEMENT",
    "REGRESSION",
    "TRADE_OFF",
    "NO_IMPROVEMENT",
    "INSUFFICIENT_EVIDENCE",
)


@dataclass
class CaseStore:
    """Reference records and the per-case context gates need."""

    refs: dict[str, dict]
    ocv: dict[str, float]
    tol: Tolerances
    scales: dict
    shapes: dict
    twins: dict[str, str] = field(
        default_factory=dict
    )  # duplicate case id -> original case id

    def important(self, cid: str) -> bool:
        r = self.refs[cid]
        return r.get("status") == "OK" and is_important(r)


def evaluate(
    preds: dict[str, dict | None],
    case_ids: list[str],
    store: CaseStore,
    infra_failed: set[str] | None = None,
) -> tuple[list[dict], dict]:
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
        row = evaluate_case(
            preds.get(cid),
            ref,
            ref.get("inputs", {}),
            store.ocv.get(cid, np.nan),
            store.tol,
            store.shapes,
            twin_pred=twin_pred,
            infra_failed=cid in infra_failed,
        )
        row["case_id"] = cid
        if row["state"] == SCORABLE:
            comp = case_components(preds[cid], ref, store.scales)
            row["components"], row["error"] = comp, case_error(comp)
            row["important"] = store.important(cid)
        rows.append(row)
    return rows, aggregate(rows)


class PredictionBank:
    """Stored predictions per model; inference on demand, never retraining."""

    def __init__(
        self,
        predictors: dict[str, Callable[[list[str]], dict[str, dict]]] | None = None,
    ):
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
                raise KeyError(
                    f"{model_id}: no stored predictions for {len(missing)} cases and no predictor"
                )
            have.update(self.predictors[model_id](missing))
            self.inference_calls[model_id] = self.inference_calls.get(model_id, 0) + 1
            self.inferred_cases[model_id] = self.inferred_cases.get(model_id, 0) + len(
                missing
            )
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
        self.__dict__.setdefault("log", []).append(
            {"version": new_version, "added": len(added_case_ids), "reason": reason}
        )


@dataclass
class ScreeningPool:
    batches: list[list[str]]  # every prepared batch, in entry order
    rotate_after: int  # admitted submissions per rotation
    n_active: int = 3
    batch_size: int | None = None  # nested prefix of each batch, if smaller
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
        rec = {
            "model_id": model_id,
            "pool_version": self.pool_version,
            "active_batches": list(self.active),
            **agg,
        }
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


def _classify(
    d: np.ndarray, base: float, rule: ComparisonRule, rng
) -> tuple[str, list[float]]:
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


def final_compare(
    inc_err: dict[str, float],
    chal_err: dict[str, float],
    important: dict[str, bool],
    rule: ComparisonRule,
    chal_eligible: bool = True,
    inc_components=None,
    chal_components=None,
) -> dict:
    """Paired comparison on the same fresh cases. Positive d means the challenger is worse."""
    rng = np.random.default_rng(rule.seed)
    ids = sorted(set(inc_err) & set(chal_err))
    out = {"n": len(ids), "rule": rule.__dict__}
    if not chal_eligible:
        return out | {
            "outcome": REGRESSION,
            "reason": "challenger failed a mandatory gate on final cases",
        }
    if len(ids) < rule.n_min:
        return out | {
            "outcome": INSUFFICIENT,
            "reason": f"{len(ids)} scorable paired cases < {rule.n_min}",
        }
    d = np.array([chal_err[c] - inc_err[c] for c in ids])
    base = float(np.mean([inc_err[c] for c in ids]))
    overall, ci = _classify(d, base, rule, rng)
    imp_ids = [c for c in ids if important.get(c)]
    if len(imp_ids) >= rule.important_min:
        di = np.array([chal_err[c] - inc_err[c] for c in imp_ids])
        imp, ci_i = _classify(
            di, float(np.mean([inc_err[c] for c in imp_ids])), rule, rng
        )
    else:
        imp, ci_i = "insufficient", None
    comp = {}
    if inc_components and chal_components:
        for k in COMPONENTS:
            dk = np.array([chal_components[c][k] - inc_components[c][k] for c in ids])
            comp[k], _ = _classify(
                dk, float(np.mean([inc_components[c][k] for c in ids])), rule, rng
            )
    out |= {
        "mean_delta": float(d.mean()),
        "ci": ci,
        "incumbent_mean": base,
        "overall": overall,
        "important": imp,
        "important_ci": ci_i,
        "n_important": len(imp_ids),
        "components": comp,
    }
    if overall == "worse":
        o, why = REGRESSION, "overall error significantly higher"
    elif imp == "worse" and overall != "better":
        o, why = (
            REGRESSION,
            "important region significantly worse without an overall gain",
        )
    elif overall == "better" and imp == "worse":
        o, why = TRADE_OFF, "overall better but important region worse"
    elif overall == "better" and imp == "insufficient":
        o, why = (
            INSUFFICIENT,
            "overall better but too few important-region cases to show no regression",
        )
    elif overall == "better":
        o, why = IMPROVEMENT, "overall better; important region not worse"
    elif overall == "equivalent" and imp == "better":
        o, why = TRADE_OFF, "overall equivalent; important region better"
    elif (
        overall == "equivalent"
        and "worse" in comp.values()
        and "better" in comp.values()
    ):
        o, why = TRADE_OFF, "overall equivalent; components move in opposite directions"
    elif overall == "equivalent":
        o, why = NO_IMPROVEMENT, "within the equivalence margin"
    else:
        o, why = (
            INSUFFICIENT,
            "confidence interval neither excludes nor fits inside the margin",
        )
    # Eligibility, not just reporting: only an IMPROVEMENT may be promoted. A significant important-region
    # regression blocks promotion even when the overall score improved (TRADE_OFF), and "equivalent" is only
    # ever concluded when the whole interval sits inside the margin - never from a failure to detect a
    # difference, which is INSUFFICIENT_EVIDENCE.
    return out | {
        "outcome": o,
        "reason": why,
        "promotable": o == IMPROVEMENT,
        "regional_block": imp == "worse",
        "existing_disposition": EXISTING_DISPOSITION[o],
    }


# The repository's DEVELOPMENT comparison (carbon.development.compare) names its dispositions
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
