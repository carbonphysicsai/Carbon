"""Explicit disposable Docker localnet setup; never a public-network operator."""

import asyncio
import hashlib
import ipaddress
import json
import os
import subprocess
from contextlib import aclosing, asynccontextmanager
from dataclasses import asdict, dataclass
from pathlib import Path

from .models import ChainContext, hash256
from .publication import PublicationFailure
from .sdk_weights import (
    journaled_substrate,
    require_sdk,
    require_shield_era_period,
)

IMAGE = "ghcr.io/raofoundation/subtensor-localnet"
DIGEST = "sha256:bb762bf7a88502e0e21f76a1e6615ad4c00316f6b0e988dba2e59035c015aa86"
SOURCE = "d3f40e44bda9019c606aeb0c907bb52ba7fe386c"

# Pinned upstream public CLI compatibility option; runtime binary is unchanged.
STARTUP = r"""set -euo pipefail
printf '%s  %s\n' 690d4a122f0ace126feccc10a76b9c1db17fbc57cc09f1cb195cea03c5c78fae /scripts/localnet.sh | sha256sum -c -
sed '/^    --validator$/a\    --network-backend libp2p' /scripts/localnet.sh > /scripts/carbon-localnet.sh
chmod 700 /scripts/carbon-localnet.sh
export RUST_LOG='info,basic-authorship=debug,mev-shield=debug,pallet-shield=debug'
exec /scripts/carbon-localnet.sh True --no-purge"""


def write_evidence(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(".tmp")
    temp.write_text(
        json.dumps(value, indent=2, allow_nan=False) + "\n", encoding="utf-8"
    )
    temp.replace(path)


def _inspect_container(container):
    """Derive endpoints from a running pinned container, not caller-provided URLs."""
    if not container or not container.startswith("carbon-localnet-"):
        raise PublicationFailure("DISPOSABLE_CONTAINER_REQUIRED")

    def docker(*args):
        result = subprocess.run(
            ["docker", *args], capture_output=True, text=True, check=True, timeout=15
        )
        return json.loads(result.stdout)

    item = docker("inspect", container)[0]
    nets = item["NetworkSettings"]["Networks"]
    if (
        item["Config"]["Image"] != IMAGE + "@" + DIGEST
        or item["Config"].get("Entrypoint") != ["/bin/bash"]
        or item["Config"].get("Cmd") != ["-c", STARTUP]
        or not item["State"]["Running"]
        or item["Config"].get("Labels", {}).get("carbon.scope") != "disposable-localnet"
        or len(nets) != 1
        or item["HostConfig"]["Privileged"]
        or item["Mounts"]
    ):
        raise PublicationFailure("CONTAINER_ISOLATION_MISMATCH")
    network = docker("network", "inspect", next(iter(nets)))[0]
    if not network["Internal"] or set(network["Containers"]) != {item["Id"]}:
        raise PublicationFailure("NETWORK_ISOLATION_MISMATCH")
    address = ipaddress.ip_address(next(iter(nets.values()))["IPAddress"])
    if not address.is_private or address.is_loopback or address.is_unspecified:
        raise PublicationFailure("INTERNAL_CONTAINER_ADDRESS_REQUIRED")
    return {
        "schema": "carbon.disposable.isolation.v1",
        "container": item["Id"],
        "image": IMAGE + "@" + DIGEST,
        "source_commit": SOURCE,
        "startup_sha256": hashlib.sha256(STARTUP.encode()).hexdigest(),
        "network_backend": "libp2p",
        "internal_network": network["Id"],
        "container_address": str(address),
        "ports": item["NetworkSettings"]["Ports"],
        "scope": "DISPOSABLE_LOCALNET_ONLY",
    }


# Process-owned capability, constructed explicitly by run(), never from a file/URL.
_ACTIVE_RELAY = None


def inspect_isolation(container):
    proof = _inspect_container(container)
    ports = proof.pop("ports")
    if _ACTIVE_RELAY is not None:
        original, servers = _ACTIVE_RELAY
        if any(ports.values()) or proof != original:
            raise PublicationFailure("RELAY_CONTAINER_CHANGED")
        endpoints = []
        for server in servers:
            if not server.is_serving() or len(server.sockets) != 1:
                raise PublicationFailure("RELAY_NOT_LISTENING")
            address, port = server.sockets[0].getsockname()
            if address != "127.0.0.1":
                raise PublicationFailure("LOOPBACK_RPC_REQUIRED")
            endpoints.append(f"ws://127.0.0.1:{port}")
        return dict(proof, endpoints=endpoints, transport="PROCESS_LOOPBACK_RELAY")
    endpoints = []
    for port in ("9944/tcp", "9945/tcp"):
        bindings = ports.get(port)
        if (
            type(bindings) is not list
            or len(bindings) != 1
            or bindings[0]["HostIp"] != "127.0.0.1"
        ):
            raise PublicationFailure("LOOPBACK_RPC_REQUIRED")
        endpoints.append("ws://127.0.0.1:" + str(int(bindings[0]["HostPort"])))
    if any(
        port not in ("9944/tcp", "9945/tcp") and value for port, value in ports.items()
    ):
        raise PublicationFailure("UNEXPECTED_PUBLISHED_PORT")
    return dict(proof, endpoints=endpoints, transport="DOCKER_LOOPBACK_BINDING")


@asynccontextmanager
async def isolated_relays(container, *, ports=(0, 0)):
    """Own fixed internal RPC relays; explicit ports preserve restart context."""
    global _ACTIVE_RELAY
    if _ACTIVE_RELAY is not None:
        raise PublicationFailure("RELAY_ALREADY_RUNNING")
    if (
        type(ports) is not tuple
        or len(ports) != 2
        or any(type(p) is not int or not 0 <= p <= 65535 for p in ports)
    ):
        raise PublicationFailure("INVALID_LOCAL_RELAY_PORTS")
    proof = _inspect_container(container)
    if any(proof.pop("ports").values()):
        raise PublicationFailure("RELAY_REQUIRES_UNPUBLISHED_INTERNAL_NETWORK")
    connections = set()

    async def bridge(reader, writer, port):
        task = asyncio.current_task()
        connections.add(task)
        remote = None
        try:
            remote_reader, remote = await asyncio.wait_for(
                asyncio.open_connection(proof["container_address"], port), 3
            )

            async def copy(source, target):
                while data := await source.read(65536):
                    target.write(data)
                    await target.drain()

            pipes = [
                asyncio.create_task(copy(reader, remote)),
                asyncio.create_task(copy(remote_reader, writer)),
            ]
            try:
                await asyncio.wait(pipes, return_when=asyncio.FIRST_COMPLETED)
            finally:
                for pipe in pipes:
                    pipe.cancel()
                await asyncio.gather(*pipes, return_exceptions=True)
        except (OSError, TimeoutError):
            pass  # RPC observes a closed connection; no payloads enter diagnostics.
        finally:
            writer.close()
            if remote is not None:
                remote.close()
            connections.discard(task)

    servers = []
    try:
        for port, local_port in zip((9944, 9945), ports):
            servers.append(
                await asyncio.start_server(
                    lambda r, w, p=port: bridge(r, w, p), "127.0.0.1", local_port
                )
            )
        _ACTIVE_RELAY = (proof, servers)
        yield inspect_isolation(container)
    finally:
        _ACTIVE_RELAY = None
        for server in servers:
            server.close()
            await server.wait_closed()
        for task in tuple(connections):
            task.cancel()
        await asyncio.gather(*connections, return_exceptions=True)


async def run(container, directory):
    """Own the relays and actual pytest lane for one disposable lifetime."""
    async with isolated_relays(container):
        await probe(container, directory)
        import pytest

        os.environ["CARBON_REQUIRE_LOCALNET"] = "1"
        return await asyncio.to_thread(
            pytest.main, ["tests/cpu/test_net5_integration.py", "-q", "-s"]
        )


async def probe(container, directory):
    require_sdk()
    isolation = inspect_isolation(container)
    import bittensor as bt

    sub = bt.RpcSubstrate(
        isolation["endpoints"][0],
        fallback_endpoints=[],
        archive_endpoints=[],
        retry_forever=False,
    )
    try:
        # Startup waits are bounded and read-only. No key exists in this function.
        for attempt in range(60):
            try:

                async def observe_once():
                    await sub.connect()
                    genesis = hash256(await sub.block_hash(0))
                    version = await sub.spec_version()
                    async with aclosing(
                        bt.Client(isolation["endpoints"][0], substrate=sub).blocks(
                            finalized=True
                        )
                    ) as headers:
                        header = await anext(headers)
                    finalized = await sub.block_hash(header.number)
                    return genesis, version, finalized

                genesis, version, finalized = await asyncio.wait_for(observe_once(), 5)
                break
            except (bt.RpcConnectionError, OSError, TimeoutError):
                inspect_isolation(container)  # Stop promptly if an authority exits.
                if attempt == 59:
                    raise PublicationFailure("LOCALNET_STARTUP_UNAVAILABLE") from None
                await asyncio.sleep(1)
        if version != 445:
            raise PublicationFailure("PINNED_RUNTIME_MISMATCH")
        isolation.update(
            genesis=genesis, spec_version=version, finalized_hash=finalized
        )
        write_evidence(Path(directory) / "isolation.json", isolation)
        print(
            "Localnet isolation/genesis/runtime observed; no signing performed.",
            flush=True,
        )
        return isolation
    finally:
        await sub.close()


ROOT_SETTINGS = {
    "start_delay": ("sudo_set_start_call_delay", (0,)),
    "admin_window": ("sudo_set_admin_freeze_window", (0,)),
    "owner_rate": ("sudo_set_owner_hparam_rate_limit", (0,)),
    "plain": ("sudo_set_commit_reveal_weights_enabled", (2, False)),
    "burn": ("sudo_set_recycle_or_burn", (2, "Burn")),
    "minimum": ("sudo_set_min_allowed_weights", (2, 1)),
    "rate": ("sudo_set_weights_set_rate_limit", (2, 0)),
    "tempo": ("sudo_set_tempo", (2, 20)),
    "registration": ("sudo_set_network_registration_allowed", (2, True)),
    "emissions": ("sudo_set_subnet_emission_enabled", (2, True)),
}


def miner_burned_q32(value):
    """Decode pinned runtime U96F32 storage without float rounding or aliasing recycle."""
    if type(value) is dict and set(value) == {"bits"}:
        value = value["bits"]
    if type(value) is not int or not 0 <= value <= 2**32:
        raise PublicationFailure("UNSUPPORTED_MINER_BURNED_ENCODING")
    return value


def root_setting(action, verify):
    """Closed, value-pinned DEV settings through the SDK public Intent extension."""
    require_sdk()
    if action not in ROOT_SETTINGS:
        raise PublicationFailure("UNSUPPORTED_LOCAL_SETUP_ACTION")
    from bittensor._generated import calls
    from bittensor.intents.base import Intent

    @dataclass
    class LocalSetting(Intent):
        op = "carbon_disposable_setup"
        signer = "coldkey"
        origin = "root"
        netuid: int = 2

        async def build(self, substrate, wallet):
            await verify()
            method, args = ROOT_SETTINGS[action]
            return await substrate.compose(getattr(calls.AdminUtils, method)(*args))

        def summary(self):
            return "disposable localnet setting: " + action

    return LocalSetting()


class LocalnetSession:
    """Setup keys stay in memory; every signed call rechecks observed genesis."""

    def __init__(self, container, directory):
        self.container, self.directory = container, Path(directory)
        self.context = self.client = self.sub = None
        self.roles, self.operations = {}, []
        self.signer = None
        self.shield_era_period = None

    async def start(self):
        import bittensor as bt
        from bittensor.keyfiles import Keypair

        if (self.directory / "setup.json").exists():
            raise PublicationFailure("EXISTING_SETUP_REQUIRES_RECONCILIATION")
        observed = json.loads((self.directory / "isolation.json").read_text())
        actual = inspect_isolation(self.container)
        if any(observed[key] != actual[key] for key in actual):
            raise PublicationFailure("ISOLATION_CHANGED")
        # Fail before constructing disposable keys if the exact pinned SDK no longer
        # agrees with v445's submit_encrypted mortality ceiling.
        self.shield_era_period = require_shield_era_period()
        self.context = ChainContext(
            "localnet",
            actual["endpoints"][0],
            "disposable-primary",
            observed["genesis"],
            2,
        )

        async def before_sign(call, signer):
            await self.verify()
            if call.spec_version != 445 or signer != self.signer:
                raise PublicationFailure("SETUP_SIGNING_CONTEXT_CHANGED")

        async def before_dispatch(tx_hash):
            self.operations[-1]["transaction"] = tx_hash
            self.save()

        async def after_inner_sign(tx_hash):
            self.operations[-1]["inner_transaction"] = tx_hash
            self.save()

        async def after_shield_key(digest, length):
            self.operations[-1]["shield_key"] = {
                "digest": digest,
                "length": length,
            }
            self.save()

        async def before_signed_extrinsic(kind, kwargs):
            if "shield_era_blocks" not in self.operations[-1]:
                return
            nonce, period = kwargs.get("nonce"), kwargs.get("period")
            if type(nonce) is not int or nonce < 0:
                raise PublicationFailure("INVALID_SHIELD_NONCE")
            if period != self.shield_era_period:
                raise PublicationFailure("SHIELD_ERA_CONTEXT_CHANGED")
            self.operations[-1].setdefault("signed_extrinsics", {})[kind] = {
                "nonce": nonce,
                "era_blocks": period,
            }
            self.save()

        self.sub = journaled_substrate(
            self.context,
            before_sign,
            before_dispatch,
            after_inner_sign=after_inner_sign,
            after_shield_key=after_shield_key,
            before_signed_extrinsic=before_signed_extrinsic,
        )
        await self.sub.connect()
        await self.verify()
        self.client = bt.Client(
            self.context.endpoint,
            substrate=self.sub,
            policy=bt.Policy(allowed_netuids=[2]),
        )
        # Publicly known development URIs; no valuable-network key is accessed.
        self.roles = {
            name: Keypair.create_from_uri(uri)
            for name, uri in (
                ("owner", "//Alice"),
                ("publisher", "//Alice_hk"),
                ("miner", "//Bob"),
                ("challenger", "//Charlie"),
                ("replacement", "//Dave"),
            )
        }
        self.save()
        return self

    async def verify(self):
        if hash256(await self.sub.block_hash(0)) != self.context.genesis_hash:
            raise PublicationFailure("ENDPOINT_GENESIS_MISMATCH")
        if await self.sub.spec_version() != 445:
            raise PublicationFailure("PINNED_RUNTIME_MISMATCH")

    def save(self):
        write_evidence(
            self.directory / "setup.json",
            {
                "schema": "carbon.disposable.setup.v1",
                "context": asdict(self.context),
                "roles": {name: pair.ss58_address for name, pair in self.roles.items()},
                "operations": self.operations,
                "treasury": None,
            },
        )

    async def execute(self, label, intent, role="owner"):
        if any(op["label"] == label for op in self.operations):
            raise PublicationFailure("SETUP_REPLAY_REQUIRES_RECONCILIATION")
        await self.verify()
        self.signer = self.roles[role].ss58_address
        async with aclosing(self.client.blocks(finalized=True)) as headers:
            start = (await anext(headers)).number
        record = {"label": label, "state": "PREPARED", "start_finalized_block": start}
        if intent.mev_shield_required:
            record["shield_era_blocks"] = self.shield_era_period
        self.operations.append(record)
        self.save()
        print("Localnet setup: " + label, flush=True)
        try:
            if intent.mev_shield_required:
                operation = self.client.submit_shielded(
                    intent,
                    self.roles[role],
                    period=self.shield_era_period,
                    wait_for_inclusion=True,
                    wait_for_finalization=True,
                )
            else:
                operation = self.client.execute(
                    intent,
                    self.roles[role],
                    retries=0,
                    wait_for_inclusion=True,
                    wait_for_finalization=True,
                )
            result = await asyncio.wait_for(operation, 90)
            if result.data.get("shielded"):
                record["shielded"] = True
                record["inner_transaction"] = hash256(
                    result.data["inner_extrinsic_hash"]
                )
            if result.error is not None and result.error.message.startswith(
                "the MEV shield accepted the encrypted submission, but the decrypted "
            ):
                record["capability_failure"] = "SHIELDED_INNER_NOT_OBSERVED_BEFORE_ERA"
            record.update(
                state="FINALIZED" if result.success else "REJECTED",
                block_hash=result.block_hash,
                extrinsic_id=result.extrinsic_id,
                error_name=None if result.error is None else result.error.name,
                error_code=None if result.error is None else result.error.code.value,
            )
            self.save()
            if not result.success and "inner_transaction" in record:
                result = await self.reconcile_inner(record, result)
            if not result.success:
                raise PublicationFailure("LOCAL_SETUP_REJECTED:" + label)
            return result
        except Exception:
            if record["state"] == "PREPARED":
                record["state"] = "AMBIGUOUS_OR_UNAVAILABLE"
            self.save()
            raise

    async def reconcile_inner(self, record, reported):
        """Read finalized exact hashes after an ambiguous shield receipt; never resend."""
        await self.verify()
        async with aclosing(self.client.blocks(finalized=True)) as headers:
            end = (await anext(headers)).number
        start = record["start_finalized_block"]
        if not 0 <= end - start <= 256:
            raise PublicationFailure("SETUP_RECONCILIATION_RANGE_EXCEEDED")
        observed = {}
        inner = None
        for block in range(start, end + 1):
            block_hash = await self.sub.block_hash(block)
            for kind in ("transaction", "inner_transaction"):
                identity = record.get(kind)
                if identity is None or kind in observed:
                    continue
                found = await self.sub.find_extrinsic(identity, block_hash)
                if found is not None:
                    if found.block_hash != block_hash:
                        raise PublicationFailure("CONFLICTING_SETUP_RECEIPT")
                    observed[kind] = {
                        "block": block,
                        "hash": block_hash,
                        "success": found.success,
                    }
                    if kind == "inner_transaction":
                        inner = found
        record["reconciled_at_finalized_block"] = end
        record["observed_transactions"] = observed
        if inner is not None and inner.success:
            record["state"] = "FINALIZED_RECONCILED"
            record["block_hash"] = inner.block_hash
            record["extrinsic_id"] = inner.extrinsic_id
        self.save()
        return inner if inner is not None else reported

    async def configure(self):
        import bittensor as bt

        for action in ("start_delay", "owner_rate", "admin_window"):
            await self.execute(action, root_setting(action, self.verify))
        await self.execute(
            "create-subnet",
            bt.RegisterSubnet(hotkey_ss58=self.roles["publisher"].ss58_address),
        )
        owner = await self.sub.query("SubtensorModule", "SubnetOwner", [2])
        hotkey = await self.sub.query("SubtensorModule", "SubnetOwnerHotkey", [2])
        if (owner, hotkey) != (
            self.roles["owner"].ss58_address,
            self.roles["publisher"].ss58_address,
        ):
            raise PublicationFailure("CREATED_SUBNET_IDENTITY_MISMATCH")
        for action in (
            "plain",
            "burn",
            "minimum",
            "rate",
            "tempo",
            "registration",
            "emissions",
        ):
            await self.execute(action, root_setting(action, self.verify))
        await self.execute("activate", bt.StartCall(netuid=2))
        await self.execute(
            "validator-stake",
            bt.AddStake(
                hotkey_ss58=self.roles["publisher"].ss58_address,
                netuid=2,
                amount_tao="1",
            ),
        )

    async def register_miners(self):
        import bittensor as bt

        for role in ("miner", "challenger"):
            await self.execute(
                "register-" + role,
                bt.BurnedRegister(netuid=2, hotkey_ss58=self.roles[role].ss58_address),
                role,
            )

    async def close(self):
        if self.sub is not None:
            await self.sub.close()


if __name__ == "__main__":
    import sys

    from carbon.chain.localnet import run as owned_run

    if sys.argv[1:] != ["run"]:
        raise SystemExit("Only the explicit disposable integration run is supported.")
    raise SystemExit(
        asyncio.run(
            owned_run(
                os.environ["CARBON_LOCALNET_CONTAINER"],
                os.environ["CARBON_LOCALNET_EVIDENCE"],
            )
        )
    )
