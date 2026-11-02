"""SHORTCUT-GAP: the owner's three accuracy checks for one Challenge version, Challenge-neutral. CUSTODY, read-only, aggregates only.

The owner's accuracy rule (the accuracy-OOD minimum record, amendment 2) admits the strict min(in-range, out-of-range) accuracy for
a version when it shows three things. This read MEASURES them and reports the gaps; the bars ("poorly", "well above") are the owner's
values and are never set or judged here:

  (1) the registered shortcuts (fits, formulae, the engineer's shortcut) score poorly OUT of range;
  (2) the noise ceiling (a prediction off by exactly the reference U) sits well above them;
  (3) ONE default trained model (no tuning search) beats them IN range, or the training set provably covers the out-of-range
      physics (that alternative is a separate record: this read reports (3) as measured and says so when it does not hold).

    python shortcut_gap.py read CONFIG.json --out OUT.json

PROBE SET: the S4a probe set of `sep_read` (`sep_read.PROBE_SCHEMA`, `sep_read.load_probe_set`): cases with inputs, the reference's
decision-output truths, the region class (``in_train`` = in range, every other class = out of range) and the U record.

PREDICTIONS (`PREDICTIONS_SCHEMA`, one file per predictor, by sha256): {"schema", "challenge", "version", "name", "kind",
"probe_set_sha256", "outputs": [...], "rows": [[value, ...] | null, ...]}, one row per probe case in the probe set's order, in
the DECISION-output space (the truths' names). ``kind`` is "fit" | "formula" | "engineer_shortcut" | "default_model". A null row
is a case the predictor's validity gate refused: it scores the atom 0 and makes that predictor GATE_FAILED (the grader's rule).
The default model may instead be an ln_harness predict record with fit "default" (`sep_read.load_predictions`, raw rows derived
by the version's own binding).

CONFIG (every key required): probe_set, shortcuts: [{"predictions", "sha256"}, ...] (at least one), default_model:
{"predictions", "sha256"} | {"predict_record", "catalog_id", "fit": "default"}.

METRIC: the version's REGISTERED A_gen atom 1 / (1 + |err| / scale), averaged over a class's cases and outputs (`sep_read.class_rows`).
The noise ceiling of a class is that atom at |err| = U (per case, the U record's absolute or relative U). Where the version has no
registered A_gen scales the read reports |err|/U only (the ceiling is |err|/U = 1 by definition) and computes no atom gaps.
A class with n < 6 is INDICATIVE.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import statistics
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))
ROOT = HERE.parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import sep_read

SCHEMA = "carbon.exam-reads.shortcut-gap.v1"
PREDICTIONS_SCHEMA = "carbon.exam-reads.case-predictions.v1"
SHORTCUT_KINDS = ("fit", "formula", "engineer_shortcut")
CONFIG_KEYS = {"probe_set", "shortcuts", "default_model"}
IN_RANGE = "in_train"


class GapRefused(ValueError):
    def __init__(self, code):
        super().__init__(code)
        self.code = code


def _need(ok, code):
    if not ok:
        raise GapRefused(code)


def _sha(raw):
    return hashlib.sha256(raw).hexdigest()


def load_case_predictions(spec, document, probe_sha, *, kinds):
    """One predictor's rows (a row is None where its validity gate refused the case), bound to THIS probe set and to its file."""
    _need(
        type(spec) is dict and set(spec) == {"predictions", "sha256"},
        "config_predictions",
    )
    raw = Path(spec["predictions"]).read_bytes()
    _need(
        _sha(raw) == spec["sha256"].removeprefix("sha256:"), "predictions_file_changed"
    )
    body = json.loads(raw)
    outputs = sorted(document["cases"][0]["truth"])
    _need(
        type(body) is dict
        and set(body)
        == {
            "schema",
            "challenge",
            "version",
            "name",
            "kind",
            "probe_set_sha256",
            "outputs",
            "rows",
        }
        and body["schema"] == PREDICTIONS_SCHEMA,
        "predictions_shape",
    )
    _need(
        body["challenge"] == document["challenge"]
        and body["version"] == document["version"],
        "predictions_other_version",
    )
    _need(
        body["probe_set_sha256"].removeprefix("sha256:") == probe_sha,
        "predictions_other_probe_set",
    )
    _need(body["kind"] in kinds, "predictions_kind")
    _need(type(body["name"]) is str and body["name"], "predictions_name")
    _need(
        type(body["outputs"]) is list and sorted(body["outputs"]) == outputs,
        "predictions_outputs",
    )
    _need(
        type(body["rows"]) is list and len(body["rows"]) == len(document["cases"]),
        "predictions_row_count",
    )
    rows = []
    for row in body["rows"]:
        if row is None:
            rows.append(None)
            continue
        _need(
            type(row) is list
            and len(row) == len(body["outputs"])
            and all(sep_read._finite(v) for v in row),
            "predictions_row_invalid",
        )
        rows.append({k: float(v) for k, v in zip(body["outputs"], row, strict=True)})
    return body["name"], body["kind"], rows


def _default_model(spec, document, probe_sha):
    if type(spec) is dict and "predict_record" in spec:
        _need(spec.get("fit") == "default", "default_model_must_be_untuned")
        raw_rows, _record = sep_read.load_predictions(
            spec, document, sep_read.probe_digest(sep_read.probe_array(document))
        )
        return (
            f"default:{spec['catalog_id']}",
            "default_model",
            sep_read.derived(document, raw_rows),
        )
    return load_case_predictions(spec, document, probe_sha, kinds=("default_model",))


def noise_ceiling(document, scales, u):
    """Per class: the atom of a prediction off by exactly U on every output (|err|/U = 1 where no scales are registered)."""
    from carbon.scoring.design_fidelity import benefit

    outputs = sorted(document["cases"][0]["truth"])
    by = {}
    for case in document["cases"]:
        if scales is None:
            by.setdefault(case["class"], []).append(1.0)
            continue
        for k in outputs:
            by.setdefault(case["class"], []).append(
                benefit(sep_read._u(u[k], case["truth"][k]) / scales[k])
            )
    return {klass: statistics.fmean(values) for klass, values in sorted(by.items())}


def _accuracy(row, who):
    entry = row[who]
    return entry["accuracy"]


def read(config_path):
    config = json.loads(Path(config_path).read_bytes())
    _need(type(config) is dict and set(config) == CONFIG_KEYS, "config_shape")
    document, probe_sha = sep_read.load_probe_set(config["probe_set"])
    classes = sorted({c["class"] for c in document["cases"]})
    _need(
        IN_RANGE in classes and len(classes) >= 2,
        "probe_set_needs_in_range_and_out_of_range_classes",
    )
    _need(type(config["shortcuts"]) is list and config["shortcuts"], "config_shortcuts")
    predictions, kinds = {}, {}
    for spec in config["shortcuts"]:
        name, kind, rows = load_case_predictions(
            spec, document, probe_sha, kinds=SHORTCUT_KINDS
        )
        _need(name not in predictions, "predictor_name_twice")
        predictions[name], kinds[name] = rows, kind
    name, kind, rows = _default_model(config["default_model"], document, probe_sha)
    _need(name not in predictions, "predictor_name_twice")
    predictions[name], kinds[name] = rows, kind
    default = name
    shortcuts = [n for n in predictions if n != default]
    scales = sep_read.agen_scales(document["challenge"], document["version"])
    u = document["u_record"]["u"]
    per_class = sep_read.class_rows(document, predictions, scales, u)
    ceiling = noise_ceiling(document, scales, u)
    out_of_range = [c for c in classes if c != IN_RANGE]
    gated = {n: sum(r is None for r in predictions[n]) for n in predictions}
    rows = {}
    for klass in classes:
        row = per_class[klass]
        rows[klass] = {
            "n": row["n"],
            "status": row["status"],
            "range": "in" if klass == IN_RANGE else "out",
            "noise_ceiling": ceiling[klass],
            "predictors": {n: row[n] for n in predictions},
        }
    checks = None
    if scales is not None:

        def best_shortcut(klass):
            return max(_accuracy(per_class[klass], n) for n in shortcuts)

        checks = {
            "1_shortcuts_out_of_range": {
                n: {
                    "in_range": _accuracy(per_class[IN_RANGE], n),
                    "out_of_range": {
                        c: _accuracy(per_class[c], n) for c in out_of_range
                    },
                    "drop_in_minus_out": {
                        c: _accuracy(per_class[IN_RANGE], n)
                        - _accuracy(per_class[c], n)
                        for c in out_of_range
                    },
                }
                for n in shortcuts
            },
            "2_ceiling_minus_best_shortcut": {
                c: ceiling[c] - best_shortcut(c) for c in out_of_range
            },
            "3_default_minus_best_shortcut_in_range": _accuracy(
                per_class[IN_RANGE], default
            )
            - best_shortcut(IN_RANGE),
            "3_holds_as_measured": _accuracy(per_class[IN_RANGE], default)
            > best_shortcut(IN_RANGE)
            and not gated[default],
        }
    result = {
        "schema": SCHEMA,
        "status": "REPORT_FIELD_AGGREGATES_ONLY",
        "provisional": document["provisional"],
        "challenge": document["challenge"],
        "version": document["version"],
        "metric": (
            "registered A_gen atom 1/(1+|err|/scale)"
            if scales is not None
            else "no registered A_gen scales: |err|/U only (no atom gaps)"
        ),
        "bars": "owner values (poorly / well above): measured gaps only, never judged here",
        "predictors": {
            n: {
                "kind": kinds[n],
                "status": "GATE_FAILED" if gated[n] else "GRADED",
                "gate_failed_cases": gated[n],
            }
            for n in predictions
        },
        "default_model": default,
        "classes": rows,
        "checks": checks,
        "indicative_below_n": sep_read.INDICATIVE_BELOW,
        "identities": {
            "probe_set_sha256": probe_sha,
            "u_record": {
                "id": document["u_record"]["id"],
                "sha256": document["u_record"]["sha256"],
            },
            "predictions_sha256": sorted(
                s["sha256"]
                for s in [*config["shortcuts"], config["default_model"]]
                if "sha256" in s
            ),
        },
    }
    result["run_digest"] = "sha256:" + _sha(json.dumps(result, sort_keys=True).encode())
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)
    r = sub.add_parser("read")
    r.add_argument("config", type=Path)
    r.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        result = read(args.config)
    except (GapRefused, sep_read.SepRefused) as refused:
        print(f"STOP: {refused}", file=sys.stderr)
        return 2
    args.out.write_text(
        json.dumps(result, sort_keys=True, indent=1) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {k: result[k] for k in ("challenge", "version", "status", "run_digest")}
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
