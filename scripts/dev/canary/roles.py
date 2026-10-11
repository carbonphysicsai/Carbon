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

**Sybil scenarios (the Test Lead, 2026-10-10).** Before its challenger
role, minerJ (its own coldkey, so the chain sees a different miner) plays a
sybil of strong. INCENTIVE-MECHANISM-SIM-01 (#974) predicts a sybil gains
weight through extra noisy draws, not a split:
- `sybil-copy`: strong's exact first recipe. D6 refuses the contested
  commitment at admission, so it is never scored (#974's `copy` row: no
  attacker weight).
- `sybil-near`: strong's neighbours at `train_fraction` 0.985, near-identical
  quality with a different digest. Weight never splits (one incumbent per
  Challenge). A takeover needs a decided final and, across coldkeys, restarts
  the clock: that is the gain #974 measures, observed, not a payment bug.

**Quality is a hypothesis.** The incentive check reports a role ordering
that inverts as ATTENTION, never as a payment blocker. It is evidence about
the recipes, not about who is paid.

    python -m scripts.dev.canary.roles generate --role strong --out FILE
    python -m scripts.dev.canary.roles generate --scenario sybil-near --out FILE
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


#: `{role: {round: recipes}}`: later rounds of a role's list, each a fresh,
#: distinct set of recipes, so a new deployment's handover test (the AX42
#: cutover to v2-bank-e1-r360, the Test Lead 2026-10-11) commits digests no
#: earlier round or scenario used. Round 1 is `ROLES[...]["recipes"]`. Every
#: recipe stays on the role's hypothesis and off the canary's grid.
ROUNDS = {
    "strong": {2: [(8, 0.98), (6, 0.98), (10, 0.98)]},
    "degraded": {2: [(64, 0.15), (64, 0.35), (64, 0.4)]},
}


def recipes_of(role, round_=1):
    """The role's recipes for `round_`, or [] when it has none."""
    hotkey = hotkey_of(role)
    if hotkey is None:
        return []
    if round_ == 1:
        return ROLES[hotkey]["recipes"]
    return ROUNDS.get(role, {}).get(round_, [])


_STRONG = "5CDGqLEPqDGSKJmkGyN2tDFTysyCqATRjLEBwvpy3FZiDqLM"
_SYBIL = "5Gv6kDWFsx8AEarVSnNXHVu1XZ7fHTmMidH5N5dnpvMuPyM5"
#: `{scenario: {"hotkey", "of", "recipes"}}`: a sybil of `of`'s miner.
SCENARIOS = {
    "sybil-copy": {"hotkey": _SYBIL, "of": _STRONG, "recipes": [(8, 0.99)]},
    "sybil-near": {
        "hotkey": _SYBIL,
        "of": _STRONG,
        "recipes": [(8, 0.985), (7, 0.985), (9, 0.985)],
    },
}


def role_of(hotkey):
    """The registered incentive role of `hotkey`, or None."""
    entry = ROLES.get(hotkey)
    return None if entry is None else entry["role"]


def hotkey_of(role):
    found = [h for h, e in ROLES.items() if e["role"] == role]
    return found[0] if len(found) == 1 else None


def generate(role=None, *, scenario=None, round_=1):
    """The role's (or the scenario's) variant list, in the canary runner's
    schema (knn only). `round_` picks a role's later list (`ROUNDS`)."""
    if scenario is not None:
        if scenario not in SCENARIOS:
            raise variants.VariantRefused("scenario_unknown")
        recipes, grid = SCENARIOS[scenario]["recipes"], {"scenario": scenario}
    else:
        recipes = recipes_of(role, round_)
        if not recipes:
            raise variants.VariantRefused("role_has_no_recipes")
        grid = {"role": role} if round_ == 1 else {"role": role, "round": round_}
    challenge = variants._challenge()
    return {
        "schema": variants.SCHEMA,
        "challenge": {"id": challenge.challenge_id, "version": challenge.version},
        "contract_digest": variants.contract_digest(),
        "method": variants.METHOD,
        "grid": {**grid, "recipes": [list(r) for r in recipes]},
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
    which = gen.add_mutually_exclusive_group(required=True)
    which.add_argument("--role", choices=("strong", "degraded"))
    which.add_argument("--scenario", choices=sorted(SCENARIOS))
    gen.add_argument("--round", type=int, default=1, dest="round_")
    gen.add_argument("--out", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        document = generate(args.role, scenario=args.scenario, round_=args.round_)
        args.out.write_bytes(variants.render(document))
    except variants.VariantRefused as refused:
        print(refused.code, file=sys.stderr)
        return 1
    print(f"wrote {args.role or args.scenario}: {len(document['variants'])} recipes")
    return 0


if __name__ == "__main__":
    sys.exit(main())
