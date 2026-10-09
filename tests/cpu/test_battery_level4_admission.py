"""Battery's Level 4 admission of a staged envelope (development only).

Claims tested:

1. `admit_envelope` admits a lowered recipe's envelope bound to the strategy
   that names it, and returns the bytes the rebuild stages
   (`staging.workspace`).
2. It refuses, as the candidate's:
   - malformed envelope JSON (`staging_malformed`);
   - an envelope whose submission is not the strategy's Level 4 field
     (`staging_submission_mismatch`);
   - a loss graph under a variant that declares no `loss_override`
     (`loss_not_permitted`).
3. The interface and batch it validates at are the ones the miner's lowering
   uses (`level4.interface`, `level4.training_batch`) and the rebuild trains
   at.
4. Its constants are battery's own.

The isolated parse (G3) needs POSIX resource limits, so the admissions that
reach it run on Linux (CI) only.
"""

from __future__ import annotations

import json
import os

import pytest

pytest.importorskip("jax")
os.environ.setdefault("JAX_PLATFORMS", "cpu")

from carbon.battery import level4 as battery
from carbon.battery import level4_admission, level4_model
from carbon.level4 import allowlist as allowlist_module
from carbon.level4 import graph, intake, staging, submission

STEPS = 16
POSIX = pytest.mark.skipif(os.name == "nt", reason="G3 needs POSIX rlimits")


def _strategy(label="scaffold_mlp", **settings):
    strategy = battery._steps(battery.level0_strategies()[label], STEPS)
    return {**strategy, "parameters": {**strategy["parameters"], **settings}}


def _envelope(strategy):
    manifest, files = battery.lower_recipe(
        strategy,
        allowlist_module.load(),
        max_bytes=intake.BOUNDS["document_bytes"],
    )
    raw = submission.canonical(manifest)
    digest = submission.digest(manifest)
    named = {
        **strategy,
        "parameters": {**strategy["parameters"], battery.FIELD: digest},
    }
    body = json.dumps(staging.envelope(raw, files)).encode()
    return named, body, raw, files


@POSIX
def test_a_lowered_recipe_is_admitted_with_the_bytes_the_rebuild_stages():
    strategy, body, raw, files = _envelope(_strategy())
    got_raw, got_files = level4_admission.admit_envelope(
        strategy, body, loss_override="graph"
    )
    assert got_raw == raw and got_files == files
    assert staging.from_workspace(
        staging.workspace(got_raw, got_files), strategy["parameters"][battery.FIELD]
    ) == (raw, files)


def test_a_malformed_or_unbound_envelope_is_the_candidates():
    strategy, body, _raw, _files = _envelope(_strategy())
    with pytest.raises(graph.GraphRefused) as refused:
        level4_admission.admit_envelope(strategy, b"{not json", loss_override=None)
    assert refused.value.code == "staging_malformed"
    other = {
        **strategy,
        "parameters": {**strategy["parameters"], battery.FIELD: "sha256:" + "0" * 64},
    }
    with pytest.raises(graph.GraphRefused) as refused:
        level4_admission.admit_envelope(other, body, loss_override=None)
    assert refused.value.code == "staging_submission_mismatch"


@POSIX
def test_a_loss_graph_without_the_variants_declaration_is_refused():
    import jax.numpy as jnp

    from carbon.level4.tooling import through_bprime

    strategy = _strategy()
    allowlist = allowlist_module.load()
    manifest, files = battery.lower_recipe(
        strategy, allowlist, max_bytes=intake.BOUNDS["document_bytes"]
    )
    by_slot = {slot: files[name] for slot, name in manifest["documents"].items()}
    interface, _batch = level4_admission.interface_and_batch(strategy)
    ((_, _, (n_in,)),) = interface.inputs
    ((_, (n_out,)),) = interface.outputs
    _, loss, _ = through_bprime(
        lambda p, t, x: jnp.sum((p - t) ** 2, axis=1) + 0.0 * jnp.sum(x, axis=1),
        (jnp.ones((1, n_out)), jnp.ones((1, n_out)), jnp.ones((1, n_in))),
        role="loss",
        allowlist=allowlist,
        input_names=["loss/pred/0", "loss/target/0", "loss/x/features"],
        max_bytes=intake.BOUNDS["document_bytes"],
    )
    built, built_files = submission.build(
        challenge=manifest["challenge"],
        interface=manifest["interface"],
        allowlist=allowlist,
        forward=json.loads(by_slot["forward"]),
        init=json.loads(by_slot["init"]),
        loss=loss,
    )
    named = {
        **strategy,
        "parameters": {
            **strategy["parameters"],
            battery.FIELD: submission.digest(built),
        },
    }
    body = json.dumps(
        staging.envelope(submission.canonical(built), built_files)
    ).encode()
    with pytest.raises(graph.GraphRefused) as refused:
        level4_admission.admit_envelope(named, body, loss_override=None)
    assert refused.value.code == "loss_not_permitted"


@pytest.mark.parametrize("fraction", [None, 0.5])
def test_admission_validates_where_the_miner_lowers_and_the_rebuild_trains(fraction):
    cases = len(battery.material().train.case_ids)
    # `batch_size` at its largest admitted value: the TRAIN cases used.
    used = cases if fraction is None else int(cases * fraction)
    settings = {} if fraction is None else {"train_fraction": fraction}
    strategy = _strategy(**settings, batch_size=used)
    interface, batch = level4_admission.interface_and_batch(strategy)
    assert interface == battery.interface(strategy)
    assert batch == battery.training_batch(strategy)
    assert batch == used


def test_the_constants_are_batterys_own():
    assert level4_admission.FIELD == battery.FIELD
    assert level4_admission.CHALLENGE == level4_model.CHALLENGE
