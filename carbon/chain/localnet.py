"""Explicit disposable Docker localnet setup; never a public-network operator."""

import asyncio
import hashlib
import ipaddress
import json
import os
import subprocess
import time
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
MANIFEST_PATH = Path(__file__).parents[2] / "scripts/dev/localnet-runtime.json"


def runtime_manifest():
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    if (
        manifest.get("schema") != "carbon.localnet.runtime.v2"
        or manifest.get("image") != IMAGE
        or manifest.get("image_digest") != DIGEST
        or manifest.get("commit") != SOURCE
        or set(manifest.get("profiles", {})) != {"fast", "standard"}
    ):
        raise PublicationFailure("LOCALNET_MANIFEST_MISMATCH")
    return manifest


def runtime_profile(name=None):
    name = name or os.environ.get("CARBON_LOCALNET_PROFILE", "fast")
    manifest = runtime_manifest()
    if name not in ("fast", "standard"):
        raise PublicationFailure("UNSUPPORTED_LOCALNET_PROFILE")
    profile = manifest["profiles"][name]
    expected = {
        "fast": (
            "True",
            "/target/fast-runtime/release/node-subtensor",
            "/target/fast-runtime/release/node_subtensor_runtime.compact.compressed.wasm",
            ("pow-faucet", "metadata-hash", "fast-runtime"),
            "0.25",
        ),
        "standard": (
            "False",
            "/target/non-fast-runtime/release/node-subtensor",
            "/target/non-fast-runtime/release/node_subtensor_runtime.compact.compressed.wasm",
            ("pow-faucet", "metadata-hash"),
            "12",
        ),
    }[name]
    actual = (
        profile.get("selector"),
        profile.get("binary_path"),
        profile.get("wasm_path"),
        tuple(profile.get("cargo_features", ())),
        profile.get("nominal_block_seconds"),
    )
    if actual != expected or profile.get("build_profile") != "release":
        raise PublicationFailure("LOCALNET_PROFILE_MISMATCH")
    return name, profile


def startup_for(profile_name):
    _, profile = runtime_profile(profile_name)
    selector = profile["selector"]
    return rf"""set -euo pipefail
printf '%s  %s\n' 690d4a122f0ace126feccc10a76b9c1db17fbc57cc09f1cb195cea03c5c78fae /scripts/localnet.sh | sha256sum -c -
sed '/^    --validator$/a\    --network-backend libp2p' /scripts/localnet.sh > /scripts/carbon-localnet.sh
chmod 700 /scripts/carbon-localnet.sh
export RUST_LOG='info,mev-shield=debug,pallet-shield=debug'
exec /scripts/carbon-localnet.sh {selector} --no-purge"""


# Compatibility name retained for the original fast-runtime tests and evidence.
STARTUP = startup_for("fast")


def inspect_image_profile(image, profile_name, directory, *, allow_unbound=False):
    """Verify both installed release artifacts before any network or keys exist."""
    if image != IMAGE + "@" + DIGEST:
        raise PublicationFailure("PINNED_IMAGE_REQUIRED")
    manifest = runtime_manifest()
    runtime_profile(profile_name)

    def docker(*args, timeout=45):
        return subprocess.run(
            ["docker", *args],
            capture_output=True,
            text=True,
            check=True,
            timeout=timeout,
        )

    image_item = json.loads(docker("image", "inspect", image).stdout)[0]
    if (
        image_item["Config"].get("Entrypoint") != manifest["image_entrypoint"]
        or image_item["Config"].get("Cmd") != manifest["image_default_command"]
    ):
        raise PublicationFailure("PINNED_IMAGE_CONFIGURATION_MISMATCH")

    script = "set -uo pipefail\n"
    for name in ("fast", "standard"):
        profile = manifest["profiles"][name]
        script += (
            f"if test -f {profile['binary_path']}; then echo '{name}_binary_present=true'; "
            f"else echo '{name}_binary_present=false'; fi\n"
            f"if test -x {profile['binary_path']}; then echo '{name}_binary_executable=true'; "
            f"else echo '{name}_binary_executable=false'; fi\n"
            f"if test -f {profile['wasm_path']}; then echo '{name}_wasm_present=true'; "
            f"else echo '{name}_wasm_present=false'; fi\n"
            f"printf '{name}_binary_sha256='; sha256sum {profile['binary_path']} 2>/dev/null | cut -d' ' -f1\n"
            f"printf '{name}_wasm_sha256='; sha256sum {profile['wasm_path']} 2>/dev/null | cut -d' ' -f1\n"
            f"version=$({profile['binary_path']} --version 2>&1); rc=$?; "
            f"printf '{name}_version_rc=%s\\n' \"$rc\"; "
            f"printf '{name}_version=%s\\n' \"${{version%%$'\\n'*}}\"\n"
        )
    output = docker(
        "run",
        "--rm",
        "--platform",
        "linux/amd64",
        "--network",
        "none",
        "--entrypoint",
        "/bin/bash",
        image,
        "-c",
        script,
        timeout=90,
    ).stdout
    observed = {}
    fields = (
        "binary_present",
        "binary_executable",
        "wasm_present",
        "binary_sha256",
        "wasm_sha256",
        "version_rc",
        "version",
    )
    for line in output.splitlines():
        key, separator, value = line.partition("=")
        if separator and key in {
            f"{name}_{field}" for name in ("fast", "standard") for field in fields
        }:
            observed[key] = value.strip()
    if len(observed) != 2 * len(fields):
        raise PublicationFailure("INSTALLED_PROFILE_IDENTITY_UNAVAILABLE")
    for name in ("fast", "standard"):
        if any(
            observed[f"{name}_{field}"] != "true"
            for field in ("binary_present", "binary_executable", "wasm_present")
        ):
            proof = {
                "schema": "carbon.localnet.image-profile-failure.v1",
                "image": image,
                "selected_profile": profile_name,
                "observed": observed,
                "outcome": "DOCUMENTED_PROFILE_ARTIFACT_MISSING",
            }
            write_evidence(Path(directory) / "image-profile.json", proof)
            raise PublicationFailure("DOCUMENTED_PROFILE_ARTIFACT_MISSING")
    if (
        observed["fast_binary_sha256"] == observed["standard_binary_sha256"]
        or observed["fast_wasm_sha256"] == observed["standard_wasm_sha256"]
    ):
        raise PublicationFailure("INSTALLED_RUNTIME_PROFILES_NOT_DISTINCT")
    for name in ("fast", "standard"):
        for field in ("binary_sha256", "wasm_sha256"):
            expected = manifest["profiles"][name].get(field)
            if expected is None and not allow_unbound:
                raise PublicationFailure("UNBOUND_INSTALLED_PROFILE_IDENTITY")
            if expected is not None and observed[f"{name}_{field}"] != expected:
                raise PublicationFailure("INSTALLED_PROFILE_IDENTITY_MISMATCH")
    proof = {
        "schema": "carbon.localnet.image-profile.v1",
        "image": image,
        "source_commit": SOURCE,
        "source_contracts": {
            "Dockerfile-localnet": manifest["build_definition_sha256"],
            "scripts/localnet.sh": manifest["startup_script_sha256"],
        },
        "image_entrypoint": image_item["Config"]["Entrypoint"],
        "image_default_command": image_item["Config"]["Cmd"],
        "selected_profile": profile_name,
        "profiles": {
            name: {
                **{
                    key: manifest["profiles"][name][key]
                    for key in (
                        "selector",
                        "binary_path",
                        "wasm_path",
                        "build_profile",
                        "cargo_features",
                        "nominal_block_seconds",
                    )
                },
                "binary_sha256": observed[f"{name}_binary_sha256"],
                "wasm_sha256": observed[f"{name}_wasm_sha256"],
                "version": observed[f"{name}_version"],
                "version_command_exit": int(observed[f"{name}_version_rc"]),
            }
            for name in ("fast", "standard")
        },
        "profiles_distinct": True,
        "scope": "DISPOSABLE_LOCALNET_ONLY",
    }
    write_evidence(Path(directory) / "image-profile.json", proof)
    return proof


def write_evidence(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(".tmp")
    temp.write_text(
        json.dumps(value, indent=2, allow_nan=False) + "\n", encoding="utf-8"
    )
    temp.replace(path)


def public_identity(value):
    """JSON-safe public authority identity; never accepts private structures."""
    if isinstance(value, bytes):
        return "0x" + value.hex()
    if isinstance(value, str):
        return value
    if type(value) is list and all(
        type(part) is int and 0 <= part <= 255 for part in value
    ):
        return "0x" + bytes(value).hex()
    raise PublicationFailure("UNSUPPORTED_PUBLIC_AUTHORITY_IDENTITY")


def public_key_digest(value):
    if not value:
        return None
    if isinstance(value, str):
        value = bytes.fromhex(value.removeprefix("0x"))
    else:
        value = bytes(value)
    return "sha256:" + hashlib.sha256(value).hexdigest()


def _inspect_container(container, profile_name=None):
    """Derive endpoints from a running pinned container, not caller-provided URLs."""
    if not container or not container.startswith("carbon-localnet-"):
        raise PublicationFailure("DISPOSABLE_CONTAINER_REQUIRED")
    profile_name, profile = runtime_profile(profile_name)
    mode = os.environ.get("CARBON_LOCALNET_MODE", "full")
    manifest = runtime_manifest()
    if mode not in manifest["budgets"]:
        raise PublicationFailure("UNSUPPORTED_LOCALNET_MODE")
    budget = manifest["budgets"][mode]

    def docker(*args):
        result = subprocess.run(
            ["docker", *args], capture_output=True, text=True, check=True, timeout=15
        )
        return json.loads(result.stdout)

    item = docker("inspect", container)[0]
    nets = item["NetworkSettings"]["Networks"]
    labels = item["Config"].get("Labels", {})
    if (
        item["Config"]["Image"] != IMAGE + "@" + DIGEST
        or item["Config"].get("Entrypoint") != ["/bin/bash"]
        or item["Config"].get("Cmd") != ["-c", startup_for(profile_name)]
        or not item["State"]["Running"]
        or labels.get("carbon.scope") != "disposable-localnet"
        or labels.get("carbon.runtime-profile") != profile_name
        or labels.get("carbon.execution-mode") != mode
        or len(nets) != 1
        or item["HostConfig"]["Privileged"]
        or item["Mounts"]
        or item["HostConfig"].get("Memory") != 5 * 1024**3
        or item["HostConfig"].get("NanoCpus") != int(budget["cpus"]) * 10**9
        or item["HostConfig"].get("PidsLimit") != budget["pids_limit"]
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
        "runtime_profile": profile_name,
        "runtime_selector": profile["selector"],
        "runtime_binary": profile["binary_path"],
        "runtime_build_profile": profile["build_profile"],
        "runtime_features": profile["cargo_features"],
        "expected_genesis": profile["expected_genesis"],
        "execution_mode": mode,
        "execution_budget": budget,
        "startup_sha256": hashlib.sha256(
            startup_for(profile_name).encode()
        ).hexdigest(),
        "network_backend": "libp2p",
        "internal_network": network["Id"],
        "container_address": str(address),
        "ports": item["NetworkSettings"]["Ports"],
        "scope": "DISPOSABLE_LOCALNET_ONLY",
    }


# Process-owned capability, constructed explicitly by run(), never from a file/URL.
_ACTIVE_RELAY = None


def inspect_isolation(container, profile_name=None):
    proof = _inspect_container(container, profile_name)
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
async def isolated_relays(container, *, ports=(0, 0), profile_name=None):
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
    proof = _inspect_container(container, profile_name)
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
    """Own relays and exactly one bounded lane for a disposable lifetime."""
    mode = os.environ.get("CARBON_LOCALNET_MODE", "full")
    profile_name, _ = runtime_profile()
    async with isolated_relays(container, profile_name=profile_name):
        await probe(
            container,
            directory,
            profile_name=profile_name,
            allow_unbound=mode == "inspect",
        )
        if mode == "inspect":
            return 0
        if mode == "diagnostic":
            return await registration_diagnostic(container, directory)
        import pytest

        os.environ["CARBON_REQUIRE_LOCALNET"] = "1"
        return await asyncio.to_thread(
            pytest.main, ["tests/cpu/test_net5_integration.py", "-q", "-s"]
        )


async def probe(container, directory, *, profile_name=None, allow_unbound=False):
    require_sdk()
    profile_name, profile = runtime_profile(profile_name)
    isolation = inspect_isolation(container, profile_name)
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
        expected = profile["expected_genesis"]
        if expected is None and not allow_unbound:
            raise PublicationFailure("UNBOUND_PROFILE_GENESIS")
        if expected is not None and genesis != expected:
            raise PublicationFailure("PROFILE_GENESIS_MISMATCH")
        block_time = await sub.block_time()
        if block_time != float(profile["nominal_block_seconds"]):
            raise PublicationFailure("PROFILE_BLOCK_TIME_MISMATCH")
        isolation.update(
            genesis=genesis,
            spec_version=version,
            block_time_seconds=block_time,
            finalized_hash=finalized,
            genesis_binding=(
                "DISCOVERY_ONLY_NO_SIGNING" if expected is None else "MANIFEST_MATCH"
            ),
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
        self._transport_hooks = None
        self._submission_lock = asyncio.Lock()
        self._transport_generation = 0
        self._transport_ready = False
        self.transport_events = []
        self.profile_name, self.profile = runtime_profile()

    def _require_no_ambiguous_submission(self):
        if any(
            operation.get("state") == "AMBIGUOUS_OR_UNAVAILABLE"
            for operation in self.operations
        ):
            raise PublicationFailure("OUTSTANDING_SUBMISSION_REQUIRES_RECONCILIATION")

    def _require_exclusive_transport_ready(self):
        if not self._submission_lock.locked():
            raise PublicationFailure("ACCOUNT_SUBMISSION_SEQUENCE_NOT_EXCLUSIVE")
        if not self._transport_ready or self._transport_generation < 1:
            raise PublicationFailure("SDK_TRANSPORT_HANDOVER_INCOMPLETE")

    async def _replace_sdk_transport(self, record=None):
        """Open a verified public SDK transport before retiring the old one."""
        import bittensor as bt

        if self.context is None or self._transport_hooks is None:
            raise PublicationFailure("LOCALNET_TRANSPORT_CONTEXT_REQUIRED")
        previous = self.sub
        if previous is not None:
            self._require_exclusive_transport_ready()
            self._require_no_ambiguous_submission()
        previous_generation = self._transport_generation or None
        replacement_generation = self._transport_generation + 1
        event = {
            "previous_generation": previous_generation,
            "replacement_generation": replacement_generation,
            "account_submission_sequence": "EXCLUSIVE",
            "state": "CONNECTING_REPLACEMENT",
        }
        self.transport_events.append(event)
        if record is not None:
            record["transport_handover"] = event
        self._transport_ready = False
        self.save()
        sub = journaled_substrate(
            self.context,
            self._transport_hooks["before_sign"],
            self._transport_hooks["before_dispatch"],
            after_inner_sign=self._transport_hooks["after_inner_sign"],
            after_shield_key=self._transport_hooks["after_shield_key"],
            before_signed_extrinsic=self._transport_hooks["before_signed_extrinsic"],
        )
        try:
            await sub.connect()
            observed_endpoint = sub.endpoint
            observed_genesis = hash256(await sub.block_hash(0))
            observed_spec = await sub.spec_version()
            observed_block_time = await sub.block_time()
        except Exception:
            await sub.close()
            event["state"] = "REPLACEMENT_CONNECTION_REQUIRES_RECONCILIATION"
            self.save()
            raise
        event["replacement_identity"] = {
            "endpoint": observed_endpoint,
            "genesis_hash": observed_genesis,
            "spec_version": observed_spec,
            "runtime_profile": self.profile_name,
            "runtime_binary": self.profile["binary_path"],
            "block_time_seconds": observed_block_time,
        }
        if (
            observed_endpoint != self.context.endpoint
            or observed_genesis != self.context.genesis_hash
            or observed_spec != 445
            or observed_block_time != float(self.profile["nominal_block_seconds"])
        ):
            await sub.close()
            event["state"] = "REPLACEMENT_IDENTITY_REJECTED"
            self.save()
            raise PublicationFailure("REPLACEMENT_TRANSPORT_IDENTITY_MISMATCH")
        event["replacement_verified_before_previous_close"] = previous is not None
        event["previous_transport_closed"] = previous is None
        self.save()
        client = bt.Client(
            self.context.endpoint,
            substrate=sub,
            policy=bt.Policy(allowed_netuids=[2]),
        )
        if previous is not None:
            try:
                await previous.close()
            except Exception:  # noqa: BLE001 - ambiguous close must fail closed
                await sub.close()
                event["state"] = "PREVIOUS_CLOSE_REQUIRES_RECONCILIATION"
                self.save()
                raise PublicationFailure(
                    "PREVIOUS_TRANSPORT_CLOSE_REQUIRES_RECONCILIATION"
                ) from None
            event["previous_transport_closed"] = True
            self.save()
        self.sub, self.client = sub, client
        self._transport_generation = replacement_generation
        self._transport_ready = True
        event["state"] = "REPLACEMENT_ACTIVE_AFTER_PREVIOUS_CLOSE"
        self.save()

    async def _refresh_after_shielded_inner(self, record):
        """Reopen the supported SDK after its outer/inner nonce transition."""
        self._require_exclusive_transport_ready()
        self._require_no_ambiguous_submission()
        if record.get("state") not in ("FINALIZED", "FINALIZED_RECONCILED"):
            raise PublicationFailure("SHIELDED_SUBMISSION_REQUIRES_RECONCILIATION")
        finalized_block_hash = hash256(record["block_hash"])
        account_identity = self.signer
        account = await self.sub.query(
            "System", "Account", [account_identity], block_hash=finalized_block_hash
        )
        observed = account.get("nonce") if type(account) is dict else None
        signed = record.get("signed_extrinsics", {})
        inner = signed.get("inner", {}).get("nonce")
        carrier = signed.get("carrier", {}).get("nonce")
        if (
            type(observed) is not int
            or type(inner) is not int
            or type(carrier) is not int
            or inner != carrier + 1
            or observed != inner + 1
        ):
            raise PublicationFailure("SHIELDED_NONCE_TRANSITION_MISMATCH")
        record["nonce_transition"] = {
            "carrier_nonce": carrier,
            "inner_nonce": inner,
            "finalized_account_next_nonce": observed,
            "account_identity": account_identity,
            "finalized_block_hash": finalized_block_hash,
            "checked_transport_generation": self._transport_generation,
            "sdk_transport": "REOPEN_REQUIRED_AFTER_EXPLICIT_OUTER_NONCE_PIN",
        }
        self.save()
        await self._replace_sdk_transport(record)
        record["nonce_transition"][
            "sdk_transport"
        ] = "REOPENED_THROUGH_SUPPORTED_PUBLIC_CLIENT"
        record["nonce_transition"][
            "replacement_transport_generation"
        ] = self._transport_generation
        self.save()

    async def start(self):
        from bittensor.keyfiles import Keypair

        if (self.directory / "setup.json").exists():
            raise PublicationFailure("EXISTING_SETUP_REQUIRES_RECONCILIATION")
        observed = json.loads((self.directory / "isolation.json").read_text())
        actual = inspect_isolation(self.container, self.profile_name)
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
            self._require_exclusive_transport_ready()
            await self.verify()
            if call.spec_version != 445 or signer != self.signer:
                raise PublicationFailure("SETUP_SIGNING_CONTEXT_CHANGED")

        async def before_dispatch(tx_hash):
            self._require_exclusive_transport_ready()
            self.operations[-1]["transaction"] = tx_hash
            self.save()

        async def after_inner_sign(tx_hash):
            self.operations[-1]["inner_transaction"] = tx_hash
            self.save()

        async def after_shield_key(digest, length, key_context):
            authors = [
                public_identity(value) for value in key_context["associated_authors"]
            ]
            query = {
                "digest": digest,
                "length": length,
                "queried_at_block": key_context["block"],
                "queried_at_hash": key_context["block_hash"],
                "expires_at_exclusive": key_context["expires_at_exclusive"],
                "associated_authors": authors,
            }
            self.operations[-1].setdefault("shield_key_queries", []).append(query)
            if digest is not None:
                if len(authors) != 1:
                    raise PublicationFailure(
                        "SHIELD_KEY_AUTHOR_ASSOCIATION_UNAVAILABLE"
                    )
                if (
                    type(query["expires_at_exclusive"]) is not int
                    or query["expires_at_exclusive"] <= query["queried_at_block"]
                ):
                    raise PublicationFailure("SHIELD_KEY_EXPIRY_INVALID")
                self.operations[-1]["shield_key"] = query
            self.save()

        async def before_signed_extrinsic(kind, kwargs):
            if "shield_era_blocks" not in self.operations[-1]:
                if kind != "carrier" or kwargs.get("nonce") is not None:
                    raise PublicationFailure("EXPLICIT_ORDINARY_NONCE_PROHIBITED")
                self.operations[-1]["sdk_nonce_observation"][
                    "nonce_argument"
                ] = "OMITTED_OR_NONE"
                self.save()
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

        self._transport_hooks = {
            "before_sign": before_sign,
            "before_dispatch": before_dispatch,
            "after_inner_sign": after_inner_sign,
            "after_shield_key": after_shield_key,
            "before_signed_extrinsic": before_signed_extrinsic,
        }
        await self._replace_sdk_transport()
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
                "schema": "carbon.disposable.setup.v2",
                "context": asdict(self.context),
                "runtime_profile": self.profile_name,
                "runtime_binary": self.profile["binary_path"],
                "roles": {name: pair.ss58_address for name, pair in self.roles.items()},
                "operations": self.operations,
                "transport_events": self.transport_events,
                "treasury": None,
            },
        )

    async def execute(self, label, intent, role="owner"):
        async with self._submission_lock:
            self._require_no_ambiguous_submission()
            return await self._execute_locked(label, intent, role)

    async def _execute_locked(self, label, intent, role="owner"):
        if any(op["label"] == label for op in self.operations):
            raise PublicationFailure("SETUP_REPLAY_REQUIRES_RECONCILIATION")
        await self.verify()
        self.signer = self.roles[role].ss58_address
        async with aclosing(self.client.blocks(finalized=True)) as headers:
            start = (await anext(headers)).number
        start_hash = hash256(await self.sub.block_hash(start))
        record = {
            "label": label,
            "state": "PREPARED",
            "start_finalized_block": start,
            "start_finalized_block_hash": start_hash,
            "account_identity": self.signer,
            "transport_generation": self._transport_generation,
        }
        if intent.mev_shield_required:
            record["shield_era_blocks"] = self.shield_era_period
            record["block_aware_deadline"] = {
                "mortality_period_blocks": self.shield_era_period,
                "sdk_inner_scan_blocks_after_carrier": self.shield_era_period,
                "maximum_scan_block": start + 2 * self.shield_era_period,
            }
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
                account = await self.sub.query(
                    "System", "Account", [self.signer], block_hash=start_hash
                )
                observed_nonce = account.get("nonce") if type(account) is dict else None
                if type(observed_nonce) is not int or observed_nonce < 0:
                    raise PublicationFailure("SDK_NONCE_READBACK_INVALID")
                record["sdk_nonce_observation"] = {
                    "account_identity": self.signer,
                    "transport_generation": self._transport_generation,
                    "finalized_block_before_signing": start,
                    "finalized_block_hash_before_signing": start_hash,
                    "finalized_account_nonce_before_signing": observed_nonce,
                    "selection_source": (
                        "PINNED_SDK_11_1_0_OMITTED_NONCE_PLUS_FINALIZED_READBACK"
                    ),
                    "nonce_supplied_by_carbon": False,
                }
                self.save()
                operation = self.client.execute(
                    intent,
                    self.roles[role],
                    retries=0,
                    wait_for_inclusion=True,
                    wait_for_finalization=True,
                )
            operation_wall_seconds = max(
                90,
                int(float(self.profile["nominal_block_seconds"]) * 12),
            )
            record["operation_wall_seconds"] = operation_wall_seconds
            self.save()
            result = await asyncio.wait_for(operation, operation_wall_seconds)
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
            if result.success and "sdk_nonce_observation" in record:
                finalized_hash = hash256(result.block_hash)
                account = await self.sub.query(
                    "System", "Account", [self.signer], block_hash=finalized_hash
                )
                finalized_nonce = (
                    account.get("nonce") if type(account) is dict else None
                )
                expected_nonce = (
                    record["sdk_nonce_observation"][
                        "finalized_account_nonce_before_signing"
                    ]
                    + 1
                )
                if (
                    type(finalized_nonce) is not int
                    or finalized_nonce != expected_nonce
                ):
                    raise PublicationFailure("SDK_NONCE_FINALIZED_READBACK_MISMATCH")
                record["sdk_nonce_observation"].update(
                    sdk_selected_nonce=finalized_nonce - 1,
                    sdk_selected_nonce_evidence=(
                        "EXCLUSIVE_SEQUENCE_AND_FINALIZED_ACCOUNT_INCREMENT"
                    ),
                    finalized_block_hash=finalized_hash,
                    finalized_account_next_nonce=finalized_nonce,
                    outcome="FINALIZED_INCREMENT_CONFIRMED",
                )
            self.save()
            if not result.success and "inner_transaction" in record:
                result = await self.reconcile_inner(record, result)
            if "inner_transaction" in record:
                await self.observe_shield_outcome(record)
            if not result.success:
                raise PublicationFailure("LOCAL_SETUP_REJECTED:" + label)
            if "inner_transaction" in record:
                await self._refresh_after_shielded_inner(record)
            return result
        except Exception:
            if record["state"] == "PREPARED":
                record["state"] = "AMBIGUOUS_OR_UNAVAILABLE"
            self.save()
            raise

    async def observe_shield_outcome(self, record):
        """Classify key rotation, ciphertext acceptance and inner execution."""
        await self.verify()
        start = record["start_finalized_block"]
        end = min(
            (await self.sub.block_number()),
            record["block_aware_deadline"]["maximum_scan_block"],
        )
        receipts = {}
        for block in range(start, end + 1):
            block_hash = await self.sub.block_hash(block)
            for kind in ("transaction", "inner_transaction"):
                if kind in receipts:
                    continue
                found = await self.sub.find_extrinsic(record[kind], block_hash)
                if found is not None:
                    receipts[kind] = {
                        "block": block,
                        "block_hash": hash256(block_hash),
                        "success": found.success,
                        "extrinsic_id": found.extrinsic_id,
                    }
        record["diagnostic_scan"] = {
            "from_finalized_block": start,
            "through_block": end,
            "receipts": receipts,
        }
        carrier = receipts.get("transaction")
        inner = receipts.get("inner_transaction")
        if carrier is None:
            outcome = "CARRIER_NOT_FINALIZED"
        elif not carrier["success"]:
            outcome = "CARRIER_REJECTED_CIPHERTEXT_NOT_ACCEPTED"
        elif inner is None:
            outcome = "CARRIER_ACCEPTED_AUTHENTICATED_UNSHIELD_NOT_OBSERVED"
        elif not inner["success"]:
            outcome = "CARRIER_ACCEPTED_INNER_DISPATCH_REJECTED"
        else:
            outcome = "CARRIER_ACCEPTED_UNSHIELDED_INNER_FINALIZED"
        record["shield_outcome"] = outcome

        key = record.get("shield_key")
        if key is not None and carrier is not None:
            at_hash = carrier["block_hash"]
            positions = {}
            for storage in ("CurrentKey", "PendingKey", "NextKey"):
                positions[storage] = public_key_digest(
                    await self.sub.query("MevShield", storage, block_hash=at_hash)
                )
            authors = []
            for author, author_key in await self.sub.query_map(
                "MevShield", "AuthorKeys", block_hash=at_hash
            ):
                if public_key_digest(author_key) == key["digest"]:
                    authors.append(public_identity(author))
            record["key_rotation_context"] = {
                "carrier_block": carrier["block"],
                "carrier_block_hash": at_hash,
                "queried_key_positions": [
                    storage
                    for storage, digest in positions.items()
                    if digest == key["digest"]
                ],
                "associated_authors_at_carrier": authors,
                "query_expiry_exclusive": key["expires_at_exclusive"],
            }
        self.save()

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

    async def configure_registration_diagnostic(self):
        """Only the source-required state for one authenticated burn registration."""
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
        await self.execute("registration", root_setting("registration", self.verify))

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
            self._transport_ready = False
            if self.transport_events:
                self.transport_events[-1]["closed_at_session_end"] = True
                self.save()


async def registration_diagnostic(container, directory):
    """One no-retry standard-runtime registration through the authenticated SDK."""
    import bittensor as bt

    profile_name, profile = runtime_profile()
    if profile_name != "standard" or profile["expected_genesis"] is None:
        raise PublicationFailure("BOUND_STANDARD_PROFILE_REQUIRED")
    directory = Path(directory)
    started = time.monotonic()
    report = {
        "schema": "carbon.net5r.registration-diagnostic.v1",
        "hypothesis": (
            "The pinned standard runtime may preserve authenticated shield key "
            "association where the fast runtime exhibited an intermittent mismatch."
        ),
        "comparison_only": True,
        "runtime_profile": profile_name,
        "runtime_binary": profile["binary_path"],
        "runtime_features": profile["cargo_features"],
        "expected_genesis": profile["expected_genesis"],
        "retry_budget": 0,
        "public_network_actions": 0,
        "g2": "NOT_READY",
        "outcome": "PREPARED",
    }
    write_evidence(directory / "registration-diagnostic.json", report)
    session = LocalnetSession(container, directory)
    try:
        await session.start()
        await session.configure_registration_diagnostic()
        report["setup"] = "MINIMAL_SUBNET_AND_REGISTRATION_GATE_ONLY"
        write_evidence(directory / "registration-diagnostic.json", report)
        await session.execute(
            "diagnostic-register-miner",
            bt.BurnedRegister(
                netuid=2, hotkey_ss58=session.roles["miner"].ss58_address
            ),
            "miner",
        )
        operation = session.operations[-1]
        head = await session.sub.block_number()
        block_hash = await session.sub.block_hash(head)
        uid = await session.sub.query(
            "SubtensorModule",
            "Uids",
            [2, session.roles["miner"].ss58_address],
            block_hash=block_hash,
        )
        owner = await session.sub.query(
            "SubtensorModule",
            "Owner",
            [session.roles["miner"].ss58_address],
            block_hash=block_hash,
        )
        if type(uid) is not int or owner != session.roles["miner"].ss58_address:
            raise PublicationFailure("REGISTRATION_ASSOCIATION_MISMATCH")
        report.update(
            outcome="AUTHENTICATED_REGISTRATION_FINALIZED",
            shield_outcome=operation["shield_outcome"],
            operation_label=operation["label"],
            registration_association={
                "observed_at_block": head,
                "observed_at_hash": hash256(block_hash),
                "hotkey": session.roles["miner"].ss58_address,
                "coldkey": owner,
                "uid": uid,
            },
            elapsed_wall_seconds=round(time.monotonic() - started, 3),
        )
        write_evidence(directory / "registration-diagnostic.json", report)
        return 0
    except Exception as error:
        report.update(
            outcome="FAILED_NO_RETRY",
            failure_type=type(error).__name__,
            failure_code=(
                str(error)
                if type(error) is PublicationFailure
                else "SEE_PRIVATE_OPERATOR_DIAGNOSTIC"
            ),
            elapsed_wall_seconds=round(time.monotonic() - started, 3),
        )
        if session.operations:
            last = session.operations[-1]
            report["last_operation"] = {
                key: last[key]
                for key in (
                    "label",
                    "state",
                    "block_aware_deadline",
                    "shield_key",
                    "transaction",
                    "inner_transaction",
                    "diagnostic_scan",
                    "key_rotation_context",
                    "shield_outcome",
                )
                if key in last
            }
        write_evidence(directory / "registration-diagnostic.json", report)
        raise
    finally:
        await session.close()


if __name__ == "__main__":
    import sys

    from carbon.chain.localnet import run as owned_run

    if sys.argv[1:] == ["inspect-image"]:
        inspect_image_profile(
            os.environ["CARBON_LOCALNET_IMAGE"],
            os.environ["CARBON_LOCALNET_PROFILE"],
            os.environ["CARBON_LOCALNET_EVIDENCE"],
            allow_unbound=os.environ["CARBON_LOCALNET_MODE"] == "inspect",
        )
        raise SystemExit(0)
    if sys.argv[1:] != ["run"]:
        raise SystemExit("Only explicit disposable image inspection/run is supported.")
    raise SystemExit(
        asyncio.run(
            owned_run(
                os.environ["CARBON_LOCALNET_CONTAINER"],
                os.environ["CARBON_LOCALNET_EVIDENCE"],
            )
        )
    )
