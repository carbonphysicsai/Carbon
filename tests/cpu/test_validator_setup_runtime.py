"""Scripted read-only metadata contrasts; no fresh chain or full parity claim."""

import asyncio

import pytest

from carbon.validator_setup import runtime
from carbon.validator_setup.bundle import SetupRefused


@pytest.mark.parametrize("network", ["testnet", "finney"])
@pytest.mark.parametrize(
    "state,spec,code",
    [
        ("COMPATIBLE_USED_SURFACE", 450, 0),
        ("COMPATIBLE_USED_SURFACE", 451, 3),
        ("INCOMPATIBLE_USED_SURFACE", 450, 3),
    ],
)
def test_used_surface_and_actual_runtime_pin_both_control_without_policy_or_signing(
    monkeypatch, network, state, spec, code
):
    from carbon.chain import runtime_probe

    calls = []

    async def probe(endpoint, genesis):
        calls.append((endpoint, genesis))
        return {
            "status": state,
            "spec_version": spec,
            "context": {"finalized_block": 100, "finalized_hash": "0x" + "a" * 64},
        }

    monkeypatch.setattr(runtime_probe, "probe", probe)
    report, status = asyncio.run(
        runtime.observe(network, "wss://fixture.invalid", "0x" + "b" * 64, 450)
    )
    assert status == code
    assert calls == [("wss://fixture.invalid", "0x" + "b" * 64)]
    assert report["transaction_authority_granted"] is False
    assert report["runtime_spec_matches"] == (spec == 450)
    assert report["configured_network"] == network
    if network == "finney":
        assert report["mainnet_policy"] == "HUMAN_INPUT"


def test_missing_or_secret_bearing_context_never_reaches_probe(monkeypatch):
    from carbon.chain import runtime_probe

    async def forbidden(*_args):
        pytest.fail("must not query")

    monkeypatch.setattr(runtime_probe, "probe", forbidden)
    with pytest.raises(SetupRefused):
        asyncio.run(
            runtime.observe(
                "finney",
                "wss://user:synthetic-secret@fixture.invalid",
                "0x" + "a" * 64,
                450,
            )
        )
