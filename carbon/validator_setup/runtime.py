"""Reuse the used-surface runtime probe; observation confers no launch authority."""

from __future__ import annotations

import asyncio

from carbon.chain.models import ChainContext, ChainFailure

from .bundle import SetupRefused


async def observe(network, endpoint, genesis_hash, expected_spec):
    from carbon.chain.runtime_probe import probe

    if (
        network not in ("testnet", "finney")
        or type(expected_spec) is not int
        or expected_spec <= 0
    ):
        raise SetupRefused("EXPLICIT_RUNTIME_CONTEXT_REQUIRED")
    try:
        # A global metadata read has no selected Carbon subnet/policy. Netuid0
        # here validates transport syntax only and is never a publication context.
        ChainContext(network, endpoint, "operator-runtime-read", genesis_hash, 0)
    except ChainFailure:
        raise SetupRefused("EXPLICIT_RUNTIME_CONTEXT_REQUIRED") from None
    report = await probe(endpoint, genesis_hash)
    matches = report["spec_version"] == expected_spec
    return {
        **report,
        "configured_network": network,
        "operator_expected_runtime_spec": expected_spec,
        "runtime_spec_matches": matches,
        "sdk_pin": "11.1.0",
        "scope": "READ_ONLY_USED_SURFACE_NOT_INSTALL_OR_NETWORK_QUALIFICATION",
        "mainnet_policy": (
            "HUMAN_INPUT" if network == "finney" else "REGISTERED_POLICY_SEPARATE"
        ),
        "transaction_authority_granted": False,
    }, (0 if matches and report["status"] == "COMPATIBLE_USED_SURFACE" else 3)


def run(args):
    return asyncio.run(
        observe(args.network, args.endpoint, args.genesis, args.expected_spec)
    )
