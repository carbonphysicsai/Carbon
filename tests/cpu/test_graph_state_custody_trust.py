"""ScoreLab custody reads a self-trust version's ensemble state (SELF_TRUST H3g R1) with the real v3 freeze, and refuses a tampered one.

The state is the registered producer codec's own output (`physical_graph_state_v3.freeze`); every parameter value is synthetic. Custody
validates inert bytes only: no graph is executed and nothing is trained or qualified.
"""

from __future__ import annotations

import io
import json
from pathlib import Path

import numpy as np
import pytest

pytest.importorskip("jax")

from test_physical_graph_state_v3 import _freeze, _recipe, _sha

from carbon.development_session import graph_state_contract
from carbon.level4 import allowlist
from scripts.dev.score_lab import public_unbound_custody as custody


@pytest.fixture(scope="module")
def raw_and_allowlist():
    permitted = allowlist.load()
    return _freeze(permitted), Path(allowlist.PATH).read_bytes()


def _header_of(raw):
    with np.load(io.BytesIO(raw), allow_pickle=False) as archive:
        return json.loads(archive["__header__"].tobytes())


def _inspect(raw, allowlist_bytes):
    return custody._bundle_header(
        raw,
        graph_source=True,
        recipe=_recipe().canonical_bytes,
        allowlist=allowlist_bytes,
    )


def _rewrite_header(raw, change):
    with np.load(io.BytesIO(raw), allow_pickle=False) as archive:
        arrays = {name: archive[name].copy() for name in archive.files}
    header = json.loads(arrays["__header__"].tobytes())
    change(header)
    arrays["__header__"] = np.frombuffer(
        json.dumps(header, sort_keys=True, separators=(",", ":")).encode(),
        dtype=np.uint8,
    )
    out = io.BytesIO()
    np.savez(out, **arrays)
    return out.getvalue()


def test_custody_reads_the_real_trust_state_and_names_its_schema(raw_and_allowlist):
    raw, allowlist_bytes = raw_and_allowlist
    header, arrays = _inspect(raw, allowlist_bytes)
    assert header["schema"] == graph_state_contract.GRAPH_ENSEMBLE_TRUST_STATE_SCHEMA
    assert header["trust"] == {"member": 0, "width": 3}
    assert "combine" in arrays and "decoder_mu" in arrays
    assert (
        custody.graph_state_schema(raw, _recipe().canonical_bytes, allowlist_bytes)
        == graph_state_contract.GRAPH_ENSEMBLE_TRUST_STATE_SCHEMA
    )


@pytest.mark.parametrize(
    "mutation",
    [
        lambda h: h.pop("trust"),
        lambda h: h.update(trust={"member": 1, "width": 3}),
        lambda h: h.update(trust={"member": 0, "width": 0}),
        lambda h: h.update(trust={"member": 0, "width": True}),
        lambda h: h.update(trust={"member": 0}),
        lambda h: h.update(trust={"member": 0, "width": 3, "extra": 1}),
        lambda h: h.update(trust=[0, 3]),
        lambda h: h.update(schema=graph_state_contract.GRAPH_ENSEMBLE_STATE_SCHEMA),
    ],
)
def test_a_malformed_or_relabelled_trust_header_refuses(raw_and_allowlist, mutation):
    raw, allowlist_bytes = raw_and_allowlist
    with pytest.raises(custody.CustodyRefused):
        _inspect(_rewrite_header(raw, mutation), allowlist_bytes)


def _fit(**changes):
    fit = {
        "adapter_id": "synthetic-codec-fixture",
        "trainer_sha256": _sha("1"),
        "members": 1,
        "steps": [1],
        "train_cases": 1,
        "train_loss": 0.0,
        "member_losses": [0.0],
        "params_sha256": _sha("2"),
        "recipe_digest": _recipe().digest,
        "trust": {"status": "trained", "held_out_rows": 4},
        "trust_trainer_sha256": _sha("3"),
    }
    fit.update(changes)
    return fit


def test_the_trust_fit_receipt_shape_is_exact(raw_and_allowlist):
    raw, allowlist_bytes = raw_and_allowlist
    header, _arrays = _inspect(raw, allowlist_bytes)
    digest = _recipe().digest
    assert custody._graph_fit_ok(_fit(), header, digest) is True
    assert (
        custody._graph_fit_ok(
            _fit(trust={"status": "no_held_out_rows", "held_out_rows": 0}),
            header,
            digest,
        )
        is True
    )
    for bad in (
        _fit(trust={"status": "other", "held_out_rows": 4}),
        _fit(trust={"status": "trained"}),
        _fit(trust={"status": "trained", "held_out_rows": -1}),
        _fit(trust={"status": "trained", "held_out_rows": True}),
        _fit(trust="trained"),
        _fit(trust_trainer_sha256="not-a-digest"),
        _fit(members=2),
    ):
        assert custody._graph_fit_ok(bad, header, digest) is False
    for name in ("trust", "trust_trainer_sha256"):
        missing = _fit()
        del missing[name]
        assert custody._graph_fit_ok(missing, header, digest) is False


def test_a_trust_key_in_a_non_trust_fit_is_still_refused_and_the_old_shape_is_unchanged(
    raw_and_allowlist,
):
    raw, allowlist_bytes = raw_and_allowlist
    header, _arrays = _inspect(raw, allowlist_bytes)
    plain_header = dict(header, schema=graph_state_contract.GRAPH_ENSEMBLE_STATE_SCHEMA)
    digest = _recipe().digest
    assert custody._graph_fit_ok(_fit(), plain_header, digest) is False
    old = _fit()
    del old["trust"], old["trust_trainer_sha256"]
    assert custody._graph_fit_ok(old, plain_header, digest) is True
    assert custody._graph_fit_ok(old, header, digest) is False


def test_a_trust_fit_may_also_carry_the_v3_trainers_training_curve(raw_and_allowlist):
    # a trust version on a v3-trainer Spec: the fit has the curve (DATA D2, `_graph_curve_ok`) AND the trust keys
    from carbon.development_session import physical_graph_trainer_v3 as trainer

    raw, allowlist_bytes = raw_and_allowlist
    header, _arrays = _inspect(raw, allowlist_bytes)
    digest = _recipe().digest
    curve = trainer.curve_block(
        [{"curve": [1.0, 0.5, 0.25], "polish_curve": None}]
    )  # one member, as the fixture's header names
    assert custody._graph_fit_ok(_fit(curve=curve), header, digest) is True
    # a malformed curve still refuses, and the curve never replaces the trust keys
    assert custody._graph_fit_ok(_fit(curve={"schema": "x"}), header, digest) is False
    without_trust = _fit(curve=curve)
    del without_trust["trust"]
    assert custody._graph_fit_ok(without_trust, header, digest) is False
