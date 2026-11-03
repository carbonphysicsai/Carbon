"""CHECK (1K), the kit-data fit (STRONG_CHECKS_SPEC_ADDENDUM_KITFIT_20261103, receipted cbdb6e84 + the Validator's 07:47 two-runs
amendment). CUSTODY scratch, never official; aggregates only. Run through ``checks_batch.py run|dry ... --kit-data KIT_MANIFEST.json``.

Check (1) fits the shortcut panel on TRAIN; check (1K) grades the SAME panel fitted (elsewhere, by `shortcut_panel` or the
validator rebuild path) on kit-scale data: everything Carbon has already solved for the version, in range and out of range. This
module FITS nothing: it binds the kit data (the manifest: every dataset by sha256 with its row count, its source status and its
disjointness receipt; the version's counter with the information budget; the panel config by sha256), re-checks the disjointness
in custody (every kit design at least `R15_PRACTICE_DISTANCE` from every exam design of the loaded bank; a breach is refused with
the COUNT only), and grades each member's two runs (``fit_data`` "in" and "in_out") and the check-(3) learners through
`checks_report.grade_contenders` (the receipted Regrader with the A_gen recorder, the geometric-v1 point classes), nothing
reimplemented.

Per member and run: the data used (n in / n out by source), the counted size vs the budget (inside / over), A per point class and
D per registered target class with the within-class bootstrap 95 % interval (`acc_noise.bootstrap` / `acc_noise.spread`), and the
margin vs the best check-(3) learner (`checks_report._gap`, in score steps). Verdict per freeze-binding class, on the "in_out" run:
FAIL if the best budget-confined (inside, graded) member beats every check-(3) learner "clearly" (the R33 bar: the 95 % lower
bound of O - K by `paired_gap`, a PAIRED within-class bootstrap (Validator 12:01), above the config's margin_n); PASS otherwise; N/A with a reason. A FAIL only in
"in_out" is labelled `EXTENTS_LABEL`. A member over budget is reported with its scores and is never verdict-bearing (section 4).
Without registered A_gen scales the verdict is PROVISIONAL (verdict-free). No value is set here: margin_n is the config's, the
distance the addendum's (the registered R15 value), the budget the manifest's.
"""

from __future__ import annotations

import hashlib
import io
import json
import statistics
from pathlib import Path

import checks_report as report
import q3_q8_whatif as reads

SCHEMA = "carbon.check-1k-report.v1"
MANIFEST_SCHEMA = "carbon.check-1k-kit.v1"
#: Addendum section 3.1: a kit design closer than the registered R15 practice distance (normalised max-norm, each input over the
#: signed EXTENDED span of the region; a zero-span input skipped, the practice bank's rule) to any exam design is never fitted on.
R15_PRACTICE_DISTANCE = 0.10
DISTANCE_RULE = "maxnorm_over_signed_extended_span_zero_span_skipped"
FIT_DATA = ("in", "in_out")
#: The learned models of check (3): `checks_report`'s check (3) compares the default model (the only learned role) with the panel.
LEARNER_ROLES = (report.DEFAULT,)
#: Addendum section 1 panel members beyond check (1)'s roles: (b') the catalog default kernel / KRR, (e) graph-recipe fits.
CATALOG_KERNEL = "catalog_kernel"
GRAPH_RECIPE = "graph_recipe:"
EXTENTS_LABEL = "fails only with Carbon-known extents"
MANIFEST_KEYS = frozenset({"schema", "datasets", "counter", "panel_config"})
DATASET_KEYS = frozenset(
    {"name", "npz", "sha256", "range", "n", "source_status", "disjointness_receipt"}
)
COUNTER_KEYS = frozenset({"name", "budget_bytes", "receipt"})
RUN_KEYS = report.CONTENDER_KEYS | {"fit_data", "info_budget"}
OUTPUTS = ("check-1k-report.json", "check-1k-report.md")

_need = reads._need


def _text(value):
    return type(value) is str and value.strip() != ""


def _member_role_ok(role):
    if type(role) is not str or role in LEARNER_ROLES:
        return False
    if role == CATALOG_KERNEL or report._role_ok(role):
        return True
    return role.startswith(GRAPH_RECIPE) and len(role) > len(GRAPH_RECIPE)


# ---------------------------------------------------------------- the inputs


def load_manifest(path):
    """KIT_MANIFEST.json, ``carbon.check-1k-kit.v1`` (every key required, nothing extra): ``datasets`` [{name, npz, sha256, range
    "in"|"out", n, source_status, disjointness_receipt}], ``counter`` {name, budget_bytes, receipt}, ``panel_config`` {path,
    sha256}. A dataset without a non-empty disjointness receipt, or a missing counter, is refused before anything else.
    """
    doc = json.loads(Path(path).read_bytes())
    _need(
        type(doc) is dict and doc.get("schema") == MANIFEST_SCHEMA, "kit_manifest_shape"
    )
    counter = doc.get("counter")
    _need(
        type(counter) is dict
        and set(counter) == COUNTER_KEYS
        and _text(counter["name"])
        and type(counter["budget_bytes"]) is int
        and counter["budget_bytes"] > 0
        and _text(counter["receipt"]),
        "kit_counter_missing",
    )
    datasets = doc.get("datasets")
    _need(type(datasets) is list and datasets, "kit_datasets")
    for entry in datasets:
        _need(
            type(entry) is dict and _text(entry.get("disjointness_receipt")),
            "kit_dataset_lacks_disjointness_receipt",
        )
    names = set()
    for entry in datasets:
        _need(
            set(entry) == DATASET_KEYS
            and _text(entry["name"])
            and entry["name"] not in names
            and _text(entry["npz"])
            and report._hex(entry["sha256"])
            and entry["range"] in ("in", "out")
            and type(entry["n"]) is int
            and entry["n"] >= 1
            and _text(entry["source_status"]),
            "kit_dataset_entry",
        )
        names.add(entry["name"])
    _need(any(e["range"] == "in" for e in datasets), "kit_no_in_range_data")
    _need(set(doc) == MANIFEST_KEYS, "kit_manifest_shape")
    panel = doc["panel_config"]
    _need(
        type(panel) is dict
        and set(panel) == {"path", "sha256"}
        and _text(panel["path"])
        and report._hex(panel["sha256"])
        and Path(panel["path"]).is_file()
        and report._sha_file(panel["path"]) == panel["sha256"].removeprefix("sha256:"),
        "kit_panel_config_sha256",
    )
    return doc


def load_kit_inputs(path):
    """REPORT_INPUTS.json in kit mode: the checks-1-3 keys, header, panel file, TRAIN and seeds checked by `checks_report`'s own
    checks; ``contenders`` holds the check-(3) learners (the checks-1-3 entry keys, a role of `LEARNER_ROLES`, exactly one
    default_model) and the kit runs (the same keys plus ``fit_data`` "in" | "in_out" and ``info_budget`` {"counted_bytes": int},
    the member's size by the version's counter). Every member must appear with both runs. Returns ``(doc, learners, runs)``.
    """
    doc = json.loads(Path(path).read_bytes())
    _need(type(doc) is dict and set(doc) == report.INPUT_KEYS, "report_inputs_shape")
    report.check_header_and_panel(doc)
    contenders = doc["contenders"]
    _need(type(contenders) is list and contenders, "report_contenders")
    learners, runs = [], []
    for entry in contenders:
        is_run = type(entry) is dict and ("fit_data" in entry or "info_budget" in entry)
        (runs if is_run else learners).append(entry)
    roles = set()
    for entry in learners:
        _need(
            type(entry) is dict
            and set(entry) == report.CONTENDER_KEYS
            and entry["role"] in LEARNER_ROLES
            and entry["role"] not in roles
            and entry["fit"] in report.FITS
            and type(entry["catalog_id"]) is str
            and report._hex(entry["record_sha256"]),
            "kit_learner_entry",
        )
        roles.add(entry["role"])
    _need(report.DEFAULT in roles, "kit_needs_the_default_model")
    seen = set()
    for entry in runs:
        budget = entry.get("info_budget")
        _need(
            set(entry) == RUN_KEYS
            and _member_role_ok(entry["role"])
            and entry["fit_data"] in FIT_DATA
            and entry["fit"] in report.FITS
            and type(entry["catalog_id"]) is str
            and report._hex(entry["record_sha256"])
            and type(budget) is dict
            and set(budget) == {"counted_bytes"}
            and type(budget["counted_bytes"]) is int
            and budget["counted_bytes"] >= 0,
            "kit_member_entry",
        )
        key = (entry["role"], entry["fit_data"])
        _need(key not in seen, "kit_member_run_repeated")
        seen.add(key)
    _need(runs, "kit_no_members")
    for role in {r for r, _ in seen}:
        _need(
            {f for r, f in seen if r == role} == set(FIT_DATA),
            "kit_member_runs_incomplete",
        )
    report.check_train_and_seeds(doc)
    return doc, learners, runs


def load_kit_designs(manifest, columns):
    """``{dataset name: inputs (n x columns)}``, each npz read only after its sha256 matches; its ``inputs`` are in TRAIN's column
    layout (``columns``) and carry exactly the manifest's ``n`` rows (``targets``, when present, too).
    """
    import zipfile

    import numpy as np

    out = {}
    for entry in manifest["datasets"]:
        path = Path(entry["npz"])
        _need(path.is_file(), "kit_dataset_missing")
        raw = path.read_bytes()
        _need(
            hashlib.sha256(raw).hexdigest() == entry["sha256"].removeprefix("sha256:"),
            "kit_dataset_sha256",
        )
        try:
            with np.load(io.BytesIO(raw), allow_pickle=False) as npz:
                files = set(npz.files)
                inputs = (
                    np.asarray(npz["inputs"], dtype=float)
                    if "inputs" in files
                    else None
                )
                targets = npz["targets"] if "targets" in files else None
        except (OSError, ValueError, KeyError, zipfile.BadZipFile):
            raise reads.ReadRefused("kit_npz_unreadable") from None
        _need(inputs is not None, "kit_npz_lacks_inputs")
        _need(
            inputs.ndim == 2
            and inputs.shape[1] == len(columns)
            and np.isfinite(inputs).all(),
            "kit_npz_inputs_shape",
        )
        _need(
            inputs.shape[0] == entry["n"]
            and (targets is None or len(targets) == entry["n"]),
            "kit_dataset_n_differs",
        )
        out[entry["name"]] = inputs
    return out


def exam_designs(regrader, names):
    """Every exam design of the loaded bank (each target's conditions + every design row), as rows over ``names``."""
    import numpy as np

    from carbon.scoring import pool_version

    design_names = list(regrader.graded.bank[pool_version.POOL_KEY]["design_names"])
    rows = []
    for spec in regrader.all_specs:
        fixed = spec.conditions["fixed"]
        for design in spec.designs:
            inputs = {**fixed, **dict(zip(design_names, design, strict=True))}
            _need(set(names) <= set(inputs), "kit_exam_point_lacks_a_region_input")
            rows.append([float(inputs[n]) for n in names])
    _need(rows, "kit_no_exam_designs")
    return np.asarray(rows, dtype=float)


def check_disjoint(kit, columns, regrader, region):
    """Addendum section 3.2, in custody, aggregate only: the count of kit designs closer than `R15_PRACTICE_DISTANCE` to any exam
    design (`DISTANCE_RULE`, over the region's inputs) must be 0; otherwise refused with that count and nothing else.
    """
    import numpy as np

    names = sorted(region["base"])
    extended = region.get("extended")
    _need(
        type(extended) is dict and all(n in extended for n in names),
        "kit_region_lacks_extended",
    )
    _need(set(names) <= set(columns), "kit_columns_lack_a_region_input")
    index = [columns.index(n) for n in names]
    spans = np.array([float(extended[n][1]) - float(extended[n][0]) for n in names])
    live = spans > 0
    exam = exam_designs(regrader, names)
    rows = np.concatenate([m[:, index] for m in kit.values()])
    if not live.any():
        close = len(
            rows
        )  # the practice bank's rule: no live input, every design too close (fail closed)
    else:
        e = exam[:, live] / spans[live]
        close = sum(
            1
            for r in rows[:, live] / spans[live]
            if float(np.abs(e - r).max(axis=1).min()) < R15_PRACTICE_DISTANCE
        )
    _need(close == 0, f"kit_data_not_disjoint:{close}")
    return {
        "distance": R15_PRACTICE_DISTANCE,
        "rule": DISTANCE_RULE,
        "kit_designs": len(rows),
        "exam_designs": len(exam),
        "closer_than_distance": 0,
    }


def prepare(config, inputs_path, manifest_path):
    """Every input loaded and checked (the dry mode's whole work): the kit inputs, the manifest and its datasets, the class source,
    the pack (the Regrader), TRAIN's sha, the disjointness and every contender's rows.
    """
    doc, learners, runs = load_kit_inputs(inputs_path)
    manifest = load_manifest(manifest_path)
    klass, region, allowed, identities = reads._class_source(doc["class_source"])
    regrader = reads.Regrader(config)
    report.train_matrix(doc["train_inputs"])
    columns = doc["train_inputs"]["columns"]
    kit = load_kit_designs(manifest, columns)
    disjoint = check_disjoint(kit, columns, regrader, region)
    n_rows = len(regrader.graded.bank["inputs"])
    for entry in learners + runs:
        reads._contender_rows(
            {"rows_npy": entry["rows_npy"], "sha256": entry["sha256"]}, n_rows
        )
    return {
        "doc": doc,
        "learners": learners,
        "runs": runs,
        "manifest": manifest,
        "class_source": (klass, region, allowed, identities),
        "regrader": regrader,
        "disjointness": disjoint,
        "bank_rows": n_rows,
    }


def _budget(entry, manifest):
    counted = entry["info_budget"]["counted_bytes"]
    limit = manifest["counter"]["budget_bytes"]
    return {
        "counted_bytes": counted,
        "budget_bytes": limit,
        "counter": manifest["counter"]["name"],
        "budget": "inside" if counted <= limit else "over",
    }


def _data_used(fit_data, manifest):
    ranges = ("in",) if fit_data == "in" else ("in", "out")
    by = {"in": {}, "out": {}}
    for entry in manifest["datasets"]:
        if entry["range"] in ranges:
            by[entry["range"]][entry["name"]] = entry["n"]
    return {
        "n_in": sum(by["in"].values()),
        "n_out": sum(by["out"].values()),
        "by_source": by,
    }


def dry(config, inputs_path, manifest_path):
    prep = prepare(config, inputs_path, manifest_path)
    return {
        "challenge": config["challenge"],
        "version": config["version"],
        "check": "1K",
        "learners": [e["role"] for e in prep["learners"]],
        "members": sorted({e["role"] for e in prep["runs"]}),
        "budget": {
            f"{e['role']}@{e['fit_data']}": _budget(e, prep["manifest"])["budget"]
            for e in prep["runs"]
        },
        "kit_rows": {
            r: sum(d["n"] for d in prep["manifest"]["datasets"] if d["range"] == r)
            for r in ("in", "out")
        },
        "disjointness": prep["disjointness"],
        "bank_rows": prep["bank_rows"],
        "dry": "OK",
    }


# ---------------------------------------------------------------- the grade and the report


def paired_gap(a, b, *, step, draws, seed):
    """``mean(a) - mean(b)`` over the SAME points (``a[i]`` and ``b[i]`` are one point graded for O and for K), with its
    PAIRED bootstrap 95 % interval: every resample draws one set of point indices and takes it for both sides (Validator
    3 Nov 12:01: the registered 'clearly' bar is within-class AND paired). The caller passes one class's points, so the
    resampling stays within the class. Unequal lengths refuse: the points must be the same.
    """
    import numpy as np

    _need(len(a) == len(b), "kit_paired_points_differ")
    if not a:
        return None
    diff = np.asarray(a, dtype=float) - np.asarray(b, dtype=float)
    value = float(diff.mean())
    rng = np.random.default_rng(seed)
    reps = np.array(
        [diff[rng.integers(0, diff.size, diff.size)].mean() for _ in range(draws)]
    )
    lo, hi = (float(x) for x in np.quantile(reps, [0.025, 0.975]))
    return {
        "value": value,
        "ci95": [lo, hi],
        "steps": value / step,
        "ci95_steps": [lo / step, hi / step],
        "paired": True,
    }


def _mean_ci(values, seed):
    """The mean with its within-class bootstrap 95 % interval (`acc_noise.bootstrap` + `acc_noise.spread`, `report.DRAWS`)."""
    import acc_noise

    if not values:
        return None
    reps = acc_noise.bootstrap(
        [("class", v) for v in values],
        lambda sample: statistics.fmean(v for _, v in sample),
        draws=report.DRAWS,
        seed=seed,
    )
    spread = acc_noise.spread(reps)
    return {
        "n": len(values),
        "value": statistics.fmean(values),
        "ci95": None if spread is None else [spread["q025"], spread["q975"]],
    }


def run_kit(config, config_path, inputs_path, manifest_path):
    """The check-1K report document (see the module docstring)."""
    from carbon.scoring import grade_feedback, pool_version

    prep = prepare(config, inputs_path, manifest_path)
    doc, learners, runs, manifest = (
        prep["doc"],
        prep["learners"],
        prep["runs"],
        prep["manifest"],
    )
    klass, region, allowed, identities = prep["class_source"]
    regrader = prep["regrader"]
    classes, order = regrader.sets_and_classes()
    scales = pool_version.registered_policies(
        config["challenge"], config["version"]
    ).agen_scales
    step = grade_feedback.step(config["margin_n"])
    margin_n = config["margin_n"]
    keyed = [(e["role"], e) for e in learners] + [
        (f"{e['role']}@{e['fit_data']}", e) for e in runs
    ]
    per, point_class, _inputs, _keys = report.grade_contenders(
        regrader,
        keyed,
        prefix="check-1k",
        classes=classes,
        scales=scales,
        klass=klass,
        region=region,
        allowed=allowed,
    )
    _need(point_class is not None, "report_every_contender_gated")
    present = set(point_class)
    class_order = [c for c in (report.IN_TRAIN,) if c in present] + sorted(
        present - {report.IN_TRAIN}
    )
    empty = sorted(set(allowed) - present)
    target_classes = sorted(set(classes.values()))
    seed = doc["bootstrap_seed"]

    def atoms(key, cls):
        points = per[key]["points"]
        if points is None or scales is None:
            return []
        return [p["atom"] for c, p in points if c == cls]

    def d_values(key):
        basis = per[key]["basis"]
        if basis is None:
            return None
        _need("sets" in basis, "kit_basis_lacks_sets")
        by = {}
        for ids, targets in zip(order, basis["sets"], strict=True):
            _need(len(ids) == len(targets), "targets_differ_from_the_pool_material")
            for tid, target in zip(ids, targets, strict=True):
                by.setdefault(classes[tid], []).append(target["d"])
        return by

    d_of = {key: d_values(key) for key, _ in keyed}
    learner_roles = [e["role"] for e in learners]

    def best_learner(values_of):
        means = [
            (statistics.fmean(values_of(r)), r) for r in learner_roles if values_of(r)
        ]
        return max(means)[1] if means else None

    def margin(own, against_values, against, gap_seed):
        if against is None or not own:
            return None
        gap = report._gap(
            own, against_values, step=step, draws=report.DRAWS, seed=gap_seed
        )
        return None if gap is None else {"learner": against, **gap}

    def a_rows(key, base):
        out = {}
        for ci, cls in enumerate(class_order):
            own = atoms(key, cls)
            best = best_learner(lambda r, cls=cls: atoms(r, cls))
            out[cls] = {
                "n": sum(1 for c in point_class if c == cls),
                "A": _mean_ci(own, base + 10 * ci),
                "margin_vs_best_learner": (
                    None
                    if key in learner_roles
                    else margin(
                        own,
                        atoms(best, cls) if best else [],
                        best,
                        base + 10 * ci + 1,
                    )
                ),
            }
        return out

    def d_rows(key, base):
        mine = d_of[key]
        if mine is None:
            return None
        out = {}
        for ti, tcls in enumerate(target_classes):
            own = mine.get(tcls, [])
            best = best_learner(lambda r, tcls=tcls: (d_of[r] or {}).get(tcls, []))
            out[tcls] = {
                "D": _mean_ci(own, base + 500 + 10 * ti),
                "margin_vs_best_learner": (
                    None
                    if key in learner_roles
                    else margin(
                        own,
                        d_of[best].get(tcls, []) if best else [],
                        best,
                        base + 500 + 10 * ti + 1,
                    )
                ),
            }
        return out

    def identity(entry):
        return {
            k: entry[k] for k in ("catalog_id", "fit", "record_sha256", "sha256")
        } | {
            "status": per_key(entry)["status"],
            "gates": per_key(entry)["gates"],
            "gate_failed": per_key(entry)["gate_failed"],
        }

    def per_key(entry):
        return per[
            (
                entry["role"]
                if "fit_data" not in entry
                else f"{entry['role']}@{entry['fit_data']}"
            )
        ]

    learner_rows = []
    for li, entry in enumerate(learners):
        base = seed + 100000 + 1000 * li
        learner_rows.append(
            {"role": entry["role"], **identity(entry)}
            | {
                "classes": a_rows(entry["role"], base),
                "d_by_target_class": d_rows(entry["role"], base),
            }
        )

    member_roles = list(dict.fromkeys(e["role"] for e in runs))
    run_of = {(e["role"], e["fit_data"]): e for e in runs}
    bearing = {}
    member_rows = []
    for mi, role in enumerate(member_roles):
        row = {"role": role, "runs": {}}
        for ri, fit_data in enumerate(FIT_DATA):
            entry = run_of[role, fit_data]
            key = f"{role}@{fit_data}"
            budget = _budget(entry, manifest)
            graded = per[key]["points"] is not None
            bearing[key] = budget["budget"] == "inside" and graded
            base = seed + 200000 + 2000 * mi + 1000 * ri
            row["runs"][fit_data] = (
                identity(entry)
                | {
                    "data_used": _data_used(fit_data, manifest),
                    "info_budget": budget,
                    "verdict_bearing": bearing[key],
                    "not_verdict_bearing_because": (
                        None
                        if bearing[key]
                        else ("over_budget" if budget["budget"] == "over" else "gated")
                    ),
                }
                | {"classes": a_rows(key, base), "d_by_target_class": d_rows(key, base)}
            )
        member_rows.append(row)

    def class_verdict(cls, ci, fit_data):
        if scales is None:
            return {
                "verdict": None,
                "status": "PROVISIONAL",
                "reason": "no_registered_agen_scales",
            }
        missing = [r for r in learner_roles if not atoms(r, cls)]
        if missing:
            return {"verdict": "N/A", "reason": f"learner_not_graded:{missing[0]}"}
        inside = [
            (statistics.fmean(atoms(f"{r}@{fit_data}", cls)), r)
            for r in member_roles
            if bearing[f"{r}@{fit_data}"] and atoms(f"{r}@{fit_data}", cls)
        ]
        if not inside:
            return {"verdict": "N/A", "reason": "no_budget_confined_member_graded"}
        best = max(inside)[1]
        own = atoms(f"{best}@{fit_data}", cls)
        against = {}
        for li, learner in enumerate(learner_roles):
            gap = paired_gap(
                own,
                atoms(learner, cls),
                step=step,
                draws=report.DRAWS,
                seed=seed + 900000 + 100 * ci + 10 * li + FIT_DATA.index(fit_data),
            )
            against[learner] = {
                **gap,
                "lower_bound_above_margin_n": gap["ci95"][0] > margin_n,
            }
        clear = all(g["lower_bound_above_margin_n"] for g in against.values())
        return {
            "verdict": "FAIL" if clear else "PASS",
            "best_budget_confined_member": best,
            "against_learners": against,
        }

    verdicts = {}
    for ci, cls in enumerate(class_order):
        both = {f: class_verdict(cls, ci, f) for f in FIT_DATA}
        verdict = both["in_out"]["verdict"]
        verdicts[cls] = {
            "verdict": verdict,
            "label": (
                EXTENTS_LABEL
                if verdict == "FAIL" and both["in"]["verdict"] != "FAIL"
                else None
            ),
            "runs": both,
        }
    for cls in empty:
        verdicts[cls] = {"verdict": "N/A", "label": None, "reason": "no_points"}
    failed = sorted(c for c, v in verdicts.items() if v["verdict"] == "FAIL")
    decided = all(
        verdicts[c]["verdict"] in ("PASS", "FAIL") for c in class_order
    ) and bool(class_order)
    overall = "FAIL" if failed else ("PASS" if decided else None)

    gate_failed_roles = sorted(k for k in per if per[k]["status"] != "SCORED")
    status = []
    if scales is None:
        status.append("PROVISIONAL_NO_REGISTERED_AGEN_SCALES")
    if gate_failed_roles:
        status.append({"MEASURED_WITH_GATE_FAILURES": gate_failed_roles})
    elif scales is not None:
        status.append("MEASURED")
    if doc["header"]["probe_set"]["provisional"]:
        status.append("PROVISIONAL")
    here = Path(__file__).resolve()
    out = {
        "schema": SCHEMA,
        "check": "1K",
        "addendum": "STRONG_CHECKS_SPEC_ADDENDUM_KITFIT_20261103",
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
            "checks_kit_sha256": report._sha_file(here),
            "checks_report_sha256": report._sha_file(here.parent / "checks_report.py"),
            "q3_q8_whatif_sha256": report._sha_file(here.parent / "q3_q8_whatif.py"),
        },
        "bootstrap": {
            "draws": report.DRAWS,
            "resampling": "within class",
            "seed": seed,
            "verdict_gap": "paired_gap (within-class, the same resampled points for O and K)",
        },
        "panel_file_sha256": doc["panel_file"]["sha256"],
        "kit": {
            "panel_config_sha256": manifest["panel_config"]["sha256"],
            "counter": manifest["counter"],
            "datasets": [
                {k: d[k] for k in sorted(DATASET_KEYS - {"npz"})}
                for d in manifest["datasets"]
            ],
            "disjointness": prep["disjointness"],
        },
        "score_step": step,
        "margin_n": margin_n,
        "learner_roles": learner_roles,
        "classes": class_order,
        "classes_without_points": empty,
        "target_classes": target_classes,
        "freeze_binding_classes": class_order,
        "freeze_binding_rule": "G1 (every out-of-range class) + G2 and G3 (every class), as g_reports: every class with points",
        "learners": learner_rows,
        "members": member_rows,
        "verdict_by_class": verdicts,
        "verdict": overall,
        "classes_failed": failed,
        "verdict_rule": (
            "FAIL if the best budget-confined member on the in_out run beats every check-(3) learner by a 95 % lower bound "
            "of A(O) - A(K) above margin_n (R33); verdict on A per point class; D is reported, not verdict-bearing"
        ),
        "bars": "registered values only: margin_n (config), the R15 distance (addendum section 3), budget_bytes (manifest)",
        "status": status,
    }
    return {**out, "run_digest": reads.run_digest(out, config_path, __file__)}


def _fmt(value):
    return "null" if value is None else f"{value:.4g}"


def summary(doc):
    """The short markdown summary: the same numbers as the JSON."""
    lines = [
        f"# Check (1K) kit-data fit: {doc['challenge']} {doc['version']}",
        "",
        (
            f"verdict: {doc['verdict']}; status {json.dumps(doc['status'])}; margin_n {_fmt(doc['margin_n'])}; "
            f"score step {_fmt(doc['score_step'])}; budget {doc['kit']['counter']['budget_bytes']} bytes "
            f"({doc['kit']['counter']['name']}); disjointness: 0 of {doc['kit']['disjointness']['kit_designs']} kit "
            f"designs closer than {doc['kit']['disjointness']['distance']}"
        ),
        "",
        "| class | verdict | label | best inside member (in_out) |",
        "|---|---|---|---|",
    ]
    for cls, row in doc["verdict_by_class"].items():
        best = (
            (row.get("runs") or {}).get("in_out", {}).get("best_budget_confined_member")
        )
        reason = row.get("reason") or (row.get("runs") or {}).get("in_out", {}).get(
            "reason"
        )
        lines.append(
            f"| {cls} | {row['verdict']}{'' if reason is None else f' ({reason})'} | "
            f"{row['label'] or ''} | {best or ''} |"
        )
    lines += [
        "",
        "| member | run | n in | n out | counted / budget | budget | class | A [95 % CI] | margin vs learner (steps) |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for member in doc["members"]:
        for fit_data, run in member["runs"].items():
            budget = run["info_budget"]
            for cls, row in run["classes"].items():
                a, m = row["A"], row["margin_vs_best_learner"]
                lines.append(
                    f"| {member['role']} | {fit_data} | {run['data_used']['n_in']} | {run['data_used']['n_out']} | "
                    f"{budget['counted_bytes']} / {budget['budget_bytes']} | {budget['budget']} | {cls} | "
                    + (
                        "null"
                        if a is None
                        else f"{_fmt(a['value'])} [{_fmt(None if a['ci95'] is None else a['ci95'][0])}, "
                        f"{_fmt(None if a['ci95'] is None else a['ci95'][1])}]"
                    )
                    + f" | {'null' if m is None else _fmt(m['steps'])} |"
                )
    return "\n".join(lines) + "\n"
