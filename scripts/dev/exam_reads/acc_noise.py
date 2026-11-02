"""ACC-NOISE-01, pure helpers: the S2 noise dry run of the adopted accuracy rule (the owner's accuracy rule, lead-records 497b5817; EXAM_QUALIFICATION_SYSTEM
section 3c). CUSTODY scratch, aggregates only, never official; no I/O here.

Per contender (the kings, the baseline, the TRAIN-kernel, the DOWN formula, the tuned operator) the input is its in-range accuracy
``a_in`` and its A_gen POINTS as ``[(class, target_id, atom), ...]``: ``atom`` the point's REGISTERED A_gen atom (pool_grader's
benefit(|err| / scale), averaged over the outputs), ``class`` the point's region class (Validator 11-01 (c): a per-POINT class, never
a target's). The pooled A_gen is today's slice exactly (`pool_grader.agen_accuracy`: per-target mean, then the mean over targets), and
A under each rule is `pool_grader.combine_a` itself: the version's REGISTERED a_rule, or {"kind": "min"}. Rulings applied (Validator 11-01, the section 3c boundary entry):
- (b) n = the class's A_gen point count; N = the version's registered accuracy-case floor per class, given as ``floor_n``; a class
  with n < N is indicative and its points pool into ``OTHER_OOD``;
- (d) out of range = every class except ``in_train``;
- (a) a contender with no registered method (the DOWN formula of a version with none) is "not available", never improvised.

The verdict (Validator 11-01, ACC-NOISE-01 ruled): the spread is the bootstrap SD of the balanced A_gen (q2.5 / q97.5 reported, not
used), the deciding spread is the MAX over the graded contenders (crown, baseline, TRAIN-kernel), the bootstrap is `DRAWS` 2000
within-class draws with the seed recorded; ``min`` is used only if that spread < margin_N, else raise N per class or fall back to
C3 + ``mean`` (reported). Still explicit arguments with no default: whether ``OTHER_OOD`` enters the balanced mean, and the
version's registered a_rule.
"""

from __future__ import annotations

import math
import statistics

import numpy as np

IN_TRAIN = "in_train"
OTHER_OOD = "other_ood"
ROLES = ("crown", "baseline", "train_kernel", "down_formula", "operator")
#: The contenders whose spread decides (the max over them).
GRADED = ("crown", "baseline", "train_kernel")
NOT_AVAILABLE = "not available"
DRAWS = 2000


class AccNoiseRefused(ValueError):
    def __init__(self, code):
        super().__init__(code)
        self.code = code


def _need(ok, code):
    if not ok:
        raise AccNoiseRefused(code)


def _finite(value):
    return (
        type(value) in (int, float)
        and not isinstance(value, bool)
        and math.isfinite(value)
    )


def checked_points(points):
    """``[(class, target_id, atom)]`` with a non-empty str class and target and an atom in [0, 1], or a refusal (never a default
    class)."""
    _need(type(points) is list and points, "points_empty")
    out = []
    for item in points:
        _need(type(item) in (list, tuple) and len(item) == 3, "point_shape")
        klass, target, atom = item
        _need(type(klass) is str and klass, "point_class_missing")
        _need(type(target) is str and target, "point_target_missing")
        _need(_finite(atom) and 0.0 <= atom <= 1.0, "point_atom")
        out.append((klass, target, float(atom)))
    return out


def _classes(points):
    grouped = {}
    for klass, _target, atom in points:
        grouped.setdefault(klass, []).append(atom)
    return grouped


def pooled(points):
    """Today's pooled A_gen slice, exactly as `pool_grader.agen_accuracy` forms it: each target's mean atom, then the mean over
    the targets (whatever the points' classes)."""
    import statistics

    per_target = {}
    for _klass, target, atom in points:
        per_target.setdefault(target, []).append(atom)
    return statistics.fmean([statistics.fmean(v) for v in per_target.values()])


def pooled_by_set(points, set_of):
    """Each pool set's pooled A_gen (`pooled` over that set's targets), as measure_pool scores A_gen per set; every point's target
    must be mapped to a set."""
    by_set = {}
    for point in points:
        _need(point[1] in set_of, f"target_has_no_set:{point[1]}")
        by_set.setdefault(set_of[point[1]], []).append(point)
    return {key: pooled(group) for key, group in sorted(by_set.items())}


def balanced(points, *, floor_n, other_ood_enters):
    """The balanced out-of-range A_gen: the mean over the out-of-range classes with n >= floor_n of each class's mean atom; the
    points of smaller out-of-range classes pool into OTHER_OOD, which joins the mean only when ``other_ood_enters``. None when no
    class qualifies."""
    means = {}
    small = []
    for klass, atoms in _classes(points).items():
        if klass == IN_TRAIN:
            continue
        if len(atoms) >= floor_n:
            means[klass] = math.fsum(atoms) / len(atoms)
        else:
            small += atoms
    if other_ood_enters and small:
        means[OTHER_OOD] = math.fsum(small) / len(small)
    return math.fsum(means.values()) / len(means) if means else None


def combine(a_in, a_gen, rule):
    """A under ``rule`` by the grader's own `pool_grader.combine_a` (a_gen None leaves A_in, as the grader does)."""
    from carbon.scoring import pool_grader

    try:
        return pool_grader.combine_a(a_in, a_gen, rule)
    except pool_grader.PoolRefused as refused:
        raise AccNoiseRefused("combine_rule") from refused


def bootstrap(points, statistic, *, draws, seed):
    """Replicates of ``statistic(points)`` with the points resampled WITHIN each class (class sizes kept)."""
    rng = np.random.default_rng(seed)
    grouped = {}
    for point in points:
        grouped.setdefault(point[0], []).append(point)
    out = []
    for _ in range(draws):
        sample = []
        for klass in sorted(grouped):
            members = grouped[klass]
            picks = rng.integers(0, len(members), size=len(members))
            sample += [members[int(i)] for i in picks]
        value = statistic(sample)
        if value is not None:
            out.append(value)
    return np.asarray(out, dtype=float)


def spread(replicates):
    """Every candidate spread statistic of the replicates, side by side: which one decides is the Validator's to name."""
    if replicates.size < 2:
        return None
    lo, hi = (float(x) for x in np.quantile(replicates, [0.025, 0.975]))
    return {
        "sd": float(np.std(replicates, ddof=1)),
        "q025": lo,
        "q975": hi,
        "width_95": hi - lo,
        "half_width_95": (hi - lo) / 2.0,
        "replicates": int(replicates.size),
    }


def report(
    contenders, *, set_of, floor_n, other_ood_enters, registered_rule, seed, margin_n
):
    """The ACC-NOISE-01 table: per contender A_in, pooled and balanced A_gen, A under {registered, min} x {pooled, balanced}, the balanced
    A_gen's bootstrap spread; per out-of-range class the mean atom and its difference to the TRAIN-kernel's (report only, C4); the
    crown - baseline gap under each rule. ``contenders``: {role: {"a_in", "points"} | None}, a None role being "not available".
    ``set_of`` maps every target to its pool set: the pooled side is measure_pool's exactly (A per set = combine_a(A_in, that set's
    pooled A_gen), then the mean over the sets); the balanced side is over every out-of-range point of the version.
    """
    _need(type(contenders) is dict and set(contenders) == set(ROLES), "contender_roles")
    _need(type(floor_n) is int and floor_n >= 1, "floor_n")
    _need(type(other_ood_enters) is bool, "other_ood_enters")
    _need(
        type(registered_rule) is dict
        and registered_rule.get("kind") in ("min", "mean", "weighted"),
        "registered_rule",
    )
    _need(type(seed) is int, "bootstrap_seed")
    _need(type(set_of) is dict and set_of, "set_of")
    _need(_finite(margin_n) and margin_n > 0, "margin_n")
    for role in ("crown", "baseline", "train_kernel"):
        _need(contenders[role] is not None, f"contender_required:{role}")

    def bal(points):
        return balanced(points, floor_n=floor_n, other_ood_enters=other_ood_enters)

    rows, classes = {}, {}
    for role in ROLES:
        entry = contenders[role]
        if entry is None:
            rows[role] = NOT_AVAILABLE
            continue
        _need(
            type(entry) is dict and set(entry) == {"a_in", "points"},
            f"contender_shape:{role}",
        )
        _need(_finite(entry["a_in"]) and 0.0 <= entry["a_in"] <= 1.0, f"a_in:{role}")
        points = checked_points(entry["points"])
        per_set = pooled_by_set(points, set_of)
        a_bal = bal(points)
        rules = (("registered", registered_rule), ("min", {"kind": "min"}))
        a_table = {}
        for name, rule in rules:
            a_table[f"{name}_pooled"] = statistics.fmean(
                combine(entry["a_in"], gen, rule) for gen in per_set.values()
            )
            a_table[f"{name}_balanced"] = combine(entry["a_in"], a_bal, rule)
        rows[role] = {
            "a_in": entry["a_in"],
            "a_gen_pooled_by_set": per_set,
            "a_gen_balanced": a_bal,
            "A": a_table,
            "balanced_spread": spread(bootstrap(points, bal, draws=DRAWS, seed=seed)),
        }
        classes[role] = {
            k: {
                "n": len(v),
                "mean": math.fsum(v) / len(v),
                "indicative": len(v) < floor_n,
            }
            for k, v in _classes(points).items()
            if k != IN_TRAIN
        }
    kernel = classes["train_kernel"]
    per_class = {
        role: {
            k: {
                **v,
                "minus_train_kernel": (
                    (v["mean"] - kernel[k]["mean"]) if k in kernel else None
                ),
            }
            for k, v in table.items()
        }
        for role, table in classes.items()
    }
    gap = {
        key: (
            None
            if rows["crown"]["A"][key] is None or rows["baseline"]["A"][key] is None
            else rows["crown"]["A"][key] - rows["baseline"]["A"][key]
        )
        for key in rows["crown"]["A"]
    }
    return {
        "contenders": rows,
        "per_class": per_class,
        "crown_minus_baseline": gap,
        "margin_n": margin_n,
        "settings": {
            "floor_n": floor_n,
            "other_ood_enters": other_ood_enters,
            "registered_rule": dict(registered_rule),
            "draws": DRAWS,
            "seed": seed,
        },
        **_verdict(rows, margin_n),
    }


def _verdict(rows, margin_n):
    """``min`` only if the MAX over the graded contenders of the balanced A_gen's bootstrap SD is < margin_N; else raise N per
    class or keep C3 + ``mean`` (the milder rule). No verdict when a graded contender has no balanced A_gen to resample.
    """
    sds = {}
    for role in GRADED:
        summary = rows[role]["balanced_spread"]
        if summary is None:
            return {"verdict": None, "verdict_reason": f"no_balanced_a_gen:{role}"}
        sds[role] = summary["sd"]
    by = max(sds, key=lambda role: (sds[role], role))
    return {
        "deciding_spread": {
            "statistic": "bootstrap_sd",
            "value": sds[by],
            "contender": by,
            "per_contender": sds,
        },
        "verdict": "min" if sds[by] < margin_n else "mean_or_raise_n",
        "verdict_reason": (
            "max_graded_sd_below_margin_n"
            if sds[by] < margin_n
            else "max_graded_sd_not_below_margin_n"
        ),
    }


# ---------------------------------------------------------------- the per-point class (Validator 11-01, ACC-NOISE ruling (4))


def plan_class_names(params):
    """The class names a REGISTERED coverage plan's params name (``classes[].class``), plus in_train; refused when empty."""
    entries = params.get("classes") if type(params) is dict else None
    _need(type(entries) is list and entries, "coverage_plan_classes")
    names = [e.get("class") for e in entries if type(e) is dict]
    _need(
        len(names) == len(entries) and all(type(n) is str and n for n in names),
        "coverage_plan_classes",
    )
    return frozenset(names) | {IN_TRAIN}


def point_classes(
    rows, *, klass, region, names, allowed, pack_classes=None, official=False
):
    """Each A_gen point's class by the registered geometric-v1 rule (``klass``, the receipted probe_set.klass loaded by its sha)
    on the signed region. An OFFICIAL read refuses until the pool material carries its own per-point class field (ruling (4)); a
    scratch read uses the rule, every class must be one the registered coverage plan names (``allowed``), and when the material
    does carry ``pack_classes`` both must agree point by point (a mismatch STOPS)."""
    _need(not official, "point_class_field_required_for_an_official_read")
    out = []
    for i, inputs in enumerate(rows):
        _need(type(inputs) is dict and set(names) <= set(inputs), "point_inputs")
        cls = klass(region, names, inputs)
        _need(cls in allowed, f"point_class_not_in_the_coverage_plan:{cls}")
        if pack_classes is not None:
            _need(pack_classes[i] == cls, "point_class_disagrees_with_the_pack")
        out.append(cls)
    if pack_classes is not None:
        _need(len(pack_classes) == len(out), "point_class_count")
    return out


def load_rule(path, sha256):
    """``klass`` of the receipted geometric-v1 rule file (SEP_PROBE_SETS probe_set.py), imported only after its sha256 is
    ``sha256`` (the file is the rule's identity; its own directory holds the modules it imports).
    """
    import hashlib
    import importlib.util
    import sys
    from pathlib import Path

    path = Path(path)
    _need(path.is_file(), "rule_file_missing")
    _need(
        hashlib.sha256(path.read_bytes()).hexdigest() == sha256.removeprefix("sha256:"),
        "rule_file_sha256_mismatch",
    )
    if str(path.parent) not in sys.path:
        sys.path.insert(0, str(path.parent))
    spec = importlib.util.spec_from_file_location("acc_noise_geometric_rule", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    _need(getattr(module, "RULE", None) == "geometric-v1", "rule_is_not_geometric_v1")
    return module.klass
