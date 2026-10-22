"""Battery's public practice measure equals the registered one (Phase A; Validator
ruling on Battery's public measure).

``battery_dual_measurement`` reaches the battery panel's attack harness through
``quiz`` and ``gate_plating_v2``, which no miner-reachable module may import. The
public modules carry the same logic without that edge, and this file pins them
equal: the functions as syntax trees, the measurement module as source after its
three documented substitutions, and the whole A/D measurement on a fixed fixture
model on the public development bank."""

from __future__ import annotations

import ast
import json
from pathlib import Path

import pytest

from carbon.battery.value import gate_plating_v2 as gp
from carbon.battery.value import public_gate, public_quiz, quiz
from carbon.challenge_kit import physical_pack
from carbon.scoring import battery_dual_measurement as original
from carbon.scoring import battery_dual_pack as registered
from carbon.scoring import battery_public_adapter as public
from carbon.scoring import battery_public_dual as pdm
from carbon.scoring import physical_dual_pack as physical

ROOT = Path(__file__).resolve().parents[2]


def _functions(path):
    tree = ast.parse(Path(path).read_text(encoding="utf-8"))
    out = {}
    for node in tree.body:
        if isinstance(node, ast.FunctionDef):
            body = node.body
            if (
                body
                and isinstance(body[0], ast.Expr)
                and isinstance(getattr(body[0], "value", None), ast.Constant)
                and isinstance(body[0].value.value, str)
            ):
                body = body[1:]
            out[node.name] = ast.dump(
                ast.Module(body=body, type_ignores=[])
            ) + ast.dump(node.args)
    return out


@pytest.mark.parametrize(
    "mine,theirs",
    [(public_gate, gp), (public_quiz, quiz)],
)
def test_the_public_functions_are_the_originals_as_syntax_trees(mine, theirs):
    ours, originals = _functions(mine.__file__), _functions(theirs.__file__)
    assert ours
    for name, tree in ours.items():
        assert originals[name] == tree, name


def test_the_public_constants_are_the_originals():
    assert public_gate.LABELS == gp.LABELS
    assert public_gate.GATE_VERSION == gp.GATE_VERSION
    assert public_gate.PLATING == gp.PLATING
    assert public_gate.M20_BINDING_TOLERANCE_MV == gp.M20_BINDING_TOLERANCE_MV
    from carbon.battery import quiz_stratum

    assert pdm.CONTRACT == quiz_stratum.CONTRACT


def test_the_public_measurement_is_the_original_after_three_substitutions():
    source = (ROOT / "carbon/scoring/battery_dual_measurement.py").read_text(
        encoding="utf-8"
    )
    for old, new in (
        (
            "    from carbon.battery import quiz_stratum\n"
            "    from carbon.battery.value import contract as ev\n\n"
            "    contract = quiz_stratum.contract(_REPOSITORY)\n",
            "    from carbon.battery.value import contract as ev\n\n"
            "    contract, _digest = ev.load(_REPOSITORY / CONTRACT)\n",
        ),
        (
            "    from carbon.battery.value import gate_plating_v2 as gp\n",
            "    from carbon.battery.value import public_gate as gp\n",
        ),
        (
            "    from carbon.battery.value import quiz\n",
            "    from carbon.battery.value import public_quiz as quiz\n",
        ),
    ):
        assert old in source
        source = source.replace(old, new)
    source = source.replace(
        'CANDIDATE = "G-FEAS/A-Q>"\n',
        'CANDIDATE = "G-FEAS/A-Q>"\nCONTRACT = '
        '"carbon/battery/value/contracts/ev4-charge-protocol-selection.v1.json"\n',
        1,
    )
    theirs = (ROOT / "carbon/scoring/battery_public_dual.py").read_text(
        encoding="utf-8"
    )
    # The module docstring is the public module's own; everything after is the
    # original's, byte for byte.
    assert theirs.split('"""', 2)[2] == source.split('"""', 2)[2]


def test_the_adapter_constants_and_definition_are_the_registered_ones():
    assert public.CHALLENGE == registered.CHALLENGE
    assert public.VERSION == registered.VERSION
    assert public.EVALUATION_VERSION == registered.EVALUATION_VERSION
    assert public.CASE_ID == registered.CASE_ID
    assert public.VERSIONS == registered.VERSIONS
    bank = physical_pack.development_bank(public.CHALLENGE, public.VERSION)
    train = physical_pack.public_roles(public.CHALLENGE, public.VERSION)["train"]
    assert public.definition(bank=bank, train_raw=train) == registered.definition(
        bank=bank, train_raw=train
    )
    assert public._contract() == registered._contract()


def _graded(measure):
    adapter_public = physical_pack.public_roles(public.CHALLENGE, public.VERSION)
    bank = physical_pack.development_bank(public.CHALLENGE, public.VERSION)
    names = physical.input_names(public)
    rows = physical.bank_rows(bank, names)
    definition = {
        **registered.definition(bank=bank, train_raw=adapter_public["train"]),
        "challenge": {"id": public.CHALLENGE, "version": public.VERSION},
        "scope": "PUBLIC_DEVELOPMENT_EXPOSED_BANK",
    }
    fixed = next(r["reference"] for r in rows if r["reference"] is not None)
    outputs = []
    for i, row in enumerate(rows):
        scale = 1.0 + 0.003 * (((i * 2654435761) % 1000) / 1000.0 - 0.5)
        ref = row["reference"] if row["reference"] is not None else fixed
        outputs.append([None if v is None else float(v) * scale for v in ref])
    measured = measure(
        bank_rows=rows,
        outputs=outputs,
        repeats=[outputs, outputs],
        definition=definition,
        limits=json.loads(adapter_public["important_limit_definition"]),
        objective=json.loads(adapter_public["design_objective"]),
        train_raw=adapter_public["train"],
        names=names,
    )
    return json.loads(json.dumps(measured, sort_keys=True, default=str))


def test_a_fixed_model_gets_the_same_grade_from_the_public_measure():
    one = _graded(registered.measure)
    two = _graded(public.measure)
    assert one == two
    assert one["D"] is not None and 0 < one["D"] <= 1
    assert set(one["gates"]) == set(original.GATES)


def test_the_public_measure_refuses_what_the_registered_one_refuses():
    bank = physical_pack.development_bank(public.CHALLENGE, public.VERSION)
    names = physical.input_names(public)
    rows = physical.bank_rows(bank, names)
    with pytest.raises(public.Refused):
        public.measure(
            bank_rows=rows,
            outputs=[[0.0]] * len(rows),
            repeats=[[[0.0]] * len(rows)] * 2,
            definition={"schema": "wrong"},
            limits={},
            objective={},
            train_raw=b"",
            names=names,
        )
