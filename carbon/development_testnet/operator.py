"""Read-only preflight for the bounded public/synthetic DEVELOPMENT testnet."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import platform
import shutil
import subprocess
from dataclasses import dataclass
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

from carbon.chain import ChainContext
from carbon.chain.models import identifier
from carbon.chain.sdk import SDK_VERSION
from carbon.chain.sdk_weights import BittensorPublicationBackend

from .model import (
    MAX_LOCAL_EVIDENCE_BYTES,
    PROFILE_ID,
    DevelopmentTestnetFailure,
    DevelopmentTestnetProfile,
    DevelopmentTransactionAuthorization,
)

SCHEMA = "carbon.development-testnet.operator.v1"
STAGE = "PUBLIC_TESTNET_DEVELOPMENT"
DEFAULT_ENDPOINT = "wss://test.finney.opentensor.ai:443"
TESTNET_GENESIS = "0x8f9cf856bf558a14440e75569c9e58594757048d7b3a84b5d25f6bd978263105"
WORKER_PROFILE = "carbon.c03.linux-x86_64-cpu.development.v1"
MINIMUM_HOST_MEMORY_BYTES = 6 * 1024**3
MINIMUM_FREE_DISK_BYTES = 8 * 1024**3
MAX_CONFIG_BYTES = 64 * 1024


@dataclass(frozen=True, slots=True)
class OperatorConfig:
    endpoint: str
    chain_id: str
    genesis_hash: str
    netuid: int | None
    expected_runtime_spec: int
    publisher_hotkey: str
    publisher_coldkey: str
    wallet_name: str
    wallet_hotkey_name: str
    worker_image_digest: str
    resource_policy_digest: str
    retention_root: Path
    export_root: Path
    max_retained_bytes: int
    transaction_authorization: DevelopmentTransactionAuthorization | None

    @property
    def context(self) -> ChainContext | None:
        if self.netuid is None:
            return None
        return ChainContext(
            "testnet",
            self.endpoint,
            self.chain_id,
            self.genesis_hash,
            self.netuid,
        )


def _regular_json(path: Path) -> dict[str, object]:
    if not isinstance(path, Path) or not path.is_absolute() or path.is_symlink():
        raise DevelopmentTestnetFailure("ABSOLUTE_REGULAR_CONFIG_REQUIRED")
    try:
        if not path.is_file() or path.stat().st_size > MAX_CONFIG_BYTES:
            raise DevelopmentTestnetFailure("BOUNDED_REGULAR_CONFIG_REQUIRED")
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        raise DevelopmentTestnetFailure("INVALID_OPERATOR_CONFIG") from None
    if type(value) is not dict:
        raise DevelopmentTestnetFailure("INVALID_OPERATOR_CONFIG")
    return value


def _digest(value: object) -> str:
    if (
        type(value) is not str
        or not value.startswith("sha256:")
        or len(value) != 71
        or any(character not in "0123456789abcdef" for character in value[7:])
    ):
        raise DevelopmentTestnetFailure("EXACT_DIGEST_REQUIRED")
    return value


def _path(config_path: Path, value: object) -> Path:
    if type(value) is not str or not value:
        raise DevelopmentTestnetFailure("EXPLICIT_OPERATOR_PATH_REQUIRED")
    path = Path(value)
    result = (path if path.is_absolute() else config_path.parent / path).absolute()
    if result.exists() and result.is_symlink():
        raise DevelopmentTestnetFailure("OPERATOR_PATH_SYMLINK_REJECTED")
    return result


def load_config(path: Path) -> OperatorConfig:
    raw = _regular_json(path)
    expected = {
        "schema",
        "profile_id",
        "stage",
        "context",
        "expected_runtime_spec",
        "publisher",
        "wallet",
        "execution",
        "retention",
        "transaction_authorization",
    }
    if set(raw) != expected:
        raise DevelopmentTestnetFailure("EXACT_OPERATOR_CONFIG_REQUIRED")
    context = raw["context"]
    publisher = raw["publisher"]
    wallet = raw["wallet"]
    execution = raw["execution"]
    retention = raw["retention"]
    if (
        raw["schema"] != SCHEMA
        or raw["profile_id"] != PROFILE_ID
        or raw["stage"] != STAGE
        or type(context) is not dict
        or set(context) != {"network", "endpoint", "chain_id", "genesis_hash", "netuid"}
        or context["network"] != "testnet"
        or context["endpoint"] != DEFAULT_ENDPOINT
        or context["chain_id"] != "bittensor-official-test"
        or context["genesis_hash"] != TESTNET_GENESIS
        or (
            context["netuid"] is not None
            and (type(context["netuid"]) is not int or context["netuid"] <= 0)
        )
        or type(raw["expected_runtime_spec"]) is not int
        or raw["expected_runtime_spec"] <= 0
        or type(publisher) is not dict
        or set(publisher) != {"hotkey", "coldkey"}
        or type(wallet) is not dict
        or set(wallet) != {"name", "hotkey_name"}
        or type(execution) is not dict
        or set(execution)
        != {"worker_profile", "worker_image_digest", "resource_policy_digest"}
        or execution["worker_profile"] != WORKER_PROFILE
        or type(retention) is not dict
        or set(retention)
        != {"root", "export_root", "max_retained_bytes", "host_loss_recoverable"}
        or type(retention["max_retained_bytes"]) is not int
        or not 0 < retention["max_retained_bytes"] <= MAX_LOCAL_EVIDENCE_BYTES
        or retention["host_loss_recoverable"] is not False
    ):
        raise DevelopmentTestnetFailure("INVALID_OPERATOR_CONFIG")
    for value in (
        publisher["hotkey"],
        publisher["coldkey"],
        wallet["name"],
        wallet["hotkey_name"],
    ):
        identifier(value)
    authorization = None
    if raw["transaction_authorization"] is not None:
        if (
            context["netuid"] is None
            or type(raw["transaction_authorization"]) is not dict
        ):
            raise DevelopmentTestnetFailure("CONTEXT_REQUIRED_FOR_AUTHORIZATION")
        authorization = DevelopmentTransactionAuthorization(
            context=ChainContext(
                "testnet",
                context["endpoint"],
                context["chain_id"],
                context["genesis_hash"],
                context["netuid"],
            ),
            **raw["transaction_authorization"],
        )
        authorization.validate(
            DevelopmentTestnetProfile(
                authorization.context, raw["expected_runtime_spec"]
            ),
            publisher["hotkey"],
        )
    return OperatorConfig(
        context["endpoint"],
        context["chain_id"],
        context["genesis_hash"],
        context["netuid"],
        raw["expected_runtime_spec"],
        publisher["hotkey"],
        publisher["coldkey"],
        wallet["name"],
        wallet["hotkey_name"],
        _digest(execution["worker_image_digest"]),
        _digest(execution["resource_policy_digest"]),
        _path(path, retention["root"]),
        _path(path, retention["export_root"]),
        retention["max_retained_bytes"],
        authorization,
    )


def _host_memory() -> int | None:
    try:
        return int(os.sysconf("SC_PAGE_SIZE")) * int(os.sysconf("SC_PHYS_PAGES"))
    except (OSError, ValueError):
        return None


def _nearest_existing(path: Path) -> Path:
    current = path
    while not current.exists() and current != current.parent:
        current = current.parent
    return current


def _docker() -> tuple[bool, bool]:
    present = shutil.which("docker") is not None
    if not present:
        return False, False
    try:
        result = subprocess.run(
            ["docker", "info", "--format", "{{.ServerVersion}}"],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=5,
            check=False,
        )
        return True, result.returncode == 0
    except (OSError, subprocess.SubprocessError):
        return True, False


async def doctor(config: OperatorConfig, *, online: bool) -> dict[str, object]:
    memory = _host_memory()
    free_disk = shutil.disk_usage(_nearest_existing(config.retention_root)).free
    docker_cli, docker_daemon = _docker()
    system = platform.system()
    machine = platform.machine()
    try:
        sdk = version("bittensor")
    except PackageNotFoundError:
        sdk = None
    host_eligible = (
        system == "Linux"
        and machine == "x86_64"
        and docker_daemon
        and memory is not None
        and memory >= MINIMUM_HOST_MEMORY_BYTES
        and free_disk >= MINIMUM_FREE_DISK_BYTES
    )
    missing = []
    if config.netuid is None:
        missing.append("context.netuid")
    if config.transaction_authorization is None:
        missing.append("transaction_authorization")
    chain: dict[str, object] = {
        "checked": False,
        "endpoint": config.endpoint,
        "genesis": config.genesis_hash,
        "registered": False,
        "uid": None,
        "validator_permit": None,
        "sufficient_stake": None,
        "runtime_spec": None,
        "finalized_block": None,
        "reason": "ONLINE_CHECK_NOT_REQUESTED",
    }
    if online and config.context is not None and sdk == SDK_VERSION:
        backend = BittensorPublicationBackend(
            config.context,
            config.publisher_hotkey,
            None,
            network="testnet",
        )
        try:
            snapshot, capabilities = await backend.observe()
            profile = DevelopmentTestnetProfile(
                config.context, config.expected_runtime_spec
            )
            capabilities.validate(
                snapshot,
                config.publisher_hotkey,
                network="testnet",
                spec_version=profile.expected_runtime_spec,
            )
            member = snapshot.resolve(config.publisher_hotkey)
            chain.update(
                checked=True,
                registered=True,
                uid=member.uid,
                validator_permit=capabilities.validator_permit,
                sufficient_stake=capabilities.sufficient_stake,
                runtime_spec=capabilities.spec_version,
                finalized_block=snapshot.finalized_block,
                reason="ELIGIBLE_RUNTIME_AND_IDENTITY_OBSERVED",
            )
        except Exception as error:  # noqa: BLE001 - publish stays disabled.
            reason = str(error)
            allowed = {
                "PUBLISHER_NOT_REGISTERED",
                "INSUFFICIENT_STAKE",
                "VALIDATOR_PERMIT_REQUIRED",
                "UNSUPPORTED_RUNTIME_VERSION",
            }
            chain["reason"] = (
                reason if reason in allowed else "CHAIN_OBSERVATION_UNAVAILABLE"
            )
        finally:
            await backend.close()
    elif online and sdk != SDK_VERSION:
        chain["reason"] = "PINNED_BITTENSOR_SDK_UNAVAILABLE"
    elif online:
        chain["reason"] = "NETUID_REQUIRED"
    transaction_ready = (
        config.transaction_authorization is not None
        and chain["checked"] is True
        and chain["registered"] is True
        and chain["sufficient_stake"] is True
        and config.transaction_authorization.valid_from_block
        <= chain["finalized_block"]
        <= config.transaction_authorization.valid_through_block
    )
    return {
        "schema": "carbon.development-testnet.doctor-report.v1",
        "profile": PROFILE_ID,
        "configuration": (
            "VALID_WITH_MISSING_EXTERNAL_INPUTS" if missing else "VALID_COMPLETE"
        ),
        "missing_external_inputs": missing,
        "host": {
            "system": system,
            "architecture": machine,
            "memory_bytes": memory,
            "free_disk_bytes": free_disk,
            "docker_cli": docker_cli,
            "docker_daemon": docker_daemon,
            "linux_isolation_host_eligible": host_eligible,
        },
        "sdk": {"required": SDK_VERSION, "installed": sdk, "exact": sdk == SDK_VERSION},
        "chain": chain,
        "transaction_ready": transaction_ready,
        "writes_performed": False,
        "protected_or_official_eligible": False,
    }


def main(arguments: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("validate", "doctor"))
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--online", action="store_true")
    args = parser.parse_args(arguments)
    try:
        config = load_config(args.config.absolute())
        if args.command == "validate":
            result = {
                "schema": "carbon.development-testnet.validate-report.v1",
                "configuration": (
                    "VALID_WITH_MISSING_EXTERNAL_INPUTS"
                    if config.netuid is None or config.transaction_authorization is None
                    else "VALID_COMPLETE"
                ),
                "chain_checked": False,
                "wallet_or_secret_read": False,
                "writes_performed": False,
            }
        else:
            result = asyncio.run(doctor(config, online=args.online))
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0
    except Exception:  # noqa: BLE001 - no provider messages or input echoed.
        print(
            json.dumps(
                {
                    "schema": "carbon.development-testnet.operator-failure.v1",
                    "status": "FAILED_CLOSED",
                    "writes_performed": False,
                },
                sort_keys=True,
            )
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
