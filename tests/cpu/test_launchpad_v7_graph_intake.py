"""Graph submissions on a v7 version are read under v7's intake bounds
(owner, 2026-10-21: no model-size caps; `intake.bounds_for`), never the
owner's 4 MiB submission bound; every other version keeps that bound.

Claims tested:
- `served_versions.graph_intake_bounds` is the version's graph allowlist's
  bounds: containment on every v7 version, the owner's BOUNDS on every other
  registered version, and BOUNDS (never v7's) for an unregistered one.
- The F08 1.4 routes (workspace staging request, retained envelope check and
  the graph adapter's own build) admit a graph over 4 MiB and under 64 MiB;
  the same bytes under v6, or on a version not serving v7, are refused.
"""

from __future__ import annotations

import json
import os

import pytest

from carbon.challenge_kit import f08_public
from carbon.challenge_kit import served_versions as sv
from carbon.development_session import direct_graph_construction_worker as worker
from carbon.development_session import physical_graph_adapter as adapter
from carbon.development_session.construction_recipe import (
    ConstructionRecipe,
    RecipeRefused,
    recipe_graph_bounds,
)
from carbon.level4 import allowlist as allowlist_module
from carbon.level4 import intake

F08 = sv.F08
OWNER = intake.BOUNDS["submission_bytes"]
CONTAINMENT = intake.CONTAINMENT_BOUNDS["submission_bytes"]
#: A forward graph of this many extra nodes is about 4.7 MB (94 bytes a node).
CHAIN = 50_000


def test_every_registered_version_reads_its_graph_allowlists_bounds():
    for key in sorted(sv.STEP2 | sv.EXISTING | sv.CATALOG | sv.V7):
        expected = intake.CONTAINMENT_BOUNDS if key in sv.V7 else intake.BOUNDS
        assert sv.graph_intake_bounds(*key) == expected, key
    for key in (("synthetic-linear-field-2d", "1.3"), (F08, "9.9"), ("x", "1.0")):
        assert sv.graph_intake_bounds(*key) == intake.BOUNDS


def _recipe(version, digest="sha256:" + "0" * 64):
    kit = f08_public.construction_kit(F08, version)
    spec = adapter.SPECS.get((F08, "1.4"))
    return ConstructionRecipe.from_dict(
        {
            "schema": "carbon.construction-recipe.v1",
            "challenge": {
                name: kit[name]
                for name in (
                    "id",
                    "version",
                    "train_digest",
                    "interface_digest",
                    "construction_limits_digest",
                )
            },
            "source": {"kind": "graph", "submission_digest": digest},
            "procedure": {
                "entrypoint": None,
                "configuration": {"training": {}},
                "train_use": {"dataset": spec.train_use, "train_fraction": 1.0},
                "initial_state": None,
            },
            "output": {
                "format": adapter.OUTPUT_FORMAT,
                "interface_digest": kit["interface_digest"],
            },
        }
    )


def test_a_recipe_reads_its_own_versions_bounds():
    assert recipe_graph_bounds(_recipe("1.4")) == intake.CONTAINMENT_BOUNDS
    assert recipe_graph_bounds(_recipe("1.2")) == intake.BOUNDS


def test_the_staging_request_takes_the_versions_document_bound():
    from carbon import research
    from carbon.level4 import staging
    from carbon.registry import ChallengeKey

    def request(version, total):
        return research.DirectStageSourceRequestV1(
            ChallengeKey(F08, version),
            staging.WORKSPACE_PREFIX + "a" * 64 + ".json",
            0,
            total,
            "sha256:" + "a" * 64,
            None,
            b"x",
        )

    request("1.4", OWNER + 1)
    request("1.4", CONTAINMENT)
    request("1.2", OWNER)
    for version, total in (("1.2", OWNER + 1), ("1.4", CONTAINMENT + 1)):
        with pytest.raises(ValueError, match="bounded digest-bound graph source"):
            request(version, total)


def _big_graph():
    """A real F08 1.4 forward graph over 4 MiB: the adapter's MLP with a
    chain of `CHAIN` negations (an even count, so the function is the MLP)."""
    pytest.importorskip("jax")
    os.environ.setdefault("JAX_PLATFORMS", "cpu")
    import jax.numpy as jnp

    from carbon.level4 import graph, initializers, submission
    from carbon.level4.tooling import through_bprime

    spec = adapter.SPECS[(F08, "1.4")]
    allowed = allowlist_module.Allowlist(allowlist_module.v7_bytes())

    def forward(w1, b1, w2, b2, x):
        y = jnp.tanh(x @ w1 + b1)
        for _ in range(CHAIN):
            y = -y
        return y @ w2 + b2

    _, document, raw = through_bprime(
        forward,
        (
            jnp.zeros((spec.inputs, 16), jnp.float32),
            jnp.zeros((16,), jnp.float32),
            jnp.zeros((16, spec.outputs), jnp.float32),
            jnp.zeros((spec.outputs,), jnp.float32),
            jnp.ones((8, spec.inputs), jnp.float32),
        ),
        role="forward",
        allowlist=allowed,
        input_names=[
            "params/0",
            "params/1",
            "params/2",
            "params/3",
            adapter.INPUT_NAME,
        ],
        max_bytes=intake.CONTAINMENT_BOUNDS["document_bytes"],
    )
    assert OWNER < len(raw) < intake.CONTAINMENT_BOUNDS["document_bytes"]

    def param(index, initializer, axes):
        return {
            "input": f"params/{index}",
            "initializer": initializer,
            "fan_in_axes": [0] if axes else [],
            "fan_out_axes": [1] if axes else [],
        }

    init_spec = {
        "schema": initializers.SCHEMA,
        "graph": graph.digest(document),
        "parameters": [
            param(0, "glorot_normal", True),
            param(1, "zeros", False),
            param(2, "glorot_normal", True),
            param(3, "zeros", False),
        ],
    }
    manifest, files = submission.build(
        challenge=spec.challenge_id,
        interface=adapter.graph_interface(spec).digest(),
        allowlist=allowed,
        forward=document,
        init_spec=init_spec,
    )
    return submission.canonical(manifest), files, submission.digest(manifest)


@pytest.fixture(scope="module")
def big():
    return _big_graph()


def test_the_retained_envelope_check_admits_it_on_1_4_only(big):
    from carbon.development_session.profile import canonical
    from carbon.level4 import staging

    raw_manifest, files, digest = big
    envelope = canonical(staging.envelope(raw_manifest, files))
    assert OWNER < len(envelope) <= 2 * CONTAINMENT
    assert worker._checked_envelope(_recipe("1.4", digest), envelope) == envelope
    with pytest.raises(RecipeRefused, match="construction_recipe_graph_bytes_invalid"):
        worker._checked_envelope(_recipe("1.2", digest), envelope)


posix = pytest.mark.skipif(os.name == "nt", reason="G3 parser needs POSIX rlimits")


@posix
def test_the_f08_1_4_adapter_admits_it_and_v6_bounds_refuse_it(big):
    raw_manifest, files, digest = big
    recipe = _recipe("1.4", digest)
    rows = adapter.SPECS[(F08, "1.4")].rows
    model = adapter.build_validated_graph(
        recipe,
        raw_manifest,
        files,
        allowlist_bytes=adapter.served_allowlist_bytes(F08, "1.4"),
        train_cases=rows,
    )
    assert model.allowlist.version == "level4-allowlist-v7"
    # The same bytes under v6's bounds: refused at the owner's 4 MiB intake.
    with pytest.raises(RecipeRefused, match="construction_recipe_graph_bytes_invalid"):
        adapter.build_validated_graph(
            recipe,
            raw_manifest,
            files,
            allowlist_bytes=allowlist_module.served_bytes(),
            train_cases=rows,
        )
    assert json.loads(raw_manifest)["allowlist"]["version"] == "level4-allowlist-v7"
