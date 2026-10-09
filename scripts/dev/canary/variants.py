"""The canary's registered variant list (CANARY-01 S1, plan §2).

Rule v2 scores one submission per hotkey per window, and a submission's id is
a digest of the hotkey, Challenge, strategy and contract: the same recipe sent
again is the same submission, never re-scored. So every canary cycle sends a
recipe it has never sent. The list is that supply of recipes, used in order.

Every entry is the cheapest registered method, `knn`, with both of its
registered knobs set explicitly:

- `neighbours`, 1 to 64 (`architecture.neighbours`, knn only);
- `train_fraction`, a seeded subset of TRAIN v1 within 0.1 to 1.0.

The grid is every `neighbours` 1-64 at each of five `train_fraction` values,
1.0 down to 0.8 in steps of 0.05: 320 recipes, about 48 days at one cycle per
1080-block rotation. These are miner-side recipe choices of a deliberately
baseline method, not thresholds or scientific values. Generation is
deterministic: the same code and contract give the same file byte for byte.

Generation checks every entry against the capability registry's bounds and the
Challenge's design check, compiles it, and records its `strategy_hash`; it
refuses a grid with two entries of one hash. The file names the contract
digest it was compiled under, and the runner refuses a list whose digest is
no longer the Challenge's (`variant_list_stale`): regenerate it then.

    python -m scripts.dev.canary.variants generate   # writes variants.json
    python -m scripts.dev.canary.variants check      # compiles every entry
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

SCHEMA = "carbon.canary.variants.v1"
LIST_PATH = Path(__file__).with_name("variants.json")
METHOD = "knn"
NEIGHBOURS = tuple(range(1, 65))
TRAIN_FRACTIONS = (1.0, 0.95, 0.9, 0.85, 0.8)
MAX_BYTES = 1 << 20
_HASH = re.compile(r"sha256:[0-9a-f]{64}")


class VariantRefused(ValueError):
    """A variant list, or one entry, the runner will not use: a closed code."""

    def __init__(self, code):
        super().__init__(code)
        self.code = code


def _challenge():
    from carbon.battery.challenge import CHALLENGE

    return CHALLENGE


def strategy(neighbours, train_fraction):
    """One canary recipe: knn with both registered knobs set."""
    return {
        "schema_version": "1.0",
        "challenge_id": _challenge().challenge_id,
        "backbone": METHOD,
        "parameters": {"neighbours": neighbours, "train_fraction": train_fraction},
    }


def strategies():
    """Every recipe of the grid, in the list's order: `train_fraction`
    outer, `neighbours` inner. Computed without compiling."""
    return [strategy(n, f) for f in TRAIN_FRACTIONS for n in NEIGHBOURS]


def registry_bounds():
    """The registered bounds of the two knobs: `{knob: (low, high)}`, read
    from the capability registry, with knn among the families each applies
    to. Raises `VariantRefused` when either is not registered so."""
    from carbon.reconstruction.capability_registry import BATTERY_REGISTRY

    found = {}
    for entry in BATTERY_REGISTRY:
        knob = entry.capability_id.rsplit(".", 1)[-1]
        if knob in ("neighbours", "train_fraction") and entry.surface is not None:
            if entry.applies_to is not None and METHOD not in entry.applies_to:
                continue
            found[knob] = (entry.surface.low, entry.surface.high)
    if set(found) != {"neighbours", "train_fraction"}:
        raise VariantRefused("variant_knob_not_registered")
    return found


def within_registry(bounds=None):
    """Whether every value of the grid is within the registered bounds."""
    bounds = registry_bounds() if bounds is None else bounds
    low, high = bounds["neighbours"]
    if not all(low <= n <= high for n in NEIGHBOURS):
        return False
    low, high = bounds["train_fraction"]
    return all(low <= f <= high for f in TRAIN_FRACTIONS)


def compiled_hash(recipe, contracts=None):
    """The recipe's `strategy_hash` when it compiles to the knn family and the
    design check calls it submittable; otherwise `VariantRefused`."""
    from carbon.battery.compile import compile_recipe
    from carbon.development_session.design_check import check_design
    from carbon.development_session.research_catalog import RecipeRejected

    try:
        _, compiled = compile_recipe(recipe, contracts=contracts)
    except RecipeRejected:
        raise VariantRefused("variant_does_not_compile") from None
    if compiled.family != METHOD:
        raise VariantRefused("variant_not_knn")
    if check_design({"strategy": recipe})["verdict"] != "submittable":
        raise VariantRefused("variant_not_submittable")
    return compiled.strategy_hash


def contract_digest():
    from carbon.reconstruction.capability_registry import contract_digest as current

    return current(_challenge().challenge_id)


def generate():
    """The whole list, every entry compiled. Deterministic."""
    from carbon.battery.contracts import battery_contracts

    if not within_registry():
        raise VariantRefused("variant_outside_registry")
    contracts = battery_contracts()
    entries, seen = [], set()
    for index, recipe in enumerate(strategies()):
        hashed = compiled_hash(recipe, contracts)
        if hashed in seen:
            raise VariantRefused("variant_hash_repeated")
        seen.add(hashed)
        entries.append({"index": index, "strategy": recipe, "strategy_hash": hashed})
    challenge = _challenge()
    return {
        "schema": SCHEMA,
        "challenge": {"id": challenge.challenge_id, "version": challenge.version},
        "contract_digest": contract_digest(),
        "method": METHOD,
        "grid": {
            "neighbours": [NEIGHBOURS[0], NEIGHBOURS[-1]],
            "train_fraction": list(TRAIN_FRACTIONS),
        },
        "variants": entries,
    }


def render(document):
    """The file's exact bytes."""
    return (json.dumps(document, indent=1, sort_keys=True) + "\n").encode()


def digest(raw):
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def parse(raw):
    """A variant list from its bytes, structurally checked: the schema, the
    method, sequential indices, a knn strategy per entry and distinct
    `strategy_hash`es. Compiling is `check_entry`'s, per entry used."""
    try:
        document = json.loads(raw)
    except ValueError:
        raise VariantRefused("variant_list_unreadable") from None
    if (
        type(document) is not dict
        or set(document)
        != {"schema", "challenge", "contract_digest", "method", "grid", "variants"}
        or document["schema"] != SCHEMA
        or document["method"] != METHOD
        or type(document["challenge"]) is not dict
        or set(document["challenge"]) != {"id", "version"}
        or type(document["contract_digest"]) is not str
        or not _HASH.fullmatch(document["contract_digest"])
        or type(document["variants"]) is not list
        or not document["variants"]
    ):
        raise VariantRefused("variant_list_unreadable")
    seen = set()
    for position, entry in enumerate(document["variants"]):
        if (
            type(entry) is not dict
            or set(entry) != {"index", "strategy", "strategy_hash"}
            or entry["index"] != position
            or type(entry["strategy"]) is not dict
            or entry["strategy"].get("backbone") != METHOD
            or type(entry["strategy_hash"]) is not str
            or not _HASH.fullmatch(entry["strategy_hash"])
        ):
            raise VariantRefused("variant_list_unreadable")
        if entry["strategy_hash"] in seen:
            raise VariantRefused("variant_hash_repeated")
        seen.add(entry["strategy_hash"])
    return document


def load(path):
    """`(document, digest)` of the list at `path`."""
    try:
        raw = Path(path).read_bytes()
    except OSError:
        raise VariantRefused("variant_list_unreadable") from None
    if len(raw) > MAX_BYTES:
        raise VariantRefused("variant_list_unreadable")
    return parse(raw), digest(raw)


def check_entry(document, index):
    """The entry at `index`, once it compiles to its recorded hash now."""
    entry = document["variants"][index]
    if compiled_hash(entry["strategy"]) != entry["strategy_hash"]:
        raise VariantRefused("variant_hash_mismatch")
    return entry


def main(argv=None):
    parser = argparse.ArgumentParser(prog="python -m scripts.dev.canary.variants")
    parser.add_argument("command", choices=("generate", "check"))
    parser.add_argument("--path", type=Path, default=LIST_PATH)
    args = parser.parse_args(argv)
    try:
        if args.command == "generate":
            args.path.write_bytes(render(generate()))
            print(f"wrote {len(strategies())} variants")
            return 0
        raw = args.path.read_bytes()
        if raw != render(generate()):
            print("variant_list_differs: regenerate it", file=sys.stderr)
            return 1
        print(f"ok: {len(parse(raw)['variants'])} variants compile, all distinct")
        return 0
    except VariantRefused as refused:
        print(refused.code, file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
