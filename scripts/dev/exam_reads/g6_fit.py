"""G6 LEARNING-CURVE FITS (STRONG_CHECKS_SPEC_20261102, G6): the default model and the best shortcut fitted on each nested TRAIN
subset of `g6_subsets`, predicting the caller's QUERY rows. CUSTODY scratch; it FITS and PREDICTS only: it grades nothing and
opens no pack (the QUERY rows are the caller's: the version's exam inputs in bank order, as every checks contender's rows are).

    g6_fit.py --subsets DIR --train TRAIN.npz --query QUERY.npy --query-sha256 HEX
              --member NAME --shortcut-role ROLE --shortcut-catalog-id ID --shortcut-fit FIT
              [--recipe RECIPE.json --submission-dir GRAPH_DIR --default-catalog-id ID] --out OUT

Per fraction f of the subsets manifest (`g6_subsets.subset_indices` re-derives and checks each subset's rows):

- the DEFAULT MODEL (``default_model@frac:<f>``), only through the official graph route v2 path, the calls and order
  `carbon/challenge_kit/local_scorer.py` makes: `ConstructionRecipe.from_bytes`, `graph_adapters.module_for`, the construction
  kit's identities (`bind_recipe`), `checked_train` on the version's public TRAIN by exact digest, `build_validated_graph(...,
  allowlist_bytes=served_allowlist_bytes, train_cases=spec.rows)`, `model.fit(inputs, targets, seed=0)`, `model.predict(QUERY,
  isolated=True)`. The official path admits exactly the version's TRAIN row count, and its one TRAIN-subset surface is the recipe's
  own ``procedure.train_use.train_fraction``: the trainer then fits the rows `physical_graph_trainer_v2.selected_rows(n, fraction,
  seed 0)` names. So below 100 % the recipe's fraction is set to f (or, when the trainer's count int(n f) differs from the
  subset's, to (k + 0.5) / n, which selects exactly k), and TRAIN's rows are placed so the trainer's own selected positions hold
  the subset's rows, in TRAIN order; every other row is the rest of TRAIN (unread by the fit). The fit is refused unless those
  selected rows are byte-equal to the subset file's arrays and the fit reports k rows. At 100 % the recipe and TRAIN are used
  unchanged. A recipe that is not a graph-route-v2 graph (a catalog or bundle recipe, a v1 or Battery adapter, a version this
  commit does not register) or that already selects a fraction below 1.0 is NOT_RUN with the reason; no other path is invented.
- the SHORTCUT (``<shortcut-role>@frac:<f>``): `shortcut_panel.fit_predict(member, subset X, subset Y, QUERY, seed=0)`, the
  call `shortcut_panel.py fit --train SUBSET.npz --query QUERY.npy --members <member> --seed 0` makes.

Writes OUT/rows/<role>.npy (float64, QUERY order), OUT/records/<role>.json (the fit record: subset sha256, fraction, seed, the
fit's own record) and OUT/g6-contenders.json: ``contenders`` (checks_report contender entries, ready to append to
REPORT_INPUTS.json's list; ``record_sha256`` is the fit record's sha256) and ``not_run`` (role, code).
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

import checks_report as report
import g6_subsets as subsets

SCHEMA = "carbon.exam-reads.g6-fit.v1"
FRAGMENT = "g6-contenders.json"
#: The seed the official build trains at (`local_scorer.OFFICIAL_SEED`), and the shortcut panel's.
OFFICIAL_SEED = 0
FRAC = "@frac:"

_need = subsets._need
SubsetsRefused = subsets.SubsetsRefused


def _sha(raw):
    return hashlib.sha256(raw).hexdigest()


def frac_role(base, fraction):
    return f"{base}{FRAC}{subsets.frac_label(fraction)}"


def _npy_bytes(array):
    import numpy as np

    buffer = io.BytesIO()
    np.save(buffer, np.ascontiguousarray(array, dtype=np.float64), allow_pickle=False)
    return buffer.getvalue()


def load_subsets(directory, train_raw):
    """The subsets manifest, bound to this TRAIN, with every subset file's sha256 checked."""
    directory = Path(directory)
    raw = (directory / subsets.MANIFEST).read_bytes()
    manifest = json.loads(raw)
    _need(
        type(manifest) is dict and manifest.get("schema") == subsets.SCHEMA,
        "g6_manifest_schema",
    )
    _need(_sha(train_raw) == manifest["train_sha256"], "g6_train_differs_from_manifest")
    fractions = [float(f) for f in manifest["fractions"]]
    _need(
        [subsets.frac_label(f) for f in fractions] == manifest["fractions"]
        and fractions == sorted(fractions)
        and fractions[-1] == 1.0,
        "g6_manifest_fractions",
    )
    files = {}
    for label in manifest["fractions"]:
        row = manifest["subsets"][label]
        data = (directory / row["file"]).read_bytes()
        _need(_sha(data) == row["sha256"], "g6_subset_file_changed")
        files[float(label)] = data
    return manifest, _sha(raw), fractions, files


def load_query(path, expected_sha256):
    import numpy as np

    raw = Path(path).read_bytes()
    _need(
        _sha(raw) == expected_sha256.removeprefix("sha256:"), "g6_query_sha256_differs"
    )
    query = np.load(io.BytesIO(raw), allow_pickle=False)
    _need(
        query.ndim == 2 and len(query) >= 1 and np.isfinite(query).all(),
        "g6_query_shape",
    )
    return np.asarray(query, dtype=np.float64), _sha(raw)


# ---------------------------------------------------------------- the default model: the official graph route v2 path


def _not_run(code):
    return {"status": "NOT_RUN", "code": code}


def _refusal_code(error):
    return getattr(error, "code", type(error).__name__)


def placed_train(inputs, targets, indices, selected):
    """TRAIN's rows re-placed so the positions ``selected`` (the trainer's own draw) hold the subset rows ``indices`` in TRAIN
    order, and the other positions the remaining TRAIN rows in TRAIN order. Returns (inputs, targets, source row of each
    position)."""
    import numpy as np

    n = len(inputs)
    _need(len(indices) == len(selected), "g6_trainer_count_differs_from_subset")
    rest = np.setdiff1d(np.arange(n), indices)
    others = np.setdiff1d(np.arange(n), selected)
    source = np.empty(n, dtype=np.int64)
    source[selected] = indices
    source[others] = rest
    return inputs[source], targets[source], source


def trainer_fraction(n, k, fraction):
    """The recipe train_fraction the official trainer turns into exactly k rows: f itself when int(n f) == k, else
    (k + 0.5) / n."""
    from carbon.development_session import physical_graph_trainer_v2 as trainer

    for value in (fraction, (k + 0.5) / n):
        selected = trainer.selected_rows(n, value, OFFICIAL_SEED)
        if 0.0 < value < 1.0 and len(selected) == k:
            return value
    raise SubsetsRefused("g6_no_trainer_fraction_selects_the_subset_count")


def default_rows(
    recipe_bytes, raw_manifest, files, train_raw, manifest, fraction, subset, query
):
    """``(rows, record)`` for the default model at ``fraction``, or ``(None, NOT_RUN record)``."""
    import contextlib

    import numpy as np

    from carbon.challenge_kit import physical_material
    from carbon.development_session import (
        graph_adapters,
        physical_graph_adapter_v2,
    )
    from carbon.development_session import physical_graph_trainer_v2 as trainer
    from carbon.development_session.construction_recipe import (
        ConstructionRecipe,
        RecipeRefused,
        bind_recipe,
    )
    from carbon.level4 import intake
    from carbon.level4.graph import GraphRefused

    try:
        recipe = ConstructionRecipe.from_bytes(recipe_bytes)
    except RecipeRefused as error:
        return None, _not_run(error.code)
    doc = recipe.to_dict()
    if doc["source"]["kind"] != "graph":
        return None, _not_run("default_model_is_not_a_graph_recipe")
    cid, version = doc["challenge"]["id"], doc["challenge"]["version"]
    module = graph_adapters.module_for(cid, version)
    if module is not physical_graph_adapter_v2:
        return None, _not_run("default_model_version_not_on_graph_route_v2")
    use = doc["procedure"]["train_use"]
    if type(use) is not dict or use.get("train_fraction") != 1.0:
        return None, _not_run("default_recipe_already_selects_a_train_fraction")
    try:
        kit = physical_material.construction_kit(cid, version)
        bind_recipe(
            doc,
            challenge_id=cid,
            challenge_version=version,
            train_digest=kit["train_digest"],
            interface_digest=kit["interface_digest"],
            construction_limits_digest=kit["construction_limits_digest"],
        )
        spec = module.spec_for(cid, version)
        inputs, targets = module.checked_train(spec, train_raw, kit["train_digest"])
    except (RecipeRefused, ValueError) as error:
        return None, _not_run(_refusal_code(error))
    n = len(inputs)
    _order, indices = subsets.subset_indices(
        manifest, fraction, n, arrays={"inputs": inputs, "targets": targets}
    )
    k = len(indices)
    if fraction == 1.0:
        tf, x, y, source = 1.0, inputs, targets, np.arange(n)
        fit_recipe = recipe
    else:
        tf = trainer_fraction(n, k, fraction)
        selected = trainer.selected_rows(n, tf, OFFICIAL_SEED)
        _need(module.selected_rows(spec, tf) == k, "g6_adapter_count_differs")
        x, y, source = placed_train(inputs, targets, indices, selected)
        _names, sub, _n = subsets.load_train(subset)
        _need(
            set(sub) == {"inputs", "targets"}
            and sub["inputs"].dtype == x.dtype
            and sub["targets"].dtype == y.dtype
            and x[selected].tobytes() == sub["inputs"].tobytes()
            and y[selected].tobytes() == sub["targets"].tobytes(),
            "g6_trainer_rows_differ_from_subset",
        )
        doc["procedure"]["train_use"]["train_fraction"] = tf
        fit_recipe = ConstructionRecipe.from_dict(doc)
    rows = np.ascontiguousarray(np.asarray(query, dtype=spec.dtype))
    _need(rows.shape[1] == spec.inputs, "g6_query_width_differs_from_interface")
    from carbon.development_session.direct_graph_construction_worker import (
        _envelope_has_wide_values,
    )
    from carbon.development_session.profile import canonical
    from carbon.level4 import staging

    wide = spec.dtype == "float64" or _envelope_has_wide_values(
        canonical(staging.envelope(raw_manifest, files))
    )
    if wide:
        import jax

        context = jax.enable_x64(True)
    else:
        context = contextlib.nullcontext()
    with context:
        try:
            model = module.build_validated_graph(
                fit_recipe,
                raw_manifest,
                files,
                allowlist_bytes=module.served_allowlist_bytes(cid, version),
                train_cases=n,
            )
            fit = model.fit(x, y, seed=OFFICIAL_SEED)
        except (GraphRefused, RecipeRefused) as error:
            return None, _not_run(_refusal_code(error))
        except intake.IntakeBlocked:
            return None, _not_run("graph_validation_not_ready")
        _need(fit["train_cases"] == k, "g6_fit_row_count_differs_from_subset")
        predictions = model.predict(rows, isolated=True)
    return np.asarray(predictions, dtype=np.float64), {
        "status": "FITTED",
        "path": "graph route v2 (local_scorer's official calls)",
        "recipe_digest": recipe.digest,
        "fit_recipe_digest": fit_recipe.digest,
        "train_fraction": tf,
        "trainer_rows": "the subset's rows, TRAIN order (trainer's own draw positions)",
        "placed_train_source_sha256": _sha(np.asarray(source, dtype="<i8").tobytes()),
        "fit": fit,
    }


# ---------------------------------------------------------------- the shortcut


def shortcut_rows(member, subset, query):
    """``(rows, record)``: `shortcut_panel.fit_predict` on the subset rows, seed 0; refusals are NOT_RUN."""
    import shortcut_panel

    try:
        x, y = shortcut_panel.load_train(io.BytesIO(subset))
        predictions, record = shortcut_panel.fit_predict(
            member, x, y, query, seed=OFFICIAL_SEED
        )
    except shortcut_panel.Refused as error:
        return None, _not_run(str(error))
    return predictions, {
        "status": "FITTED",
        "path": "shortcut_panel.fit_predict",
        "fit": record,
    }


# ---------------------------------------------------------------- the run


def run(args):
    out = Path(args.out)
    _need(not out.exists(), "g6_out_exists")
    _need(
        report._role_ok(args.shortcut_role) and args.shortcut_role != report.DEFAULT,
        "g6_shortcut_role_not_a_panel_role",
    )
    _need(args.shortcut_fit in report.FITS, "g6_shortcut_fit")
    with_default = args.recipe is not None
    _need(
        with_default == (args.submission_dir is not None)
        and with_default == (args.default_catalog_id is not None),
        "g6_default_needs_recipe_graph_dir_and_catalog_id",
    )
    train_raw = Path(args.train).read_bytes()
    manifest, manifest_sha, fractions, files = load_subsets(args.subsets, train_raw)
    query, query_sha = load_query(args.query, args.query_sha256)
    if with_default:
        from carbon.level4 import staging

        _digest, raw_manifest, graph_files = staging.read_directory(
            Path(args.submission_dir)
        )
        recipe_bytes = Path(args.recipe).read_bytes()
    (out / "rows").mkdir(parents=True)
    (out / "records").mkdir()
    contenders, not_run = [], []
    for fraction in fractions:
        subset = files[fraction]
        label = subsets.frac_label(fraction)
        jobs = []
        if with_default:
            jobs.append(
                (
                    frac_role(report.DEFAULT, fraction),
                    args.default_catalog_id,
                    "default",
                    lambda f=fraction, s=subset: default_rows(
                        recipe_bytes,
                        raw_manifest,
                        graph_files,
                        train_raw,
                        manifest,
                        f,
                        s,
                        query,
                    ),
                )
            )
        else:
            not_run.append(
                {
                    "role": frac_role(report.DEFAULT, fraction),
                    "code": "no_default_recipe_given",
                }
            )
        jobs.append(
            (
                frac_role(args.shortcut_role, fraction),
                args.shortcut_catalog_id,
                args.shortcut_fit,
                lambda s=subset: shortcut_rows(args.member, s, query),
            )
        )
        for role, catalog_id, fit_kind, job in jobs:
            rows, record = job()
            if rows is None:
                not_run.append({"role": role, "code": record["code"]})
                continue
            _need(rows.ndim == 2 and len(rows) == len(query), "g6_prediction_shape")
            safe = role.replace(":", "_")
            data = _npy_bytes(rows)
            (out / "rows" / f"{safe}.npy").write_bytes(data)
            record = {
                "schema": SCHEMA,
                "role": role,
                "fraction": label,
                "member": args.member if not role.startswith(report.DEFAULT) else None,
                "seed": OFFICIAL_SEED,
                "subset": {
                    "sha256": manifest["subsets"][label]["sha256"],
                    "n": manifest["subsets"][label]["n"],
                },
                "subsets_manifest_sha256": manifest_sha,
                "rule": manifest["rule"],
                "count": manifest["count"],
                "train_sha256": manifest["train_sha256"],
                "query_sha256": query_sha,
                "rows_sha256": _sha(data),
                "rows_shape": list(rows.shape),
                **record,
            }
            raw = (
                json.dumps(record, indent=1, sort_keys=True, allow_nan=False) + "\n"
            ).encode()
            (out / "records" / f"{safe}.json").write_bytes(raw)
            contenders.append(
                {
                    "role": role,
                    "catalog_id": catalog_id,
                    "fit": fit_kind,
                    "record_sha256": "sha256:" + _sha(raw),
                    "rows_npy": str((out / "rows" / f"{safe}.npy").resolve()),
                    "sha256": _sha(data),
                }
            )
    fragment = {
        "schema": SCHEMA,
        "scratch_only": True,
        "subsets_manifest_sha256": manifest_sha,
        "train_sha256": manifest["train_sha256"],
        "query_sha256": query_sha,
        "fractions": manifest["fractions"],
        "contenders": contenders,
        "not_run": not_run,
        "use": "append `contenders` to REPORT_INPUTS.json's contenders; checks_batch grades them, g_reports reads G6",
    }
    (out / FRAGMENT).write_bytes(
        (json.dumps(fragment, indent=1, sort_keys=True) + "\n").encode()
    )
    return fragment


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--subsets", type=Path, required=True)
    parser.add_argument("--train", type=Path, required=True)
    parser.add_argument("--query", type=Path, required=True)
    parser.add_argument("--query-sha256", required=True)
    parser.add_argument("--member", required=True, help="the shortcut_panel member")
    parser.add_argument("--shortcut-role", required=True, help="its checks role")
    parser.add_argument("--shortcut-catalog-id", required=True)
    parser.add_argument("--shortcut-fit", required=True, choices=report.FITS)
    parser.add_argument("--recipe", type=Path)
    parser.add_argument("--submission-dir", type=Path)
    parser.add_argument("--default-catalog-id")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        fragment = run(args)
    except SubsetsRefused as refused:
        print(f"REFUSED: {refused.code}", file=sys.stderr)
        return 2
    print(_sha((args.out / FRAGMENT).read_bytes()), FRAGMENT)
    for entry in fragment["not_run"]:
        print("NOT_RUN", entry["role"], entry["code"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
