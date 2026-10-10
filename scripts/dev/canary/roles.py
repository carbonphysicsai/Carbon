"""INCENTIVE-CANARY-01 slice 2: the incentive roles' hotkeys and recipes.

Three registered rehearsal miners on testnet 567, paid, never canary-listed,
on the main deployment only (the Test Lead, 2026-10-10; registered by the
owner). Each runs the canary runner (#901) with its own role list:

| Role | Miner | Recipes | Hypothesis |
|---|---|---|---|
| strong | carbon-rehearsal-minerH, UID 14 | knn k = 8, 7 or 9 at train_fraction 0.99 | well-chosen neighbours with almost all the data |
| degraded | carbon-rehearsal-minerI, UID 15 | knn k = 64 at train_fraction 0.2, 0.25 or 0.3 | oversmoothed and data-starved: worse than strong |
| challenger | carbon-rehearsal-minerJ, UID 16 | none yet (slice 3) | calibrated against strong's measured score |

**Off the canary's grid.** Every role recipe uses a `train_fraction` the
canary's grid never uses, so no role commits a digest the canary committed
first (OWNER-COMMITMENT-POSTER-01 D6 refuses a contested commitment).

**Quality is a hypothesis.** The incentive check reports a role ordering
that inverts as ATTENTION, never as a payment blocker. It is evidence about
the recipes, not about who is paid.

    python -m scripts.dev.canary.roles generate --role strong --out FILE
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from scripts.dev.canary import variants

RECORD = "INCENTIVE-CANARY-01 (the Test Lead, 2026-10-10; owner-registered UIDs 14-16)"
#: `{hotkey: {"role", "uid", "recipes": [(neighbours, train_fraction), ...]}}`.
ROLES = {
    "5CDGqLEPqDGSKJmkGyN2tDFTysyCqATRjLEBwvpy3FZiDqLM": {
        "role": "strong",
        "uid": 14,
        "recipes": [(8, 0.99), (7, 0.99), (9, 0.99)],
    },
    "5Fux2HubeZZU2BmDnUgJ2MmE58aXrawbhwEkyyCqrWNKdLLm": {
        "role": "degraded",
        "uid": 15,
        "recipes": [(64, 0.2), (64, 0.25), (64, 0.3)],
    },
    "5Gv6kDWFsx8AEarVSnNXHVu1XZ7fHTmMidH5N5dnpvMuPyM5": {
        "role": "challenger",
        "uid": 16,
        "recipes": [],
    },
}


def role_of(hotkey):
    """The registered incentive role of `hotkey`, or None."""
    entry = ROLES.get(hotkey)
    return None if entry is None else entry["role"]


def hotkey_of(role):
    found = [h for h, e in ROLES.items() if e["role"] == role]
    return found[0] if len(found) == 1 else None


def generate(role):
    """The role's variant list, in the canary runner's schema (knn only)."""
    hotkey = hotkey_of(role)
    if hotkey is None or not ROLES[hotkey]["recipes"]:
        raise variants.VariantRefused("role_has_no_recipes")
    challenge = variants._challenge()
    recipes = ROLES[hotkey]["recipes"]
    return {
        "schema": variants.SCHEMA,
        "challenge": {"id": challenge.challenge_id, "version": challenge.version},
        "contract_digest": variants.contract_digest(),
        "method": variants.METHOD,
        "grid": {"role": role, "recipes": [list(r) for r in recipes]},
        "variants": [
            {
                "index": index,
                "strategy": variants.strategy(n, f),
                "strategy_hash": variants.compiled_hash(variants.strategy(n, f)),
            }
            for index, (n, f) in enumerate(recipes)
        ],
    }


def main(argv=None):
    parser = argparse.ArgumentParser(prog="python -m scripts.dev.canary.roles")
    sub = parser.add_subparsers(dest="command", required=True)
    gen = sub.add_parser("generate")
    gen.add_argument("--role", required=True, choices=("strong", "degraded"))
    gen.add_argument("--out", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        args.out.write_bytes(variants.render(generate(args.role)))
    except variants.VariantRefused as refused:
        print(refused.code, file=sys.stderr)
        return 1
    print(f"wrote {args.role}: {len(ROLES[hotkey_of(args.role)]['recipes'])} recipes")
    return 0


if __name__ == "__main__":
    sys.exit(main())
