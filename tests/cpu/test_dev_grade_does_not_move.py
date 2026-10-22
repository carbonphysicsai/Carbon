"""A development grade never moves with the sealed-bank and copy changes (E4,
traceable copies; Validator, 2026-10-22): a fixed fixture model graded on each
Challenge's development bank gives byte-identical A, D and gates before
(``e3390ce23``) and after. Only producer digests may change."""

from __future__ import annotations

import hashlib
import json

from carbon.challenge_kit import physical_pack
from carbon.scoring import (
    battery_dual_pack,
    cooling_dual_pack,
    f02_dual_pack,
    f08_dual_pack,
    motor_dual_pack,
)
from carbon.scoring import physical_dual_pack as physical

ADAPTERS = {
    "motor": motor_dual_pack,
    "cooling": cooling_dual_pack,
    "f08": f08_dual_pack,
    "f02": f02_dual_pack,
    "battery": battery_dual_pack,
}
#: sha256 of the canonical measurement of the fixture model, taken on e3390ce23.
GOLDEN = "4d6cee84f962a9d50b55e7f68bdc64b04cfa64a563ebdd04791e657cd1b84386"


def _graded(adapter):
    version, challenge = adapter.VERSION, adapter.CHALLENGE
    public = physical_pack.public_roles(challenge, version)
    bank = physical_pack.development_bank(challenge, version)
    names = physical.input_names(adapter)
    rows = physical.bank_rows(bank, names)
    definition = {
        **adapter.definition(bank=bank, train_raw=public["train"]),
        "challenge": {"id": challenge, "version": version},
        "scope": "PUBLIC_DEVELOPMENT_EXPOSED_BANK",
        "bank_digest": physical.bank_digest(bank),
    }
    fixed = next(r["reference"] for r in rows if r["reference"] is not None)
    outputs = []
    for i, row in enumerate(rows):
        scale = 1.0 + 0.003 * (((i * 2654435761) % 1000) / 1000.0 - 0.5)
        ref = row["reference"] if row["reference"] is not None else fixed
        outputs.append([None if v is None else float(v) * scale for v in ref])
    measured = adapter.measure(
        bank_rows=rows,
        outputs=outputs,
        repeats=[outputs, outputs],
        definition=definition,
        limits=json.loads(public["important_limit_definition"]),
        objective=json.loads(public["design_objective"]),
        train_raw=public["train"],
        names=names,
    )
    return json.loads(json.dumps(measured, sort_keys=True, default=str))


def test_a_fixed_model_gets_the_same_development_grade_on_every_challenge():
    graded = {name: _graded(adapter) for name, adapter in ADAPTERS.items()}
    body = json.dumps(graded, sort_keys=True, indent=1, default=str).encode("utf-8")
    assert hashlib.sha256(body).hexdigest() == GOLDEN
