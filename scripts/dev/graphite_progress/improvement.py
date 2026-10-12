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
SMALL_N = 5


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
    interval. A single value has no interval (None)."""
    if len(values) < 2:
        return None
    rng = random.Random(seed)
    medians = sorted(
        statistics.median(rng.choices(values, k=len(values))) for _ in range(reps)
    )
    low = medians[int(((1 - level) / 2) * reps)]
    high = medians[min(reps - 1, int((1 - (1 - level) / 2) * reps))]
    return [round(low, 6), round(high, 6)]


def public_dev_block(records):
    """`{metric: {value (median), best, ci95, n, small_n, ...}}` over the runs that hold a record."""
    if not records:
        return unmeasured(
            "no run has a public-development improvement record from the executor"
        )
    out = {}
    for name in METRICS:
        values = [
            r
            for rec in records
            if (r := relative(rec["baseline"].get(name), rec["model"].get(name)))
            is not None
        ]
        if not values:
            out[name] = unmeasured(f"no run measured {name} on both sides")
            continue
        out[name] = {
            **metric(round(statistics.median(values), 6), len(values), LABEL),
            "best": round(max(values), 6),
            "ci95": bootstrap_interval(values),
            "small_n": len(values) < SMALL_N,
            "interval": f"percentile bootstrap of the median, {BOOTSTRAP_REPS} resamples, seed {BOOTSTRAP_SEED}",
        }
    return out
