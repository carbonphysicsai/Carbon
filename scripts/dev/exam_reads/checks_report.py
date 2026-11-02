"""CHECKS 1-3 REPORT (OWNER-ACCURACY-OOD-MIN-01 amendment 2): the Validator's one report format, rev 2 (`CHECKS_1_3_REPORT_FORMAT`
sha e4487c4e), schema ``carbon.checks-1-3-report.v1``. CUSTODY scratch, never official; aggregates only.

Every contender (the pre-registered panel and the default model, rows in bank order) is regraded through the receipted
`q3_q8_whatif.Regrader` with the A_gen recorder; each A_gen point's class is the receipted geometric-v1 rule inside the
registered coverage plan (`q3_q8_whatif._class_source`). Per class and contender: n, gate failures, the mean A_gen atom, the
median and p90 of |err|/U per output, the Monte-Carlo U ceiling (each output perturbed uniformly on [-U, +U], scored by the
grader's own atom), and the class's normalised distance to TRAIN. The three checks' gaps carry within-class bootstrap 95 %
intervals and are also given in score steps (`grade_feedback.step`). No bar and no pass/fail: the owner sets every bar.

Usage: ``checks_report.py --config CONFIG.json --inputs REPORT_INPUTS.json --out DIR`` writes ``checks-1-3-report.json`` and
``checks-1-3-report.md``.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import statistics
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

import q3_q8_whatif as reads

SCHEMA = "carbon.checks-1-3-report.v1"
#: The Validator's 04:28 condition (b): report runs use 2000 draws for the bootstrap and the ceiling.
DRAWS = 2000
IN_TRAIN = "in_train"
DEFAULT = "default_model"
GENERIC = ("gp", "poly_ridge", "rbf_ridge", "gbt", "knn")
#: The rev-2 panel roles (`king_replay:<id>` is matched by prefix).
PANEL_ROLES = ("engineer_shortcut", *GENERIC, "sparse_physics")
FITS = ("default", "tuned", "registered-cheap")
INPUT_KEYS = frozenset(
    {
        "header",
        "panel_file",
        "contenders",
        "class_source",
        "train_inputs",
        "bootstrap_seed",
        "ceiling_seed",
    }
)
HEADER_KEYS = frozenset(
    {"train_version", "probe_set", "u_record", "tool_commit", "coverage_table"}
)
CONTENDER_KEYS = frozenset(
    {"role", "catalog_id", "fit", "record_sha256", "rows_npy", "sha256"}
)
#: nearest_train's distance: TRAIN's own per-column min-max scaling, then the Euclidean distance over sqrt(columns).
NEAREST_RULE = "train_minmax_euclidean_over_sqrt_dim"

_need = reads._need
ReadRefused = reads.ReadRefused


def _sha_file(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _hex(value):
    return type(value) is str and len(value.removeprefix("sha256:")) == 64


def _role_ok(role):
    if role == DEFAULT or role in PANEL_ROLES:
        return True
    return (
        type(role) is str
        and role.startswith("king_replay:")
        and len(role) > len("king_replay:")
    )


def load_inputs(path):
    """The report inputs (every key required, nothing extra): ``header`` {train_version {version, name, sha256}, probe_set
    {sha256, provisional}, u_record {id, sha256}, tool_commit, coverage_table {sha256, receipt} or null}; ``panel_file`` {path,
    sha256} (the pre-registered panel definitions); ``contenders`` [{role, catalog_id, fit, record_sha256, rows_npy, sha256}]
    with exactly one ``default_model``; ``class_source`` (as ACC-NOISE: the geometric-v1 rule, region and coverage plan by sha);
    ``train_inputs`` {npy, columns, sha256}; ``bootstrap_seed``, ``ceiling_seed``."""
    doc = json.loads(Path(path).read_bytes())
    _need(type(doc) is dict and set(doc) == INPUT_KEYS, "report_inputs_shape")
    header = doc["header"]
    _need(type(header) is dict and set(header) == HEADER_KEYS, "report_header_shape")
    train = header["train_version"]
    _need(
        type(train) is dict
        and set(train) == {"version", "name", "sha256"}
        and _hex(train["sha256"]),
        "report_train_version",
    )
    probe = header["probe_set"]
    _need(
        type(probe) is dict
        and set(probe) == {"sha256", "provisional"}
        and _hex(probe["sha256"])
        and type(probe["provisional"]) is bool,
        "report_probe_set",
    )
    u_record = header["u_record"]
    _need(
        type(u_record) is dict
        and set(u_record) == {"id", "sha256"}
        and type(u_record["id"]) is str
        and _hex(u_record["sha256"]),
        "report_u_record",
    )
    _need(
        type(header["tool_commit"]) is str and len(header["tool_commit"]) == 40,
        "report_tool_commit",
    )
    table = header["coverage_table"]
    _need(
        table is None
        or (
            type(table) is dict
            and set(table) == {"sha256", "receipt"}
            and _hex(table["sha256"])
            and type(table["receipt"]) is str
        ),
        "report_coverage_table",
    )
    panel = doc["panel_file"]
    _need(
        type(panel) is dict
        and set(panel) == {"path", "sha256"}
        and Path(panel["path"]).is_file()
        and _sha_file(panel["path"]) == panel["sha256"].removeprefix("sha256:"),
        "report_panel_file_sha256",
    )
    contenders = doc["contenders"]
    _need(type(contenders) is list and contenders, "report_contenders")
    roles = set()
    for entry in contenders:
        _need(
            type(entry) is dict
            and set(entry) == CONTENDER_KEYS
            and _role_ok(entry["role"])
            and entry["role"] not in roles
            and entry["fit"] in FITS
            and type(entry["catalog_id"]) is str
            and _hex(entry["record_sha256"]),
            "report_contender_entry",
        )
        roles.add(entry["role"])
    _need(DEFAULT in roles and len(roles) >= 2, "report_needs_default_and_a_panel")
    train_inputs = doc["train_inputs"]
    _need(
        type(train_inputs) is dict
        and set(train_inputs) == {"npy", "columns", "sha256"}
        and type(train_inputs["columns"]) is list
        and train_inputs["columns"]
        and all(type(c) is str for c in train_inputs["columns"]),
        "report_train_inputs",
    )
    _need(
        all(type(doc[k]) is int for k in ("bootstrap_seed", "ceiling_seed")),
        "report_seeds",
    )
    return doc


def train_matrix(spec):
    """TRAIN's inputs (rows x the named columns), read only after the file's sha256 matches."""
    import numpy as np

    raw = Path(spec["npy"]).read_bytes()
    _need(
        hashlib.sha256(raw).hexdigest() == spec["sha256"].removeprefix("sha256:"),
        "report_train_inputs_sha256",
    )
    import io

    matrix = np.load(io.BytesIO(raw), allow_pickle=False)
    _need(
        matrix.ndim == 2
        and matrix.shape[0] > 0
        and matrix.shape[1] == len(spec["columns"])
        and np.isfinite(matrix).all(),
        "report_train_inputs_shape",
    )
    return np.asarray(matrix, dtype=float)


def nearest_train(points, train, columns):
    """Per class: min / median / p90 / max over its points of the normalised distance to the nearest TRAIN row
    (`NEAREST_RULE`). A point lacking a TRAIN column is refused, never defaulted."""
    import numpy as np

    lo, hi = train.min(axis=0), train.max(axis=0)
    width = np.where(hi > lo, hi - lo, 1.0)
    scaled = (train - lo) / width
    by = {}
    for cls, inputs in points:
        _need(set(columns) <= set(inputs), "report_point_lacks_a_train_column")
        x = (np.array([float(inputs[c]) for c in columns]) - lo) / width
        d = float(np.sqrt(((scaled - x) ** 2).sum(axis=1).min() / len(columns)))
        by.setdefault(cls, []).append(d)
    return {
        cls: {
            "min": min(v),
            "median": statistics.median(v),
            "p90": reads.quantile(v, 0.9),
            "max": max(v),
        }
        for cls, v in sorted(by.items())
    }


def _recorder(pool_grader, sink, scales):
    """`pool_grader.agen_accuracy` unchanged, recording each A_gen point once: its atom (the grader's own benefit of |err| / scale,
    averaged over the outputs; None when no scales are registered) and its |err| / U per output (U = `pool_grader.u_value` of the
    target's registered U at the truth). The same tap as `q3_q8_whatif._recording_agen`, plus |err| / U.
    """
    real = pool_grader.agen_accuracy
    seen = set()

    def recording(specs, predict, agen_scales, **kwargs):
        calls = []

        def tap(conditions, designs):
            batch = predict(conditions, designs)
            calls.append(batch)
            return batch

        value = real(specs, tap, agen_scales, **kwargs)
        with_slice = [spec for spec in specs if spec.agen]
        _need(len(calls) == len(with_slice), "agen_predict_calls_differ")
        for spec, batch in zip(with_slice, calls, strict=True):
            for index, prediction in zip(spec.agen, batch, strict=True):
                key = (spec.target_id, index)
                if key in seen:
                    continue
                seen.add(key)
                truth = spec.truths[index]
                err = {k: abs(prediction[k] - truth[k]) for k in spec.outputs}
                sink.append(
                    {
                        "target_id": spec.target_id,
                        "conditions": spec.conditions,
                        "design": list(spec.designs[index]),
                        "atom": (
                            None
                            if scales is None
                            else statistics.fmean(
                                pool_grader.benefit(err[k] / scales[k])
                                for k in spec.outputs
                            )
                        ),
                        "err_over_u": {
                            k: err[k] / pool_grader.u_value(spec.u[k], truth[k])
                            for k in spec.outputs
                        },
                    }
                )
        return value

    return recording


def ceiling_atoms(specs, scales, *, draws, seed):
    """Each A_gen point's Monte-Carlo U-ceiling atom: the truth with every output perturbed independently and uniformly on
    [-U, +U], scored by the grader's own atom formula, averaged over ``draws`` (``{(target_id, index): atom}``).
    """
    import random

    from carbon.scoring import pool_grader

    out = {}
    for spec in specs:
        for index in spec.agen:
            truth = spec.truths[index]
            rng = random.Random(f"{seed}:{spec.target_id}:{index}")
            u = {k: pool_grader.u_value(spec.u[k], truth[k]) for k in spec.outputs}
            atoms = [
                statistics.fmean(
                    pool_grader.benefit(abs(rng.uniform(-1.0, 1.0) * u[k]) / scales[k])
                    for k in spec.outputs
                )
                for _ in range(draws)
            ]
            out[spec.target_id, index] = statistics.fmean(atoms)
    return out


def _gap(a, b, *, step, draws, seed, sign=1.0):
    """``mean(a) - mean(b)`` (atoms), with its bootstrap 95 % interval (each side resampled within itself) and the same in steps."""
    import numpy as np

    if not a or not b:
        return None
    value = sign * (statistics.fmean(a) - statistics.fmean(b))
    rng = np.random.default_rng(seed)
    aa, bb = np.asarray(a), np.asarray(b)
    reps = np.array(
        [
            sign
            * (
                aa[rng.integers(0, aa.size, aa.size)].mean()
                - bb[rng.integers(0, bb.size, bb.size)].mean()
            )
            for _ in range(draws)
        ]
    )
    lo, hi = (float(x) for x in np.quantile(reps, [0.025, 0.975]))
    return {
        "value": value,
        "ci95": [lo, hi],
        "steps": value / step,
        "ci95_steps": [lo / step, hi / step],
    }


def run_report(config, config_path, inputs_path, *, keep=None):
    """The report document (see the module docstring). ``keep`` (a dict), if given, receives the classed point inputs, TRAIN and
    its columns for `g_reports` (custody memory only: never written into the report)."""
    import acc_noise

    from carbon.scoring import grade_feedback, pool_grader, pool_version

    doc = load_inputs(inputs_path)
    klass, region, allowed, identities = reads._class_source(doc["class_source"])
    regrader = reads.Regrader(config)
    classes, _order = regrader.sets_and_classes()
    policies = pool_version.registered_policies(config["challenge"], config["version"])
    scales = policies.agen_scales
    step = grade_feedback.step(config["margin_n"])
    n_rows = len(regrader.graded.bank["inputs"])
    material = regrader.graded.bank[pool_version.POOL_KEY]
    design_names = list(material["design_names"])
    names = sorted(region["base"])
    train = train_matrix(doc["train_inputs"])
    columns = doc["train_inputs"]["columns"]

    per = {}
    point_class = None
    point_inputs = None
    for entry in doc["contenders"]:
        rows = reads._contender_rows(
            {"rows_npy": entry["rows_npy"], "sha256": entry["sha256"]}, n_rows
        )
        sink = []
        with reads._patched(
            pool_grader, "agen_accuracy", _recorder(pool_grader, sink, scales)
        ):
            result = regrader.grade(
                rows, f"checks:{entry['role']}", classes=classes, slacks=True
            )
        slack = result["physics_slack"]
        failed = slack["schema_failed"] + sum(
            law["fail"] for law in slack["laws"].values() if law is not None
        )
        gated = result["basis"] is None or result["basis"].get("gated") is not False
        if not gated:
            inputs = [
                {
                    **p["conditions"]["fixed"],
                    **dict(zip(design_names, p["design"], strict=True)),
                }
                for p in sink
            ]
            try:
                cls = acc_noise.point_classes(
                    inputs, klass=klass, region=region, names=names, allowed=allowed
                )
            except acc_noise.AccNoiseRefused as refused:
                raise ReadRefused(refused.code) from refused
            keys = [(p["target_id"], tuple(p["design"])) for p in sink]
            if point_class is None:
                point_class, point_inputs, point_keys = cls, inputs, keys
            _need(keys == point_keys, "report_points_differ_between_contenders")
        per[entry["role"]] = {
            "entry": entry,
            "status": result["status"],
            "gates": result["gates"],
            "gate_failed": failed,
            "points": None if gated else list(zip(point_class, sink, strict=True)),
        }
    _need(point_class is not None, "report_every_contender_gated")
    class_order = [IN_TRAIN] + sorted(c for c in set(point_class) if c != IN_TRAIN)

    ceiling = None
    if scales is not None:
        atoms = ceiling_atoms(
            regrader.all_specs, scales, draws=DRAWS, seed=doc["ceiling_seed"]
        )
        index_of = {
            (s.target_id, tuple(s.designs[i])): i
            for s in regrader.all_specs
            for i in s.agen
        }
        by = {}
        for cls, key in zip(point_class, point_keys, strict=True):
            by.setdefault(cls, []).append(atoms[key[0], index_of[key]])
        ceiling = {cls: statistics.fmean(v) for cls, v in by.items()}

    def atoms_of(role, cls):
        points = per[role]["points"]
        if points is None or scales is None:
            return []
        return [p["atom"] for c, p in points if c == cls]

    def eou(role, cls):
        points = per[role]["points"]
        if points is None:
            return None
        out = {}
        for c, p in points:
            if c == cls:
                for k, v in p["err_over_u"].items():
                    out.setdefault(k, []).append(v)
        return {
            k: {"median": statistics.median(v), "p90": reads.quantile(v, 0.9)}
            for k, v in sorted(out.items())
        }

    roles = [e["role"] for e in doc["contenders"]]
    panel = [r for r in roles if r != DEFAULT]
    admitted = [r for r in panel if per[r]["points"] is not None]
    seed = doc["bootstrap_seed"]
    rows_by_class = []
    checks = {"1_shortcuts_out_of_range": {}, "2_ceiling_gap": {}, "3_default": {}}
    for i, cls in enumerate(class_order):
        n = sum(1 for c in point_class if c == cls)
        accuracy = {
            r: (statistics.fmean(atoms_of(r, cls)) if atoms_of(r, cls) else None)
            for r in roles
        }
        best = max(
            ((accuracy[r], r) for r in admitted if accuracy[r] is not None),
            default=(None, None),
        )
        rows_by_class.append(
            {
                "class": cls,
                "n": n,
                "gate_failed": {r: per[r]["gate_failed"] for r in roles},
                "accuracy": accuracy,
                "err_over_u": {r: eou(r, cls) for r in roles},
                "noise_ceiling": None if ceiling is None else ceiling.get(cls),
                "err_over_u_ceiling": 1.0,
                "best_shortcut": best[1],
            }
        )
        if best[1] is not None:
            checks["2_ceiling_gap"][cls] = {
                "member": best[1],
                **_gap(
                    [ceiling[cls]],
                    atoms_of(best[1], cls),
                    step=step,
                    draws=DRAWS,
                    seed=seed + 2000 + i,
                ),
            }
            checks["3_default"][cls] = {
                "against": best[1],
                "gap": _gap(
                    atoms_of(DEFAULT, cls),
                    atoms_of(best[1], cls),
                    step=step,
                    draws=DRAWS,
                    seed=seed + 4000 + i,
                ),
            }
        if cls != IN_TRAIN:
            checks["1_shortcuts_out_of_range"][cls] = {
                r: {
                    "gap_in_vs_ood": _gap(
                        atoms_of(r, IN_TRAIN),
                        atoms_of(r, cls),
                        step=step,
                        draws=DRAWS,
                        seed=seed + i * 100 + panel.index(r),
                    ),
                    "err_over_u_ratio": _ratio(eou(r, cls), eou(r, IN_TRAIN)),
                }
                for r in admitted
            }
    if keep is not None:
        keep.update(
            points=list(zip(point_class, point_inputs, strict=True)),
            train=train,
            columns=columns,
        )
    checks["3_coverage"] = {
        "nearest_train": nearest_train(
            list(zip(point_class, point_inputs, strict=True)), train, columns
        ),
        "rule": NEAREST_RULE,
        "coverage_table": doc["header"]["coverage_table"],
    }
    failed_roles = sorted(r for r in roles if per[r]["status"] != "SCORED")
    status = []
    if scales is None:
        status.append("ACCURACY_NULL_NO_REGISTERED_SCALES")
    status.append(
        {"MEASURED_WITH_GATE_FAILURES": failed_roles}
        if failed_roles
        else ("MEASURED" if scales is not None else None)
    )
    if doc["header"]["probe_set"]["provisional"]:
        status.append("PROVISIONAL")
    here = Path(__file__).resolve()
    report = {
        "schema": SCHEMA,
        "challenge": config["challenge"],
        "version": config["version"],
        "scratch_only": True,
        "train_version": doc["header"]["train_version"],
        "probe_set": {
            **doc["header"]["probe_set"],
            "class_rule": "geometric-v1",
            **identities,
        },
        "u_record": doc["header"]["u_record"],
        "agen_scales": {"source": None if scales is None else "registered"},
        "tool": {
            "commit": doc["header"]["tool_commit"],
            "checks_report_sha256": _sha_file(here),
            "q3_q8_whatif_sha256": _sha_file(here.parent / "q3_q8_whatif.py"),
        },
        "bootstrap": {
            "draws": DRAWS,
            "resampling": "within class",
            "seed": doc["bootstrap_seed"],
        },
        "noise_ceiling_mc": {"draws": DRAWS, "seed": doc["ceiling_seed"]},
        "panel_file_sha256": doc["panel_file"]["sha256"],
        "contenders": [
            {k: e[k] for k in ("role", "catalog_id", "fit", "record_sha256", "sha256")}
            | {
                "status": per[e["role"]]["status"],
                "gates": per[e["role"]]["gates"],
            }
            for e in doc["contenders"]
        ],
        "score_step": step,
        "margin_n": config["margin_n"],
        "gate_failed_scope": "every pool answer of the contender (the per-class split is not measured)",
        "classes": rows_by_class,
        "checks": checks,
        "bars": "owner values: measured gaps only, no pass/fail",
        "status": [s for s in status if s is not None],
    }
    return {**report, "run_digest": reads.run_digest(report, config_path, __file__)}


def _ratio(cls, base):
    if cls is None or base is None:
        return None
    return {
        k: None if base[k]["median"] == 0 else cls[k]["median"] / base[k]["median"]
        for k in cls
        if k in base
    }


def _fmt(value):
    return "null" if value is None else f"{value:.4g}"


def summary(report):
    """The short markdown summary: the same numbers as the JSON, nothing judged."""
    lines = [
        f"# Checks (1)-(3): {report['challenge']} {report['version']}",
        "",
        (
            f"status: {json.dumps(report['status'])}; score step {_fmt(report['score_step'])}; "
            f"bootstrap {DRAWS} within class; panel file {report['panel_file_sha256']}"
        ),
        "",
        "| class | n | best member | best acc | default acc | ceiling |",
        "|---|---|---|---|---|---|",
    ]
    for row in report["classes"]:
        best = row["best_shortcut"]
        lines.append(
            f"| {row['class']} | {row['n']} | {best} | "
            f"{_fmt(None if best is None else row['accuracy'][best])} | "
            f"{_fmt(row['accuracy'][DEFAULT])} | {_fmt(row['noise_ceiling'])} |"
        )
    lines += ["", "Gaps (value [95 % CI], in steps):", ""]
    for cls, gap in report["checks"]["2_ceiling_gap"].items():
        lines.append(
            f"- (2) {cls}: ceiling - {gap['member']} = {_fmt(gap['value'])} "
            f"[{_fmt(gap['ci95'][0])}, {_fmt(gap['ci95'][1])}], {_fmt(gap['steps'])} steps"
        )
    for cls, row in report["checks"]["3_default"].items():
        gap = row["gap"]
        if gap is not None:
            lines.append(
                f"- (3) {cls}: default - {row['against']} = {_fmt(gap['value'])} "
                f"[{_fmt(gap['ci95'][0])}, {_fmt(gap['ci95'][1])}], {_fmt(gap['steps'])} steps"
            )
    return "\n".join(lines) + "\n"


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--inputs", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    _need(not args.out.exists(), "report_out_exists")
    config = reads.load_config(args.config)
    report = run_report(config, args.config, args.inputs)
    args.out.mkdir(parents=True)
    raw = json.dumps(report, indent=2, sort_keys=True).encode() + b"\n"
    (args.out / "checks-1-3-report.json").write_bytes(raw)
    (args.out / "checks-1-3-report.md").write_bytes(summary(report).encode())
    print(hashlib.sha256(raw).hexdigest())


if __name__ == "__main__":
    sys.exit(main())
