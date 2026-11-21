"""Motor Specialist Bank, PATH B v0: retrain ONE recipe arm from scratch on public TRAIN and record public signals.

Design: codex-queue/reports/BANK/PATHB_REPRODUCE_HARNESS_DESIGN_20261121.md (V2 pre-read Y 01:30:52Z). It WRAPS the
data kit's local scorer (``carbon.challenge_kit.local_scorer.build_and_predict``: the official adapter's admission,
public TRAIN by digest, ``build_validated_graph``, ``model.fit``, predict) and holds no training or scoring logic of
its own. It adds only:

- ``seed``: 0 (the official build seed every miner submission was built at: ``research_tasks._seed_for``; a
  reproduction check only, contract row 6) or a bank seed ``BANK_SEED_BASE + i`` (V2: i in 0..9999). Any other seed
  is refused, so the bank never builds at a crown rebuild seed it could have learned.
- ``arm``: one named change to the RECIPE document (never to weights), re-validated by the adapter; an arm that would
  not change the recipe is refused.
- the trained state's digest (``model.frozen_state()``, the worker's own ``sha256:`` form), compared, when given,
  with the miner build's recorded digest.
- the kit verify set's aggregate (the local scorer's own ``LOCAL_CHECKS``): public designs only.

It never reads a hidden pool, a grade, a gate, the crown, Ladder feedback or ``direct_task_seeds``. It runs only on
a Carbon custody host (custody3 / custody2, V2 01:30:52Z), never on GPUYard (TEAM_RULES #15) or a third-party box,
and each run line has its own V2 receipt. Its report stays in custody: metrics leave only as per-regime counts /
medians over >= 3 recipes (V2), never per recipe. Curves and TRAIN cross-validation are v1 (the trainer's curve knob
lands with door-code D2; a TRAIN subset is refused by ``checked_train``'s digest, by design).
"""

from __future__ import annotations

import argparse
import contextlib
import copy
import hashlib
import json
import sys
import time
from pathlib import Path

SCHEMA = "carbon.bank-retrain.v0"
LABEL = "bank retrain: public signals only, never a grade"
#: V2 01:30:52Z: bank seeds are BANK_SEED_BASE + i, i in 0..BANK_SEEDS - 1.
BANK_SEED_BASE = 900_000_000
BANK_SEEDS = 10_000
OFFICIAL_SEED = 0
FIXED_ARMS = ("original", "single_member", "defaults_all")
DEFAULT_PREFIX = "default:"


class BankRefused(RuntimeError):
    """A typed refusal before anything is built (``code`` is closed)."""

    def __init__(self, code):
        super().__init__(code)
        self.code = code


def check_seed(seed):
    if type(seed) is not int or not (
        seed == OFFICIAL_SEED or BANK_SEED_BASE <= seed < BANK_SEED_BASE + BANK_SEEDS
    ):
        raise BankRefused("seed_not_bank")
    return seed


def arm_recipe(doc, arm):
    """The recipe document for ``arm``: one named change, or the original."""
    if not isinstance(doc, dict):
        raise BankRefused("recipe_malformed")
    out = copy.deepcopy(doc)
    if arm == "original":
        return out
    try:
        config = out["procedure"]["configuration"]
    except (KeyError, TypeError):
        raise BankRefused("recipe_malformed") from None
    if not isinstance(config, dict):
        raise BankRefused("recipe_malformed")
    members = (config.get("ensemble") or {}).get("members") or []
    if arm == "single_member":
        config.pop("ensemble", None)
    elif arm == "defaults_all":
        config["training"] = {}
        for member in members:
            member.pop("training", None)
    elif isinstance(arm, str) and arm.startswith(DEFAULT_PREFIX):
        knob = arm[len(DEFAULT_PREFIX) :]
        if not knob:
            raise BankRefused("arm_unknown")
        (config.get("training") or {}).pop(knob, None)
        for member in members:
            (member.get("training") or {}).pop(knob, None)
    else:
        raise BankRefused("arm_unknown")
    if out == doc:
        raise BankRefused("arm_no_change")
    return out


@contextlib.contextmanager
def _seed(module, seed):
    """Run the local scorer's own call sequence at ``seed``; its module default is restored after."""
    before = module.OFFICIAL_SEED
    module.OFFICIAL_SEED = seed
    try:
        yield
    finally:
        module.OFFICIAL_SEED = before


def retrain(
    recipe_doc,
    raw_manifest,
    files,
    verify_bytes,
    verify_sha256,
    *,
    seed,
    arm,
    expect_state_digest=None,
):
    """One arm at one seed; returns the custody report (no per-design row)."""
    from carbon.challenge_kit import local_scorer as ls
    from carbon.development_session.construction_recipe import (
        ConstructionRecipe,
        RecipeRefused,
    )

    check_seed(seed)
    try:
        original = ConstructionRecipe.from_dict(recipe_doc)
    except RecipeRefused as refused:
        raise BankRefused(refused.code) from None
    try:
        changed = ConstructionRecipe.from_dict(arm_recipe(recipe_doc, arm))
    except RecipeRefused as refused:
        changed, admission = None, {"state": "REFUSED", "code": refused.code}
    report = {
        "schema": SCHEMA,
        "label": LABEL,
        "arm": arm,
        "seed": seed,
        "recipe_digest": original.digest,
        "arm_recipe_digest": None if changed is None else changed.digest,
        "code": ls.code_identity(),
    }
    if changed is None:
        report["admission"] = admission
        return report
    arm_bytes = changed.canonical_bytes
    names = ls._input_names(arm_bytes)
    document = ls.load_verify_set(verify_bytes, verify_sha256, names)
    designs = document["designs"]
    rows = [[float(d["inputs"][n]) for n in names] for d in designs]
    started = time.perf_counter()
    with _seed(ls, seed):
        built = ls.build_and_predict(arm_bytes, raw_manifest, files, rows)
    report["wall_s"] = time.perf_counter() - started
    report["admission"] = built["admission"]
    if built["admission"]["state"] != "ADMITTED":
        return report
    import numpy as np

    spec, predictions = built["spec"], built["predictions"]
    state = built["model"].frozen_state()
    state_digest = "sha256:" + hashlib.sha256(state).hexdigest()
    per_design, aggregate = ls.LOCAL_CHECKS[spec.challenge_id]
    u = ls._u(document)
    results = [per_design(d, predictions[i], u) for i, d in enumerate(designs)]
    report.update(
        challenge={"id": spec.challenge_id, "version": spec.version},
        fit=built["fit"],
        state_digest=state_digest,
        reproduced=(
            None
            if expect_state_digest is None or seed != OFFICIAL_SEED or arm != "original"
            else state_digest == expect_state_digest
        ),
        verify={
            "sha256": hashlib.sha256(verify_bytes).hexdigest(),
            "designs": len(designs),
            "aggregate": aggregate(results, u),
        },
        predictions_sha256=hashlib.sha256(
            np.ascontiguousarray(predictions, dtype=spec.dtype).tobytes()
        ).hexdigest(),
    )
    return report


def _graph(args):
    from carbon.level4 import staging

    if args.envelope:
        _digest, raw_manifest, files = staging.from_envelope(
            json.loads(Path(args.envelope).read_text(encoding="utf-8"))
        )
    else:
        _digest, raw_manifest, files = staging.read_directory(Path(args.submission_dir))
    return raw_manifest, files


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument(
        "--recipe", required=True, help="the construction recipe JSON (in custody)"
    )
    graph = parser.add_mutually_exclusive_group(required=True)
    graph.add_argument("--envelope", help="the build's source-envelope.json")
    graph.add_argument("--submission-dir", help="a lowered graph directory")
    parser.add_argument("--verify", required=True, help="the kit verify set JSON")
    parser.add_argument("--verify-sha256", required=True)
    parser.add_argument("--seed", required=True, type=int)
    parser.add_argument("--arm", required=True)
    parser.add_argument("--expect-state-digest", default=None)
    parser.add_argument("--out", required=True, help="the report JSON (in custody)")
    args = parser.parse_args(argv)
    out = Path(args.out)
    if out.exists():
        print(json.dumps({"refused": "out_exists"}))
        return 2
    try:
        raw_manifest, files = _graph(args)
        report = retrain(
            json.loads(Path(args.recipe).read_text(encoding="utf-8")),
            raw_manifest,
            files,
            Path(args.verify).read_bytes(),
            args.verify_sha256,
            seed=args.seed,
            arm=args.arm,
            expect_state_digest=args.expect_state_digest,
        )
    except BankRefused as refused:
        print(json.dumps({"refused": refused.code}))
        return 2
    out.write_text(
        json.dumps(report, indent=1, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    state = report["admission"]["state"]
    # one line, no digest or value: the report stays in custody
    print(
        json.dumps(
            {"state": state, "arm": args.arm, "reproduced": report.get("reproduced")}
        )
    )
    return 0 if state == "ADMITTED" else 3


if __name__ == "__main__":
    sys.exit(main())
