"""Bounded loss expressions and battery's Level-1 draft (GRAPHITE-ADMISSION-01 slice B).

Claims tested:
- an expression is validated against a closed operation set, put in canonical
  form and pinned by digest; anything outside the set is refused by code;
- Carbon rebuilds an expression from its pinned bytes alone, in a clean
  process, to the same trained parameters;
- the expression that restates battery's registered objective menu computes
  the menu's loss;
- nothing is opened: battery's contract, its expansion records and every miner
  path are unchanged, and the draft surface is refused by name.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import math
import os
import random
import subprocess
import sys
import time
from pathlib import Path

import numpy as np
import pytest

from carbon.battery import level1_draft as l1
from carbon.challenge_pipeline import proposals
from carbon.reconstruction import capability_registry as cr
from carbon.reconstruction import expansion_record
from carbon.reconstruction import loss_expressions as le
from carbon.reconstruction.challenge_contracts import validate_for_challenge

REPOSITORY = Path(__file__).resolve().parents[2]
BATTERY = cr.BATTERY_CHALLENGE
T = 12

EXPRESSION = {
    "op": "add",
    "args": [
        {"op": "div", "args": [{"term": "sq_error"}, {"term": "target_energy"}]},
        {"op": "scale", "by": 0.5, "arg": {"term": "traj_d1"}},
        {
            "op": "log1p",
            "arg": {"op": "pow", "exponent": 1.5, "arg": {"term": "traj_spectral"}},
        },
    ],
}


def arrays(seed=0, cases=5):
    rng = np.random.default_rng(seed)
    width = 2 * T + 3
    return (
        rng.normal(size=(cases, width)),
        rng.normal(size=(cases, width)),
        rng.uniform(0.5, 1.5, size=width),
    )


def trajectory(z):
    return z[:, :T], z[:, T : 2 * T]


def test_an_expression_compiles_to_a_canonical_pinned_form():
    first = le.compile_expression(EXPRESSION, l1.OPERATIONS)
    reordered = {**EXPRESSION, "args": list(reversed(EXPRESSION["args"]))}
    assert le.compile_expression(reordered, l1.OPERATIONS).digest == first.digest
    scaled = le.compile_expression(
        {"op": "scale", "by": 2, "arg": {"term": "sq_error"}}, l1.OPERATIONS
    )
    assert scaled.expression["by"] == 2.0 and type(scaled.expression["by"]) is float
    assert (
        le.compile_expression(
            {"op": "scale", "by": 2.0, "arg": {"term": "sq_error"}}, l1.OPERATIONS
        ).digest
        == scaled.digest
    )
    assert scaled.digest != first.digest
    assert first.document()["operation_set"] == l1.OPERATIONS.digest
    rebuilt = le.from_bytes(first.canonical_bytes(), l1.OPERATIONS)
    assert rebuilt == first


@pytest.mark.parametrize(
    "expression, code",
    [
        ({"term": "score"}, "term_not_registered"),
        ({"op": "exp", "arg": {"term": "sq_error"}}, "operation_not_in_the_set"),
        ("lambda z: z", "node_is_an_object"),
        ({"term": "sq_error", "op": "add"}, "node_fields"),
        ({"op": "scale", "by": True, "arg": {"term": "sq_error"}}, "by_outside_bounds"),
        (
            {"op": "scale", "by": math.nan, "arg": {"term": "sq_error"}},
            "by_outside_bounds",
        ),
        ({"op": "scale", "by": 10.5, "arg": {"term": "sq_error"}}, "by_outside_bounds"),
        ({"op": "scale", "by": -1, "arg": {"term": "sq_error"}}, "by_outside_bounds"),
        (
            {"op": "pow", "exponent": 3, "arg": {"term": "sq_error"}},
            "exponent_outside_bounds",
        ),
        ({"op": "add", "args": [{"term": "sq_error"}]}, "arity"),
        (
            {"op": "mul", "args": [{"term": "sq_error"}] * 3},
            "arity",
        ),
        (
            {
                "op": "log1p",
                "arg": {
                    "op": "log1p",
                    "arg": {
                        "op": "log1p",
                        "arg": {"op": "sqrt", "arg": {"term": "sq_error"}},
                    },
                },
            },
            "too_deep",
        ),
        (
            {
                "op": "add",
                "args": [
                    {"op": "add", "args": [{"term": "sq_error"}] * 8},
                    {"op": "add", "args": [{"term": "traj_d1"}] * 8},
                ],
            },
            "too_many_nodes",
        ),
    ],
)
def test_an_expression_outside_the_set_is_refused_by_code(expression, code):
    with pytest.raises(le.ExpressionRefused) as refused:
        le.compile_expression(expression, l1.OPERATIONS)
    assert refused.value.code == code


def test_pinned_bytes_bind_their_operation_set():
    compiled = le.compile_expression(EXPRESSION, l1.OPERATIONS)
    other = le.OperationSet(
        name="other",
        terms=l1.OPERATIONS.terms,
        max_depth=5,
        max_nodes=16,
        max_arity=8,
        scale=(0.0, 10.0),
        exponent=(0.5, 2.0),
        epsilon=1e-6,
    )
    with pytest.raises(le.ExpressionRefused, match="operation_set_mismatch"):
        le.from_bytes(compiled.canonical_bytes(), other)
    with pytest.raises(le.ExpressionRefused, match="not_json"):
        le.from_bytes(b"{", l1.OPERATIONS)


def _registered_case_loss(settings, zhat, zt, gw):
    """`carbon/battery/training.py` train.case_loss, restated in numpy."""
    base = np.sum((zhat - zt) ** 2 * gw[None, :], axis=1)
    if settings["relative_loss"]:
        base = base / (np.sum(zt**2 * gw[None, :], axis=1) + 1e-6)
    extra = 0.0
    for a, b in zip(trajectory(zhat), trajectory(zt)):
        e = a - b
        if settings["time_weighting"] != "uniform":
            ramp = (
                np.linspace(2.0, 0.0, e.shape[1])
                if settings["time_weighting"] == "early"
                else np.linspace(0.0, 2.0, e.shape[1])
            )
            extra = extra + np.mean(ramp * e**2, axis=1)
        if settings["h1_weight"]:
            extra = extra + settings["h1_weight"] * np.mean(
                np.diff(e, axis=1) ** 2, axis=1
            )
        if settings["h2_weight"]:
            extra = extra + settings["h2_weight"] * np.mean(
                np.diff(e, n=2, axis=1) ** 2, axis=1
            )
        if settings["spectral_weight"]:
            spectrum = np.abs(np.fft.rfft(e, axis=1)) ** 2
            k = np.linspace(0.0, 1.0, spectrum.shape[1])
            extra = (
                extra
                + settings["spectral_weight"]
                * np.mean(k * spectrum, axis=1)
                / e.shape[1]
            )
    return base + extra


MENUS = [
    {
        "relative_loss": False,
        "time_weighting": "uniform",
        "h1_weight": 0.0,
        "h2_weight": 0.0,
        "spectral_weight": 0.0,
    },
    {
        "relative_loss": True,
        "time_weighting": "early",
        "h1_weight": 0.5,
        "h2_weight": 0.0,
        "spectral_weight": 2.0,
    },
    {
        "relative_loss": False,
        "time_weighting": "late",
        "h1_weight": 1.0,
        "h2_weight": 3.0,
        "spectral_weight": 0.25,
    },
]


@pytest.mark.parametrize("settings", MENUS)
def test_the_menu_expression_computes_the_registered_objective(settings):
    zhat, zt, gw = arrays()
    compiled = le.compile_expression(l1.menu_expression(settings), l1.OPERATIONS)
    got = le.evaluate(compiled, l1.terms(np, zhat, zt, gw, trajectory), np)
    expected = _registered_case_loss(settings, zhat, zt, gw)
    np.testing.assert_allclose(got, expected, rtol=1e-12, atol=0)


def test_every_operation_keeps_the_loss_finite_and_differentiable():
    jax = pytest.importorskip("jax")
    import jax.numpy as jnp

    zhat, zt, gw = (jnp.asarray(a, jnp.float32) for a in arrays(1))
    exact = jnp.asarray(np.asarray(zt))  # a perfect prediction: every error is 0
    for op in ("sqrt", "log1p"):
        compiled = le.compile_expression(
            {"op": op, "arg": {"term": "sq_error"}}, l1.OPERATIONS
        )

        def loss(z, compiled=compiled):
            return jnp.mean(
                le.evaluate(compiled, l1.terms(jnp, z, zt, gw, trajectory), jnp)
            )

        for z in (zhat, exact):
            value, grad = jax.value_and_grad(loss)(z)
            assert np.isfinite(float(value)) and np.isfinite(np.asarray(grad)).all()
    compiled = le.compile_expression(EXPRESSION, l1.OPERATIONS)
    value = le.evaluate(compiled, l1.terms(jnp, zhat, zt, gw, trajectory), jnp)
    assert (np.asarray(value) >= 0).all()


#: A tiny deterministic fit with a compiled loss, run in this process and in a
#: clean one from the pinned bytes alone.
FIT = """
def fit(compiled, steps=30):
    import hashlib
    import jax
    import jax.numpy as jnp
    import numpy as np
    from carbon.battery.level1_draft import terms
    from carbon.reconstruction.loss_expressions import evaluate
    T = 8
    rng = np.random.RandomState(7)
    x = jnp.asarray(rng.normal(size=(6, 3)), jnp.float32)
    zt = jnp.asarray(rng.normal(size=(6, 2 * T + 1)), jnp.float32)
    gw = jnp.asarray(rng.uniform(0.5, 1.5, size=2 * T + 1), jnp.float32)
    w = jnp.asarray(rng.normal(size=(3, 2 * T + 1)) * 0.1, jnp.float32)
    def traj(z):
        return z[:, :T], z[:, T:2 * T]
    def loss(w):
        return jnp.mean(evaluate(compiled, terms(jnp, x @ w, zt, gw, traj), jnp))
    grad = jax.jit(jax.grad(loss))
    for _ in range(steps):
        w = w - 0.05 * grad(w)
    return hashlib.sha256(np.asarray(w).tobytes()).hexdigest()


if __name__ == "__main__":
    import sys
    from carbon.battery.level1_draft import OPERATIONS
    from carbon.reconstruction.loss_expressions import from_bytes
    with open(sys.argv[1], "rb") as pinned:
        print(fit(from_bytes(pinned.read(), OPERATIONS)))
"""


def test_carbon_rebuilds_an_expression_in_a_clean_process(tmp_path):
    pytest.importorskip("jax")
    compiled = le.compile_expression(EXPRESSION, l1.OPERATIONS)
    source = tmp_path / "rebuild_fit.py"
    source.write_text(FIT)
    spec = importlib.util.spec_from_file_location("rebuild_fit", source)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    here = module.fit(compiled)
    pinned = tmp_path / "expression.json"
    pinned.write_bytes(compiled.canonical_bytes())
    # A clean process that has only the pinned bytes.
    clean = subprocess.run(
        [sys.executable, str(source), str(pinned)],
        cwd=tmp_path,
        env={**os.environ, "PYTHONPATH": str(REPOSITORY)},
        capture_output=True,
        text=True,
        check=True,
        timeout=300,
    )
    assert clean.stdout.strip() == here
    # A different expression trains to different parameters.
    other = le.compile_expression({"term": "sq_error"}, l1.OPERATIONS)
    assert module.fit(other) != here


def test_the_draft_is_shaped_like_a_level_proposal():
    assert l1.DRAFT["status"] == "ENGINEERING_DRAFT" and l1.DRAFT["level"] == 1
    # It is the implementing agent's draft, never presented as Graphite's.
    assert "proposed_by" not in l1.DRAFT and "not a Graphite" in l1.DRAFT["drafted_by"]
    for capability in l1.DRAFT["capabilities"]:
        assert set(capability) == proposals.CAPABILITY_KEYS
        assert proposals.CAPABILITY_ID.match(capability["id"])
        assert capability["sources"] and all(capability["sources"])
    assert l1.DRAFT["left_out"]
    assert l1.DRAFT["capabilities"][0]["id"] == l1.PERMISSION


def test_nothing_is_opened_to_miners():
    battery = cr.contract(BATTERY)
    assert cr.capability(l1.PERMISSION, BATTERY).status is cr.Status.EXCLUDED
    assert "loss_expressions" not in cr.catalog_surfaces(BATTERY)
    public = {c["id"]: c["status"] for c in cr.public_registry(BATTERY)["capabilities"]}
    assert public[l1.PERMISSION] == "excluded"
    # The miner path refuses the draft surface by name.
    strategy = {
        "schema_version": "1.0",
        "challenge_id": BATTERY,
        "backbone": "mlp",
        "parameters": {"loss_expressions": "sq_error"},
    }
    result = validate_for_challenge(strategy)
    assert not result.ok
    assert ("parameter.not_rebuildable", "/parameters/loss_expressions") in {
        (i.code, i.path) for i in result.errors
    }
    # No expansion was recorded and the contract is its newest record.
    assert expansion_record.unrecorded() == {}
    newest = expansion_record.records(BATTERY)[-1]
    assert newest["contract_digest"] == battery.digest
    # The development profile is not a contract and is never served.
    profile = l1.development_profile()
    assert profile["scope"] == "DEVELOPMENT_ONLY_NEVER_SERVED_TO_MINERS"
    assert profile["base_contract_digest"] == battery.digest
    assert profile["digest"] not in {c.digest for c in cr.CONTRACTS.values()}
    # No miner-facing module reads the draft.
    for relative in (
        "carbon/reconstruction/capability_registry.py",
        "carbon/reconstruction/challenge_contracts.py",
        "carbon/battery/compile.py",
        "carbon/battery/training.py",
        "carbon/battery/intake.py",
        "carbon/battery/daemon.py",
        *(
            str(p.relative_to(REPOSITORY))
            for p in (REPOSITORY / "carbon/miner_mcp").rglob("*.py")
        ),
    ):
        text = (REPOSITORY / relative).read_text()
        assert "level1_draft" not in text and "loss_expressions import" not in text


# --- B1: every refusal is typed ------------------------------------------------------
# A refusal that escapes as an untyped exception could be classified as an
# infrastructure failure, a refund path. Each guard below has a mutation in
# tests/cpu/test_graphite_admission_mutations.py.

#: Valid documents and their digests, pinned before the B1 hardening: a valid
#: document compiles to exactly the bytes it compiled to before.
OPERATIONS_DIGEST = (
    "sha256:03373c324baeba5c4d999cd4121d76f69c7cb180fb1389d2db41c759416844f6"
)
PINNED = {
    "expression": (
        EXPRESSION,
        "4f2b74d244eedef1ff2dc47b2c3fc5287a9fc41142b41fcfff3e2b4fb4afd7a6",
    ),
    "menu_0": (
        l1.menu_expression(MENUS[0]),
        "b59b786d4b8cc426222e1de8b1e9c6c533498d735d7887d16cc981b7e71ed8d4",
    ),
    "menu_1": (
        l1.menu_expression(MENUS[1]),
        "9c6a781c13729b60dedbc9f889f64be8869463eb4480c0f450a0614fada11f9d",
    ),
    "menu_2": (
        l1.menu_expression(MENUS[2]),
        "98f954a0db1faa0bd2ddb445c6d24e76111a26bc10a3e10b7273a3471e39a3c9",
    ),
    "scale_int_2": (
        {"op": "scale", "by": 2, "arg": {"term": "sq_error"}},
        "aeb859d60814d84f33fb6ac2f207004d79d580a38a368a469006346836447b57",
    ),
    "scale_zero": (
        {"op": "scale", "by": 0.0, "arg": {"term": "traj_d2"}},
        "0754018b647afa4cd87dbce3d0bc9ae4547953498ad321a165fd9228cdfad4d1",
    ),
    "scale_subnormal": (
        {"op": "scale", "by": 5e-324, "arg": {"term": "sq_error"}},
        "997f60f5477630e4ce33ac694d888dbd752b8a49325442939d92be6035bfda8b",
    ),
    "pow_half": (
        {
            "op": "pow",
            "exponent": 0.5,
            "arg": {
                "op": "mul",
                "args": [{"term": "traj_spectral"}, {"term": "sq_error"}],
            },
        },
        "537d3611f28d93cd85f6897b1272d7e918a2685aa853ea5c9de0ec118053b9ec",
    ),
}


def _code(call):
    """The refusal code `call` raises; fails on acceptance or on an untyped
    exception (which is what a missing guard looks like)."""
    try:
        call()
    except le.ExpressionRefused as refused:
        return refused.code
    except Exception as error:  # noqa: BLE001 -- the failure being tested for
        pytest.fail(f"untyped {type(error).__name__}: {str(error)[:120]}")
    pytest.fail("accepted")


def _document(expression_json):
    """A document's bytes around raw expression JSON, in canonical key order."""
    return (
        b'{"expression":'
        + expression_json
        + b',"operation_set":"'
        + l1.OPERATIONS.digest.encode()
        + b'","schema":"'
        + le.SCHEMA.encode()
        + b'"}'
    )


def test_valid_documents_keep_their_digests():
    assert l1.OPERATIONS.digest == OPERATIONS_DIGEST
    for name, (expression, digest) in PINNED.items():
        compiled = le.compile_expression(expression, l1.OPERATIONS)
        assert compiled.digest == "sha256:" + digest, name
        body = compiled.canonical_bytes()
        assert hashlib.sha256(body).hexdigest() == digest, name
        assert le.from_bytes(body, l1.OPERATIONS) == compiled, name
        # The same canonical document as text or as a bytearray.
        assert le.from_bytes(body.decode(), l1.OPERATIONS) == compiled, name
        assert le.from_bytes(bytearray(body), l1.OPERATIONS) == compiled, name


def test_an_oversized_integer_constant_is_refused_by_code():
    for field, op in (("by", "scale"), ("exponent", "pow")):
        for value in (10**400, -(10**400), 2**1024):
            expression = {"op": op, field: value, "arg": {"term": "sq_error"}}
            assert (
                _code(lambda e=expression: le.compile_expression(e, l1.OPERATIONS))
                == field + "_outside_bounds"
            )
    body = _document(
        b'{"arg":{"term":"sq_error"},"by":' + b"9" * 400 + b',"op":"scale"}'
    )
    assert _code(lambda: le.from_bytes(body, l1.OPERATIONS)) == "by_outside_bounds"


def test_negative_zero_has_the_digest_of_zero():
    def scaled(by):
        return le.compile_expression(
            {"op": "scale", "by": by, "arg": {"term": "sq_error"}}, l1.OPERATIONS
        )

    negative, positive = scaled(-0.0), scaled(0.0)
    assert negative.digest == positive.digest == scaled(0).digest
    assert math.copysign(1.0, negative.expression["by"]) == 1.0
    assert b"-0.0" not in negative.canonical_bytes()
    # Bytes spelling -0.0 are not the canonical bytes of what they compile to.
    body = positive.canonical_bytes().replace(b'"by":0.0', b'"by":-0.0')
    assert _code(lambda: le.from_bytes(body, l1.OPERATIONS)) == "not_canonical"


def test_an_oversized_document_is_refused_before_parsing():
    canonical = le.compile_expression(EXPRESSION, l1.OPERATIONS).canonical_bytes()
    limit = le._byte_limit(l1.OPERATIONS)
    # The bound leaves room for the largest valid document.
    largest = {
        "op": "add",
        "args": [
            {
                "op": "scale",
                "by": 1.2345678901234567e-300,
                "arg": {"term": "traj_ramp_early"},
            }
        ]
        * 7,
    }
    assert len(le.compile_expression(largest, l1.OPERATIONS).canonical_bytes()) < limit
    for body in (
        b" " * limit + canonical,
        b"[" * 200_000 + b"]" * 200_000,
        _document(b'{"term":"' + b"a" * limit + b'"}'),
    ):
        assert _code(lambda b=body: le.from_bytes(b, l1.OPERATIONS)) == (
            "document_too_large"
        )


def test_a_deeply_nested_document_is_refused_before_parsing():
    limit = le._byte_limit(l1.OPERATIONS)
    deep = _document(b"[" * 1400 + b"]" * 1400)
    assert len(deep) < limit  # inside the size bound: only the depth bound refuses it
    assert _code(lambda: le.from_bytes(deep, l1.OPERATIONS)) == "document_too_deep"
    # Expression nesting past the depth bound is refused before parsing too.
    nested = _document(b'{"op":"sqrt","arg":' * 30 + b'{"term":"sq_error"}' + b"}" * 30)
    assert len(nested) < limit
    assert _code(lambda: le.from_bytes(nested, l1.OPERATIONS)) == "document_too_deep"
    # Brackets inside strings are not nesting.
    assert not le._too_deep('{"a":"[[[[[[","b":"\\"[[[["}', 1)
    assert le._too_deep('{"a":[[]]}', 2)


def test_a_repeated_key_is_refused():
    for body in (
        _document(b'{"term":"traj_d1","term":"sq_error"}'),
        b'{"expression":{"term":"sq_error"},"operation_set":"x","schema":"y","schema":"z"}',
    ):
        assert _code(lambda b=body: le.from_bytes(b, l1.OPERATIONS)) == "duplicate_key"


def test_non_canonical_or_non_json_bytes_are_refused():
    compiled = le.compile_expression(EXPRESSION, l1.OPERATIONS)
    canonical = compiled.canonical_bytes()
    document = compiled.document()
    shuffled = dict(document["expression"])
    shuffled["args"] = list(reversed(shuffled["args"]))
    for body in (
        json.dumps(document, indent=2).encode(),
        json.dumps(document, sort_keys=False).encode(),
        json.dumps(
            {**document, "expression": shuffled}, sort_keys=True, separators=(",", ":")
        ).encode(),
        canonical + b"\n",
        b" " + canonical,
        canonical.replace(b'"by":0.5', b'"by":0.50'),
    ):
        assert body != canonical
        assert _code(lambda b=body: le.from_bytes(b, l1.OPERATIONS)) == "not_canonical"
    for body in (b"\xff\xfe", canonical.decode().encode("utf-16"), b"", b"{"):
        assert _code(lambda b=body: le.from_bytes(b, l1.OPERATIONS)) == "not_json"
    for body in (None, 7, memoryview(canonical), [canonical]):
        assert _code(lambda b=body: le.from_bytes(b, l1.OPERATIONS)) == "not_bytes"


_TOKENS = (
    b"{",
    b"}",
    b"[",
    b"]",
    b'"',
    b",",
    b":",
    b"\\",
    b"0",
    b"-0.0",
    b"1e400",
    b"9" * 40,
    b"NaN",
    b"Infinity",
    b"true",
    b"null",
    b'"term"',
    b'"op"',
    b'"args"',
    b'"arg"',
    b'"by"',
    b'"exponent"',
    b'"sq_error"',
    b'"add"',
    b'"scale"',
    b'"pow"',
    b'"exp"',
    b"\xff",
    b"\x00",
    b" ",
)


def _mutated(rng, seed):
    body = bytearray(seed)
    for _ in range(rng.randint(1, 4)):
        kind = rng.randrange(5)
        at = rng.randint(0, len(body))
        if kind == 0 and body:
            body[min(at, len(body) - 1)] = rng.randrange(256)
        elif kind == 1:
            body[at:at] = rng.choice(_TOKENS)
        elif kind == 2:
            del body[at : at + rng.randint(1, 12)]
        elif kind == 3:
            body[at:at] = body[max(0, at - 24) : at]
        else:
            del body[at:]
    return bytes(body)


def _random_value(rng, depth):
    """A random JSON-like value. Each container has fewer than one child on
    average and the depth is capped, so the size stays small."""
    pick = rng.randrange(12 if depth < 14 else 6)
    if pick == 0:
        return rng.choice(
            [10**400, -(10**400), 2**63, -0.0, 0.0, 10.0, 0.5, True, None]
        )
    if pick == 1:
        return rng.choice([math.nan, math.inf, 1e-320, 1e308, -1.0, 2.0, 3])
    if pick == 2:
        return rng.choice(["sq_error", "traj_d1", "score", "", "add", "x" * 60])
    if pick == 3:
        return {"term": rng.choice(["sq_error", "target_energy", "label"])}
    if pick in (4, 5):
        return rng.choice([[], {}, "[[[["])
    if pick in (6, 7, 8):
        node = {"op": rng.choice(le.OPERATIONS + ("exp", "sub", None, 1))}
        for key in rng.sample(
            ["args", "arg", "by", "exponent", "term", "extra"], rng.randint(0, 3)
        ):
            node[key] = _random_value(rng, depth + 1)
        return node
    return [_random_value(rng, depth + 1) for _ in range(rng.randint(0, 3))]


def test_random_inputs_only_compile_or_refuse_by_code():
    """Seeded fuzzing: noise, mutated canonical documents and random JSON-like
    values. Each either compiles (and then is exactly canonical) or is refused
    with a code; nothing else escapes, within a bounded time."""
    rng = random.Random(20261005)
    seeds = [
        le.compile_expression(e, l1.OPERATIONS).canonical_bytes()
        for e, _ in PINNED.values()
    ]
    start = time.monotonic()
    accepted, codes = 0, set()

    def check(call, body=None):
        nonlocal accepted
        try:
            compiled = call()
        except le.ExpressionRefused as refused:
            codes.add(refused.code)
            return
        except Exception as error:  # noqa: BLE001 -- the failure being tested for
            pytest.fail(f"untyped {type(error).__name__} for {body!r:.200}")
        accepted += 1
        if body is not None:
            assert compiled.canonical_bytes() == body

    for _ in range(1500):
        body = bytes(rng.randrange(256) for _ in range(rng.randint(0, 300)))
        check(lambda b=body: le.from_bytes(b, l1.OPERATIONS), body)
    for _ in range(3000):
        body = _mutated(rng, rng.choice(seeds))
        check(lambda b=body: le.from_bytes(b, l1.OPERATIONS), body)
    for _ in range(1500):
        value = _random_value(rng, 0)
        check(lambda v=value: le.compile_expression(v, l1.OPERATIONS))
        expression = json.dumps(value, sort_keys=True, separators=(",", ":"))
        body = _document(expression.encode())
        check(lambda b=body: le.from_bytes(b, l1.OPERATIONS), body)
    for _ in range(500):
        # The same document re-serialized: only the canonical spelling passes.
        document = json.loads(rng.choice(seeds))
        body = json.dumps(
            document,
            sort_keys=rng.random() < 0.5,
            indent=rng.choice([None, None, 0, 1, 2]),
            separators=rng.choice([(",", ":"), (", ", ": "), (",", ": ")]),
        ).encode()
        check(lambda b=body: le.from_bytes(b, l1.OPERATIONS), body)
    for depth in (10, 100, 1000, 5000):
        value = {"term": "sq_error"}
        for _ in range(depth):
            value = {"op": "sqrt", "arg": value}
        check(lambda v=value: le.compile_expression(v, l1.OPERATIONS))
    for seed in seeds:
        check(lambda b=seed: le.from_bytes(b, l1.OPERATIONS), seed)
    assert accepted >= len(seeds)
    assert {"not_json", "not_canonical", "document_too_deep"} <= codes
    assert time.monotonic() - start < 60
