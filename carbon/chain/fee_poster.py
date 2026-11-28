"""Miner-side atomic submission fee poster (`FeePoster`) — never double-burns.

Modeled directly on ``carbon.chain.commitment_poster.CommitmentPoster``:
- Coordinates across processes and campaign roots via `exclusive_file_lock` in a
  shared per-miner state directory (`~/.carbon/fee-burns`, `H11`, `N5`) so concurrent
  submits can never double-burn.
- Writes pending state (`BROADCAST`) **only after** `carbon-miner-signer` has signed
  and verified the extrinsic (`Ctrl-C` or timeout at the signer TTY prompt leaves
  local state untouched instead of causing an era lockout).
- Reuses door-reported `server_unspent` receipts immediately even if an older
  broadcast is reconciling, chunks mortal-era range reads into 32-block slices so
  129-block scans never time out, and holds `FINALIZED_UNVERIFIED` (`B7(c)`) without
  ever auto-burning a second time if a broadcast reported `FINALIZED` success while
  event decoding did not yet observe `AddStakeBurn`.
- Maps `SignerFailure` to closed `_CODE`-compatible refusal codes (`failure.refusal
  or failure.code`, zero colons) so Launchpad and MCP surface exact next steps.
"""

from __future__ import annotations

import argparse
import asyncio
import concurrent.futures
import contextlib
import datetime
import json
import os
import sys
import threading
from enum import Enum
from importlib.metadata import version
from pathlib import Path

from .external_signer import SignerFailure
from .fee_burns import (
    DEFAULT_MAX_LOOKBACK_BLOCKS,
    EXTRINSIC_ID,
    ChainFeeBurnReader,
    exclusive_file_lock,
    fee_remark,
    fee_remark_hash,
    parse_extrinsic_id,
)
from .models import ChainContext, ChainFailure, FailureCode, hash256, uint
from .sdk import SDK_VERSION

SCHEMA = "carbon.miner.fee-burn-post.v1"
ERA_PERIOD = 128
RANGE_CHUNK_BLOCKS = 32
PENDING = frozenset({"REQUESTED", "BROADCAST", "AMBIGUOUS", "FINALIZED_UNVERIFIED"})
DEFAULT_POSTER_DIR_ENV = "CARBON_FEE_POSTER_DIR"


class FeePostCode(str, Enum):
    BURNED = "fee_burn_finalized"
    REUSED_UNSPENT = "fee_burn_reused_unspent"
    BAD_REQUEST = "fee_burn_bad_request"
    CHAIN_UNAVAILABLE = "fee_burn_chain_unavailable"
    FEE_UNKNOWN = "fee_burn_tx_fee_unknown"
    FEE_OVER_CEILING = "fee_burn_tx_fee_over_ceiling"
    CALL_MISMATCH = "fee_burn_call_mismatch"
    SIGNATURE_INVALID = "fee_burn_signature_invalid"
    IN_FLIGHT = "fee_burn_in_flight"
    AMBIGUOUS = "fee_burn_ambiguous"
    FAILED = "fee_burn_failed"
    NOT_OBSERVED = "fee_burn_not_observed"


DONE = frozenset({FeePostCode.BURNED.value, FeePostCode.REUSED_UNSPENT.value})


def default_fee_poster_dir() -> Path:
    """Shared per-user directory so concurrent campaign roots coordinate under one lock (`H11`)."""
    env = os.environ.get(DEFAULT_POSTER_DIR_ENV)
    if env:
        return Path(env).expanduser()
    return Path.home() / ".carbon" / "fee-burns"


def _verify(payload: bytes, signature: bytes, hotkey: str) -> bool:
    from bittensor.sp_core import verify

    return bool(verify(payload, signature, hotkey, 1))


class _PublicAccount:
    """Public-key-only account wrapper for `substrate.estimate_fee`."""

    crypto_type = 1

    def __init__(self, address: str) -> None:
        from bittensor.sp_core import ss58_decode

        self.ss58_address = address
        public_key = bytes(ss58_decode(address))
        if len(public_key) != 32:
            raise ValueError("an sr25519 public key is 32 bytes")
        self.public_key = public_key


FINALITY_SECONDS = 240
PREPARE_TIMEOUT_S = 25.0


class SdkFeeBurnChain:
    """Read-only prepare/estimate + single-broadcast chain adapter over SDK 11.1.0."""

    def __init__(self, context: ChainContext) -> None:
        if type(context) is not ChainContext:
            raise TypeError("a ChainContext is required")
        self.context = context
        self.reader = ChainFeeBurnReader(context)

    def finalized_block(self) -> int:
        return self.reader.finalized_head()

    def read_block_burns(self, block: int):
        return self.reader.read_block(block)[1]

    def read_burns_in_range(self, start_block: int, end_block: int):
        return self.reader.read_blocks_range(start_block, end_block)[1]

    @staticmethod
    async def _compose_batch(
        substrate,
        *,
        hotkey: str,
        receiver: str,
        netuid: int,
        challenge_id: str,
        amount_rao: int,
        limit_price_rao: int | None,
    ):
        from bittensor._generated import calls

        c1 = await substrate.compose(
            calls.SubtensorModule.add_stake_burn(
                hotkey=hotkey,
                netuid=netuid,
                amount=amount_rao,
                limit=limit_price_rao,
            )
        )
        c2 = await substrate.compose(
            calls.System.remark_with_event(
                remark=fee_remark(netuid, challenge_id, receiver, hotkey)
            )
        )
        return await substrate.compose(calls.Utility.batch_all(calls=[c1, c2]))

    def prepare_and_estimate(
        self,
        *,
        hotkey: str,
        receiver: str,
        netuid: int,
        challenge_id: str,
        amount_rao: int,
        limit_price_rao: int | None,
        era_period: int = ERA_PERIOD,
    ) -> tuple[dict, dict]:
        pool = concurrent.futures.ThreadPoolExecutor(max_workers=1)
        try:
            fut = pool.submit(
                asyncio.run,
                asyncio.wait_for(
                    self._prepare_async(
                        hotkey=hotkey,
                        receiver=receiver,
                        netuid=netuid,
                        challenge_id=challenge_id,
                        amount_rao=amount_rao,
                        limit_price_rao=limit_price_rao,
                        era_period=era_period,
                    ),
                    timeout=PREPARE_TIMEOUT_S,
                ),
            )
            return fut.result(timeout=PREPARE_TIMEOUT_S + 5.0)
        finally:
            pool.shutdown(wait=False, cancel_futures=True)

    async def _prepare_async(
        self,
        *,
        hotkey: str,
        receiver: str,
        netuid: int,
        challenge_id: str,
        amount_rao: int,
        limit_price_rao: int | None,
        era_period: int,
    ) -> tuple[dict, dict]:
        if version("bittensor") != SDK_VERSION:
            raise ChainFailure(FailureCode.UNSUPPORTED)
        import bittensor as bt

        substrate = bt.RpcSubstrate(
            self.context.endpoint,
            fallback_endpoints=[],
            archive_endpoints=[],
            retry_forever=False,
        )
        try:
            await substrate.connect()
            if hash256(await substrate.block_hash(0)) != self.context.genesis_hash:
                raise ChainFailure(FailureCode.IDENTITY)
            batch = await self._compose_batch(
                substrate,
                hotkey=hotkey,
                receiver=receiver,
                netuid=netuid,
                challenge_id=challenge_id,
                amount_rao=amount_rao,
                limit_price_rao=limit_price_rao,
            )
            unsigned = await substrate.prepare(
                batch, address=hotkey, crypto_type=1, period=era_period, tip=0
            )
            fee = await substrate.estimate_fee(batch, _PublicAccount(hotkey))
            data = unsigned.to_dict()
            return (
                {"unsigned": data, "payload": data["payload"]},
                {"partial_fee_rao": uint(int(fee.rao)), "deposit_rao": 0},
            )
        finally:
            with contextlib.suppress(Exception):
                await asyncio.wait_for(substrate.close(), timeout=3.0)

    def broadcast(self, prepared: dict, signature: bytes) -> dict:
        pool = concurrent.futures.ThreadPoolExecutor(max_workers=1)
        try:
            fut = pool.submit(
                asyncio.run,
                asyncio.wait_for(
                    self._broadcast_async(prepared, signature),
                    timeout=FINALITY_SECONDS + 10.0,
                ),
            )
            return fut.result(timeout=FINALITY_SECONDS + 15.0)
        finally:
            pool.shutdown(wait=False, cancel_futures=True)

    async def _broadcast_async(self, prepared: dict, signature: bytes) -> dict:
        if version("bittensor") != SDK_VERSION:
            raise ChainFailure(FailureCode.UNSUPPORTED)
        import bittensor as bt
        from bittensor._transport.contract import UnsignedExtrinsic

        unsigned = UnsignedExtrinsic.from_dict(prepared["unsigned"])
        substrate = bt.RpcSubstrate(
            self.context.endpoint,
            fallback_endpoints=[],
            archive_endpoints=[],
            retry_forever=False,
        )
        try:
            await substrate.connect()
            if hash256(await substrate.block_hash(0)) != self.context.genesis_hash:
                raise ChainFailure(FailureCode.IDENTITY)
            result = await asyncio.wait_for(
                substrate.submit_signature(
                    unsigned,
                    signature,
                    wait_for_inclusion=True,
                    wait_for_finalization=True,
                ),
                timeout=FINALITY_SECONDS,
            )
            block = None
            if result.extrinsic_id:
                block = int(result.extrinsic_id.split("-", 1)[0])
            fee = None if result.fee is None else int(result.fee.rao)
            if result.success:
                return {
                    "outcome": "FINALIZED",
                    "block": block,
                    "fee_rao": fee,
                    "extrinsic_id": result.extrinsic_id,
                }
            if result.block_hash is not None:
                message = result.error.message if result.error else result.message
                return {"outcome": "FAILED", "block": block, "error": message}
            return {"outcome": "UNKNOWN"}
        finally:
            with contextlib.suppress(Exception):
                await asyncio.wait_for(substrate.close(), timeout=3.0)


class FeePoster:
    """One hotkey's submission-burn poster for one `(Challenge, receiver)`; never double-burns."""

    def __init__(
        self,
        *,
        hotkey: str,
        receiver: str,
        netuid: int,
        challenge_id: str,
        chain,
        sign,
        state_dir: Path | str | None = None,
        verify=_verify,
        clock=None,
    ) -> None:
        self.hotkey = hotkey
        self.receiver = receiver
        self.netuid = netuid
        self.challenge_id = challenge_id
        self.chain = chain
        self._sign = sign
        self._verify = verify
        base_dir = default_fee_poster_dir() if state_dir is None else Path(state_dir)
        stem = f"fee-burn-{netuid}-{challenge_id}-{receiver}-{hotkey}"
        self.path = base_dir / f"{stem}.json"
        self._lock_path = base_dir / f".{stem}.lock"
        self._clock = clock or (lambda: datetime.datetime.now(datetime.UTC))
        self._lock = threading.Lock()

    @contextlib.contextmanager
    def _exclusive_guard(self, *, blocking: bool):
        if not self._lock.acquire(blocking=blocking):
            raise BlockingIOError("in-process fee poster lock busy")
        try:
            with exclusive_file_lock(self._lock_path, blocking=blocking):
                yield
        finally:
            self._lock.release()

    def record(self) -> dict | None:
        try:
            if self.path.is_symlink():
                return None
            return json.loads(self.path.read_text(encoding="utf-8"))
        except (FileNotFoundError, ValueError, OSError):
            return None

    def _write(self, **fields: object) -> dict:
        prev = self.record() or {}
        unspent = list(fields.pop("unspent", prev.get("unspent", [])))
        seen_list = [x for x in prev.get("seen_extrinsic_ids", []) if type(x) is str]
        seen_set = set(seen_list)
        for item in unspent:
            if isinstance(item, dict) and type(item.get("extrinsic_id")) is str:
                eid = item["extrinsic_id"]
                if eid not in seen_set:
                    seen_list.append(eid)
                    seen_set.add(eid)
        extra_seen = fields.pop("add_seen_extrinsic_id", None)
        if type(extra_seen) is str and extra_seen not in seen_set:
            seen_list.append(extra_seen)
        row = {
            "schema": SCHEMA,
            "hotkey": self.hotkey,
            "receiver": self.receiver,
            "netuid": self.netuid,
            "challenge_id": self.challenge_id,
            "unspent": unspent,
            "seen_extrinsic_ids": seen_list[-128:],
            **fields,
            "updated_at": self._clock().isoformat(),
        }
        self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        tmp = self.path.with_suffix(".tmp")
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(row, handle, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp, self.path)
        return row

    def note_spent(self, extrinsic_id: str) -> None:
        """Best-effort non-blocking local prune once the door admits the submission (`M3`)."""
        with contextlib.suppress(BlockingIOError, OSError):
            self.prune_unspent(extrinsic_id, blocking=False)

    def prune_unspent(self, extrinsic_id: str, *, blocking: bool = True) -> None:
        """Remove a spent, expired, or chain-confirmed missing ``extrinsic_id`` from local `unspent`."""
        with self._exclusive_guard(blocking=blocking):
            row = self.record()
            if row is None:
                return
            remaining = [
                item
                for item in row.get("unspent", [])
                if isinstance(item, dict) and item.get("extrinsic_id") != extrinsic_id
            ]
            self._write(
                state=row.get("state", "IDLE"),
                unspent=remaining,
                add_seen_extrinsic_id=extrinsic_id,
            )

    def confirm_extrinsic_missing_on_chain(self, extrinsic_id: str) -> bool:
        """Verify on the miner's own chain reader whether ``extrinsic_id`` is genuinely
        absent at its finalized block (`M1`: prevents auto-pruning/re-burning on a
        validator indexer miss or lag!). Returns False on any doubt or RPC error."""
        parsed = parse_extrinsic_id(extrinsic_id)
        if parsed is None:
            return True
        block, _ = parsed
        try:
            head = int(self.chain.finalized_block())
            if block > head:
                return False
            if hasattr(self.chain, "read_block_burns"):
                burns = self.chain.read_block_burns(block)
            else:
                burns = self.chain.read_burns_in_range(block, block).get(block, ())
        except Exception:  # noqa: BLE001
            return False
        expected_hash = fee_remark_hash(
            self.netuid, self.challenge_id, self.receiver, self.hotkey
        )
        for burn in burns:
            if (
                burn.extrinsic_id == extrinsic_id
                and burn.hotkey == self.hotkey
                and burn.remark_hash == expected_hash
            ):
                return False
        return True

    def obtain_extrinsic(
        self,
        *,
        amount_rao: int,
        min_block: int = 0,
        max_lookback_blocks: int = DEFAULT_MAX_LOOKBACK_BLOCKS,
        limit_price_rao: int | None = None,
        server_unspent: list[str] | tuple[str, ...] = (),
    ) -> dict[str, object]:
        """Return an unspent finalized ``extrinsic_id`` or broadcast exactly one new burn."""
        if type(amount_rao) is not int or amount_rao <= 0:
            return {"schema": SCHEMA, "code": FeePostCode.BAD_REQUEST.value}
        try:
            with self._exclusive_guard(blocking=False):
                return self._obtain_locked(
                    amount_rao=amount_rao,
                    min_block=min_block,
                    max_lookback_blocks=max_lookback_blocks,
                    limit_price_rao=limit_price_rao,
                    server_unspent=server_unspent,
                )
        except BlockingIOError:
            return {
                "schema": SCHEMA,
                "code": FeePostCode.IN_FLIGHT.value,
                "retry_after_s": 12,
            }

    def _obtain_locked(
        self,
        *,
        amount_rao: int,
        min_block: int,
        max_lookback_blocks: int,
        limit_price_rao: int | None,
        server_unspent: list[str] | tuple[str, ...],
    ) -> dict[str, object]:
        # 1. Reconcile any pending/ambiguous earlier broadcast first; however, if the
        # door ALREADY reports a valid unspent receipt in `server_unspent`, allow
        # reusing it even if an older broadcast is still ambiguous!
        reconcile_outcome: dict[str, object] | None = None
        try:
            reconcile_outcome = self._reconcile_locked(
                amount_rao=amount_rao, min_block=min_block
            )
        except Exception:  # noqa: BLE001
            reconcile_outcome = {
                "schema": SCHEMA,
                "code": FeePostCode.CHAIN_UNAVAILABLE.value,
                "retry_after_s": 12,
            }

        if reconcile_outcome is not None and reconcile_outcome.get("code") in DONE:
            return reconcile_outcome

        # 2. Reuse any unspent receipt reported by preflight (already lookback-filtered & newest-first).
        for ext_id in server_unspent:
            if type(ext_id) is str and EXTRINSIC_ID.fullmatch(ext_id):
                blk = int(ext_id.split("-", 1)[0])
                if blk >= min_block:
                    return {
                        "schema": SCHEMA,
                        "code": FeePostCode.REUSED_UNSPENT.value,
                        "extrinsic_id": ext_id,
                    }

        if reconcile_outcome is not None:
            return reconcile_outcome

        # 3. Reuse local unspent receipt (sorted newest-first, pruning lookback-expired ones).
        row = self.record() or {}
        local_items = [
            it
            for it in row.get("unspent", [])
            if isinstance(it, dict) and type(it.get("extrinsic_id")) is str
        ]
        if local_items:
            head_now: int | None = None
            with contextlib.suppress(Exception):
                head_now = int(self.chain.finalized_block())
            floor = min_block
            if head_now is not None and max_lookback_blocks > 0:
                floor = max(floor, head_now - max_lookback_blocks)
            valid_local = [it for it in local_items if int(it.get("block", 0)) >= floor]
            if len(valid_local) != len(local_items):
                self._write(state=row.get("state", "IDLE"), unspent=valid_local)
            valid_local.sort(key=lambda it: int(it.get("block", 0)), reverse=True)
            for item in valid_local:
                if int(item.get("amount_rao", 0)) >= amount_rao:
                    return {
                        "schema": SCHEMA,
                        "code": FeePostCode.REUSED_UNSPENT.value,
                        "extrinsic_id": item["extrinsic_id"],
                    }

        # 4. Prepare, sign via carbon-miner-signer, verify, THEN record `BROADCAST` and send once.
        try:
            prepared, tx_fee = self.chain.prepare_and_estimate(
                hotkey=self.hotkey,
                receiver=self.receiver,
                netuid=self.netuid,
                challenge_id=self.challenge_id,
                amount_rao=amount_rao,
                limit_price_rao=limit_price_rao,
                era_period=ERA_PERIOD,
            )
        except Exception:  # noqa: BLE001
            return {
                "schema": SCHEMA,
                "code": FeePostCode.CHAIN_UNAVAILABLE.value,
                "retry_after_s": 12,
            }
        if tx_fee is None:
            return {"schema": SCHEMA, "code": FeePostCode.FEE_UNKNOWN.value}

        unsigned = prepared["unsigned"]
        era = unsigned.get("era")
        if (
            not isinstance(era, dict)
            or type(era.get("current")) is not int
            or type(era.get("period")) is not int
            or era["period"] <= 0
        ):
            return {"schema": SCHEMA, "code": FeePostCode.BAD_REQUEST.value}

        request = {
            "netuid": self.netuid,
            "challenge_id": self.challenge_id,
            "receiver": self.receiver,
            "amount_rao": amount_rao,
            "limit_price_rao": limit_price_rao,
            "unsigned": {
                key: unsigned[key]
                for key in (
                    "call_data",
                    "era",
                    "nonce",
                    "tip",
                    "genesis_hash",
                    "era_block_hash",
                    "spec_version",
                    "transaction_version",
                    "metadata_hash",
                    "included_in_extrinsic",
                    "included_in_signed_data",
                )
            },
            "fee": tx_fee,
        }
        try:
            answer = self._sign(request)
        except SignerFailure as failure:
            # Map to closed `_CODE`-compatible refusal (no colons, `Merge Blocker 1`!).
            refusal_code = failure.refusal or failure.code
            self._write(state="REFUSED", code=refusal_code)
            return {"schema": SCHEMA, "code": refusal_code}

        payload = bytes.fromhex(str(prepared["payload"]).removeprefix("0x"))
        call = bytes.fromhex(str(unsigned["call_data"]).removeprefix("0x"))
        if answer["call"] != call:
            self._write(state="NOT_SENT", code=FeePostCode.CALL_MISMATCH.value)
            return {"schema": SCHEMA, "code": FeePostCode.CALL_MISMATCH.value}
        if not self._verify(payload, answer["signature"], self.hotkey):
            self._write(state="NOT_SENT", code=FeePostCode.SIGNATURE_INVALID.value)
            return {"schema": SCHEMA, "code": FeePostCode.SIGNATURE_INVALID.value}
        if (
            tx_fee["partial_fee_rao"] + tx_fee["deposit_rao"]
            > answer["tx_fee_ceiling_rao"]
        ):
            self._write(state="NOT_SENT", code=FeePostCode.FEE_OVER_CEILING.value)
            return {"schema": SCHEMA, "code": FeePostCode.FEE_OVER_CEILING.value}

        # Persist `BROADCAST` immediately BEFORE sending over the network (so a Ctrl-C
        # at the signer prompt above never writes a pending state, while a crash mid-send
        # ALWAYS reconciles across the mortal era!).
        self._write(
            state="BROADCAST",
            amount_rao=amount_rao,
            nonce=unsigned["nonce"],
            era_current=era["current"],
            era_period=era["period"],
        )
        try:
            outcome = self.chain.broadcast(prepared, answer["signature"])
        except Exception:  # noqa: BLE001 - network drop after send -> reconcile!
            outcome = {"outcome": "UNKNOWN"}

        return self._settle_broadcast_locked(amount_rao, outcome, era)

    def _find_matching_burn_in_range(
        self, start_block: int, end_block: int, min_amount_rao: int
    ) -> dict | None:
        expected_hash = fee_remark_hash(
            self.netuid, self.challenge_id, self.receiver, self.hotkey
        )
        rec = self.record() or {}
        existing_ids = {
            item.get("extrinsic_id")
            for item in rec.get("unspent", [])
            if isinstance(item, dict)
        } | {x for x in rec.get("seen_extrinsic_ids", []) if type(x) is str}
        range_fn = getattr(self.chain, "read_burns_in_range", None)
        for chunk_start in range(start_block, end_block + 1, RANGE_CHUNK_BLOCKS):
            chunk_end = min(end_block, chunk_start + RANGE_CHUNK_BLOCKS - 1)
            if callable(range_fn):
                burns_by_block = range_fn(chunk_start, chunk_end)
                ordered_blocks = sorted(burns_by_block)
                block_iter = ((blk, burns_by_block[blk]) for blk in ordered_blocks)
            else:
                block_iter = (
                    (blk, self.chain.read_block_burns(blk))
                    for blk in range(chunk_start, chunk_end + 1)
                )
            for _blk, burns in block_iter:
                for burn in burns:
                    if (
                        burn.hotkey == self.hotkey
                        and burn.remark_hash == expected_hash
                        and burn.amount_rao >= min_amount_rao
                        and burn.extrinsic_id not in existing_ids
                    ):
                        return {
                            "extrinsic_id": burn.extrinsic_id,
                            "block": burn.block,
                            "amount_rao": burn.amount_rao,
                        }
        return None

    def _settle_broadcast_locked(
        self, amount_rao: int, outcome: dict, era: dict
    ) -> dict[str, object]:
        kind = outcome.get("outcome")
        if kind == "FAILED":
            self._write(state="FAILED", error=outcome.get("error"))
            return {
                "schema": SCHEMA,
                "code": FeePostCode.FAILED.value,
                "error": outcome.get("error"),
            }
        if kind != "FINALIZED":
            self._write(
                state="AMBIGUOUS",
                amount_rao=amount_rao,
                era_current=era["current"],
                era_period=era["period"],
            )
            return {
                "schema": SCHEMA,
                "code": FeePostCode.AMBIGUOUS.value,
                "retry_after_s": 12,
            }

        block = outcome.get("block")
        reported_ext_id = outcome.get("extrinsic_id")
        if type(block) is not int:
            self._write(
                state="FINALIZED_UNVERIFIED",
                amount_rao=amount_rao,
                era_current=era["current"],
                era_period=era["period"],
                reported_extrinsic_id=reported_ext_id,
            )
            return {
                "schema": SCHEMA,
                "code": FeePostCode.NOT_OBSERVED.value,
                "retry_after_s": 12,
            }

        try:
            matched = self._find_matching_burn_in_range(block, block, amount_rao)
        except Exception:  # noqa: BLE001
            self._write(
                state="FINALIZED_UNVERIFIED",
                amount_rao=amount_rao,
                era_current=era["current"],
                era_period=era["period"],
                finalized_block=block,
                reported_extrinsic_id=reported_ext_id,
            )
            return {
                "schema": SCHEMA,
                "code": FeePostCode.AMBIGUOUS.value,
                "retry_after_s": 12,
            }

        if matched is None:
            # `B7(c)`: Broadcast reported `FINALIZED` success at `block`! Keep
            # `FINALIZED_UNVERIFIED` so we re-read `block` on retry if RPC lagged,
            # and NEVER auto-expire into signing a second burn after era expiry!
            self._write(
                state="FINALIZED_UNVERIFIED",
                amount_rao=amount_rao,
                era_current=era["current"],
                era_period=era["period"],
                finalized_block=block,
                reported_extrinsic_id=reported_ext_id,
            )
            return {
                "schema": SCHEMA,
                "code": FeePostCode.NOT_OBSERVED.value,
                "retry_after_s": 12,
            }

        prev_unspent = list((self.record() or {}).get("unspent", []))
        prev_unspent.append(matched)
        self._write(
            state="BURNED",
            block=matched["block"],
            extrinsic_id=matched["extrinsic_id"],
            unspent=prev_unspent,
        )
        return {
            "schema": SCHEMA,
            "code": FeePostCode.BURNED.value,
            "extrinsic_id": matched["extrinsic_id"],
            "block": matched["block"],
        }

    def _reconcile_locked(self, *, amount_rao: int, min_block: int) -> dict | None:
        row = self.record()
        if row is None or row.get("state") not in PENDING:
            return None
        state = row.get("state")
        start = row.get("era_current")
        period = row.get("era_period")
        recorded_amount = int(row.get("amount_rao", amount_rao))

        if state == "FINALIZED_UNVERIFIED":
            head = self.chain.finalized_block()
            f_blk = row.get("finalized_block")
            if type(f_blk) is int and f_blk <= head:
                matched = self._find_matching_burn_in_range(
                    f_blk, f_blk, recorded_amount
                )
            elif type(start) is int and type(period) is int and head >= start:
                matched = self._find_matching_burn_in_range(
                    start, min(head, start + period), recorded_amount
                )
            else:
                matched = None
            if matched is not None:
                prev_unspent = list(row.get("unspent", []))
                prev_unspent.append(matched)
                self._write(
                    state="BURNED",
                    block=matched["block"],
                    extrinsic_id=matched["extrinsic_id"],
                    unspent=prev_unspent,
                )
                if (
                    matched["amount_rao"] >= amount_rao
                    and matched["block"] >= min_block
                ):
                    return {
                        "schema": SCHEMA,
                        "code": FeePostCode.BURNED.value,
                        "extrinsic_id": matched["extrinsic_id"],
                        "block": matched["block"],
                    }
                return None
            # Sticky `NOT_OBSERVED` (`B7(c)`): never auto-burn again after a `FINALIZED` broadcast!
            return {
                "schema": SCHEMA,
                "code": FeePostCode.NOT_OBSERVED.value,
                "retry_after_s": 12,
            }

        if type(start) is not int or type(period) is not int or period <= 0:
            # Corrupt/legacy pending row without mortal era bounds: clear instead of wedging forever.
            self._write(state="FAILED", error="invalid_era_record")
            return None

        head = self.chain.finalized_block()
        scan_end = min(head, start + period)
        if scan_end >= start:
            matched = self._find_matching_burn_in_range(
                start, scan_end, recorded_amount
            )
            if matched is not None:
                prev_unspent = list(row.get("unspent", []))
                prev_unspent.append(matched)
                self._write(
                    state="BURNED",
                    block=matched["block"],
                    extrinsic_id=matched["extrinsic_id"],
                    unspent=prev_unspent,
                )
                if (
                    matched["amount_rao"] >= amount_rao
                    and matched["block"] >= min_block
                ):
                    return {
                        "schema": SCHEMA,
                        "code": FeePostCode.BURNED.value,
                        "extrinsic_id": matched["extrinsic_id"],
                        "block": matched["block"],
                    }
                return None
        if head > start + period:
            self._write(state="EXPIRED")
            return None
        return {
            "schema": SCHEMA,
            "code": FeePostCode.AMBIGUOUS.value,
            "retry_after_s": 12,
        }


def _cli_status(poster_dir: Path) -> int:
    files = sorted(poster_dir.glob("fee-burn-*.json")) if poster_dir.is_dir() else []
    records = []
    for f in files:
        with contextlib.suppress(OSError, ValueError):
            records.append(
                {"file": str(f), **json.loads(f.read_text(encoding="utf-8"))}
            )
    print(
        json.dumps(
            {"poster_dir": str(poster_dir), "count": len(records), "records": records},
            indent=2,
            sort_keys=True,
        )
    )
    return 0


def _cli_clear(poster_dir: Path, *, target_file: Path | None, force: bool) -> int:
    files = (
        [target_file]
        if target_file is not None
        else (sorted(poster_dir.glob("fee-burn-*.json")) if poster_dir.is_dir() else [])
    )
    cleared = []
    for f in files:
        if not f.is_file() or f.is_symlink():
            continue
        lock_path = f.parent / f".{f.stem}.lock"
        with exclusive_file_lock(lock_path, blocking=True):
            row = json.loads(f.read_text(encoding="utf-8"))
            st = row.get("state")
            if st in PENDING and not force:
                raise SystemExit(
                    f"refusing to clear {f} in active state {st!r} without --force "
                    "(verify on-chain first so you do not double-burn)"
                )
            row["state"] = "IDLE"
            tmp = f.with_suffix(".tmp")
            fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(row, handle, sort_keys=True)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(tmp, f)
            cleared.append(str(f))
    print(json.dumps({"cleared": cleared}, indent=2))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m carbon.chain.fee_poster",
        description="Inspect or reset local miner submission-burn state (~/.carbon/fee-burns).",
    )
    parser.add_argument(
        "--dir",
        type=Path,
        default=None,
        help="Poster directory (default: ~/.carbon/fee-burns or $CARBON_FEE_POSTER_DIR)",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("status", help="Show local unspent/pending submission burn state")
    clr = sub.add_parser(
        "clear",
        help="Reset pending poster state to IDLE while keeping unspent receipts",
    )
    clr.add_argument("--file", type=Path, default=None, help="Specific state file")
    clr.add_argument(
        "--force",
        action="store_true",
        help="Force reset of a PENDING/FINALIZED_UNVERIFIED state after checking chain",
    )
    args = parser.parse_args(argv)
    pdir = default_fee_poster_dir() if args.dir is None else args.dir.expanduser()
    if args.cmd == "status":
        return _cli_status(pdir)
    if args.cmd == "clear":
        return _cli_clear(pdir, target_file=args.file, force=bool(args.force))
    return 1


__all__ = [
    "DEFAULT_POSTER_DIR_ENV",
    "DONE",
    "ERA_PERIOD",
    "PENDING",
    "RANGE_CHUNK_BLOCKS",
    "SCHEMA",
    "FeePostCode",
    "FeePoster",
    "SdkFeeBurnChain",
    "default_fee_poster_dir",
    "main",
]


if __name__ == "__main__":
    sys.exit(main())
