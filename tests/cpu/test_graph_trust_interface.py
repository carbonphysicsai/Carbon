"""Graph route v2, self-trust interface (SELF_TRUST DESIGN_v2, head H2): a version MAY register a trust interface of
`outputs + k` columns beside its base interface. The recipe binds one of the two interface digests; that binding is the
explicit declaration. Every existing version offers none, so its interface, adapter block and limits are unchanged.
"""

from __future__ import annotations

import dataclasses

import pytest

from carbon.development_session import physical_graph_adapter_v2 as v2


def test_no_served_version_offers_a_trust_interface_yet():
    assert all(spec.trust_outputs == 0 for spec in v2.SPECS.values())


@pytest.mark.parametrize("key", sorted(v2.SPECS))
def test_a_version_without_trust_keeps_its_interface_and_block_exactly(key):
    spec = v2.SPECS[key]
    base = v2.graph_interface(spec)
    assert base.outputs == ((spec.dtype, (spec.outputs,)),)
    assert base.digest() == v2.graph_interface(spec, trust=False).digest()
    assert "trust" not in v2.adapter_block(*key)
    with pytest.raises(ValueError, match="no trust interface"):
        v2.graph_interface(spec, trust=True)


def test_a_trust_version_registers_a_second_wider_interface_with_its_own_digest():
    spec = dataclasses.replace(next(iter(v2.SPECS.values())), trust_outputs=3)
    base, trust = v2.graph_interface(spec), v2.graph_interface(spec, trust=True)
    assert base.outputs == ((spec.dtype, (spec.outputs,)),)
    assert trust.outputs == ((spec.dtype, (spec.outputs + 3,)),)
    assert base.inputs == trust.inputs
    assert base.digest() != trust.digest()
    # the base interface of a trust version is byte-identical to the same version without the field
    plain = dataclasses.replace(spec, trust_outputs=0)
    assert v2.graph_interface(plain).digest() == base.digest()


def test_the_adapter_block_names_the_trust_interface_only_for_a_trust_version(
    monkeypatch,
):
    key, spec = next(iter(v2.SPECS.items()))
    trust_spec = dataclasses.replace(spec, trust_outputs=2)
    monkeypatch.setitem(v2.SPECS, key, trust_spec)
    block = v2.adapter_block(*key)
    assert block["trust"] == {
        "outputs": 2,
        "interface_output_shape": [spec.outputs + 2],
        "mode": "the interface digest the recipe binds",
    }
    without = dict(block)
    del without["trust"]
    monkeypatch.setitem(v2.SPECS, key, spec)
    assert without == v2.adapter_block(*key)
