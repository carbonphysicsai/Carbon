"""SEP-READ-01 (S4a): the learning-separation read of one Challenge version. CUSTODY, read-only, aggregates only.

Two contenders, both trained on the version's PUBLIC TRAIN only by the receipted two-phase LN harness
(`scripts/dev/learning_necessity/ln_harness.py`: the pod selects, custody `predict` retrains and predicts the probe inputs):
(K) the TRAIN-kernel interpolation reference (the tuned prior_krr entry) and (O) the best tuned catalog operator. They are
scored here on cases ALREADY solved outside TRAIN, per region class.

    python sep_read.py probe-npy PROBE_SET.json PROBE.npy --train-provenance TRAIN.provenance.json
                                      # the exact probe-input array ln_harness predict takes (TRAIN's column order)
    python sep_read.py read CONFIG.json --out OUT.json

PROBE SET (`PROBE_SCHEMA`, one closed custody document per version, assembled by DC / the TL; never leaves custody):
  {"schema", "challenge", "version", "provisional": bool, "input_names": [...],
   "u_record": {"id", "sha256", "u": {output: U | {"relative": r}}},
   "cases": [{"inputs": {name: value}, "truth": {output: value}, "class", "class_rule", "region_class", "source"}]}
  ``class`` is the S4a region class (in_train, inner_band, side_*, outer_shell, regime:*, neighbour task, ...), ``class_rule`` the
  rule that assigned it, ``region_class`` pool_grader.region_class's value for the case (in_train | extended_shell | regime:*),
  checked against the class (Validator 11-01: inner_band / in_train -> in_train; outer_shell / side_* -> extended_shell; regime:x
  -> regime:x); a contradiction STOPS. ``truth`` holds the derived decision outputs (the reference's L0 truths).

CONFIG (every key required):
  probe_set, kernel / operator: {"predict_record", "catalog_id", "fit": "tuned" | "default"}, koth_rebuild_noise,
  nearest_train: {"payload_dir", "region", "region_sha256", "train_npz", "train_provenance"}
  bootstrap_seed: the seed of the C1 paired bootstrap (recorded in the output)

Per class (Validator rulings 11-01):
- accuracy = the mean over the class's cases and outputs of the version's REGISTERED A_gen atom, 1 / (1 + |err| / scale), with the
  version's registered A_gen scales (`pool_version.registered_policies`); O - K is reported beside margin_N. Where the scales are not
  registered, no accuracy and no flag: |err|/U only;
- the median |err| / U per output for K and O (U from the probe set's U record; a relative U is relative to the true value);
- the flag "K loses by > margin_N AND O beats K", set ONLY for n >= 6 (n < 6 is INDICATIVE and never flagged);
- the nearest-TRAIN distance quantiles from DC's receipted nearest_train.py, run IN PLACE (its SHA256SUMS checked first).
Overall, the C1 gate's read (OWNER-ACCURACY-OOD-MIN-01 amendment, the Validator's "clearly"): the paired O - K atom balanced over the
out-of-range classes with n >= 6, its within-class paired bootstrap (2000 draws, ``bootstrap_seed`` recorded), and whether its 95 %
lower bound clears margin_N (`clear_win`).
Raw predictions become decision outputs through the version's own `pool_adapters.official_binding(...).derive`. No pass rule: report
fields only. No case, design, input, truth or prediction leaves: counts, classes and aggregates.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
import os
import re
import shutil
import statistics
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

PROBE_SCHEMA = "carbon.exam-reads.sep-probe-set.v1"
SCHEMA = "carbon.exam-reads.sep-read.v1"
PREDICT_SCHEMA = "carbon.ln-harness-predict.v1"
#: The receipted NEAREST_TRAIN_READ_20261101 payload (DC; Validator receipt 11-01).
NEAREST_TRAIN_SUMS = "923b662bf64d1fbabc2f265d7099fbd2f0734aa75f063a5759bcc6d3d894fae2"
INDICATIVE_BELOW = 6
CONFIG_KEYS = {
    "probe_set",
    "kernel",
    "operator",
    "koth_rebuild_noise",
    "nearest_train",
    "bootstrap_seed",
}
#: The C1 "clearly beats" read (OWNER-ACCURACY-OOD-MIN-01 amendment; the Validator's definition, no new constant).
BOOTSTRAP_DRAWS = 2000
CONTENDER_KEYS = {"predict_record", "catalog_id", "fit"}
NEAREST_KEYS = {
    "payload_dir",
    "region",
    "region_sha256",
    "train_npz",
    "train_provenance",
}
CASE_KEYS = {"inputs", "truth", "class", "class_rule", "region_class", "source"}
_CLASS = re.compile(r"[a-z0-9][a-z0-9_:.-]{0,63}")
_REGION = re.compile(r"in_train|extended_shell|regime:[a-z0-9_]+")
_SHA = re.compile(r"[0-9a-f]{64}")


class SepRefused(ValueError):
    def __init__(self, code):
        super().__init__(code)
        self.code = code


def _need(ok, code):
    if not ok:
        raise SepRefused(code)


def _sha_bytes(raw):
    return hashlib.sha256(raw).hexdigest()


def _finite(value):
    return (
        type(value) in (int, float)
        and not isinstance(value, bool)
        and math.isfinite(value)
    )


def region_agrees(klass, region):
    """The class cross-check (Validator 11-01, corrected): a case labelled ``in_train`` must have region class ``in_train``, and
    EVERY other label (the coverage plan's registered names regime:inner_band, regime:side_*, extended_shell, and the legacy
    inner_band / outer_shell / side_*) must have a region class other than ``in_train``: the registered inner band lies outside
    the TRAIN box."""
    return (klass == "in_train") == (region == "in_train")


def load_probe_set(path):
    """The closed probe set, or `SepRefused`. Every case carries every input and the same truth outputs; the class agrees with its
    region class."""
    raw = Path(path).read_bytes()
    document = json.loads(raw)
    _need(
        type(document) is dict
        and set(document)
        == {
            "schema",
            "challenge",
            "version",
            "provisional",
            "input_names",
            "u_record",
            "cases",
        }
        and document["schema"] == PROBE_SCHEMA,
        "probe_set_shape",
    )
    # PROVISIONAL: early probes from a region not yet signed (e.g. F08 2.0's UEDGE cases): the read is labelled so, end to end
    _need(type(document["provisional"]) is bool, "probe_set_provisional")
    names = document["input_names"]
    _need(
        type(names) is list
        and names
        and all(type(n) is str and n for n in names)
        and len(set(names)) == len(names),
        "probe_set_input_names",
    )
    u_record = document["u_record"]
    _need(
        type(u_record) is dict
        and set(u_record) == {"id", "sha256", "u"}
        and type(u_record["id"]) is str
        and u_record["id"]
        and type(u_record["sha256"]) is str
        and _SHA.fullmatch(u_record["sha256"].removeprefix("sha256:"))
        and type(u_record["u"]) is dict
        and u_record["u"],
        "probe_set_u_record",
    )
    for value in u_record["u"].values():
        _need(
            (_finite(value) and value > 0)
            or (
                type(value) is dict
                and set(value) == {"relative"}
                and _finite(value["relative"])
                and value["relative"] > 0
            ),
            "probe_set_u_value",
        )
    cases = document["cases"]
    _need(type(cases) is list and cases, "probe_set_cases")
    outputs = None
    for case in cases:
        _need(type(case) is dict and set(case) == CASE_KEYS, "probe_set_case_shape")
        _need(
            type(case["inputs"]) is dict
            and set(case["inputs"]) == set(names)
            and all(_finite(v) for v in case["inputs"].values()),
            "probe_set_case_inputs",
        )
        truth = case["truth"]
        _need(
            type(truth) is dict and truth and all(_finite(v) for v in truth.values()),
            "probe_set_case_truth",
        )
        outputs = set(truth) if outputs is None else outputs
        _need(
            set(truth) == outputs and outputs <= set(u_record["u"]),
            "probe_set_case_outputs",
        )
        _need(
            type(case["class"]) is str and _CLASS.fullmatch(case["class"]),
            "probe_set_case_class",
        )
        _need(
            type(case["class_rule"]) is str and case["class_rule"],
            "probe_set_case_class_rule",
        )
        _need(type(case["source"]) is str and case["source"], "probe_set_case_source")
        _need(
            type(case["region_class"]) is str
            and _REGION.fullmatch(case["region_class"]),
            "probe_set_case_region_class",
        )
        _need(
            region_agrees(case["class"], case["region_class"]),
            "class_contradicts_region_class:" + case["class"],
        )
    return document, _sha_bytes(raw)


def check_train_order(document, provenance_path):
    """ln_harness predict reads the probe columns in the TRAIN artifact's order: the probe set's input_names must BE that order."""
    provenance = json.loads(Path(provenance_path).read_bytes())
    names = provenance.get("numeric_interface", {}).get("input_names")
    _need(names == document["input_names"], "probe_set_input_order_differs_from_train")


def probe_array(document):
    """The probe inputs as ln_harness predict reads them: float64, one row per case, in the probe set's input order."""
    import numpy as np

    return np.asarray(
        [
            [float(case["inputs"][n]) for n in document["input_names"]]
            for case in document["cases"]
        ],
        dtype=np.float64,
    )


def probe_digest(probe):
    """ln_harness.probe_digest, exactly: the sha256 of the array's contiguous bytes."""
    import numpy as np

    return "sha256:" + _sha_bytes(np.ascontiguousarray(probe).tobytes())


def load_predictions(spec, document, digest):
    """One contender's raw prediction rows from an ln_harness predict record, bound to THIS probe set by its inputs digest and to
    its own file by sha256."""
    import numpy as np

    _need(
        type(spec) is dict
        and set(spec) == CONTENDER_KEYS
        and spec["fit"] in ("tuned", "default"),
        "config_contender",
    )
    path = Path(spec["predict_record"])
    record = json.loads(path.read_bytes())
    _need(
        record.get("schema") == PREDICT_SCHEMA and record.get("truths_read") is False,
        "predict_record_schema",
    )
    _need(
        record.get("challenge")
        == {"id": document["challenge"], "version": document["version"]},
        "predict_record_other_version",
    )
    _need(
        record.get("probe_inputs_sha256") == digest, "predict_record_other_probe_inputs"
    )
    _need(
        record.get("probe_rows") == len(document["cases"]), "predict_record_row_count"
    )
    found = [
        c
        for c in record.get("contenders", [])
        if c.get("catalog_id") == spec["catalog_id"]
    ]
    _need(len(found) == 1, "predict_record_contender:" + spec["catalog_id"])
    export = found[0].get("exports", {}).get(spec["fit"])
    _need(type(export) is dict, "predict_record_export:" + spec["fit"])
    raw = (path.parent / export["file"]).read_bytes()
    _need("sha256:" + _sha_bytes(raw) == export["sha256"], "prediction_file_changed")
    import io

    rows = np.load(io.BytesIO(raw), allow_pickle=False)
    _need(
        rows.ndim == 2
        and rows.shape[0] == len(document["cases"])
        and np.isfinite(rows).all(),
        "prediction_shape",
    )
    return [[float(v) for v in row] for row in rows], record


def derived(document, rows):
    """Each case's raw prediction row as the version's decision outputs (`official_binding(...).derive`)."""
    from carbon.scoring import pool_adapters, pool_version

    kind = pool_version.KINDS.get(document["challenge"])
    _need(kind is not None, "challenge_has_no_pool_kind")
    binding = pool_adapters.official_binding(kind, document["version"])
    _need(
        set(binding.input_names) == set(document["input_names"]),
        "probe_set_input_names_differ_from_the_binding",
    )
    outputs = set(document["cases"][0]["truth"])
    out = []
    for case, row in zip(document["cases"], rows, strict=True):
        prediction = binding.derive(dict(case["inputs"]), list(row))
        _need(
            type(prediction) is dict and outputs <= set(prediction),
            "derive_lacks_a_truth_output",
        )
        _need(
            all(_finite(prediction[k]) for k in outputs),
            "derived_prediction_not_finite",
        )
        out.append({k: float(prediction[k]) for k in outputs})
    return out


def agen_scales(challenge, version):
    """The version's REGISTERED A_gen scales, or None when the version has none registered (then no accuracy and no flag)."""
    from carbon.scoring import pool_version

    try:
        return dict(pool_version.registered_policies(challenge, version).agen_scales)
    except pool_version.PoolConstantsNotRegistered:
        return None


def margin_n(path, challenge):
    raw = Path(path).read_bytes()
    entry = json.loads(raw).get("challenges", {}).get(challenge)
    _need(type(entry) is dict and _finite(entry.get("value")), "margin_n_unregistered")
    return float(entry["value"]), _sha_bytes(raw)


def _u(u, truth):
    from carbon.scoring import pool_grader

    return pool_grader.u_value(u, truth)


def class_rows(document, predictions, scales, u):
    """Per class: n, the K / O accuracy (or None) and the median |err|/U per output. ``predictions`` = {"K": [...], "O": [...]}."""
    from carbon.scoring.design_fidelity import benefit

    by = {}
    for index, case in enumerate(document["cases"]):
        by.setdefault(case["class"], []).append(index)
    outputs = sorted(document["cases"][0]["truth"])
    if scales is not None:
        _need(
            set(outputs) <= set(scales)
            and all(_finite(scales[k]) and scales[k] > 0 for k in outputs),
            "agen_scales_must_cover_the_outputs",
        )
    out = {}
    for klass, indices in sorted(by.items()):
        row = {
            "n": len(indices),
            "status": "INDICATIVE" if len(indices) < INDICATIVE_BELOW else "REPORT",
        }
        for who, rows in sorted(predictions.items()):
            errors = {
                k: [abs(rows[i][k] - document["cases"][i]["truth"][k]) for i in indices]
                for k in outputs
            }
            row[who] = {
                "median_err_over_in_range_u": {
                    k: statistics.median(
                        errors[k][j] / _u(u[k], document["cases"][i]["truth"][k])
                        for j, i in enumerate(indices)
                    )
                    for k in outputs
                },
                "accuracy": (
                    None
                    if scales is None
                    else statistics.fmean(
                        benefit(errors[k][j] / scales[k])
                        for j in range(len(indices))
                        for k in outputs
                    )
                ),
            }
        out[klass] = row
    return out


def paired_atoms(document, predictions, scales):
    """Per case, the paired O - K difference of the registered A_gen atom (each case's mean over its outputs)."""
    from carbon.scoring.design_fidelity import benefit

    outputs = sorted(document["cases"][0]["truth"])

    def atom(rows, index, truth):
        return statistics.fmean(
            benefit(abs(rows[index][k] - truth[k]) / scales[k]) for k in outputs
        )

    return [
        atom(predictions["O"], index, case["truth"])
        - atom(predictions["K"], index, case["truth"])
        for index, case in enumerate(document["cases"])
    ]


def _quantile(values, q):
    ordered = sorted(values)
    position = q * (len(ordered) - 1)
    low = int(position)
    high = min(low + 1, len(ordered) - 1)
    return ordered[low] + (ordered[high] - ordered[low]) * (position - low)


def clear_win(document, predictions, scales, margin, seed):
    """The C1 gate's read: does a trained operator CLEARLY beat the TRAIN-kernel out of range? The statistic is the paired O - K
    registered A_gen atom, balanced (the mean of class means) over the OUT-OF-RANGE classes (every class but in_train) with n >= 6;
    its paired bootstrap resamples cases WITHIN each class (``BOOTSTRAP_DRAWS`` draws, ``seed`` recorded). ``clear`` is the lower
    end: the ONE-SIDED 95 % lower bound (q 0.05) > margin_N (Validator 11-01); the two-sided bound (q 0.025) is reported beside it. No eligible
    class, or no registered scales: not computed (no clear win)."""
    import random

    if scales is None:
        return {
            "computed": False,
            "reason": "no registered A_gen scales",
            "clear": False,
        }
    diffs = paired_atoms(document, predictions, scales)
    by = {}
    for index, case in enumerate(document["cases"]):
        if case["class"] != "in_train":
            by.setdefault(case["class"], []).append(diffs[index])
    eligible = {k: v for k, v in sorted(by.items()) if len(v) >= INDICATIVE_BELOW}
    if not eligible:
        return {
            "computed": False,
            "reason": "no out-of-range class with n >= 6",
            "clear": False,
        }
    statistic = statistics.fmean(statistics.fmean(v) for v in eligible.values())
    draw = random.Random(seed)
    boots = []
    for _ in range(BOOTSTRAP_DRAWS):
        boots.append(
            statistics.fmean(
                statistics.fmean(draw.choice(v) for _ in v) for v in eligible.values()
            )
        )
    lower_two_sided, lower_one_sided = _quantile(boots, 0.025), _quantile(boots, 0.05)
    return {
        "computed": True,
        "classes": sorted(eligible),
        "n_classes": len(eligible),
        "statistic": statistic,
        "lower95_two_sided": lower_two_sided,
        "lower95_one_sided": lower_one_sided,
        "margin_n": margin,
        "draws": BOOTSTRAP_DRAWS,
        "seed": seed,
        "clear": lower_one_sided > margin,
    }


def flag(row, margin):
    """K loses by > margin_N AND O beats K, for n >= 6 with registered scales; None (not computed) otherwise."""
    k, o = row["K"]["accuracy"], row["O"]["accuracy"]
    if k is None or o is None or row["n"] < INDICATIVE_BELOW:
        return None
    return (o - k) > margin and o > k


def _sums_ok(payload_dir):
    raw = (Path(payload_dir) / "SHA256SUMS").read_bytes()
    _need(
        _sha_bytes(raw) == NEAREST_TRAIN_SUMS,
        "nearest_train_sums_not_the_receipted_ones",
    )
    for line in raw.decode("utf-8").splitlines():
        if not line.strip():
            continue
        digest, name = line.split(maxsplit=1)
        name = name.lstrip("*").removeprefix("./")
        _need(
            _sha_bytes((Path(payload_dir) / name).read_bytes()) == digest,
            "nearest_train_file_changed:" + name,
        )


def nearest_train(cfg, document):
    """DC's receipted nearest_train.build, run IN PLACE, once per S4a class: each class's probe designs go to a private temporary
    pool-source document carrying the case's region class, and the class keeps the summary nearest_train returns. Deleted after.
    """
    _need(type(cfg) is dict and set(cfg) == NEAREST_KEYS, "config_nearest_train")
    _sums_ok(cfg["payload_dir"])
    spec = importlib.util.spec_from_file_location(
        "nearest_train", Path(cfg["payload_dir"]) / "nearest_train.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    by = {}
    for case in document["cases"]:
        by.setdefault(case["class"], []).append(case)
    out = {}
    scratch = Path(tempfile.mkdtemp(prefix="sep-read-"))
    os.chmod(scratch, 0o700)
    try:
        for klass, cases in sorted(by.items()):
            regions = {c["region_class"] for c in cases}
            _need(len(regions) == 1, "class_spans_region_classes:" + klass)
            folder = scratch / f"c{len(out)}"
            folder.mkdir(mode=0o700)
            names = list(document["input_names"])
            (folder / "pool-source-probe.json").write_text(
                json.dumps(
                    {
                        "region": regions.pop(),
                        "conditions": {"fixed": {}},
                        "design_names": names,
                        "designs": [
                            [float(c["inputs"][n]) for n in names] for c in cases
                        ],
                    }
                ),
                encoding="utf-8",
            )
            result = module.build(
                {
                    "region": cfg["region"],
                    "region_sha256": cfg["region_sha256"],
                    "train_npz": cfg["train_npz"],
                    "train_provenance": cfg["train_provenance"],
                    "pool_sources": [str(folder)],
                }
            )
            (summary,) = result["classes"].values()
            out[klass] = summary
        return out, (
            {"train_sha256": result["train_sha256"], "units": result["units"]}
            if out
            else {}
        )
    finally:
        shutil.rmtree(scratch, ignore_errors=True)


def read(config_path):
    config = json.loads(Path(config_path).read_bytes())
    _need(type(config) is dict and set(config) == CONFIG_KEYS, "config_shape")
    document, probe_sha = load_probe_set(config["probe_set"])
    _need(
        type(config["nearest_train"]) is dict
        and "train_provenance" in config["nearest_train"],
        "config_nearest_train",
    )
    check_train_order(document, config["nearest_train"]["train_provenance"])
    digest = probe_digest(probe_array(document))
    predictions, records = {}, {}
    for who, key in (("K", "kernel"), ("O", "operator")):
        rows, record = load_predictions(config[key], document, digest)
        predictions[who] = derived(document, rows)
        records[who] = {
            "catalog_id": config[key]["catalog_id"],
            "fit": config[key]["fit"],
            "grid_digest": record.get("grid_digest"),
        }
    scales = agen_scales(document["challenge"], document["version"])
    margin, noise_sha = margin_n(config["koth_rebuild_noise"], document["challenge"])
    classes = class_rows(document, predictions, scales, document["u_record"]["u"])
    distances, train = nearest_train(config["nearest_train"], document)
    for klass, row in classes.items():
        row["k_loses_and_o_wins"] = flag(row, margin)
        if row["K"]["accuracy"] is not None:
            row["o_minus_k"] = row["O"]["accuracy"] - row["K"]["accuracy"]
        row["nearest_train"] = distances[klass]
    seed = config["bootstrap_seed"]
    _need(type(seed) is int and not isinstance(seed, bool), "config_bootstrap_seed")
    c1 = clear_win(document, predictions, scales, margin, seed)
    everything = {"n": len(document["cases"]), "K": None, "O": None}
    if scales is not None:
        whole = class_rows(
            {**document, "cases": [{**c, "class": "all"} for c in document["cases"]]},
            predictions,
            scales,
            document["u_record"]["u"],
        )["all"]
        everything.update(
            K=whole["K"]["accuracy"],
            O=whole["O"]["accuracy"],
            o_minus_k=whole["O"]["accuracy"] - whole["K"]["accuracy"],
        )
    result = {
        "schema": SCHEMA,
        "status": "REPORT_FIELD_AGGREGATES_ONLY",
        "provisional": document["provisional"],
        "challenge": document["challenge"],
        "version": document["version"],
        "contenders": records,
        "u_scope": (
            "in-range U: one U per set from the probe set's U record"
            " (a per-class U comes when the ext-U records land)"
        ),
        "accuracy": (
            "registered A_gen atom 1/(1+|err|/scale)"
            if scales is not None
            else "no registered A_gen scales: |err|/U only"
        ),
        "margin_n": margin,
        "indicative_below_n": INDICATIVE_BELOW,
        "classes": classes,
        "overall": everything,
        "c1_clear_win": c1,
        "identities": {
            "probe_set_sha256": probe_sha,
            "probe_inputs_sha256": digest,
            "u_record": {
                "id": document["u_record"]["id"],
                "sha256": document["u_record"]["sha256"],
            },
            "koth_rebuild_noise_sha256": noise_sha,
            "nearest_train_sums": NEAREST_TRAIN_SUMS,
            **train,
        },
    }
    result["run_digest"] = "sha256:" + _sha_bytes(
        json.dumps(
            {
                "result": result,
                "script_sha256": _sha_bytes(Path(__file__).read_bytes()),
            },
            sort_keys=True,
        ).encode()
    )
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    commands = parser.add_subparsers(dest="command", required=True)
    npy = commands.add_parser("probe-npy")
    npy.add_argument("probe_set", type=Path)
    npy.add_argument("out", type=Path)
    npy.add_argument("--train-provenance", type=Path, required=True)
    run = commands.add_parser("read")
    run.add_argument("config", type=Path)
    run.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "probe-npy":
            import numpy as np

            document, _ = load_probe_set(args.probe_set)
            check_train_order(document, args.train_provenance)
            probe = probe_array(document)
            _need(not args.out.exists(), "output_exists")
            np.save(args.out, probe, allow_pickle=False)
            print(
                json.dumps(
                    {"probe_inputs_sha256": probe_digest(probe), "rows": len(probe)}
                )
            )
            return 0
        _need(not args.out.exists(), "output_exists")
        result = read(args.config)
    except SepRefused as refused:
        print(f"STOP: {refused.code}", file=sys.stderr)
        return 3
    args.out.write_bytes((json.dumps(result, indent=1, sort_keys=True) + "\n").encode())
    print(json.dumps({"out": str(args.out), "run_digest": result["run_digest"]}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
