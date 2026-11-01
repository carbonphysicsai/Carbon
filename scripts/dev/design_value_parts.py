#!/usr/bin/env python3
"""Why a graded model has the design value D it has: the grader's own per-target parts, recomputed (read-only).

Run it in custody on ONE graded model. It re-measures the model through the SAME code the grader used
(`private_evaluation_source.produce_dual_benchmark_input` -> the adapter's `measure` -> `pool_exam.measure_pool` ->
`pool_grader.grade_set`/`grade_target`), imported and not copied. Two of the grader's functions are wrapped, in this
process only, to record what they return (`pool_grader.grade_set`, `pool_exam.measure_pool`); nothing is changed, nothing is
written, and the grader does not know.

It exits 0 only when the recomputed D equals the stored D exactly (bit for bit, no tolerance). Otherwise it prints what
differs and exits 1 (a mismatch) or 2 (an input it cannot use).

    python -m scripts.dev.design_value_parts --inputs inputs.json [--binding private-evaluation-binding.json] [--json]

`inputs.json` names the custody files the grade was made from (paths; everything else is read from them):

    {"pack": {"root": DIR, "relative_path": "...", "digest": "sha256:...", "challenge": ID, "version": "x.y"},
     "public_root": DIR, "private_root": DIR,
     "entry": entry.json, "trusted_job": job.json, "registration": benchmark-registration.json,
     "references": references.json (a list), "evaluation_source_receipt": evaluation-source-receipt.json,
     "originals": {"inference_receipt_raw": file, "predictions_raw": file, ...},   # the graded originals, as bytes
     "timed_query": {"receipt_raw": file, "predictions_raw": file | null} | null,
     "single_call_raw": file | null, "timing_step": number, "copy_hotkey": str | null,
     "dual_measurement": dual-measurement.json}                                    # the stored D is read from it

What it prints (scalars only: no inputs, truth values, designs, picks as rows or pool rows):

  per set      C, the mean of the targets' d (the grader's `SetGrade.d`), and min(mean d, C), as `measure_pool` composes it
  per target   feasible, d, q, e, h and s_h (h = exp(-e / s_h)), reason, whether it reached the reference, queries used
               (the names are those of `pool_grader.TargetGrade`; s_h is `HonestyPolicy.scale` as the policy in force)
  per target   regret, marked "derived (not a grader output)": (s_ref - s_pick) / (s_ref - s_low), from the TargetSpec's
               own `s_ref`, `s_low`, `sign` and the pick's true objective value (so 1 - the unclipped q)
  and the stored D, the recomputed D, and, when `--binding` is given, the binding's design_benefit(s).
"""

from __future__ import annotations

import argparse
import contextlib
import json
import math
import statistics
import sys
from pathlib import Path

REPOSITORY = Path(__file__).resolve().parents[2]
if str(REPOSITORY) not in sys.path:
    sys.path.insert(0, str(REPOSITORY))

from carbon.scoring import pool_exam, pool_grader

D_METRIC = "verified_value_benefit"


class PartsError(ValueError):
    """An input this tool cannot use (never a candidate's score)."""


class Recorder:
    """What the grader returned while it ran: each set's `SetGrade` (with its specs) and the measure's result."""

    def __init__(self):
        self.sets = []
        self.measured = None
        self.agen_calls = (
            []
        )  # {"digests", "value", "alts"}: each A_gen the grader computed, and the same at other scales
        self.combine_calls = (
            []
        )  # (a, a_gen, rule): each A_gen combination the grader made
        self.picks = (
            []
        )  # per recorded set (with pick_values): each target's predicted and true outputs at its pick


@contextlib.contextmanager
def recording(agen_scale_sets=None, pick_values=False):
    """Wrap `pool_grader.grade_set` and `pool_exam.measure_pool` so their returns are recorded; restore on exit.

    ``agen_scale_sets`` (optional, a list of ``{output: scale}``) also records, for every A_gen the grader computes, the
    same A_gen at each of those scales (`pool_grader.agen_accuracy` on the SAME specs and predictions, called inside the
    wrapper while the model is still being served) and every A_gen combination, so `agen_sweep` can give A at stricter
    accuracy scales. ``pick_values`` also keeps, per target, the model's predicted outputs and the true outputs at the
    target's final pick (named scalars: no design, no row index). The grader's own result is unchanged.
    """
    recorder = Recorder()
    real_grade_set, real_measure_pool = pool_grader.grade_set, pool_exam.measure_pool
    real_agen, real_combine = pool_grader.agen_accuracy, pool_grader.combine_a

    def grade_set(specs, predict, optimizer, honesty):
        asked = {}

        def watching(conditions, designs):
            batch = predict(conditions, designs)
            for design, prediction in zip(designs, batch):
                asked[(repr(sorted(conditions.items())), tuple(design))] = prediction
            return batch

        grade = real_grade_set(
            specs, watching if pick_values else predict, optimizer, honesty
        )
        recorder.sets.append((tuple(specs), grade, honesty))
        if pick_values:
            recorder.picks.append(
                [
                    _pick_values(spec, target, asked)
                    for spec, target in zip(specs, grade.targets)
                ]
            )
        return grade

    def measure_pool(*args, **kwargs):
        recorder.measured = real_measure_pool(*args, **kwargs)
        return recorder.measured

    def agen_accuracy(specs, predict, scales):
        value = real_agen(specs, predict, scales)
        if agen_scale_sets:
            recorder.agen_calls.append(
                {
                    "digests": tuple(s.digest for s in specs),
                    "value": value,
                    "alts": [real_agen(specs, predict, s) for s in agen_scale_sets],
                }
            )
        return value

    def combine_a(a, a_gen, rule):
        recorder.combine_calls.append((a, a_gen, dict(rule)))
        return real_combine(a, a_gen, rule)

    pool_grader.grade_set, pool_exam.measure_pool = grade_set, measure_pool
    if agen_scale_sets:
        pool_grader.agen_accuracy, pool_grader.combine_a = agen_accuracy, combine_a
    try:
        yield recorder
    finally:
        pool_grader.grade_set, pool_exam.measure_pool = (
            real_grade_set,
            real_measure_pool,
        )
        pool_grader.agen_accuracy, pool_grader.combine_a = real_agen, real_combine


def agen_sweep(recorder, agen_scale_sets):
    """A of the recorded exam at each alternative A_gen scale set: ``[{"scales": set, "A": a}]`` (a mean over sets).

    The exam's A per set is ``combine_a(a_bank, mean A_gen, rule)`` (`pool_exam.measure_pool`), the LAST combinations the
    grader made (one per set, after the per-set scoring). Each is redone with the A_gen recomputed at the alternative scale
    on the same specs. Only the A_gen scale changes: a_bank, the rule and every prediction are the grader's own.
    """
    n = len(recorder.sets)
    if not recorder.agen_calls or len(recorder.combine_calls) < n or n == 0:
        raise PartsError("no A_gen sweep was recorded (recording(agen_scale_sets=...))")
    out = []
    for j, scales in enumerate(agen_scale_sets):
        values = []
        for (specs, _grade, _honesty), (a_bank, gen, rule) in zip(
            recorder.sets, recorder.combine_calls[-n:], strict=True
        ):
            digests = tuple(s.digest for s in specs)
            calls = [c for c in recorder.agen_calls if c["digests"] == digests]
            match = [c for c in calls if c["value"] == gen]
            if gen is None:
                values.append(a_bank)
                continue
            if not match:
                raise PartsError(
                    "a recorded A_gen does not match the exam's combination"
                )
            values.append(pool_grader.combine_a(a_bank, match[0]["alts"][j], rule))
        out.append({"scales": dict(scales), "A": statistics.fmean(values)})
    return out


def _pick_values(spec, target, asked):
    """``{output: {"predicted", "true"}}`` at the target's final pick, or None (no pick, or the pick was not predicted)."""
    if target.pick is None:
        return None
    key = (repr(sorted(spec.conditions.items())), tuple(spec.designs[target.pick]))
    predicted = asked.get(key)
    if predicted is None:
        return None
    return {
        name: {
            "predicted": float(predicted[name]),
            "true": float(spec.truths[target.pick][name]),
        }
        for name in spec.outputs
        if name in predicted
    }


def _regret(spec, grade):
    """(s_ref - s_pick) / (s_ref - s_low) from the TargetSpec's own fields; None when there is no pick."""
    if grade.pick is None:
        return None
    s_pick = spec.sign * spec.truths[grade.pick][spec.objective]
    return (spec.s_ref - s_pick) / (spec.s_ref - spec.s_low)


def parts(recorder):
    """The scalar parts of every set and target the grader recorded, in the order it graded them."""
    measured = recorder.measured
    if measured is None:
        raise PartsError("the measure did not reach the pool grade")
    c = ((measured.get("design_fidelity") or {}).get("C")) if measured else None
    sets = []
    for set_index, (specs, grade, honesty) in enumerate(recorder.sets):
        targets = []
        for spec, target in zip(specs, grade.targets, strict=True):
            targets.append(
                {
                    **(
                        {"pick": recorder.picks[set_index][len(targets)]}
                        if recorder.picks
                        else {}
                    ),
                    "target": target.digest.removeprefix("sha256:")[:16],
                    "feasible": target.feasible,
                    "reason": target.reason,
                    "d": target.d,
                    "q": target.q,
                    "e": target.e,
                    "s_h": honesty.scale,
                    "h": target.h,
                    "reached_reference": target.reached_reference,
                    "queries": target.queries,
                    "regret": _regret(spec, target),
                }
            )
        sets.append(
            {
                "mean_d": grade.d,
                "C": c,
                "min_mean_d_C": None if c is None else min(grade.d, c),
                "targets": targets,
            }
        )
    return sets


def recomputed_d(sets):
    """D as `measure_pool` composes it: the mean over sets of min(set mean d, C)."""
    if not sets or any(s["C"] is None for s in sets):
        raise PartsError("no C to compose D with")
    return statistics.fmean(s["min_mean_d_C"] for s in sets)


def _numbers_under(document, key):
    found = []

    def walk(value):
        if isinstance(value, dict):
            for name, inner in value.items():
                if name == key and isinstance(inner, (int, float)):
                    found.append(inner)
                elif name == "verified_value_benefit" and key == "design_benefit":
                    if isinstance(inner, dict) and isinstance(
                        inner.get("value"), (int, float)
                    ):
                        found.append(inner["value"])
                    else:
                        walk(inner)
                else:
                    walk(inner)
        elif isinstance(value, list):
            for inner in value:
                walk(inner)

    walk(document)
    return found


def stored_d(dual_measurement):
    """The D in a `dual-measurement.json` document: benchmark.models[0].measurements.verified_value_benefit.value."""
    try:
        value = dual_measurement["benchmark"]["models"][0]["measurements"][D_METRIC][
            "value"
        ]
    except (KeyError, IndexError, TypeError):
        raise PartsError("dual-measurement.json has no " + D_METRIC) from None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise PartsError("dual-measurement.json " + D_METRIC + " is not a number")
    return value


def binding_ds(binding):
    """Every design_benefit / verified_value_benefit number in a private-evaluation binding."""
    found = _numbers_under(binding, "design_benefit") + _numbers_under(
        binding, D_METRIC
    )
    if not found:
        raise PartsError("the binding names no design_benefit or " + D_METRIC)
    return found


def recompute(run_measure, stored, *, binding=None):
    """Run ``run_measure()`` (the grader's own measurement of the model) recorded, and compare D.

    Returns the report dict: ``sets``, ``stored_d``, ``recomputed_d``, ``measure_d``, ``binding_d`` (a list) and
    ``ok`` (every comparison exact). A gated model (a failed mandatory gate gives no pool grade) reports no sets and is
    ``ok`` only when the stored D is the 0.0 the grader gave it."""
    with recording() as recorder:
        run_measure()
    measured = recorder.measured
    report = {"stored_d": stored, "sets": [], "binding_d": [], "ok": False}
    if measured is None:
        raise PartsError("the measure did not reach the pool grade")
    report["measure_d"] = measured.get("D")
    if not recorder.sets:
        report["gated"] = True
        report["recomputed_d"] = measured.get("D")
        report["ok"] = stored == measured.get("D") == 0.0
        return report
    report["sets"] = parts(recorder)
    report["recomputed_d"] = recomputed_d(report["sets"])
    comparisons = [stored == report["recomputed_d"] == report["measure_d"]]
    if binding is not None:
        report["binding_d"] = binding_ds(binding)
        comparisons.append(all(value == stored for value in report["binding_d"]))
    report["ok"] = all(comparisons)
    return report


def _jsonable(value):
    """JSON has no inf/nan: a non-finite float (e.g. e of an infeasible pick) is written as its repr string."""
    if isinstance(value, float) and not math.isfinite(value):
        return repr(value)
    if isinstance(value, dict):
        return {name: _jsonable(inner) for name, inner in value.items()}
    if isinstance(value, list):
        return [_jsonable(inner) for inner in value]
    return value


def render(report):
    lines = []
    for index, one in enumerate(report["sets"], 1):
        lines.append(
            f"set {index}: C={one['C']!r} mean_d={one['mean_d']!r} min(mean_d,C)={one['min_mean_d_C']!r}"
        )
        for number, target in enumerate(one["targets"], 1):
            regret = target["regret"]
            lines.append(
                f"  target {index}.{number} [{target['target']}]: feasible={target['feasible']} reason={target['reason']}"
                f" d={target['d']!r} q={target['q']!r} e={target['e']!r} s_h={target['s_h']!r} h={target['h']!r}"
                f" reached_reference={target['reached_reference']} queries={target['queries']}"
                f" regret={'none' if regret is None else repr(regret)} (derived (not a grader output))"
            )
            for name, value in sorted((target.get("pick") or {}).items()):
                lines.append(
                    f"    pick {name}: predicted={value['predicted']!r} true={value['true']!r}"
                )
    if report.get("gated"):
        lines.append("gated: a mandatory gate failed, so the grader composed no pool D")
    lines.append(f"stored D     = {report['stored_d']!r}")
    lines.append(f"recomputed D = {report['recomputed_d']!r}")
    if report["binding_d"]:
        lines.append(f"binding D    = {report['binding_d']!r}")
    lines.append("MATCH" if report["ok"] else "MISMATCH")
    return "\n".join(lines)


# --- the custody loader ------------------------------------------------------------------------------------------------


def _read(path):
    return Path(path).read_bytes()


def _json(path):
    return json.loads(_read(path))


def load_run(manifest, base=None):
    """(run_measure, stored D, dual-measurement document) from an inputs manifest (see the module docstring)."""
    from carbon.challenge_validator.evaluation_pack import load_pack
    from carbon.scoring import private_evaluation_source as source

    base = Path(base or ".")

    def path(value):
        return base / value

    pack = manifest["pack"]
    selected = load_pack(
        Path(pack["root"]),
        pack["relative_path"],
        expected_digest=pack["digest"],
        challenge_id=pack["challenge"],
        challenge_version=pack["version"],
    )
    originals = {
        name: _read(path(file)) for name, file in manifest.get("originals", {}).items()
    }
    timed = manifest.get("timed_query")
    if timed is not None:
        originals["timed_query"] = {
            "receipt_raw": _read(path(timed["receipt_raw"])),
            "registered_sha256": timed["registered_sha256"],
            **(
                {"predictions_raw": _read(path(timed["predictions_raw"]))}
                if timed.get("predictions_raw")
                else {}
            ),
        }
    if "inference_pair_raw" in originals:
        import hashlib

        originals["inference_pair_sha256"] = (
            "sha256:" + hashlib.sha256(originals["inference_pair_raw"]).hexdigest()
        )
    single = manifest.get("single_call_raw")
    dual = _json(path(manifest["dual_measurement"]))

    def run_measure():
        return source.produce_dual_benchmark_input(
            selected_pack=selected,
            public_root=Path(manifest["public_root"]),
            private_root=Path(manifest["private_root"]),
            entry=_json(path(manifest["entry"])),
            trusted_job=_json(path(manifest["trusted_job"])),
            registration=_json(path(manifest["registration"])),
            references=_json(path(manifest["references"])),
            graph_originals=originals,
            evaluation_source_receipt_raw=_read(
                path(manifest["evaluation_source_receipt"])
            ),
            timing_step=float(manifest["timing_step"]),
            copy_hotkey=manifest.get("copy_hotkey"),
            single_call_raw=None if single is None else _read(path(single)),
        )

    return run_measure, stored_d(dual)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--inputs", required=True, type=Path)
    parser.add_argument("--binding", type=Path, default=None)
    parser.add_argument("--json", action="store_true", help="print the report as JSON")
    args = parser.parse_args(argv)
    try:
        manifest = json.loads(args.inputs.read_bytes())
        run_measure, stored = load_run(manifest, base=args.inputs.parent)
        binding = None if args.binding is None else _json(args.binding)
        report = recompute(run_measure, stored, binding=binding)
    except (OSError, ValueError, KeyError, TypeError) as refused:
        print(f"REFUSED: {type(refused).__name__}: {refused}", file=sys.stderr)
        return 2
    print(
        json.dumps(_jsonable(report), indent=2, sort_keys=True, allow_nan=False)
        if args.json
        else render(report)
    )
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
