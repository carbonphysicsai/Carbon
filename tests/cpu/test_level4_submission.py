"""Level 4 submission manifest (development only): `carbon.level4.submission`.

Claims tested:

1. `build` then `verify` round-trips; the submission digest is stable and a
   document's name equals `graph.digest` of the document.
2. One byte form: non-canonical bytes are refused.
3. Integrity and pinning: tampered bytes, a missing or extra file, the wrong
   allowlist, interface or Challenge, a role in the wrong slot, a bad init
   slot and an init spec bound to another graph are each refused.
"""

from __future__ import annotations

import copy
import json
import os

import pytest

pytest.importorskip("jax")
os.environ.setdefault("JAX_PLATFORMS", "cpu")

from carbon.level4 import allowlist as allowlist_module
from carbon.level4 import graph, submission, tooling

MAX_BYTES = 1 << 26  # the tests' parser bound; not a G3 or transport limit
CHALLENGE = "example-challenge"
INTERFACE = "sha256:" + "1" * 64


@pytest.fixture(scope="module")
def allowlist():
    return allowlist_module.load()


@pytest.fixture(scope="module")
def documents(allowlist):
    import jax
    import jax.numpy as jnp

    def init(key):
        key, sub = jax.random.split(key)
        return key, jax.random.normal(sub, (3, 2)), jnp.zeros(2)

    def forward(w, b, x):
        return jnp.tanh(x @ w + b)

    def loss(y, t):
        return jnp.mean((y - t) ** 2)

    x = jnp.ones((1, 3))
    _, fwd, _ = tooling.through_bprime(
        forward,
        (jnp.ones((3, 2)), jnp.zeros(2), x),
        role="forward",
        allowlist=allowlist,
        input_names=["params/0", "params/1", "inputs/x"],
        max_bytes=MAX_BYTES,
    )
    _, ini, _ = tooling.through_bprime(
        init,
        (jax.random.PRNGKey(0),),
        role="init",
        allowlist=allowlist,
        input_names=["carbon/key"],
        max_bytes=MAX_BYTES,
    )
    _, los, _ = tooling.through_bprime(
        loss,
        (jnp.ones((1, 2)), jnp.ones((1, 2))),
        role="loss",
        allowlist=allowlist,
        input_names=["outputs/0", "targets/0"],
        max_bytes=MAX_BYTES,
    )
    return fwd, ini, los


def _build(allowlist, documents, **overrides):
    fwd, ini, los = documents
    kwargs = {
        "challenge": CHALLENGE,
        "interface": INTERFACE,
        "allowlist": allowlist,
        "forward": fwd,
        "loss": los,
        "init": ini,
        **overrides,
    }
    return submission.build(**kwargs)


def _verify(allowlist, manifest, files, raw=None):
    return submission.verify(
        submission.canonical(manifest) if raw is None else raw,
        files,
        allowlist=allowlist,
        challenge=CHALLENGE,
        interface=INTERFACE,
        max_bytes=MAX_BYTES,
    )


def test_round_trip_and_identity(allowlist, documents):
    manifest, files = _build(allowlist, documents)
    again, _ = _build(allowlist, documents)
    assert submission.digest(manifest) == submission.digest(again)
    assert manifest["documents"]["forward"] == graph.digest(documents[0])
    parsed_manifest, parsed = _verify(allowlist, manifest, files)
    assert parsed_manifest == manifest and set(parsed) == {"forward", "loss", "init"}
    assert parsed["forward"] == documents[0]


def test_non_canonical_refused(allowlist, documents):
    manifest, files = _build(allowlist, documents)
    pretty = json.dumps(manifest, indent=1).encode()
    with pytest.raises(graph.GraphRefused) as refused:
        _verify(allowlist, manifest, files, raw=pretty)
    assert refused.value.code == "not_canonical"
    forward = manifest["documents"]["forward"]
    loose = dict(files)
    loose[forward] = json.dumps(documents[0], indent=1).encode()
    with pytest.raises(graph.GraphRefused) as refused:
        _verify(allowlist, manifest, loose)
    assert refused.value.code == "document_digest_mismatch"


def _refusal(allowlist, manifest, files):
    with pytest.raises(graph.GraphRefused) as refused:
        _verify(allowlist, manifest, files)
    return refused.value.code


def test_integrity_and_pinning(allowlist, documents):
    manifest, files = _build(allowlist, documents)
    forward = manifest["documents"]["forward"]

    tampered = dict(files)
    tampered[forward] = files[forward].replace(
        b'"role":"forward"', b'"role":"forward" '
    )
    assert _refusal(allowlist, manifest, tampered) == "document_digest_mismatch"
    extra = {**files, "sha256:" + "0" * 64: b"{}"}
    assert _refusal(allowlist, manifest, extra) == "submission_documents"
    missing = {k: v for k, v in files.items() if k != forward}
    assert _refusal(allowlist, manifest, missing) == "submission_documents"

    for field, value, code in (
        (
            "allowlist",
            {"version": allowlist.version, "digest": "sha256:" + "2" * 64},
            "submission_allowlist",
        ),
        ("interface", "sha256:" + "3" * 64, "submission_interface"),
        ("challenge", "other-challenge", "submission_challenge"),
        ("level", 3, "submission_level"),
    ):
        bad = copy.deepcopy(manifest)
        bad[field] = value
        assert _refusal(allowlist, bad, files) == code, field

    swapped = copy.deepcopy(manifest)
    swapped["documents"]["forward"], swapped["documents"]["loss"] = (
        manifest["documents"]["loss"],
        manifest["documents"]["forward"],
    )
    assert _refusal(allowlist, swapped, files) == "role_mismatch"
    no_init = copy.deepcopy(manifest)
    del no_init["documents"]["init"]
    files_no_init = {
        k: v for k, v in files.items() if k != manifest["documents"]["init"]
    }
    assert _refusal(allowlist, no_init, files_no_init) == "submission_init_slot"
    with pytest.raises(graph.GraphRefused) as refused:
        _build(allowlist, documents, init=None)
    assert refused.value.code == "submission_init_slot"


def test_init_spec_bound_to_its_forward_graph(allowlist, documents):
    from carbon.level4 import initializers

    spec = {
        "schema": initializers.SCHEMA,
        "graph": graph.digest(documents[0]),
        "parameters": [
            {
                "input": "params/0",
                "initializer": "he_normal",
                "fan_in_axes": [0],
                "fan_out_axes": [1],
            },
            {
                "input": "params/1",
                "initializer": "zeros",
                "fan_in_axes": [],
                "fan_out_axes": [],
            },
        ],
    }
    manifest, files = _build(allowlist, documents, init=None, init_spec=spec)
    _, parsed = _verify(allowlist, manifest, files)
    assert parsed["init_spec"]["graph"] == manifest["documents"]["forward"]
    other = dict(spec, graph="sha256:" + "4" * 64)
    manifest, files = _build(allowlist, documents, init=None, init_spec=other)
    assert _refusal(allowlist, manifest, files) == "init_spec_graph_mismatch"
