"""Motor Specialist Bank, PATH B: S-PUB selection, public signals only, RANKED per regime stratum.

Design: codex-queue/reports/BANK/PATHB_SPUB_SELECTION_DESIGN_20261121.md (V2 04:50:41Z: shape Y). Its only input is
the bank file (``bank_features.py`` + ``bank_graph_features.py`` output), which holds allow-listed PUBLIC-SIGNAL
tables only, so no grade, gate, score, crown, Ladder or per-case value can enter the selection.

- Eligible recipe: one of its submissions SUCCEEDED with a public train loss and no infra class, and is not an exact
  copy of another submission (``copy_of``); the earliest such submission's pseudonymous owner is the recipe's owner;
  its forward graph was found (``graph_features``).
- Stratum (Specialist_Bank section 6 within Motor 1.8: only the backbone and training family vary): the physics op
  groups the forward graph uses AT ALL (presence, no threshold) x members (1 / >1) x learning (max steps per member
  1 / >1) x trained arrays (0 / >0: the larger of the init-spec parameter count and the forward graph's ``params/``
  inputs). v1 (21 Nov): v0's "learned" op pattern is dropped (hand-built physics uses it too); learning is the
  training family's s and p. Strata with fewer than ``POOL_BELOW`` eligible recipes pool into
  ``other`` (V2's >= 3 rule for anything that leaves custody).
- Within a stratum: at most ONE recipe per owner (its best), ordered by public TRAIN fit (train loss, lower first),
  then earliest first seen, then digest. EVERY such recipe is ranked; how many are run (K) is HUMAN_INPUT, applied
  later on a receipted line, never here.

Writes the ``selection_spub`` table into the bank file (class C, GPUYard). stdout: per-stratum counts only.
S-PUB means no hidden-derived SELECTION, not uncontaminated recipes (miners shaped recipes on official feedback):
that caveat rides every result.
"""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
import stat
import sys
from collections import Counter, defaultdict
from pathlib import Path

SCHEMA = "carbon.bank-select-spub.v1"
CAVEAT = "S-PUB: no hidden-derived selection; recipes were shaped on official feedback (not uncontaminated)"
#: V2: no metric leaves custody for a cell under 3 recipes; strata under it pool into "other".
POOL_BELOW = 3
GROUPS = {
    "linsolve": {
        "triangular_solve",
        "cholesky",
        "lu",
        "qr",
        "svd",
        "eigh",
        "custom_linear_solve",
    },
    "spectral": {"fft"},
    "loops": {"scan", "cond", "while"},
    "trig": {"sin", "cos"},
}
DDL = """
DROP TABLE IF EXISTS selection_spub;
CREATE TABLE selection_spub(
    recipe_digest TEXT PRIMARY KEY, stratum TEXT NOT NULL, rank INTEGER NOT NULL, cpu_built INTEGER NOT NULL);
"""


class BankRefused(RuntimeError):
    def __init__(self, code):
        super().__init__(code)
        self.code = code


def backbone(ops):
    """The op groups a forward graph uses at all (presence only)."""
    names = {k for k, v in ops.items() if v}
    groups = [g for g, members in GROUPS.items() if names & members]
    return "+".join(sorted(groups)) or "plain"


def training_family(members, max_steps, parameters):
    return "m{}-s{}-p{}".format(
        "1" if (members or 1) <= 1 else "n",
        "1" if (max_steps or 0) <= 1 else "n",
        "0" if not parameters else "n",
    )


def _ranked(rows):
    """{stratum: [(digest, cpu_built)]}: one recipe per owner per stratum, by train loss, first seen, digest."""
    ranked, seen = defaultdict(list), set()
    for stratum, owner, _loss, _first, digest, cpu in sorted(
        rows, key=lambda r: (r[0], r[2], r[3], r[4])
    ):
        if owner is not None and (stratum, owner) in seen:
            continue
        seen.add((stratum, owner))
        ranked[stratum].append((digest, cpu))
    return ranked


def _owner_only(path):
    info = os.lstat(path)
    if stat.S_ISLNK(info.st_mode):
        return False
    if os.name != "posix":
        return True
    return info.st_uid == os.getuid() and not stat.S_IMODE(info.st_mode) & 0o077


def build(bank_file):
    bank_file = Path(bank_file)
    if not bank_file.is_file() or not _owner_only(bank_file):
        raise BankRefused("bank_file_not_owner_only")
    db = sqlite3.connect(bank_file)
    try:
        meta = dict(db.execute("SELECT k, v FROM meta"))
        if (
            meta.get("schema") != "carbon.bank-features.v0"
            or "graph_features_schema" not in meta
        ):
            raise BankRefused("bank_file_incomplete")
        features = {
            r[0]: r[1:]
            for r in db.execute(
                "SELECT recipe_digest, parse_code, members, first_seen_s FROM recipe_features"
            )
        }
        steps = defaultdict(int)
        for digest, knobs in db.execute(
            "SELECT recipe_digest, knobs FROM member_knobs"
        ):
            value = json.loads(knobs).get("steps")
            if isinstance(value, int):
                steps[digest] = max(steps[digest], value)
        forward, params = {}, {}
        for digest, role, ops, parameters, param_inputs in db.execute(
            "SELECT recipe_digest, role, ops, parameters, param_inputs FROM graph_features"
        ):
            if role == "forward":
                forward[digest] = json.loads(ops)
            params[digest] = max(
                params.get(digest, 0), parameters or 0, param_inputs or 0
            )
        owner_of = dict(db.execute("SELECT submission_id, owner FROM lineage"))
        best = {}
        for sid, digest, state, infra, copy_of, device, loss in db.execute(
            "SELECT submission_id, recipe_digest, task_state, infra_class, copy_of, build_device, train_loss"
            " FROM outcomes WHERE recipe_digest IS NOT NULL ORDER BY submission_id"
        ):
            if (
                state != "SUCCEEDED"
                or infra is not None
                or copy_of is not None
                or loss is None
            ):
                continue
            first = features.get(digest, (None, None, None))[2] or 0.0
            current = best.get(digest)
            entry = (first, sid, owner_of.get(sid), loss, device)
            if current is None or entry < current:
                best[digest] = entry
        ineligible = Counter()
        rows = []
        for digest, (parse_code, members, first_seen) in features.items():
            if parse_code is not None:
                ineligible["adapter_refused"] += 1
            elif digest not in best:
                ineligible["no_public_success"] += 1
            elif digest not in forward:
                ineligible["no_graph"] += 1
            else:
                _first, _sid, owner, loss, device = best[digest]
                stratum = (
                    backbone(forward[digest])
                    + "|"
                    + training_family(members, steps.get(digest), params.get(digest))
                )
                rows.append(
                    (stratum, owner, loss, first_seen or 0.0, digest, device == "CPU")
                )
        # pool by the size a stratum has AFTER one-per-owner, then rank the pooled strata again
        sizes = Counter(s for s, _items in _ranked(rows).items() for _ in _items)
        rows = [
            ((r[0] if sizes[r[0]] >= POOL_BELOW else "other"),) + r[1:] for r in rows
        ]
        ranked = _ranked(rows)
        db.executescript(DDL)
        for stratum, items in ranked.items():
            db.executemany(
                "INSERT INTO selection_spub VALUES(?,?,?,?)",
                [(d, stratum, i, int(cpu)) for i, (d, cpu) in enumerate(items)],
            )
        db.execute(
            "INSERT OR REPLACE INTO meta VALUES('selection_spub_schema', ?)", (SCHEMA,)
        )
        db.execute(
            "INSERT OR REPLACE INTO meta VALUES('selection_spub_caveat', ?)", (CAVEAT,)
        )
        db.commit()
    finally:
        db.close()
    eligible = Counter(r[0] for r in rows)
    return {
        "caveat": CAVEAT,
        "eligible": len(rows),
        "ineligible": dict(ineligible),
        "strata": {
            s: {
                "eligible": eligible[s],
                "ranked": len(ranked[s]),
                "cpu_built_ranked": sum(c for _d, c in ranked[s]),
            }
            for s in sorted(ranked)
        },
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--bank", required=True)
    args = parser.parse_args(argv)
    try:
        counts = build(args.bank)
    except BankRefused as refused:
        print(json.dumps({"refused": refused.code}))
        return 2
    print(json.dumps(counts, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
