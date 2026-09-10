"""Explicit DEVELOPMENT operator entry points around existing journal/publisher owners."""

import argparse
import asyncio
import json
import os
import signal
import stat
import time
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path
from urllib.parse import urlsplit

from carbon.candidates.model import FixtureEvaluationContext
from carbon.candidates.store import CandidateJournal
from carbon.fees import ExecutionEnvironmentPin, SubmissionResourceLimits
from carbon.rewards.core import RewardFailure
from carbon.rewards.intents import LocalnetIntentIssuer
from carbon.rewards.ledger import FixtureRewardLedger
from carbon.traineval import FixtureStubProfile
from carbon.transport.store import ReceiptJournal

from .adapter import ReadOnlyChainAdapter
from .localnet import inspect_isolation, isolated_relays
from .models import ChainContext, ChainFailure, identifier
from .operator_store import (
    OperatorFailure,
    backup,
    health,
    identity,
    journal_view,
    publisher_lease,
    read_json,
    regular,
    restore,
)
from .publication import PublicationFailure
from .publisher import LocalnetPublisher
from .sdk import BittensorReader
from .sdk_weights import BittensorPublicationBackend

GENESIS = "0x25ce33ee6a48d7a8fa1b485359a4e8f120b92321846e962bdf1e0dae9922e007"
SCHEMA = "carbon.localnet.operator.config.v1"
# Same bounded C0 fixture construction budget; never a production resource policy.
LIMITS = SubmissionResourceLimits(
    10000, 256, 256, 4096, 512, 1000000, 256, 8, 64, 100000, 4000000
)


@dataclass(frozen=True, repr=False)
class OperatorConfig:
    context: ChainContext
    container: str
    container_id: str
    relay_ports: tuple[int, int]
    publisher: str
    journal: Path
    key_file: Path
    evaluations: tuple[FixtureEvaluationContext, ...]
    interval_seconds: int


def load_config(path):
    path = regular(path, maximum=65536)
    raw = read_json(path)
    if type(raw) is not dict or set(raw) != {
        "schema",
        "stage",
        "context",
        "container",
        "container_id",
        "relay_ports",
        "publisher",
        "journal",
        "key_file",
        "evaluations",
        "interval_seconds",
        "treasury",
    }:
        raise OperatorFailure("EXACT_LOCALNET_CONFIG_REQUIRED")
    context = ChainContext(**raw["context"])
    if (
        raw["schema"] != SCHEMA
        or raw["stage"] != "DISPOSABLE_LOCALNET"
        or context.network != "localnet"
        or context.genesis_hash != GENESIS
        or context.netuid != 2
        or raw["treasury"] is not None
    ):
        raise OperatorFailure("PUBLIC_OR_UNPINNED_OPERATION_DISABLED")
    ports = raw["relay_ports"]
    if (
        type(ports) is not list
        or len(ports) != 2
        or len(set(ports)) != 2
        or any(type(p) is not int or not 1024 <= p <= 65535 for p in ports)
        or context.endpoint != f"ws://127.0.0.1:{ports[0]}"
    ):
        raise OperatorFailure("EXPLICIT_LOOPBACK_PORTS_REQUIRED")
    if (
        type(raw["interval_seconds"]) is not int
        or not 1 <= raw["interval_seconds"] <= 30
    ):
        raise OperatorFailure("DEVELOPMENT_INTERVAL_REJECTED")
    if type(raw["container"]) is not str or not raw["container"].startswith(
        "carbon-localnet-"
    ):
        raise OperatorFailure("DISPOSABLE_CONTAINER_REQUIRED")
    if (
        type(raw["container_id"]) is not str
        or len(raw["container_id"]) != 64
        or any(c not in "0123456789abcdef" for c in raw["container_id"])
    ):
        raise OperatorFailure("EXACT_CONTAINER_ID_REQUIRED")
    identifier(raw["publisher"])
    if type(raw["evaluations"]) is not list or not 1 <= len(raw["evaluations"]) <= 3:
        raise OperatorFailure("FINITE_FIXTURE_CONFIGURATION_REQUIRED")
    evaluations = []
    for value in raw["evaluations"]:
        if type(value) is not dict or set(value) != {"localnet_fixture", "environment"}:
            raise OperatorFailure("EXACT_FIXTURE_CONTEXT_REQUIRED")
        profile = FixtureStubProfile(localnet_fixture=value["localnet_fixture"])
        evaluations.append(
            FixtureEvaluationContext(
                profile.score_pack_pin(),
                ExecutionEnvironmentPin(**value["environment"]),
            )
        )
    if len({v.identity for v in evaluations}) != len(evaluations):
        raise OperatorFailure("DUPLICATE_FIXTURE_CONTEXT")
    paths = []
    for name in ("journal", "key_file"):
        if type(raw[name]) is not str or not raw[name]:
            raise OperatorFailure("EXPLICIT_PRIVATE_PATH_REQUIRED")
        value = Path(raw[name])
        paths.append((value if value.is_absolute() else path.parent / value).absolute())
    return OperatorConfig(
        context,
        raw["container"],
        raw["container_id"],
        tuple(ports),
        raw["publisher"],
        *paths,
        tuple(evaluations),
        raw["interval_seconds"],
    )


def config_document(
    receipts,
    container,
    publisher,
    evaluations,
    endpoints,
    container_id,
    key_file="publisher.key",
):
    """Export safe configuration for already registered fixture contexts, never keys."""
    values = []
    for context in evaluations:
        name = context.pack.challenge_key.challenge_id
        values.append(
            {
                "localnet_fixture": None if name == "a5_fixture" else name,
                "environment": asdict(context.environment),
            }
        )
    return {
        "schema": SCHEMA,
        "stage": "DISPOSABLE_LOCALNET",
        "context": asdict(receipts.context),
        "container": container,
        "container_id": container_id,
        "relay_ports": [urlsplit(e).port for e in endpoints],
        "publisher": publisher,
        "journal": str(receipts.path.absolute()),
        "key_file": key_file,
        "evaluations": values,
        "interval_seconds": 5,
        "treasury": None,
    }


def restored_publisher(config, backend, adapter):
    """Require existing accepted journal ownership before constructing its consumers."""
    with journal_view(config.journal) as db:
        if identity(db) != config.context:
            raise OperatorFailure("JOURNAL_CONTEXT_MISMATCH")
        registered = {r[0] for r in db.execute("SELECT context FROM reward_state_v1")}
        candidates = {
            r[0] for r in db.execute("SELECT identity FROM candidate_context_v1")
        }
    expected = {context.identity for context in config.evaluations}
    if registered != expected or not expected.issubset(candidates):
        raise OperatorFailure("INCOMPLETE_REGISTERED_FIXTURE_CONTEXTS")
    receipts = ReceiptJournal(config.journal, config.context)
    journals = tuple(
        CandidateJournal(receipts, context, LIMITS) for context in config.evaluations
    )
    ledger = FixtureRewardLedger(receipts, adapter, journals)
    return LocalnetPublisher(LocalnetIntentIssuer(ledger), backend)


async def verified_key(config, backend, verify):
    """No keyfile access until actual isolated chain and runtime capabilities pass."""
    await verify()
    snapshot, caps = await backend.observe()
    if snapshot.context != config.context:
        raise OperatorFailure("CHAIN_CONTEXT_MISMATCH")
    caps.validate(snapshot, config.publisher)
    path = regular(config.key_file, maximum=4096)
    if os.name != "posix" or path.stat().st_mode & 0o077:
        raise OperatorFailure("PRIVATE_CANONICAL_KEY_FILE_REQUIRED")
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    with os.fdopen(fd, "rb") as stream:
        info = os.fstat(stream.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_mode & 0o077:
            raise OperatorFailure("PRIVATE_KEY_FILE_REJECTED")
        secret = stream.read(4097)
    if not 1 <= len(secret) <= 4096:
        raise OperatorFailure("KEY_FILE_SIZE_REJECTED")
    from bittensor_wallet import Keypair

    failed = False
    try:
        pair = Keypair.create_from_uri(secret.decode().strip())
    except Exception:  # noqa: BLE001
        failed = True
    finally:
        del secret
    if failed:
        raise OperatorFailure("KEY_INPUT_REJECTED")
    if pair.ss58_address != config.publisher:
        raise OperatorFailure("PUBLISHER_KEY_IDENTITY_MISMATCH")
    return pair


async def _supervise_locked(publisher, stop, verify, interval_seconds, max_ticks):
    ticks = 0
    last_success = None
    try:
        while not stop.is_set():
            try:
                await verify()
                result = await publisher.heartbeat("operator-" + uuid.uuid4().hex)
                publisher.last_status = result["state"]
                if result["state"] == "ROW_VERIFIED":
                    last_success = time.time_ns() // 1000000
            except (OperatorFailure, PublicationFailure, RewardFailure) as error:
                publisher.last_status = str(error)
                await publisher.backend.close()
            except ChainFailure as error:
                publisher.last_status = error.code.value
                await publisher.backend.close()
            except Exception:  # noqa: BLE001
                publisher.last_status = "OPERATION_UNAVAILABLE_RECONCILIATION_REQUIRED"
                await publisher.backend.close()
            ticks += 1
            if max_ticks is not None and ticks >= max_ticks:
                break
            try:
                await asyncio.wait_for(stop.wait(), timeout=interval_seconds)
            except TimeoutError:
                pass
        return {
            **health(publisher.issuer.receipts.path),
            "publisher_status": publisher.last_status,
            "ticks": ticks,
            "last_success_wall_ms": last_success,
            "process": "STOPPED",
            "shutdown_clears_weights": False,
        }
    finally:
        await publisher.backend.close()


def _settings(publisher, interval_seconds, max_ticks):
    if type(publisher) is not LocalnetPublisher:
        raise OperatorFailure("OWNED_LOCALNET_PUBLISHER_REQUIRED")
    if type(interval_seconds) is not int or not 1 <= interval_seconds <= 30:
        raise OperatorFailure("DEVELOPMENT_INTERVAL_REJECTED")
    if max_ticks is not None and (type(max_ticks) is not int or max_ticks < 1):
        raise OperatorFailure("INVALID_TICK_BOUND")


async def supervise(publisher, stop, verify, *, interval_seconds=5, max_ticks=None):
    _settings(publisher, interval_seconds, max_ticks)
    with publisher_lease(publisher.issuer.receipts.path):
        return await _supervise_locked(
            publisher, stop, verify, interval_seconds, max_ticks
        )


async def run_config(config, *, max_ticks=None):
    if os.name != "posix":
        raise OperatorFailure("CANONICAL_LINUX_OPERATOR_REQUIRED")
    with publisher_lease(config.journal):
        async with isolated_relays(config.container, ports=config.relay_ports):

            async def verify():
                proof = inspect_isolation(config.container)
                if (
                    proof["endpoints"][0] != config.context.endpoint
                    or proof["container"] != config.container_id
                ):
                    raise OperatorFailure("ISOLATED_ENDPOINT_MISMATCH")

            backend = BittensorPublicationBackend(
                config.context, config.publisher, None
            )
            try:
                publisher = restored_publisher(
                    config,
                    backend,
                    ReadOnlyChainAdapter(config.context, BittensorReader()),
                )
                _settings(publisher, config.interval_seconds, max_ticks)
                backend.wallet = await verified_key(config, backend, verify)
                stop = asyncio.Event()
                loop = asyncio.get_running_loop()
                for sig in (signal.SIGINT, signal.SIGTERM):
                    loop.add_signal_handler(sig, stop.set)
                try:
                    return await _supervise_locked(
                        publisher, stop, verify, config.interval_seconds, max_ticks
                    )
                finally:
                    for sig in (signal.SIGINT, signal.SIGTERM):
                        loop.remove_signal_handler(sig)
            finally:
                await backend.close()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    for command in ("validate", "run"):
        sub = commands.add_parser(command)
        sub.add_argument("--config", required=True, type=Path)
        if command == "run":
            sub.add_argument("--max-ticks", type=int)
    sub = commands.add_parser("health")
    sub.add_argument("--journal", type=Path, required=True)
    sub = commands.add_parser("backup")
    sub.add_argument("--journal", type=Path, required=True)
    sub.add_argument("--destination", type=Path, required=True)
    sub = commands.add_parser("restore")
    sub.add_argument("--backup", type=Path, required=True)
    sub.add_argument("--destination", type=Path, required=True)
    sub.add_argument("--config", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if args.command in ("validate", "run", "restore"):
            config = load_config(args.config)
        if args.command == "validate":
            result = {
                "configuration": "VALID_LOCALNET_ONLY",
                "chain_checked": False,
                "key_read": False,
            }
        elif args.command == "run":
            result = asyncio.run(run_config(config, max_ticks=args.max_ticks))
        elif args.command == "health":
            result = health(args.journal)
        elif args.command == "backup":
            result = backup(args.journal, args.destination)
        else:
            result = restore(args.backup, args.destination, config.context)
        print(json.dumps(result, indent=2))
        return 0
    except Exception:  # noqa: BLE001
        print(
            json.dumps(
                {
                    "status": "OPERATOR_FAILED_CLOSED",
                    "stored_weights_may_remain_effective": True,
                }
            )
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
