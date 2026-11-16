"""Additive operator configuration over the existing registered winner publisher."""

from __future__ import annotations

import asyncio
import json
import os
import stat
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

from carbon.chain import ChainContext
from carbon.chain.models import ChainFailure, identifier
from carbon.chain.publication import PublicationFailure
from carbon.challenge_validator import operator_pause

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
        from carbon.chain import networks

        # the network's own row (F4): its genesis and netuid, never a mixed pair (finney's genesis with 567, or the
        # reverse). The endpoint and provider label stay the operator's: the genesis read at connect is the check.
        networks.check_context(
            network=context["network"],
            genesis_hash=context["genesis_hash"],
            netuid=context["netuid"],
        )
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
    archive = getattr(args, "reconcile_archive_endpoint", None)
    if archive is not None:
        return await reconcile_from_archive(args, config, archive)
    fallback = getattr(args, "archive_fallback_endpoint", None)
    if args.action != "preview" and operator_pause.weights_paused(
        Path(args.journal).parent
    ):
        # The operator's pause blocks every NEW commit or publish (no wallet is opened), but a dispatch already
        # committed keeps reconciling, read-only, so a long pause cannot age its reveal past the node's window
        # (116 epochs 26433 and 26442). Its outcome is reported on stderr; the run still ends WEIGHTS_PAUSED.
        reconciled = await reconcile_during_pause(args, config, fallback)
        print(
            json.dumps({"paused_reconcile": reconciled}, sort_keys=True),
            file=sys.stderr,
        )
        raise SetupRefused(operator_pause.WEIGHTS_PAUSED)
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
    from carbon.chain import runtime_accept

    issuer = publication._issuer(args, config, args.journal)
    # H8: the live runtime, after the issuer's own offline refusals and before any wallet. A new spec with the
    # accepted used-surface digest is published under at once; anything else refuses here, before signing.
    try:
        spec = None
        if runtime_accept.has_baseline(args.journal):
            spec = await runtime_accept.resolve(
                config.context.endpoint, config.context.genesis_hash, args.journal
            )
    except runtime_accept.RuntimeRefused as refused:
        raise SetupRefused(refused.code) from None
    if spec is not None and spec != config.expected_runtime_spec:
        issuer = publication._issuer(args, config, args.journal, runtime_spec=spec)
    wallet = open_operator_wallet(
        config.wallet_name,
        config.wallet_hotkey_name,
        config.publisher_hotkey,
        config.publisher_coldkey,
        wallet_path=config.wallet_path,
    )
    backend = BittensorPublicationBackend(
        config.context,
        config.publisher_hotkey,
        wallet,
        network=config.context.network,
        archive_endpoint=fallback,
        archive_fallback=fallback is not None,
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


async def reconcile_during_pause(args, config, fallback):
    """RECONCILE ONLY while the weights pause is ON: settle the journal's pending dispatch (reads only; no wallet,
    no new dispatch, no publish), reading history from the pinned node with the archive fallback when one is
    configured. Never raises: the pause outcome is the caller's; this returns what happened.
    """
    from carbon.chain.sdk_weights import BittensorPublicationBackend
    from carbon.rewards import testnet_winner_publication as publication

    if args.action != "run" or not Path(args.journal).is_file():
        return {"status": "NOTHING_PENDING"}
    try:
        issuer = publication._issuer(args, config, args.journal)
        backend = BittensorPublicationBackend(
            config.context,
            config.publisher_hotkey,
            None,
            network=config.context.network,
            archive_endpoint=fallback,
            archive_fallback=fallback is not None,
        )
    except (PublicationFailure, SetupRefused, OSError, ValueError) as failure:
        return {"status": "RECONCILE_NOT_RUN", "reason": str(failure)[:120]}
    try:
        publisher = publication.TestnetWinnerPublisher(issuer, backend)
        before = publisher.journal.pending()
        if before is None:
            return {"status": "NOTHING_PENDING"}
        pending = await publication.settle_pending(publisher)
        return {
            "status": "RECONCILE_PENDING" if pending is not None else "SETTLED",
            "dispatch": before,
            "reason": None if pending is None else pending.get("reason"),
        }
    except (PublicationFailure, ChainFailure, OSError, ValueError) as failure:
        return {"status": "RECONCILE_UNAVAILABLE", "reason": str(failure)[:120]}
    finally:
        await backend.close()


async def reconcile_from_archive(args, config, archive_endpoint):
    """RECONCILE ONLY: settle a pending dispatch whose finalized history is past the pinned node's state window.

    Reads that history (the transaction, the reveal events, the weight readback) through `archive_endpoint`; the
    journal keeps its pinned context (endpoint included) and the pinned node still names every block, whose hash the
    archive must match (`BittensorPublicationBackend._history`). It never publishes: no wallet is opened (the backend
    gets none) and no new dispatch is issued; the normal loop publishes the next epoch afterwards on the normal
    config. It runs only while the operator's weights pause is ON, so the loop cannot touch the journal meanwhile.
    """
    from carbon.chain.sdk_weights import BittensorPublicationBackend
    from carbon.rewards import testnet_winner_publication as publication

    if args.action != "run":
        raise SetupRefused("ARCHIVE_RECONCILE_REQUIRES_RUN")
    if not operator_pause.weights_paused(Path(args.journal).parent):
        raise SetupRefused("ARCHIVE_RECONCILE_REQUIRES_WEIGHTS_PAUSE")
    if not Path(args.journal).is_file():
        raise SetupRefused("ARCHIVE_RECONCILE_REQUIRES_EXISTING_JOURNAL")
    issuer = publication._issuer(args, config, args.journal)
    try:
        backend = BittensorPublicationBackend(
            config.context,
            config.publisher_hotkey,
            None,
            network=config.context.network,
            archive_endpoint=archive_endpoint,
        )
    except PublicationFailure as failure:
        raise SetupRefused(str(failure)) from None
    try:
        publisher = publication.TestnetWinnerPublisher(issuer, backend)
        before = publisher.journal.pending()
        if before is None:
            return {"status": "NOTHING_PENDING", "published": False}
        pending = await publication.settle_pending(publisher)
        return {
            "status": "RECONCILE_PENDING" if pending is not None else "SETTLED",
            "dispatch": before,
            "state": None if pending is None else pending["state"],
            "reason": None if pending is None else pending.get("reason"),
            "settled_row": publisher.journal.get(before)["state"],
            "published": False,
        }
    finally:
        await backend.close()


def run(args):
    return asyncio.run(execute(args))
