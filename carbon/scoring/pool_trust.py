"""R3: self-trust on the POOL route (owner TRUST-AMPLIFIER, 23 Nov 2026; model-eval 5685).

A pool-graded version grades a candidate by asking its model the exam's pool rows. A candidate that
DECLARED self-trust is built with a trust head (graph route H3d: Carbon's trust trainer fits it, a fixed loss) and its graded
inference splits the k trust columns off into ``sigma.json`` (`trust_infer`, retained with the evidence by R2), so the
physics answers the pool exam reads are byte-identical with or without the head. This module reads that ``sigma.json``
beside the grade's per-case errors and gives the trust skill T of `self_trust.trust_skill` on the ADMITTED cells:

- one TrustCase per answered case and trust output whose (class, output) cell the version's admission read admitted, built
  from the grade's own per-case record (`case_errors.assemble`: |error|, U, the bank row it was answered from) and that
  bank row's sigma. The interval score of a central band p +- h depends on the truth only through |p - t|, so the case is
  read as prediction |error|, truth 0: no truth is re-derived and no other output moves;
- sigma = floor + exp(log_sigma): EXACTLY the trust trainer's transform (`physical_graph_trainer_v4.trust_nll`), with the
  version's floors (the same values its trust REGISTRATIONS entry trains with), never exp alone;
- a candidate with no ``sigma.json`` gives T 0 (``absent``); an unreadable one, or a non-finite sigma on a case T reads,
  gives T 0 (``invalid``): never a penalty for not taking part, never a refusal of the physics grade.

`POOL_TRUST` is EMPTY: a version reads trust only once its own registration head names its trust outputs (in the trust
column order) and floors here. With no entry nothing in the pool grade calls this module, so every registered version is
bit for bit unchanged. Whether T then enters the grade is `self_trust.amplifier_for` (also empty): T alone is custody.

Custody only: the record holds per-cell skills over hidden cases (as private as the hidden pack); no miner surface reads it.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass

from carbon.scoring import self_trust

#: The largest ``sigma.json`` a grade reads (the build worker's own cap on the file: 16 MiB).
MAX_SIGMA_BYTES = 16 * 1024**2
#: The custody sidecar a trust version's grade writes beside its accuracy record (`lean_recipe_retention`).
SIDECAR = "trust-record.json"
SCHEMA = "carbon.pool.trust-record.v1"


class PoolTrustRefused(ValueError):
    """The version's registration or the grade's own record cannot give a sound trust read: Carbon's, never the candidate's."""

    def __init__(self, code):
        super().__init__(code)
        self.code = code


def _require(condition, code):
    if not condition:
        raise PoolTrustRefused(code)


@dataclass(frozen=True)
class PoolTrust:
    """One version's pool trust registration: the trust outputs in the ``sigma.json`` column order, and the trainer's sigma
    floor per output (the version's trust REGISTRATIONS values: one source, a test holds them equal).
    """

    outputs: tuple
    sigma_floor: tuple


#: (challenge_id, version) -> PoolTrust. EMPTY until a version's registration head adds it.
POOL_TRUST: dict = {}


def check(trust):
    _require(isinstance(trust, PoolTrust), "pool_trust_registration_malformed")
    _require(
        type(trust.outputs) is tuple
        and len(trust.outputs) >= 1
        and all(type(o) is str and o for o in trust.outputs)
        and len(set(trust.outputs)) == len(trust.outputs),
        "pool_trust_outputs_malformed",
    )
    _require(
        type(trust.sigma_floor) is tuple
        and len(trust.sigma_floor) == len(trust.outputs)
        and all(
            type(v) in (int, float) and math.isfinite(v) and v >= 0
            for v in trust.sigma_floor
        ),
        "pool_trust_sigma_floor_malformed",
    )


def sigma_rows(raw, n_rows, trust):
    """The per-bank-row ``{output: sigma}`` of a candidate's ``sigma.json`` bytes, or None when it is unreadable (the
    candidate's: its T is then 0, ``invalid``). ``raw`` None = no trust block (T 0, ``absent``): returns ``()``.
    ``n_rows`` None takes the file's own row count (`record` then refuses a case row the file does not cover).
    """
    check(trust)
    if raw is None:
        return ()
    if type(raw) is not bytes or len(raw) > MAX_SIGMA_BYTES:
        return None
    try:
        document = json.loads(raw)
    except (ValueError, UnicodeDecodeError):
        return None
    k = len(trust.outputs)
    if type(document) is not list or (n_rows is not None and len(document) != n_rows):
        return None
    rows = []
    for row in document:
        if type(row) is not list or len(row) != k:
            return None
        values = {}
        columns = zip(trust.outputs, trust.sigma_floor, row, strict=True)
        for name, floor, cell in columns:
            if type(cell) not in (int, float) or not math.isfinite(cell):
                return None
            try:
                sigma = floor + math.exp(cell)
            except OverflowError:
                return None
            if not (math.isfinite(sigma) and sigma > 0):
                return None
            values[name] = sigma
        rows.append(values)
    return tuple(rows)


def _admitted_pairs(admitted):
    _require(
        type(admitted) in (list, tuple, set, frozenset), "pool_trust_admitted_malformed"
    )
    pairs = set()
    for cell in admitted:
        _require(
            type(cell) in (list, tuple)
            and len(cell) == 3
            and all(type(v) is str for v in cell),
            "pool_trust_admitted_malformed",
        )
        pairs.add((cell[1], cell[2]))
    return pairs


def record(content, sigma, admitted, trust, band_level):
    """T over the admitted cells of one pool grade (A1-A2 of `self_trust`), from the grade's per-case content
    (`case_errors.assemble`), the candidate's `sigma_rows` (``()`` absent, None unreadable), the admitted
    ``(family, class, output)`` cells and the band level. Returns `self_trust.trust_skill`'s dict plus ``n_cells``.
    """
    check(trust)
    pairs = _admitted_pairs(admitted)
    _require(type(content) is dict, "pool_trust_case_record_malformed")
    for key in ("row_index", "class_index", "class_names", "invalid", "output_names"):
        _require(key in content, "pool_trust_case_record_malformed")
    names = content["output_names"]
    # the trust outputs the grade measured, by their column in the case record
    wanted = [(j, o) for j, o in enumerate(names) if o in trust.outputs]
    if sigma == ():
        return {
            "status": self_trust.ABSENT,
            "reason": None,
            "t": 0.0,
            "cells": None,
            "n_cells": 0,
        }
    if sigma is None:
        return {
            "status": self_trust.INVALID,
            "reason": "pool_trust_sigma_unreadable",
            "t": 0.0,
            "cells": None,
            "n_cells": 0,
        }
    from carbon.scoring import case_errors

    cells = {}
    sources = content.get("source")
    for i, row in enumerate(content["row_index"]):
        if content["invalid"][i]:
            continue  # an invalid physics answer is already the grade's; T reads valid answers only
        if sources is not None and sources[i] == case_errors.SOURCE_CONFIRMATION:
            continue  # the confirmation rows are the crown's alone (CROWN-CONFIRMATION-SET): never in T
        _require(
            type(row) is int and 0 <= row < len(sigma), "pool_trust_row_not_in_sigma"
        )
        name = content["class_names"][content["class_index"][i]]
        for j, output in wanted:
            if (name, output) not in pairs:
                continue
            error, u = content["abs_error"][i][j], content["u"][i][j]
            if error is None or u is None or not u > 0:
                continue  # no measured error on this case (a typed output, an absent value): not read
            case = self_trust.TrustCase(
                predictions={output: float(error)},
                truths={output: 0.0},
                u={output: float(u)},
                status=self_trust.PRESENT,
                answer=self_trust.TrustAnswer(
                    form=self_trust.SIGMA,
                    sigmas={output: sigma[row][output]},
                    bands={},
                    flag=False,
                ),
            )
            cells.setdefault((name, output), []).append(case)
    if not cells:
        return {
            "status": self_trust.SCORED,
            "reason": "pool_trust_no_admitted_trust_cell",
            "t": 0.0,
            "cells": [],
            "n_cells": 0,
        }
    out = self_trust.trust_skill(self_trust.SIGMA, band_level, cells)
    # JSON-safe: per cell [class, output, T_cell or None], in sorted cell order
    listed = [[c, o, out["cells"][(c, o)]] for c, o in sorted(out["cells"])]
    return {**out, "cells": listed, "n_cells": len(cells)}


def admitted_cells(accuracy):
    """The admitted ``(family, class, output)`` cells of a grade's custody accuracy record (`pool_physics_score`: a row
    is ``scored`` exactly when its cell is a scoring / admitted headroom cell)."""
    _require(
        type(accuracy) is dict and type(accuracy.get("rows")) is list,
        "pool_trust_accuracy_record_malformed",
    )
    return sorted(
        {
            (row["family"], row["class"], row["output"])
            for row in accuracy["rows"]
            if row.get("scored") is True and row.get("family") is not None
        }
    )


def band_level(challenge_id, version):
    """The band T is read at: the version's switched-on amplifier's, else the owner's (TRUST-AMPLIFIER-VALUES)."""
    amplifier = self_trust.amplifier_for(challenge_id, version)
    return (amplifier or self_trust.OWNER_AMPLIFIER).band_level


def grade_record(challenge_id, version, *, sigma_raw, case_content, accuracy):
    """The custody document of one grade of a trust version, or None for every other version (nothing read)."""
    trust = POOL_TRUST.get((challenge_id, version))
    if trust is None:
        return None
    sigma = sigma_rows(sigma_raw, None, trust)
    out = record(
        case_content,
        sigma,
        admitted_cells(accuracy),
        trust,
        band_level(challenge_id, version),
    )
    return {
        "schema": SCHEMA,
        "challenge_id": challenge_id,
        "version": version,
        "outputs": list(trust.outputs),
        "band_level": band_level(challenge_id, version),
        "amplified": self_trust.amplifier_for(challenge_id, version) is not None,
        "record": out,
    }
