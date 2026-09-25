"""Read-only runtime compatibility probe for the pinned Bittensor SDK.

Carbon publishes through `bittensor==11.1.0` (`sdk.SDK_VERSION`). The SDK
composes calls and reads storage by name, using bindings generated from
runtime metadata (`bittensor._generated`). An operator pins the chain runtime
it validated (`expected_runtime_spec`). When the chain upgrades, the pin fails
closed with `UNSUPPORTED_RUNTIME_VERSION` until someone checks the new
runtime.

This probe is that check, for the surface Carbon actually uses. It compares
each item in `SURFACE` between the live runtime metadata and the SDK's
generated bindings:
- a call's name, argument names and order, and argument types;
- a storage item's presence and value type;
- a runtime API method's presence.

It reports every difference and a digest of the observed surface.

What it establishes, and what it does not:
- `COMPATIBLE_USED_SURFACE` means the names and types Carbon's publish path
  encodes against are unchanged. It is not proof that the runtime *behaves*
  the same. The owner decides whether to adopt the new spec, using this
  report and the upstream release notes.
- It never signs, never opens a wallet and never submits.
"""

from __future__ import annotations

import hashlib
import inspect
import json

SCHEMA = "carbon.chain.runtime-surface-probe.v1"

#: Exactly what Carbon's Phase A publish and capability observation touch
#: (`sdk_weights`, `sdk`, and the pinned SDK's SetWeights preflight, timelock
#: build and MEV-shield submission).
SURFACE = {
    "calls": (
        ("SubtensorModule", "set_mechanism_weights"),
        ("SubtensorModule", "commit_timelocked_mechanism_weights"),
        ("MevShield", "submit_encrypted"),
    ),
    "storage": (
        ("SubtensorModule", "SubnetOwner"),
        ("SubtensorModule", "SubnetOwnerHotkey"),
        ("SubtensorModule", "MechanismCountCurrent"),
        ("SubtensorModule", "MaxMechanismCount"),
        ("SubtensorModule", "RecycleOrBurn"),
        ("SubtensorModule", "MinAllowedWeights"),
        ("SubtensorModule", "MaxWeightsLimit"),
        ("SubtensorModule", "WeightsVersionKey"),
        ("SubtensorModule", "WeightsSetRateLimit"),
        ("SubtensorModule", "LastUpdate"),
        ("SubtensorModule", "CommitRevealWeightsEnabled"),
        ("SubtensorModule", "ValidatorPermit"),
        ("SubtensorModule", "StakeThreshold"),
        ("SubtensorModule", "OwnedHotkeys"),
        ("SubtensorModule", "TimelockedWeightCommits"),
        ("SubtensorModule", "Uids"),
        ("SubtensorModule", "Tempo"),
        ("SubtensorModule", "BlocksSinceLastStep"),
        ("SubtensorModule", "LastEpochBlock"),
        ("SubtensorModule", "PendingEpochAt"),
        ("SubtensorModule", "RevealPeriodEpochs"),
        ("SubtensorModule", "SubnetEpochIndex"),
        ("MevShield", "NextKey"),
        ("MevShield", "NextKeyExpiresAt"),
        ("MevShield", "AuthorKeys"),
        ("System", "LastRuntimeUpgrade"),
        ("Timestamp", "Now"),
    ),
    "runtime_apis": (("SubnetInfoRuntimeApi", "get_metagraph"),),
}


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def expected_surface(generated=None):
    """The surface as the pinned SDK's generated bindings describe it."""
    if generated is None:
        from bittensor._generated import calls, runtime_apis, storage

        generated = (calls, storage, runtime_apis)
    calls, storage, runtime_apis = generated
    out = {"calls": {}, "storage": {}, "runtime_apis": []}
    for pallet, name in SURFACE["calls"]:
        builder = getattr(getattr(calls, pallet, None), name, None)
        out["calls"][f"{pallet}.{name}"] = (
            None
            if builder is None
            else [
                [p.name, p.annotation if isinstance(p.annotation, str) else "Any"]
                for p in inspect.signature(builder).parameters.values()
            ]
        )
    for pallet, name in SURFACE["storage"]:
        item = getattr(getattr(storage, pallet, None), name, None)
        out["storage"][f"{pallet}.{name}"] = (
            None if item is None else item.value_type_ident
        )
    for api, method in SURFACE["runtime_apis"]:
        if getattr(getattr(runtime_apis, api, None), method, None) is not None:
            out["runtime_apis"].append(f"{api}.{method}")
    return out


def _generated_type(type_ident):
    """How codegen writes an argument type: named types stay, others are Any."""
    if type_ident.isidentifier():
        return type_ident
    return "Any"


def raw_call_types(ir):
    """The runtime's own argument types for the surface's calls, unnormalized.

    The SDK annotates structural arguments (`Vec<u16>`, `Compact<u64>`) as
    `Any`, so the comparison cannot see a change inside them. The report
    carries these raw types, and the surface digest covers them.
    """
    pallets = {p["name"]: p for p in ir["pallets"]}
    out = {}
    for pallet, name in SURFACE["calls"]:
        calls = {c["name"]: c for c in (pallets.get(pallet) or {}).get("calls") or []}
        call = calls.get(name)
        out[f"{pallet}.{name}"] = (
            None
            if call is None
            else [[a["name"], a["type_ident"]] for a in call["args"]]
        )
    return out


def observed_surface(ir):
    """The same surface read from a runtime's metadata IR (`MetadataIR.to_dict`)."""
    pallets = {p["name"]: p for p in ir["pallets"]}
    out = {"calls": {}, "storage": {}, "runtime_apis": []}
    for pallet, name in SURFACE["calls"]:
        calls = {c["name"]: c for c in (pallets.get(pallet) or {}).get("calls") or []}
        call = calls.get(name)
        out["calls"][f"{pallet}.{name}"] = (
            None
            if call is None
            else [[a["name"], _generated_type(a["type_ident"])] for a in call["args"]]
        )
    for pallet, name in SURFACE["storage"]:
        items = {s["name"]: s for s in (pallets.get(pallet) or {}).get("storage") or []}
        item = items.get(name)
        out["storage"][f"{pallet}.{name}"] = (
            None if item is None else item["value_type_ident"]
        )
    apis = {a["name"]: set(a["methods"]) for a in ir.get("runtime_apis") or []}
    for api, method in SURFACE["runtime_apis"]:
        if method in apis.get(api, ()):
            out["runtime_apis"].append(f"{api}.{method}")
    return out


def compare(expected, observed, *, spec_version, context, raw_calls=None):
    differences = []
    for kind in ("calls", "storage"):
        for key, want in expected[kind].items():
            got = observed[kind].get(key)
            if want is None:
                differences.append({"item": key, "kind": kind, "issue": "sdk_lacks"})
            elif got is None:
                differences.append({"item": key, "kind": kind, "issue": "missing"})
            elif got != want:
                differences.append(
                    {
                        "item": key,
                        "kind": kind,
                        "issue": "changed",
                        "sdk": want,
                        "runtime": got,
                    }
                )
    for key in sorted(set(expected["runtime_apis"]) - set(observed["runtime_apis"])):
        differences.append({"item": key, "kind": "runtime_apis", "issue": "missing"})
    return {
        "schema": SCHEMA,
        "context": context,
        "spec_version": spec_version,
        "sdk": "bittensor==11.1.0",
        "status": "INCOMPATIBLE" if differences else "COMPATIBLE_USED_SURFACE",
        "differences": differences,
        "runtime_call_types": raw_calls,
        "surface_digest": "sha256:"
        + hashlib.sha256(
            _canonical({"surface": observed, "raw_calls": raw_calls})
        ).hexdigest(),
        "claims": {
            "names_and_types_unchanged": not differences,
            "runtime_behaviour_verified": False,
            "authorizes_publication": False,
        },
    }


async def probe(endpoint, genesis_hash):
    """Read the finalized head's metadata. Read-only: nothing is signed."""
    from .sdk_weights import require_sdk

    require_sdk()
    import bittensor as bt

    substrate = bt.RpcSubstrate(endpoint, fallback_endpoints=[], archive_endpoints=[])
    await substrate.connect()
    try:
        raw = substrate.raw
        if (await substrate.block_hash(0)).lower() != genesis_hash.lower():
            raise ValueError("genesis differs from the configured testnet")
        head = await raw.get_chain_finalised_head()
        ir = (await raw.metadata_ir(head)).to_dict()
        number = await raw.get_block_number(head)
    finally:
        await substrate.close()
    return compare(
        expected_surface(),
        observed_surface(ir),
        spec_version=ir["spec_version"],
        raw_calls=raw_call_types(ir),
        context={
            "endpoint": endpoint,
            "genesis_hash": genesis_hash,
            "finalized_block": number,
            "finalized_hash": head,
        },
    )


def main(argv=None):
    import argparse
    import asyncio

    from carbon.development_testnet.operator import load_config

    parser = argparse.ArgumentParser(prog="python -m carbon.chain.runtime_probe")
    parser.add_argument("--config", required=True, help="the operator config")
    args = parser.parse_args(argv)
    config = load_config(args.config)
    report = asyncio.run(probe(config.endpoint, config.genesis_hash))
    report["operator_expected_runtime_spec"] = config.expected_runtime_spec
    print(json.dumps(report, sort_keys=True, indent=2))
    return 0 if report["status"] == "COMPATIBLE_USED_SURFACE" else 3


if __name__ == "__main__":
    raise SystemExit(main())
