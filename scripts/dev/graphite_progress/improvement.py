"""Public-development improvement per level: the executor's per-run results, aggregated with a bootstrap.

The executor scores each BUNDLED run's best model on PUBLIC development data only (the public EV4
development panel for accuracy, the public decision questions for decision value) against the same
lane's Level 0 baseline, and writes one `carbon.graphite.public-improvement.v1` record per run (the spec is
`PUBLIC_IMPROVEMENT_SPEC.md`). This module reads those records and reports, per level, the median and
best relative improvement with a bootstrap interval and the sample size.

Never sealed, never a qualification claim; small samples are flagged, not hidden.
"""

from __future__ import annotations

import json
import random
import statistics
from pathlib import Path

from .model import ProgressError, metric, unmeasured

IMPROVEMENT_SCHEMA = "carbon.graphite.public-improvement.v1"
#: The two lower-is-better public metrics.
METRICS = ("accuracy_error", "decision_loss")
#: The one scoring set a public-improvement record may use: #1188's `public_ev4_scoring_set`, the committed public
#: EV4 decision references. `carbon.battery.value.scoring.scoring_set` loads the retained exam-design private-role
#: references and is never used on this path.
#:
#: The PIN is the committed contract `ev4-dev-proof-l1-v1.json`, whose `public_reference_sha256` is a literal digest
#: that #1188's test asserts equals the runner's reference digest (and that no "private" path is in the scoring
#: identity). The runner's own check compares a fresh read of the file with a digest taken from the same file at
#: import, which guards a change in between, not the content. So this module reads the digest from the committed
#: contract and compares the record's digest with that literal; the contract being absent refuses every record.
PUBLIC_EV4_FUNCTION = "public_ev4_scoring_set"
CONTRACT = (
    Path(__file__).resolve().parents[3]
    / "carbon/battery/value/contracts/ev4-dev-proof-l1-v1.json"
)
PRIVATE_MARKERS = ("refs-b", "private-role", "battery_refs")
LABEL = (
    "PUBLIC-DEV-MEASURED: the public EV4 development panel and the public decision questions, "
    "against the lane's Level 0 baseline; never sealed data; not a qualification claim"
)
BOOTSTRAP_SEED = 20261012
BOOTSTRAP_REPS = 2000
SMALL_N = 10
#: A percentile bootstrap of a median from fewer than three values is just the range of the values, so no interval is
#: reported below this size; the ledger says so instead of printing a fabricated one.
MIN_N_INTERVAL = 3
#: Below this size the interval is reported but flagged coarse: a bootstrap of the median of n values can only return
#: observed values, so it is roughly the sample's range.
COARSE_N = 5
#: Why a record above Level 0 carries a caveat: the executor rebuilds the bundle through `level_compile.base_for`
#: without `member_bundle`'s registered-panel guard (a Graphite bundle is not a registered panel member).
LEVEL_REBUILD_CAVEAT = (
    "the model was rebuilt through level_compile.base_for then the Level 0 base, i.e. member_bundle's level path "
    "WITHOUT its registered-panel guard; the bundle is not a registered member of the level panel"
)


def committed_reference_sha(contract=None):
    """The public EV4 reference digest as the COMMITTED contract states it (its literal
    `public_reference_sha256`), or a typed refusal when the contract is absent or has none.
    """
    path = Path(contract) if contract is not None else CONTRACT
    try:
        value = json.loads(path.read_bytes()).get("public_reference_sha256")
    except (OSError, ValueError, AttributeError) as error:
        raise ProgressError("public_improvement_contract_unreadable") from error
    if not (
        isinstance(value, str) and value.startswith("sha256:") and len(value) == 71
    ):
        raise ProgressError("public_improvement_contract_has_no_reference_digest")
    return value


def validate(record, contract=None):
    """The record as a checked dict, or a typed refusal. Its scoring-set digest must equal the
    committed contract's literal."""
    if type(record) is not dict or record.get("schema") != IMPROVEMENT_SCHEMA:
        raise ProgressError("public_improvement_schema")
    if record.get("public_only") is not True:
        raise ProgressError("public_improvement_not_public_only")
    scoring = (record.get("panel") or {}).get("scoring_set")
    if (
        type(scoring) is not dict
        or scoring.get("function") != PUBLIC_EV4_FUNCTION
        or scoring.get("sha256") != committed_reference_sha(contract)
    ):
        raise ProgressError("public_improvement_scoring_set_not_public_ev4")
    if any(marker in repr(record).lower() for marker in PRIVATE_MARKERS):
        raise ProgressError("public_improvement_names_a_private_source")
    for side in ("baseline", "model"):
        row = record.get(side)
        if type(row) is not dict:
            raise ProgressError(f"public_improvement_missing_{side}")
        for name in METRICS:
            value = row.get(name)
            if value is not None and (type(value) not in (int, float) or value < 0):
                raise ProgressError(f"public_improvement_bad_{side}_{name}")
    return record


def relative(baseline, model):
    """Relative improvement of a lower-is-better metric: positive is better; None if unmeasurable."""
    if baseline is None or model is None or baseline <= 0:
        return None
    return (baseline - model) / baseline


def bootstrap_interval(values, *, seed=BOOTSTRAP_SEED, reps=BOOTSTRAP_REPS, level=0.95):
    """Percentile bootstrap interval of the median: fixed seed, so the same values give the same
    interval. Fewer than `MIN_N_INTERVAL` values have no interval (None): the bootstrap of two values is only their
    range."""
    if len(values) < MIN_N_INTERVAL:
        return None
    rng = random.Random(seed)
    medians = sorted(
        statistics.median(rng.choices(values, k=len(values))) for _ in range(reps)
    )
    low = medians[int(((1 - level) / 2) * reps)]
    high = medians[min(reps - 1, int((1 - (1 - level) / 2) * reps))]
    return [round(low, 6), round(high, 6)]


NOISY = "MEASURED_BUT_NOISY"


def _decision_noise(pairs):
    """Why a decision-loss column must not be read as an improvement claim, or []: the common resolved
    masks differ between runs (each run is scored on a different set of questions), or the runs disagree
    in sign (some better, some worse than their own baseline)."""
    reasons = []
    masks = {m for _, m, _ in pairs if m is not None}
    if len(masks) > 1:
        reasons.append(
            f"the common masks differ per run ({sorted(masks)} of the development scenarios)"
        )
    values = [v for v, _, _ in pairs]
    if min(values) < 0 < max(values):
        reasons.append(
            "the runs disagree in sign; at least one is worse than its own baseline"
        )
    return reasons


#: Level 4 caveat (executor report, 2026-10-12): the Level 4 bundles scored here were built on variant ad15d6a8
#: with no graph, so the accuracy numbers measure the BASE recipe, not any graph lowering or Level 4 freedom.
L4_BASE_RECIPE_CAVEAT = (
    "LEVEL 4 BASE-RECIPE-ONLY MEASUREMENT: the bundles scored here are on variant ad15d6a8 with no graph, so the "
    "number measures the base recipe, NOT graph lowering or the Level 4 freedoms; not evidence about Level 4"
)


def _caveats(records):
    """Caveats the ledger line must carry for these records (levels above 0 rebuild without the panel guard)."""
    out = []
    if any((rec.get("level") or 0) > 0 for rec in records):
        out.append(LEVEL_REBUILD_CAVEAT)
    if any(rec.get("level") == 4 for rec in records):
        out.append(L4_BASE_RECIPE_CAVEAT)
    return out


def line_caveats(records):
    """The caveats a ledger line must carry for its public-improvement records (empty when none apply)."""
    return _caveats([r for r in records if r])


def _null_reasons(records, name):
    """The executor's own reasons for a null `name`, de-duplicated, in record order."""
    seen = []
    for rec in records:
        reason = (rec.get("questions") or {}).get(f"{name}_null_reason")
        if reason and reason not in seen:
            seen.append(reason)
    return seen


PANEL_MEMBER_NOTE = (
    "decision loss at Levels 2-4 needs the panel-member registration (the Test Engineer's decision); the executor "
    "can score accuracy error without it, and this run has no record"
)


def public_dev_block(records, level=None):
    """`{metric: {value (median), best, ci95, n, small_n, ...}}` over the runs that hold a record. A
    decision-loss column whose masks differ or whose runs disagree in sign is MEASURED_BUT_NOISY: its
    per-run values are shown and it is NOT an improvement claim."""
    if not records:
        return unmeasured(
            "no run has a public-development improvement record from the executor"
            + (f"; {PANEL_MEMBER_NOTE}" if (level or 0) >= 2 else "")
        )
    out = {}
    for name in METRICS:
        pairs = [
            (
                r,
                (rec.get("questions") or {}).get("common_mask"),
                rec.get("run_id"),
            )
            for rec in records
            if (r := relative(rec["baseline"].get(name), rec["model"].get(name)))
            is not None
        ]
        if not pairs:
            reasons = _null_reasons(records, name)
            out[name] = unmeasured(
                f"no run measured {name} on both sides"
                + (f" ({'; '.join(reasons)})" if reasons else "")
            )
            continue
        values = [r for r, _, _ in pairs]
        reasons = _decision_noise(pairs) if name == "decision_loss" else []
        out[name] = {
            **metric(
                NOISY if reasons else round(statistics.median(values), 6),
                len(values),
                LABEL,
            ),
            "best": round(max(values), 6),
            "ci95": bootstrap_interval(values),
            "small_n": len(values) < SMALL_N,
            **(
                {"ci95_note": f"interval not meaningful at n={len(values)}"}
                if len(values) < MIN_N_INTERVAL
                else {
                    "ci95_note": f"coarse at n={len(values)}: the bootstrap median can only take the observed values"
                }
                if len(values) < COARSE_N
                else {}
            ),
            **({"caveats": _caveats(records)} if _caveats(records) else {}),
            "interval": f"percentile bootstrap of the median, {BOOTSTRAP_REPS} resamples, seed {BOOTSTRAP_SEED}",
            **(
                {
                    "reading": f"{NOISY}: "
                    + "; ".join(reasons)
                    + "; NOT an improvement claim",
                    "median_if_read": round(statistics.median(values), 6),
                    "per_run": [
                        {
                            "run": run,
                            "relative_improvement": round(r, 6),
                            "common_mask": mask,
                        }
                        for r, mask, run in pairs
                    ],
                }
                if reasons
                else {}
            ),
        }
    return out
