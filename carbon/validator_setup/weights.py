"""Additive operator configuration over the existing registered winner publisher."""

from __future__ import annotations

import asyncio
import json
import os
import stat
import tempfile
from dataclasses import dataclass
from pathlib import Path

from carbon.chain import ChainContext
from carbon.chain.models import ChainFailure, identifier
from carbon.chain.publication import PublicationFailure

from .bundle import SetupRefused

SCHEMA = "carbon.validator-weights-operator.v1"


@dataclass(frozen=True)
class WeightsOperator:
    context: ChainContext
    expected_runtime_spec: int
    publisher_hotkey: str
    publisher_coldkey: str
    wallet_name: str
    wallet_hotkey_name: str
    wallet_path: Path

    @property
    def netuid(self):
        return self.context.netuid


def load_config(path):
    """Parse only; neither opens a wallet nor adopts a network's economic policy."""
    path = Path(path)
    if not path.is_absolute() or path.is_symlink():
        raise SetupRefused("OWNER_ONLY_OPERATOR_CONFIG_REQUIRED")
    try:
        info = path.stat()
        if (
            not stat.S_ISREG(info.st_mode)
            or info.st_mode & 0o077
            or info.st_size > 64 * 1024
        ):
            raise ValueError
        raw = json.loads(path.read_bytes())
        if (
            type(raw) is not dict
            or set(raw)
            != {"schema", "context", "expected_runtime_spec", "publisher", "wallet"}
            or raw["schema"] != SCHEMA
        ):
            raise ValueError
        context, publisher, wallet = raw["context"], raw["publisher"], raw["wallet"]
        if (
            type(context) is not dict
            or set(context)
            != {"network", "endpoint", "chain_id", "genesis_hash", "netuid"}
            or context["network"] not in ("testnet", "finney")
        ):
            raise ValueError
        if (
            type(raw["expected_runtime_spec"]) is not int
            or raw["expected_runtime_spec"] <= 0
            or type(publisher) is not dict
            or set(publisher) != {"hotkey", "coldkey"}
            or type(wallet) is not dict
            or set(wallet) != {"name", "hotkey_name", "path"}
        ):
            raise ValueError
        for value in (*publisher.values(), wallet["name"], wallet["hotkey_name"]):
            identifier(value)
        if (
            type(wallet["path"]) is not str
            or not Path(wallet["path"]).is_absolute()
            or Path(wallet["path"]).is_symlink()
        ):
            raise ValueError
        return WeightsOperator(
            ChainContext(
                context["network"],
                context["endpoint"],
                context["chain_id"],
                context["genesis_hash"],
                context["netuid"],
            ),
            raw["expected_runtime_spec"],
            publisher["hotkey"],
            publisher["coldkey"],
            wallet["name"],
            wallet["hotkey_name"],
            Path(wallet["path"]),
        )
    except (OSError, ValueError, KeyError, TypeError, PublicationFailure, ChainFailure):
        raise SetupRefused("OPERATOR_CONTEXT_OR_IDENTITY_REFUSED") from None


async def execute(args):
    """Delegate checked publication; registry/context refusal precedes wallet access."""
    from carbon.chain.sdk import BittensorReader
    from carbon.chain.sdk_weights import (
        BittensorPublicationBackend,
        open_operator_wallet,
    )
    from carbon.rewards import testnet_winner_publication as publication

    config = load_config(Path(args.config).absolute())
    if args.action == "preview":
        # The operator image has a read-only root and no implicit writable /tmp.
        # This explicit journal parent is already a required state mount; each
        # preview gets a private 0700 directory removed even on refusal/failure.
        parent = Path(args.journal).parent
        try:
            info = parent.lstat()
            if (
                not parent.is_absolute()
                or not stat.S_ISDIR(info.st_mode)
                or info.st_uid != os.geteuid()
                or info.st_mode & 0o077
                or any(p.is_symlink() for p in parent.parents)
            ):
                raise ValueError
        except (OSError, ValueError):
            raise SetupRefused("OWNER_ONLY_PREVIEW_JOURNAL_PARENT_REQUIRED") from None
        with tempfile.TemporaryDirectory(
            prefix="carbon-weights-preview-", dir=parent
        ) as scratch:
            issuer = publication._issuer(
                args, config, Path(scratch) / "preview.sqlite3"
            )
            snapshot = await BittensorReader().capture(config.context)
            return publication.preview(issuer, snapshot)
    issuer = publication._issuer(args, config, args.journal)
    wallet = open_operator_wallet(
        config.wallet_name,
        config.wallet_hotkey_name,
        config.publisher_hotkey,
        config.publisher_coldkey,
        wallet_path=config.wallet_path,
    )
    backend = BittensorPublicationBackend(
        config.context, config.publisher_hotkey, wallet, network=config.context.network
    )
    try:
        publisher = publication.TestnetWinnerPublisher(issuer, backend)
        pending = await publication.settle_pending(publisher)
        if pending is not None:
            return {
                "status": "RECONCILE_PENDING",
                "dispatch": pending.get("identity"),
                "state": pending["state"],
                "reason": pending.get("reason"),
            }
        snapshot, _ = await backend.observe()
        return await publisher.publish(issuer.issue(snapshot))
    finally:
        await backend.close()


def run(args):
    return asyncio.run(execute(args))
