#!/usr/bin/env python3
"""Prediction tables for the pool grid run: a built model's raw outputs at every pool input row.

Two steps, on two hosts (the build host never sees a target, a limit, a truth or a seed):

  custody:     python scripts/dev/pool_predict_table.py rows --kind K --version V \
                   --pools-dir CUSTODY/pools --sets SETS.json --out rows-K.json
               Inputs only (fixed condition values + design, in the interface's input order), deduplicated and
               sorted, so the file carries no grouping into targets.

  build host:  python scripts/dev/pool_predict_table.py predict --kind K --bound BOUND.json --role good|default \
                   --rows rows-K.json --out table-K-ROLE.json --work-dir DIR \
                   --parent-identity IDENTITY.json --cache-root LIBRARY_CACHE
               Re-binds the pick on THIS tree and refuses (exit 3) unless its bound and bundle recipe digests equal
               the table's, then builds the pick once and asks it for every row (`pool_serving.predict_rows`).

It needs `proof_run_bind.py` and `practice_v2_curves.py` beside it (the receipted binder and the curves job's
practice builder) and Docker with the pinned PyTorch CPU worker, as the curves job does. $0 of Carbon money;
nothing here is a grade.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
ROWS_SCHEMA = "carbon.pool-rows.v1"


class Stop(Exception):
    """Back to the Validator: the tree or the pick is not the one the table was bound on."""


def _sibling(name):
    path = HERE / (name + ".py")
    if not path.exists():
        raise Stop(f"{name}.py must sit beside this script")
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def bank_input_rows(kind, version):
    """The model input rows of the version's public practice bank (its cells and probes, inputs only, in the
    interface's input order): what the grid's bank leg asks the tables about, beside the pool rows.
    """
    from carbon.scoring import physical_dual_pack as physical
    from carbon.scoring import practice_grid

    bank = practice_grid.practice_bank(kind, version)
    names = practice_grid.input_names(kind, version)
    return [
        [float(row["inputs"][name]) for name in names]
        for row in physical.bank_rows(bank, names)
    ]


def build_rows(kind, version, documents, bank_rows=None):
    """The deduplicated, sorted model input rows of the pool-source ``documents`` and, when given, the
    ``bank_rows`` (inputs only); one list, so the file carries no grouping into targets or into pool and bank.
    """
    from carbon.scoring import pool_adapters

    chosen = pool_adapters.adapter(kind, version)
    seen = {}
    for document in documents:
        if tuple(document.get("design_names", ())) != tuple(chosen.design_names):
            raise Stop("a pool source's design_names differ from the adapter's")
        fixed = document["conditions"]["fixed"]
        for design in document["designs"]:
            row = tuple(chosen.model_row(fixed, design))
            seen[row] = None
    for row in bank_rows or ():
        if len(row) != len(chosen.input_names):
            raise Stop("a bank row's width differs from the adapter's input names")
        seen[tuple(float(v) for v in row)] = None
    return {
        "schema": ROWS_SCHEMA,
        "kind": kind,
        "version": version,
        "input_names": list(chosen.input_names),
        "rows": [list(row) for row in sorted(seen)],
    }


def rows_command(args):
    sets = json.loads(Path(args.sets).read_text(encoding="utf-8"))
    pools = Path(args.pools_dir)
    documents = [
        json.loads((pools / f"pool-source-{tid}.json").read_text(encoding="utf-8"))
        for names in sets.values()
        for tid in names
    ]
    bank = (
        bank_input_rows(args.kind, args.version)
        if getattr(args, "with_bank", False)
        else None
    )
    document = build_rows(args.kind, args.version, documents, bank)
    Path(args.out).write_text(
        json.dumps(document, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({"rows": len(document["rows"]), "out": str(args.out)}))
    return 0


def check_pick(binder, bound, role, challenge_id, version):
    """The bound pick, after re-binding it on this tree and comparing the digests the table pinned."""
    found = [
        p
        for p in bound["picks"]
        if (p["role"], p["challenge_id"], p["version"]) == (role, challenge_id, version)
    ]
    if len(found) != 1:
        raise Stop("the bound table has no single pick for this role and version")
    pick = found[0]
    again = binder.bind_pick(
        {
            "role": role,
            "challenge_id": challenge_id,
            "version": version,
            "catalog_id": pick["catalog_id"],
            "procedure": pick.get("procedure") or {},
        },
        pick.get("runtime"),
    )
    for key in ("bound_recipe_digest", "bundle_recipe_digest"):
        if again[key] != pick[key]:
            raise Stop(f"{key} differs on this tree: the kit or catalog moved")
    return pick


def predict_command(args, *, binder=None, curves=None):
    from carbon.scoring import pool_serving

    binder = binder or _sibling("proof_run_bind")
    curves = curves or _sibling("practice_v2_curves")
    challenge_id, version = curves.TARGETS[args.kind]
    bound = json.loads(Path(args.bound).read_text(encoding="utf-8"))
    pick = check_pick(binder, bound, args.role, challenge_id, version)
    rows_document = json.loads(Path(args.rows).read_text(encoding="utf-8"))
    if rows_document.get("schema") != ROWS_SCHEMA or (
        rows_document["kind"],
        rows_document["version"],
    ) != (args.kind, version):
        raise Stop("the rows file is not this Challenge version's")
    strategy = binder.catalog_recipe(
        challenge_id, version, pick["catalog_id"], pick.get("procedure")
    )
    args.out_dir = (
        args.work_dir
    )  # the curves job's practice builder keeps its ledger here
    practice = curves.practice_for(args.kind, args)
    raw, state = pool_serving.predict_rows(
        practice, f"pool-{args.kind}-{args.role}", strategy, rows_document["rows"]
    )
    pool_serving.write_table(
        args.out,
        kind=args.kind,
        version=version,
        input_names=rows_document["input_names"],
        rows=rows_document["rows"],
        raw=raw,
        state_digest=state,
        recipe=pick["bundle_recipe_digest"],
    )
    print(
        json.dumps(
            {
                "role": args.role,
                "rows": len(raw),
                "state_digest": state,
                "bundle_recipe_digest": pick["bundle_recipe_digest"],
            }
        )
    )
    return 0


def train_command(args):
    """The TRAIN-fit model's table: learned-krr-v1 on TRAIN only (Validator spec section 9.2). No Docker, $0."""
    from carbon.scoring import pool_baseline, pool_serving

    rows_document = json.loads(Path(args.rows).read_text(encoding="utf-8"))
    if rows_document.get("schema") != ROWS_SCHEMA or rows_document["kind"] != args.kind:
        raise Stop("the rows file is not this Challenge's")
    predict, choice = pool_baseline.fit(args.kind, rows_document["version"])
    raw = predict(rows_document["rows"])
    pool_serving.write_table(
        args.out,
        kind=args.kind,
        version=rows_document["version"],
        input_names=rows_document["input_names"],
        rows=rows_document["rows"],
        raw=raw,
        state_digest="learned-krr-v1:"
        + json.dumps([choice["length"], choice["ridge"]]),
        recipe="learned-krr-v1",
    )
    print(json.dumps({"role": "train", "rows": len(raw), **choice}))
    if choice.get("gate_failed_on_practice"):
        print(
            "FLAG: even the chosen values fail a practice gate (ranked by accuracy)",
            file=sys.stderr,
        )
    if choice["at_edge"]:
        print(
            "FLAG: the choice lands on the grid edge for "
            + ", ".join(choice["at_edge"]),
            file=sys.stderr,
        )
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)
    rows = sub.add_parser("rows")
    rows.add_argument(
        "--with-bank",
        action="store_true",
        help="also the version's public practice bank rows (cells and probes): the grid's bank leg asks for them",
    )
    for flag in ("kind", "version", "pools-dir", "sets", "out"):
        rows.add_argument("--" + flag, required=True)
    predict = sub.add_parser("predict")
    for flag in (
        "kind",
        "bound",
        "role",
        "rows",
        "out",
        "work-dir",
        "parent-identity",
        "cache-root",
    ):
        predict.add_argument("--" + flag, required=True)
    train = sub.add_parser("train")
    for flag in ("kind", "rows", "out"):
        train.add_argument("--" + flag, required=True)
    args = parser.parse_args(argv)
    sys.path.insert(0, str(ROOT))
    commands = {
        "rows": rows_command,
        "predict": predict_command,
        "train": train_command,
    }
    try:
        return commands[args.command](args)
    except Stop as stop:
        print(f"STOP, back to the Validator: {stop}", file=sys.stderr)
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
