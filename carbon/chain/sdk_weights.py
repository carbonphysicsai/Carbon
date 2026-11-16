"""Narrow 11.1.0 publication extension; SDK policy and execute remain in control."""

import asyncio
import hashlib
from contextlib import aclosing
from importlib.metadata import version

from .adapter import translate
from .models import ChainContext, hash256, uint
from .publication import PublicationFailure, RuntimeCapabilities
from .sdk import SDK_VERSION

PINNED_SHIELD_ERA_PERIOD = 8


def require_sdk():
    if version("bittensor") != SDK_VERSION:
        raise PublicationFailure("UNSUPPORTED_SDK_VERSION")


def open_operator_wallet(
    name, hotkey_name, expected_hotkey, expected_coldkey, *, wallet_path=None
):
    """Open the OPERATOR's own validator wallet (weight publication) and
    identity-check it. Never a miner's key: miners sign through their own
    `carbon-miner-signer` (`carbon.chain.external_signer`)."""

    require_sdk()
    try:
        import bittensor as bt

        options = {} if wallet_path is None else {"path": str(wallet_path)}
        wallet = bt.Wallet(name=name, hotkey=hotkey_name, **options)
        if (
            wallet.hotkey.ss58_address != expected_hotkey
            or wallet.coldkeypub.ss58_address != expected_coldkey
        ):
            raise PublicationFailure("WALLET_IDENTITY_MISMATCH")
        return wallet
    except PublicationFailure:
        raise
    except Exception:  # noqa: BLE001 - never expose wallet/provider details.
        raise PublicationFailure("EXTERNAL_WALLET_UNAVAILABLE") from None


def require_shield_era_period():
    """Return the exact SDK/runtime-compatible MEV-shield mortality period."""
    require_sdk()
    from bittensor.settings import MEV_SHIELD_ERA_PERIOD

    if (
        type(MEV_SHIELD_ERA_PERIOD) is not int
        or MEV_SHIELD_ERA_PERIOD != PINNED_SHIELD_ERA_PERIOD
    ):
        raise PublicationFailure("UNSUPPORTED_SHIELD_ERA_PERIOD")
    return MEV_SHIELD_ERA_PERIOD


def guarded_weights(netuid, plan, check_integers, checked_call):
    """Public SetWeights subclass with one version-pinned pre-encryption seam.

    Closure hooks are not serialized intent fields. No registry/global patch.
    _preflight/_conform/_build_timelocked mirror installed 11.1.0 SetWeights.build;
    contract tests must fail before adopting a different SDK implementation.
    """
    require_sdk()
    from bittensor._generated import calls
    from bittensor.intents import SetWeights
    from bittensor.intents.base import BuiltCall
    from bittensor.intents.weights import (
        DEFAULT_COMMIT_REVEAL_VERSION,
        _build_timelocked,
        _conform,
        _preflight,
    )

    class CheckedSetWeights(SetWeights):
        async def build(self, substrate, wallet):
            preflight = await _preflight(
                substrate, self.hotkey_address(wallet), self.netuid, self.mechid
            )
            uids, values = _conform(self.uids, self.weights, preflight, self.netuid)
            await check_integers(uids, values, preflight)
            if preflight.commit_reveal:
                result = await _build_timelocked(
                    substrate,
                    self.hotkey_public_key(wallet),
                    self.netuid,
                    self.mechid,
                    uids,
                    values,
                    self.version_key,
                    DEFAULT_COMMIT_REVEAL_VERSION,
                )
            else:
                result = await substrate.compose(
                    calls.SubtensorModule.set_mechanism_weights(
                        netuid=self.netuid,
                        mecid=self.mechid,
                        dests=uids,
                        weights=values,
                        version_key=self.version_key,
                    )
                )
            await checked_call(
                result.call if isinstance(result, BuiltCall) else result,
                result.extras if isinstance(result, BuiltCall) else {},
            )
            return result

    return CheckedSetWeights(
        netuid=netuid,
        mechid=0,
        version_key=plan.version_key,
        uids=[uid for uid, _ in plan.q12],
        weights=[amount for _, amount in plan.q12],
    )


def journaled_substrate(
    context,
    before_sign,
    before_dispatch,
    *,
    network="localnet",
    after_inner_sign=None,
    after_shield_key=None,
    before_signed_extrinsic=None,
):
    """SDK transport subclass: record hash before wire submission, without key logs."""
    require_sdk()
    if (
        type(context) is not ChainContext
        or context.network != network
        or context.netuid == 0
    ):
        raise PublicationFailure("DISPOSABLE_SUBNET_REQUIRED")
    import bittensor as bt

    class JournaledRpcSubstrate(bt.RpcSubstrate):
        async def mev_next_key(self):
            # Preserve the pinned SDK's public storage path while binding the
            # rotating key, author association and exclusive expiry to one head.
            block = await self.block_number()
            block_hash = await self.block_hash(block)
            value = await self.query("MevShield", "NextKey", block_hash=block_hash)
            if not value:
                key = None
            elif isinstance(value, str):
                key = bytes.fromhex(value.removeprefix("0x"))
            else:
                key = bytes(value)
            if after_shield_key is not None:
                digest = (
                    None if key is None else "sha256:" + hashlib.sha256(key).hexdigest()
                )
                expiry = await self.query(
                    "MevShield", "NextKeyExpiresAt", block_hash=block_hash
                )
                matches = []
                if key is not None:
                    for author, author_key in await self.query_map(
                        "MevShield", "AuthorKeys", block_hash=block_hash
                    ):
                        if isinstance(author_key, str):
                            author_key = bytes.fromhex(author_key.removeprefix("0x"))
                        else:
                            author_key = bytes(author_key)
                        if author_key == key:
                            matches.append(author)
                context = {
                    "block": block,
                    "block_hash": hash256(block_hash),
                    "expires_at_exclusive": expiry,
                    "associated_authors": matches,
                }
                await after_shield_key(digest, 0 if key is None else len(key), context)
            return key

        async def sign_extrinsic(self, call, keypair, **kwargs):
            # MEV inner signing is a public SDK path separate from submit().
            await before_sign(call, keypair.ss58_address)
            if before_signed_extrinsic is not None:
                await before_signed_extrinsic("inner", kwargs)
            signed, identity = await super().sign_extrinsic(call, keypair, **kwargs)
            if after_inner_sign is not None:
                await after_inner_sign(hash256(identity))
            return signed, identity

        async def submit(self, call, keypair, **kwargs):
            await before_sign(call, keypair.ss58_address)
            if before_signed_extrinsic is not None:
                await before_signed_extrinsic("carrier", kwargs)
            return await super().submit(call, keypair, **kwargs)

        async def _submit_and_report(self, extrinsic, **kwargs):
            # Private 11.1 reporting seam: super() retains SDK decoding/policy flow.
            # Only the hash is persisted; signed bytes/private keys stay in memory.
            await before_dispatch(hash256(extrinsic.extrinsic_hash))
            return await super()._submit_and_report(extrinsic, **kwargs)

    return JournaledRpcSubstrate(
        context.endpoint,
        fallback_endpoints=[],
        archive_endpoints=[],
        retry_forever=False,
    )


async def capture_capabilities(client, sub, context, publisher):
    """Observe identity and runtime constraints at the same finalized block."""
    import bittensor as bt

    if hash256(await sub.block_hash(0)) != context.genesis_hash:
        raise PublicationFailure("ENDPOINT_GENESIS_MISMATCH")
    async with aclosing(client.blocks(finalized=True)) as headers:
        header = await anext(headers)
    block = uint(header.number)
    block_hash = hash256(await sub.block_hash(block))
    view = await client.at(block)
    graph = await view.read("metagraph", netuid=context.netuid)
    now = uint(await view.query(bt.storage.Timestamp.Now))
    snapshot = translate(context, block, block_hash, now, graph)
    member = snapshot.resolve(publisher)
    if member is None:
        raise PublicationFailure("PUBLISHER_NOT_REGISTERED")

    async def query(name, args=None):
        return await sub.query("SubtensorModule", name, args, block_hash=block_hash)

    (
        owner,
        owner_hotkey,
        count,
        maximum,
        mode,
        minimum,
        limit,
        version_key,
        rate,
        last,
        cr,
        permits,
        threshold,
        upgrade,
    ) = await asyncio.gather(
        query("SubnetOwner", [context.netuid]),
        query("SubnetOwnerHotkey", [context.netuid]),
        query("MechanismCountCurrent", [context.netuid]),
        query("MaxMechanismCount"),
        query("RecycleOrBurn", [context.netuid]),
        query("MinAllowedWeights", [context.netuid]),
        query("MaxWeightsLimit", [context.netuid]),
        query("WeightsVersionKey", [context.netuid]),
        query("WeightsSetRateLimit", [context.netuid]),
        query("LastUpdate", [context.netuid]),
        query("CommitRevealWeightsEnabled", [context.netuid]),
        query("ValidatorPermit", [context.netuid]),
        query("StakeThreshold"),
        sub.query("System", "LastRuntimeUpgrade", block_hash=block_hash),
    )
    if type(upgrade) is not dict or "spec_version" not in upgrade:
        raise PublicationFailure("RUNTIME_VERSION_OBSERVATION_UNAVAILABLE")
    owned = await query("OwnedHotkeys", [owner])
    if type(owned) is not list or type(last) is not list or type(permits) is not list:
        raise PublicationFailure("MALFORMED_RUNTIME_CAPABILITY")
    if member.uid >= len(last) or member.uid >= len(permits):
        raise PublicationFailure("INCOMPLETE_PUBLISHER_CAPABILITY")
    registered_owner_keys = tuple(
        sorted({key for key in [owner_hotkey, *owned] if snapshot.resolve(key)})
    )
    total_stake = graph.get("total_stake", [])
    if type(total_stake) is not list or member.uid >= len(total_stake):
        raise PublicationFailure("STAKE_OBSERVATION_UNAVAILABLE")
    sufficient = publisher == owner_hotkey or uint(total_stake[member.uid]) >= uint(
        threshold
    )
    pending = 0
    if cr:
        commits = await sub.query_map(
            "SubtensorModule",
            "TimelockedWeightCommits",
            [context.netuid],
            block_hash=block_hash,
        )
        if type(commits) is not list or len(commits) > 256:
            raise PublicationFailure("UNBOUNDED_COMMITMENT_STATE")
        for _, entries in commits:
            if type(entries) is not list or len(entries) > 256:
                raise PublicationFailure("MALFORMED_COMMITMENT_STATE")
            for entry in entries:
                if type(entry) not in (list, tuple) or len(entry) != 4:
                    raise PublicationFailure("MALFORMED_COMMITMENT_STATE")
                pending += entry[0] == publisher
    caps = RuntimeCapabilities(
        snapshot.snapshot_id,
        uint(upgrade["spec_version"]),
        uint(count),
        uint(maximum),
        mode,
        owner,
        owner_hotkey,
        registered_owner_keys,
        uint(minimum),
        uint(limit),
        uint(version_key),
        uint(rate),
        uint(last[member.uid]),
        cr,
        permits[member.uid],
        sufficient,
        pending,
    )
    if (
        hash256(await sub.block_hash(block)) != block_hash
        or hash256(await sub.block_hash(0)) != context.genesis_hash
    ):
        raise PublicationFailure("CONFLICTING_PROVIDER_IDENTITY")
    return snapshot, caps


class BittensorPublicationBackend:
    """Exact-network checked SDK lifecycle. Wallet is supplied externally."""

    def __init__(
        self,
        context,
        publisher,
        wallet,
        *,
        network="localnet",
        archive_endpoint=None,
        archive_fallback=False,
    ):
        if (
            type(context) is not ChainContext
            or context.network != network
            or context.netuid == 0
        ):
            raise PublicationFailure("DISPOSABLE_SUBNET_REQUIRED")
        if archive_endpoint is not None and (
            type(archive_endpoint) is not str
            or not archive_endpoint.startswith(("wss://", "ws://"))
            or len(archive_endpoint) > 512
        ):
            raise PublicationFailure("INVALID_ARCHIVE_ENDPOINT")
        self.context, self.publisher, self.wallet = context, publisher, wallet
        self.network = network
        self.client = self.substrate = None
        # Read-only reconcile reads of finalized history past the pinned node's state window (a non-archive node
        # serves events/state for ~256 blocks). The pinned context, the journal and every signing path are unchanged:
        # the archive is never given to `observe` or `execute`.
        self.archive_endpoint = archive_endpoint
        # FALLBACK mode (the normal loop): history is read from the pinned node first, and only a pinned read that
        # FAILS (state past the node's window) is retried on the archive, under the same genesis + block-hash check.
        # Without it, a configured archive serves every history read (the one-off reconcile, cffc9e08).
        self.archive_fallback = bool(archive_fallback) and archive_endpoint is not None
        self.archive_client = self.archive = None

    async def start(self):
        require_sdk()
        if self.client is not None:
            return
        import bittensor as bt

        sub = bt.RpcSubstrate(
            self.context.endpoint,
            fallback_endpoints=[],
            archive_endpoints=[],
            retry_forever=False,
        )
        client = bt.Client(self.context.endpoint, substrate=sub)
        succeeded = False
        try:
            async with asyncio.timeout(30):
                await sub.connect()
                succeeded = (
                    hash256(await sub.block_hash(0)) == self.context.genesis_hash
                )
        except Exception:  # noqa: BLE001 - never retain provider messages
            succeeded = False
        if not succeeded:
            await client.close()
            raise PublicationFailure("ENDPOINT_UNAVAILABLE_OR_GENESIS_MISMATCH")
        self.client, self.substrate = client, sub

    async def close(self):
        client, self.client, self.substrate = self.client, None, None
        archive, self.archive_client, self.archive = self.archive_client, None, None
        try:
            if client is not None:
                await client.close()
        finally:
            if archive is not None:
                await archive.close()

    async def _start_archive(self):
        if self.archive is not None:
            return
        import bittensor as bt

        sub = bt.RpcSubstrate(
            self.archive_endpoint,
            fallback_endpoints=[],
            archive_endpoints=[],
            retry_forever=False,
        )
        client = bt.Client(self.archive_endpoint, substrate=sub)
        succeeded = False
        try:
            async with asyncio.timeout(30):
                await sub.connect()
                succeeded = (
                    hash256(await sub.block_hash(0)) == self.context.genesis_hash
                )
        except Exception:  # noqa: BLE001 - never retain provider messages
            succeeded = False
        if not succeeded:
            await client.close()
            raise PublicationFailure("ARCHIVE_UNAVAILABLE_OR_GENESIS_MISMATCH")
        self.archive_client, self.archive = client, sub

    async def _history(self, block):
        """The substrate and block hash a reconcile read uses for finalized `block`.

        Without an archive endpoint: the pinned node, as before. With one: the pinned node still names the block
        (genesis + its hash for `block`), and the archive must report the same genesis and the same hash for that
        block before its state/events are read at that hash.
        """
        block_hash = await self._block(block)
        if self.archive_endpoint is None:
            return self.substrate, block_hash
        return await self._archive_at(block, block_hash)

    async def _archive_at(self, block, block_hash):
        await self._start_archive()
        if (
            hash256(await self.archive.block_hash(0)) != self.context.genesis_hash
            or hash256(await self.archive.block_hash(block)) != block_hash
        ):
            raise PublicationFailure("ARCHIVE_CHAIN_MISMATCH")
        return self.archive, block_hash

    async def _read_history(self, block, read):
        """`read(reader, block_hash)` at finalized `block`: the pinned node (no archive), the archive (explicit
        archive mode), or the pinned node with an archive retry when the pinned read raises (fallback mode).
        """
        if not self.archive_fallback:
            reader, block_hash = await self._history(block)
            return await read(reader, block_hash)
        block_hash = await self._block(block)
        try:
            return await read(self.substrate, block_hash)
        except Exception:  # noqa: BLE001
            # A pinned miss (state past the node's window) is retried on the checked archive.
            reader, block_hash = await self._archive_at(block, block_hash)
            return await read(reader, block_hash)

    async def observe(self):
        await self.start()
        result, reason = None, None
        try:
            async with asyncio.timeout(30):
                result = await capture_capabilities(
                    self.client, self.substrate, self.context, self.publisher
                )
        except PublicationFailure as error:
            reason = str(error)
        except Exception:  # noqa: BLE001
            reason = "RUNTIME_OBSERVATION_UNAVAILABLE_OR_MALFORMED"
        if reason:
            raise PublicationFailure(reason)
        return result

    async def execute(self, plan, integers, call_checked, before_sign, before_dispatch):
        import bittensor as bt

        sub = journaled_substrate(
            self.context, before_sign, before_dispatch, network=self.network
        )
        client = bt.Client(
            self.context.endpoint,
            substrate=sub,
            # SetWeights is a direct call (including timelocked commits), not
            # a shielded carrier. Unknown or positive fees must block signing.
            policy=bt.Policy(
                allowed_netuids=[self.context.netuid],
                max_spend_tao=0,
                max_fee_tao=0,
            ),
        )
        reason = None
        try:
            async with asyncio.timeout(120):
                await sub.connect()
                if hash256(await sub.block_hash(0)) != self.context.genesis_hash:
                    raise PublicationFailure("ENDPOINT_GENESIS_MISMATCH")
                intent = guarded_weights(
                    self.context.netuid, plan, integers, call_checked
                )
                # The SDK replans here. Guarded build checks this final plan.
                await client.execute(
                    intent,
                    self.wallet,
                    retries=0,
                    wait_for_inclusion=True,
                    wait_for_finalization=True,
                )
        except PublicationFailure as error:
            reason = str(error)
        except bt.PolicyError:
            reason = "SDK_PUBLICATION_POLICY_REJECTED"
        except Exception:  # noqa: BLE001
            reason = "SDK_EXECUTION_OUTCOME_REQUIRES_RECONCILIATION"
        finally:
            await client.close()
        if reason:
            raise PublicationFailure(reason)

    async def _block(self, block):
        await self.start()
        if hash256(await self.substrate.block_hash(0)) != self.context.genesis_hash:
            raise PublicationFailure("ENDPOINT_GENESIS_MISMATCH")
        return hash256(await self.substrate.block_hash(block))

    async def transaction(self, tx_hash, block):
        from .publisher import TransactionObservation

        async def read(reader, block_hash):
            found = await reader.find_extrinsic(hash256(tx_hash), block_hash)
            if found is None:
                return None
            if found.block_hash != block_hash or type(found.success) is not bool:
                raise PublicationFailure("CONFLICTING_TRANSACTION_BLOCK")
            return TransactionObservation(found.success, block, block_hash)

        result, failed = None, False
        try:
            result = await self._read_history(block, read)
        except Exception:  # noqa: BLE001
            failed = True
        if failed:
            raise PublicationFailure("TRANSACTION_RECONCILIATION_UNAVAILABLE")
        return result

    async def weight_row(self, snapshot, uid):
        async def read(reader, block_hash):
            if block_hash != snapshot.block_hash:
                raise PublicationFailure("CONFLICTING_READBACK_BLOCK")
            row, last = await asyncio.gather(
                reader.query(
                    "SubtensorModule",
                    "Weights",
                    [self.context.netuid, uid],
                    block_hash=block_hash,
                ),
                reader.query(
                    "SubtensorModule",
                    "LastUpdate",
                    [self.context.netuid],
                    block_hash=block_hash,
                ),
            )
            if (
                type(row) is not list
                or len(row) > 65
                or type(last) is not list
                or uid >= len(last)
            ):
                raise PublicationFailure("MALFORMED_WEIGHT_READBACK")
            return [[uint(u, 65535), uint(v, 65535)] for u, v in row], uint(last[uid])

        result, failed = None, False
        try:
            result = await self._read_history(snapshot.finalized_block, read)
        except Exception:  # noqa: BLE001
            failed = True
        if failed:
            raise PublicationFailure("WEIGHT_READBACK_UNAVAILABLE_OR_MALFORMED")
        return result

    async def revealed(self, publisher, block):
        """v445 emits subnet+hotkey, not commit hash. Require exclusive publisher.

        Compilation refuses pre-existing pending commitments. A matching finalized
        reveal event plus checked row is required; a repeated old row alone is not.
        Credential compromise remains outside development security qualification.
        """

        async def read(reader, block_hash):
            matched = False
            events = await reader.events(block_hash)
            if type(events) is not list or len(events) > 10000:
                raise PublicationFailure("MALFORMED_REVEAL_EVENTS")
            for entry in events:
                event = entry.get("event", entry)
                if (
                    event.get("module_id") != "SubtensorModule"
                    or event.get("event_id") != "TimelockedWeightsRevealed"
                ):
                    continue
                attributes = event.get("attributes")
                # The pinned SDK decodes positional SCALE attributes as tuples.
                if type(attributes) in (list, tuple) and len(attributes) == 2:
                    attributes = dict(zip(("netuid", "hotkey"), attributes))
                if (
                    type(attributes) is dict
                    and attributes
                    == {"netuid": self.context.netuid, "hotkey": publisher}
                    and type(attributes["netuid"]) is int
                    and type(attributes["hotkey"]) is str
                ):
                    matched = True
            return matched

        matched, failed = False, False
        try:
            matched = await self._read_history(block, read)
        except Exception:  # noqa: BLE001
            failed = True
        if failed:
            raise PublicationFailure("REVEAL_OBSERVATION_UNAVAILABLE")
        return matched
