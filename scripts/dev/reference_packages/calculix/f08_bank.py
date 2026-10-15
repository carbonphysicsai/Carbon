"""Register and freeze an f08 reference bank (F08-SCIENCE-VALUES-01, DEVELOPMENT).

    python3 f08_bank.py register --out REGISTRATION.json
    python3 f08_bank.py freeze --registration REGISTRATION.json --seed SEED \
        --out DIR [--count 256] [--h 3] [--jobs 4] [--public-seed] \
        [--role train] [--exclude OTHER_MANIFEST.json ...]

`register` seals a `carbon.f08-preparation.v1` registration from the current
sources: the Q1 lattice (length 180:5:260, width 60:5:100, thickness 4:0.5:8,
rib height 8:1:16, rib thickness 3:0.5:5, relief 20:5:60 mm), P = Q = w = 1/3
over the three damping ratios (all three are solved for every geometry), and
the image, mesh image, deck, proof, material and observer pins.

`freeze` draws `count` distinct valid lattice geometries with
`structures_readiness.actions` (uniform, Q1/Q2), writes one deck per geometry
(static, 48-mode eigen and the three damping sweeps in one ccx launch, at the
V9 bank mesh) and a `carbon.reference-triage.frozen-decks.v1` manifest the
triage runner executes unchanged (`reservation: bank`). The seed is recorded
only with --public-seed; a hidden bank's seed is owner-held and never written
here. Nothing is solved by this script.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(ROOT))

import f08_deck as deck
import f08_freeze as freeze_mod

from carbon.challenge_pipeline import structures_readiness as s

STEPS = (5, 5, 0.5, 1, 0.5, 5)  # Q1 lattice steps, packet field order
MODES = 48


def _sha(path):
    return "sha256:" + hashlib.sha256(Path(path).read_bytes()).hexdigest()


def registration(scope="PUBLIC_DEVELOPMENT"):
    return s.seal(
        {
            "schema": s.SCHEMA,
            "family": s.FAMILY,
            "scope": scope,
            "authority": "F08-SCIENCE-VALUES-01 under OWNER-SOLVER-READINESS-SCIENCE-DELEGATION-01; DEVELOPMENT only",
            "grammar": {
                field: {"min": lo, "max": hi, "step": step}
                for field, (lo, hi), step in zip(s.FIELDS, s.BOUNDS, STEPS)
            },
            "P": {str(z): 1 / 3 for z in s.DAMPING},
            "Q": {str(z): 1 / 3 for z in s.DAMPING},
            "w": {str(z): 1 / 3 for z in s.DAMPING},
            "pins": {
                "image": s.IMAGE,
                "mesh_image": s.MESH_IMAGE,
                "deck": _sha(HERE / "f08_deck.py"),
                "proof": _sha(HERE / "f08_proof.py"),
                "material": s.tasks.digest(s.MATERIAL),
                "observer": _sha(HERE / "f08_freeze.py"),
            },
        }
    )


def draw(reg, seed, count, exclude=frozenset()):
    """`count` distinct valid lattice actions in a deterministic order.

    structures_readiness.actions draws at most 1000 per call, so larger sets
    (the 8x TRAIN rung) chain sub-seeds derived from `seed`; prefixes of one
    draw are the nested smaller sets. Actions whose digest is in `exclude`
    (another role's manifest) are skipped, which keeps roles disjoint.
    """
    rows, seen, chunk = [], set(exclude), 0
    while len(rows) < count:
        sub = int(
            hashlib.sha256(f"f08-draw:{seed}:{chunk}".encode()).hexdigest()[:15], 16
        )
        for row in s.actions(
            reg, seed=sub if chunk else seed, count=min(1000, max(count, 1))
        ):
            key = s.tasks.digest(row)
            if key not in seen:
                seen.add(key)
                rows.append(row)
                if len(rows) == count:
                    break
        chunk += 1
    return rows


def beam_screen(c):
    """SCREENING_ONLY Euler-Bernoulli estimate of a ribbed cantilever (relief mass only).

    Returns mass kg, static tip mm/N, f1 Hz and the worst 80-600 Hz single-mode
    tip compliance at zeta 0.005. Within 2-10 % of the eight measured triage
    primaries (triage-f08-observed.json); never a reference value.
    """
    L, W, t, hr, tr, lr = (c[k] for k in s.FIELDS)
    area = W * t + 2 * tr * hr
    zbar = (W * t * t / 2 + 2 * tr * hr * (t + hr / 2)) / area
    inertia = (
        W * t**3 / 12
        + W * t * (t / 2 - zbar) ** 2
        + 2 * (tr * hr**3 / 12 + tr * hr * (t + hr / 2 - zbar) ** 2)
    )
    mass = deck.RHO * (area * L - 20 * lr * t) * 1000
    static = (L - deck.PAD_X / 2) ** 3 / (3 * deck.E * inertia)
    f1 = (
        1.8751040687**2
        / (2 * math.pi)
        * math.sqrt(deck.E * inertia / (deck.RHO * area * L**4))
    )
    worst = 0.0
    for f in [80 + 0.5 * k for k in range(1041)] + [f1]:
        if 80 <= f <= 600:
            r = f / f1
            worst = max(
                worst, static / math.sqrt((1 - r * r) ** 2 + (2 * 0.005 * r) ** 2)
            )
    return {
        "mass_kg": mass,
        "static_mm_per_n": static,
        "f1_hz": f1,
        "worst_mm_per_n": worst,
    }


#: The 27-cell P_job grid (question-law.json) used to flag boundary geometries.
GRID = [
    (dyn, st, m)
    for dyn in (0.10, 0.15, 0.20)
    for st in (0.02, 0.03, 0.04)
    for m in (0.35, 0.45, 0.55)
]


def boundary(c, band=0.2):
    """Q_boundary membership (R4): some grid cell's binding ratio lies in [1 - band, 1 + band]."""
    e = beam_screen(c)
    return any(
        1 - band
        <= max(e["worst_mm_per_n"] / dyn, e["static_mm_per_n"] / st, e["mass_kg"] / m)
        <= 1 + band
        for dyn, st, m in GRID
    )


def answer_region(c, band=0.2):
    """Q2 enrichment membership: feasible or within +band of feasible for some grid cell."""
    e = beam_screen(c)
    return any(
        max(e["worst_mm_per_n"] / dyn, e["static_mm_per_n"] / st, e["mass_kg"] / m)
        <= 1 + band
        for dyn, st, m in GRID
    )


SCREENS = {"boundary": boundary, "answer-region": answer_region}


def screen(reg, seed, pool, count, exclude=frozenset(), kind="boundary"):
    """The first `count` screen-flagged geometries of a `pool` draw; flagged fraction gives w."""
    rows = draw(reg, seed, pool, exclude)
    flagged = [r for r in rows if SCREENS[kind](r)]
    return {
        "screen": kind,
        "pool": pool,
        "flagged": len(flagged),
        "flagged_fraction": len(flagged) / pool,
        "actions": flagged[:count],
    }


def enriched(reg, seed, count, exclude=frozenset(), fraction=0.5):
    """Q2 amendment: (1 - fraction) of the set from P, the rest from P | answer region.

    Returns the actions and, per action, w = P/Q for population-mean diagnostics.
    """
    n_p = count - round(fraction * count)
    base = draw(reg, seed, n_p, exclude)
    taken = frozenset(exclude) | {s.tasks.digest(r) for r in base}
    sub = int(hashlib.sha256(f"f08-enrich:{seed}".encode()).hexdigest()[:15], 16)
    pool = 16 * (count - n_p)
    extra = screen(reg, sub, pool, count - n_p, taken, "answer-region")
    if len(extra["actions"]) < count - n_p:
        raise SystemExit(
            "answer-region pool too small; raise the pool, never shrink the set silently"
        )
    p_region = extra["flagged_fraction"]
    rows = base + extra["actions"]
    q = [
        (1 - fraction) + (fraction / p_region if answer_region(r) else 0.0)
        for r in rows
    ]
    return rows, [1 / x for x in q], p_region


def _excluded(paths):
    keys = set()
    for path in paths or ():
        keys |= {
            c["action_digest"]
            for c in json.loads(Path(path).read_text())["cases"]
            if "action_digest" in c
        }
    return frozenset(keys)


def freeze(
    reg,
    seed,
    out,
    count=256,
    h_mm=3.0,
    jobs=1,
    public_seed=False,
    role="bank",
    exclude=None,
    actions=None,
    enrich=0.0,
):
    s.validate(reg)
    if reg["pins"] != registration(reg["scope"])["pins"]:
        raise SystemExit(
            "current sources differ from the registration pins; re-register"
        )
    weights, p_region = None, None
    if actions is not None:
        rows = actions
    elif enrich:
        rows, weights, p_region = enriched(reg, seed, count, _excluded(exclude), enrich)
    else:
        rows = draw(reg, seed, count, _excluded(exclude))
    rows = [s.action(reg, r) for r in rows]
    count = len(rows)
    out = Path(out)

    def one(item):
        i, row = item
        name = f"{role}-{i:04d}"
        d = out / "f08" / name
        size = deck.write_case(row, d, h_mm, MODES)
        return {"family": "f08", "case": name, "reservation": role, "command": deck.BANK_COMMAND,
                "mesh": size, **deck.estimate(size["nodes"]), "action": row, "action_digest": s.tasks.digest(row),
                "files": freeze_mod._digest(d)}  # fmt: skip

    with ThreadPoolExecutor(max(1, jobs)) as pool:
        cases = list(pool.map(one, enumerate(rows)))
    for case, w in zip(cases, weights or ()):
        case["w_P_over_Q"] = w
    manifest = {
        "schema": "carbon.reference-triage.frozen-decks.v1",
        "ticket": "F08-SCIENCE-VALUES-01 bank freeze",
        "authority": "DEVELOPMENT bank; no LIVE, reward or spend",
        "image": reg["pins"]["image"],
        "mesh_image_f08": reg["pins"]["mesh_image"],
        "bank": {
            "registration_digest": reg["registration_digest"],
            "scope": reg["scope"],
            "count": count,
            "h_mm": h_mm,
            "modes": MODES,
            "seed": seed if public_seed else "WITHHELD",
            "role": role,
            "Q_geometry": (
                f"{1 - enrich:g} P + {enrich:g} P | screen answer region (flagged fraction {p_region:.4f})"
                if enrich
                else ("explicit action list" if actions is not None else "P")
            ),
            "excluded_manifests": [str(p) for p in exclude or ()],
        },
        "cases": cases,
        "counts": {role: len(cases)},
    }
    (out / "manifest.json").write_text(json.dumps(manifest, indent=1) + "\n")
    return manifest


def gate(observed, h_mm):
    """0 iff the triage observation's V9 bank mesh is `h_mm` (bank decks frozen at it)."""
    path = Path(observed)
    pick = json.loads(path.read_text()).get("bank_mesh", {}) if path.exists() else {}
    ok = pick.get("status") == "PASS" and pick.get("h_mm") == h_mm
    print(json.dumps({"gate": "PASS" if ok else "REFUSED", "v9": pick, "h_mm": h_mm}))
    return 0 if ok else 1


def main(argv=None):
    p = argparse.ArgumentParser(prog="f08_bank")
    sub = p.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("register")
    r.add_argument("--out", type=Path, required=True)
    f = sub.add_parser("freeze")
    f.add_argument("--registration", type=Path, required=True)
    f.add_argument("--seed", type=int, required=True)
    f.add_argument("--out", type=Path, required=True)
    f.add_argument("--count", type=int, default=256)
    f.add_argument("--h", type=float, default=3.0)
    f.add_argument("--jobs", type=int, default=1)
    f.add_argument("--public-seed", action="store_true")
    f.add_argument(
        "--role",
        default="bank",
        help="data role, e.g. train, practice, decision-study, bank",
    )
    f.add_argument(
        "--exclude",
        type=Path,
        nargs="*",
        help="manifests whose actions this role must not reuse",
    )
    f.add_argument(
        "--actions",
        type=Path,
        help="freeze this `screen` action list instead of drawing",
    )
    f.add_argument(
        "--enrich",
        type=float,
        default=0.0,
        help="Q2 answer-region fraction (bank roles: 0.5)",
    )
    b = sub.add_parser("screen")
    b.add_argument("--registration", type=Path, required=True)
    b.add_argument("--seed", type=int, required=True)
    b.add_argument("--pool", type=int, default=1024)
    b.add_argument("--count", type=int, default=64)
    b.add_argument("--exclude", type=Path, nargs="*")
    b.add_argument("--kind", choices=sorted(SCREENS), default="boundary")
    b.add_argument("--out", type=Path, required=True)
    g = sub.add_parser("gate", help="exit 1 unless V9 picked this bank mesh")
    g.add_argument("--observed", type=Path, required=True)
    g.add_argument("--h", type=float, required=True)
    args = p.parse_args(argv)
    if args.cmd == "gate":
        return gate(args.observed, args.h)
    if args.cmd == "register":
        args.out.write_text(json.dumps(registration(), indent=1, sort_keys=True) + "\n")
        print(json.loads(args.out.read_text())["registration_digest"])
    elif args.cmd == "screen":
        reg = json.loads(args.registration.read_text())
        doc = screen(
            reg, args.seed, args.pool, args.count, _excluded(args.exclude), args.kind
        )
        args.out.write_text(json.dumps(doc, indent=1) + "\n")
        print(
            json.dumps(
                {k: doc[k] for k in ("screen", "pool", "flagged", "flagged_fraction")}
            )
        )
    else:
        reg = json.loads(args.registration.read_text())
        acts = json.loads(args.actions.read_text())["actions"] if args.actions else None
        doc = freeze(
            reg,
            args.seed,
            args.out,
            args.count,
            args.h,
            args.jobs,
            args.public_seed,
            args.role,
            args.exclude,
            acts,
            args.enrich,
        )
        print(
            json.dumps(
                {"cases": len(doc["cases"]), "registration": reg["registration_digest"]}
            )
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
