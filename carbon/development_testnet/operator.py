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
from carbon.chain.publication import PublicationFailure
from carbon.chain.sdk import SDK_VERSION
from carbon.chain.sdk_weights import BittensorPublicationBackend, open_external_wallet

from .execution import (
    execute_resume,
    execute_run,
    execution_status,
    load_source_handoff,
)
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
        "endpoint_genesis_compatible": None,
        "runtime_compatible": None,
        "registered": None,
        "uid": None,
        "publisher_coldkey": None,
        "configured_coldkey_matches": None,
        "subnet_owner_hotkey": None,
        "subnet_owner_coldkey": None,
        "owner_exception_applies": None,
        "burn_recipient_uid": None,
        "burn_recipient_hotkey": None,
        "burn_recipient_coldkey": None,
        "burn_mode": None,
        "validator_permit": None,
        "sufficient_stake": None,
        "runtime_spec": None,
        "mechanism_count": None,
        "mechanism_id": 0,
        "publication_method": None,
        "rate_limit_blocks": None,
        "last_update_block": None,
        "next_rate_eligible_block": None,
        "pending_commitments": None,
        "finalized_block": None,
        "publication_capability_eligible": None,
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
            member = snapshot.resolve(config.publisher_hotkey)
            sink = snapshot.resolve(capabilities.owner_hotkey)
            chain.update(
                checked=True,
                endpoint_genesis_compatible=True,
                runtime_compatible=(
                    capabilities.spec_version == profile.expected_runtime_spec
                ),
                registered=member is not None,
                uid=None if member is None else member.uid,
                publisher_coldkey=None if member is None else member.coldkey,
                configured_coldkey_matches=(
                    None
                    if member is None
                    else member.coldkey == config.publisher_coldkey
                ),
                subnet_owner_hotkey=capabilities.owner_hotkey,
                subnet_owner_coldkey=capabilities.owner_coldkey,
                owner_exception_applies=(
                    config.publisher_hotkey == capabilities.owner_hotkey
                ),
                burn_recipient_uid=None if sink is None else sink.uid,
                burn_recipient_hotkey=capabilities.owner_hotkey,
                burn_recipient_coldkey=(None if sink is None else sink.coldkey),
                burn_mode=capabilities.burn_mode,
                validator_permit=capabilities.validator_permit,
                sufficient_stake=capabilities.sufficient_stake,
                runtime_spec=capabilities.spec_version,
                mechanism_count=capabilities.mechanism_count,
                publication_method=(
                    "TIMELOCKED_COMMIT_REVEAL"
                    if capabilities.commit_reveal
                    else "SET_MECHANISM_WEIGHTS"
                ),
                rate_limit_blocks=capabilities.rate_limit,
                last_update_block=capabilities.last_update,
                next_rate_eligible_block=(
                    capabilities.last_update + capabilities.rate_limit
                    if capabilities.last_update
                    else snapshot.finalized_block
                ),
                pending_commitments=capabilities.pending_commits,
                finalized_block=snapshot.finalized_block,
            )
            try:
                capabilities.validate(
                    snapshot,
                    config.publisher_hotkey,
                    network="testnet",
                    spec_version=profile.expected_runtime_spec,
                )
            except Exception as error:  # noqa: BLE001 - stable allow-list below.
                reason = str(error)
                allowed = {
                    "EXISTING_UNREVEALED_COMMITMENTS",
                    "INSUFFICIENT_PUBLISHER_STAKE",
                    "PUBLICATION_RATE_LIMITED",
                    "REGISTERED_RUNTIME_OWNER_SINK_REQUIRED",
                    "UNSUPPORTED_MECHANISM_CONFIGURATION",
                    "UNSUPPORTED_RUNTIME_VERSION",
                    "VALIDATOR_PERMIT_REQUIRED",
                    "VERIFIED_BURN_MODE_REQUIRED",
                }
                chain.update(
                    publication_capability_eligible=False,
                    reason=(
                        reason
                        if reason in allowed
                        else "PUBLICATION_CAPABILITY_OBSERVATION_INVALID"
                    ),
                )
            else:
                chain.update(
                    publication_capability_eligible=True,
                    reason="ELIGIBLE_RUNTIME_AND_IDENTITY_OBSERVED",
                )
        except Exception as error:  # noqa: BLE001 - publish stays disabled.
            reason = str(error)
            if reason == "PUBLISHER_NOT_REGISTERED":
                chain.update(
                    checked=True,
                    endpoint_genesis_compatible=True,
                    registered=False,
                    publication_capability_eligible=False,
                    reason=reason,
                )
            else:
                chain["reason"] = "CHAIN_OBSERVATION_UNAVAILABLE"
        finally:
            await backend.close()
    elif online and sdk != SDK_VERSION:
        chain["reason"] = "PINNED_BITTENSOR_SDK_UNAVAILABLE"
    elif online:
        chain["reason"] = "NETUID_REQUIRED"
    authorization = {
        "configured": config.transaction_authorization is not None,
        "context_matches": None,
        "valid_at_observed_block": None,
        "valid_from_block": None,
        "valid_through_block": None,
        "max_dispatches": None,
        "max_spend_tao": None,
    }
    if config.transaction_authorization is not None:
        approved = config.transaction_authorization
        authorization.update(
            context_matches=(
                approved.context == config.context
                and approved.publisher_hotkey == config.publisher_hotkey
                and approved.expected_runtime_spec == config.expected_runtime_spec
            ),
            valid_from_block=approved.valid_from_block,
            valid_through_block=approved.valid_through_block,
            max_dispatches=approved.max_dispatches,
            max_spend_tao=approved.max_spend_tao,
        )
        if chain["finalized_block"] is not None:
            authorization["valid_at_observed_block"] = (
                approved.valid_from_block
                <= chain["finalized_block"]
                <= approved.valid_through_block
            )
    chain_transaction_ready = (
        config.transaction_authorization is not None
        and chain["checked"] is True
        and chain["registered"] is True
        and chain["configured_coldkey_matches"] is True
        and chain["publication_capability_eligible"] is True
        and authorization["context_matches"] is True
        and authorization["valid_at_observed_block"] is True
    )
    full_execution_prerequisites_ready = bool(
        host_eligible and sdk == SDK_VERSION and chain_transaction_ready
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
        "authorization": authorization,
        "chain_transaction_ready": chain_transaction_ready,
        "full_execution_prerequisites_ready": full_execution_prerequisites_ready,
        # Compatibility alias retained prospectively; it means chain-only readiness.
        "transaction_ready": chain_transaction_ready,
        "writes_performed": False,
        "protected_or_official_eligible": False,
    }


def _wallet(config: OperatorConfig):
    """Open the configured external wallet only after every public preflight gate."""

    try:
        return open_external_wallet(
            config.wallet_name,
            config.wallet_hotkey_name,
            config.publisher_hotkey,
            config.publisher_coldkey,
        )
    except PublicationFailure as error:
        reason = str(error)
        if reason == "WALLET_IDENTITY_MISMATCH":
            raise DevelopmentTestnetFailure(reason) from None
        raise DevelopmentTestnetFailure("EXTERNAL_WALLET_UNAVAILABLE") from None


async def _run(config: OperatorConfig, source_path: Path) -> dict[str, object]:
    if config.context is None or config.transaction_authorization is None:
        raise DevelopmentTestnetFailure("COMPLETE_AUTHORIZED_CONTEXT_REQUIRED")
    report = await doctor(config, online=True)
    if report["full_execution_prerequisites_ready"] is not True:
        raise DevelopmentTestnetFailure("EXECUTION_PREREQUISITES_NOT_READY")
    source = load_source_handoff(
        source_path,
        retention_root=config.retention_root,
        export_root=config.export_root,
    )
    if source.evidence.local_retention.retained_bytes > config.max_retained_bytes:
        raise DevelopmentTestnetFailure("SOURCE_OUTSIDE_BOUNDED_RETENTION_ROOT")
    result = await execute_run(config, source, _wallet(config))
    return {
        "schema": "carbon.development-testnet.run-result.v1",
        "dispatch": result,
        "wallet_identity_checked": True,
        "protected_or_official_eligible": False,
    }


async def _resume(
    config: OperatorConfig, source_path: Path, *, rescan_reveal: bool = False
) -> dict[str, object]:
    if config.context is None or config.transaction_authorization is None:
        raise DevelopmentTestnetFailure("COMPLETE_AUTHORIZED_CONTEXT_REQUIRED")
    source = load_source_handoff(
        source_path,
        retention_root=config.retention_root,
        export_root=config.export_root,
    )
    result = await execute_resume(config, source, rescan_reveal=rescan_reveal)
    return {
        "schema": "carbon.development-testnet.resume-result.v1",
        "dispatch": result,
        "wallet_read": False,
        "transaction_resubmitted": False,
        "protected_or_official_eligible": False,
    }


def main(arguments: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "command", choices=("validate", "doctor", "run", "status", "resume")
    )
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--online", action="store_true")
    parser.add_argument("--source", type=Path)
    parser.add_argument(
        "--rescan-reveal",
        action="store_true",
        help="Resume only: restart bounded event reads after a finalized commitment.",
    )
    args = parser.parse_args(arguments)
    try:
        if args.rescan_reveal and args.command != "resume":
            raise DevelopmentTestnetFailure("REVEAL_RESCAN_REQUIRES_RESUME")
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
        elif args.command == "doctor":
            result = asyncio.run(doctor(config, online=args.online))
        else:
            if args.online or args.source is None:
                raise DevelopmentTestnetFailure("EXACT_EXECUTION_ARGUMENTS_REQUIRED")
            source_path = args.source.absolute()
            if args.command == "run":
                result = asyncio.run(_run(config, source_path))
            elif args.command == "resume":
                result = asyncio.run(
                    _resume(config, source_path, rescan_reveal=args.rescan_reveal)
                )
            else:
                result = execution_status(
                    config,
                    load_source_handoff(
                        source_path,
                        retention_root=config.retention_root,
                        export_root=config.export_root,
                    ),
                )
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
