"""Genesis- and finality-pinned reader & indexer (`carbon.chain.fee_burns`) for submission fee burns.

A miner pays an official submission fee directly on-chain in one atomic extrinsic:

    Utility.batch_all([
        SubtensorModule.add_stake_burn(
            hotkey=miner_hotkey_ss58,
            netuid=context.netuid,
            amount=fee_rao,
            limit=limit_price_rao,   # None or fill-or-kill price cap
        ),
        System.remark_with_event(
            remark=b"carbon.fee.v2|<netuid>|<challenge_id>|<receiver_ss58>|<miner_hotkey_ss58>"
        ),
    ])

Subtensor executes ``do_add_stake``/``do_add_stake_limit`` (``allow_partial=False``)
and ``do_burn_alpha`` inside one ``with_transaction`` rollback guard, emitting
``SubtensorModule.AddStakeBurn {netuid, hotkey, amount, alpha}`` while
``frame_system`` emits ``System.Remarked {sender, hash: blake2b_256(remark)}``.
Carbon never holds keys, custodies TAO/Alpha, or runs a buyback keeper.

Security invariants:
- Only **finalized** blocks on the pinned ``ChainContext.genesis_hash`` are read,
  with ``block_hash(0)`` and ``block_hash(block)`` verified before and after reading
  ``System.Events`` so a split RPC provider cannot spoof finality or chain identity.
- ``SubtensorModule.AddStakeBurn`` is decoded from named fields only
  (``{netuid, hotkey, amount, alpha}``) so positional field reordering can never
  swap ``amount`` and ``alpha``.
- Any extrinsic lacking ``System.ExtrinsicSuccess`` or carrying
  ``System.ExtrinsicFailed``, ``Utility.BatchInterrupted``, ``Utility.ItemFailed``,
  or failed ``Proxy.ProxyExecuted`` is rejected unconditionally.
- Exactly one ``SubtensorModule.AddStakeBurn`` on ``context.netuid`` and one
  ``System.Remarked`` must appear in the extrinsic, eliminating multi-call ambiguity.
- Every RPC call is bounded by an explicit ``asyncio.wait_for`` deadline and
  non-blocking executor shutdown so a hung WebSocket never wedges request locks
  or backfill semaphores.
- No scoring, KOTH, Crown, bank, or weight module may import this module
  (enforced by ``tests/invariants/test_submission_fee_unreachable.py``).
"""

from __future__ import annotations

import asyncio
import concurrent.futures
import contextlib
import hashlib
import os
import re
import threading
import time
from collections.abc import Sequence
from contextlib import aclosing
from dataclasses import dataclass
from importlib.metadata import version
from pathlib import Path

from .models import ChainContext, ChainFailure, FailureCode, hash256, identifier, uint
from .sdk import SDK_VERSION

try:
    import fcntl as _fcntl
except ImportError:  # pragma: no cover - native Windows fallback (`N5`)
    _fcntl = None  # type: ignore[assignment]

try:
    import msvcrt as _msvcrt
except ImportError:  # pragma: no cover - POSIX
    _msvcrt = None  # type: ignore[assignment]

REMARK_VERSION = "carbon.fee.v2"
EXTRINSIC_ID = re.compile(r"([0-9]{1,12})-([0-9]{1,6})\Z", re.ASCII)
_CHALLENGE_ID = re.compile(r"[a-z0-9][a-z0-9-]{0,63}\Z", re.ASCII)
_SS58 = re.compile(r"[1-9A-HJ-NP-Za-km-z]{46,48}\Z", re.ASCII)
_HEX32 = re.compile(r"0x[0-9a-f]{64}\Z", re.ASCII)

#: Default lookback ceiling (~3 days at 12s blocks) for on-demand finalized catch-up.
DEFAULT_MAX_LOOKBACK_BLOCKS = 21_600
#: Maximum concurrent single-block backfill RPC calls across all request threads.
MAX_CONCURRENT_BACKFILLS = 2
#: Per-RPC operation timeout so hung sockets fail closed (503) without wedging locks.
DEFAULT_RPC_TIMEOUT_S = 15.0
#: Minimum Subtensor runtime spec_version carrying `SubtensorModule.add_stake_burn`
#: (aligned with `carbon_miner_signer.fee_burn.DEFAULT_RECORD`, spec >= 497).
MIN_RUNTIME_SPEC_VERSION = 497

DEFAULT_ARCHIVE_ENDPOINTS: dict[str, tuple[str, ...]] = {
    "finney": ("wss://archive.chain.opentensor.ai:443",),
    "testnet": ("wss://test.finney.opentensor.ai:443",),
}

_B58_ALPHABET = b"123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
_B58_INDEX = {chr(b): idx for idx, b in enumerate(_B58_ALPHABET)}
_VERIFIED_RUNTIME_GUARD = threading.Lock()
_VERIFIED_RUNTIMES: set[tuple[str, int]] = set()


class FeeBurnUnavailable(RuntimeError):
    """Chain RPC or finality read failed: validator-side infrastructure, never a
    candidate refusal or a spent burn."""


class FeeBurnNotFinalized(ValueError):
    """The named block is ahead of the validator's observed finalized head."""


@dataclass(frozen=True, slots=True)
class ObservedFeeBurn:
    """One verified atomic buyback-and-burn extrinsic in a finalized block.

    Note: ``payer`` records the ``System.Remarked`` origin account for audit
    visibility only; Carbon never sends on-chain refunds and never uses ``payer``
    as an authorization identity (authorization binds ``hotkey`` + ``remark_hash``).
    """

    extrinsic_id: str
    block: int
    extrinsic_idx: int
    block_hash: str
    netuid: int
    hotkey: str
    payer: str
    amount_rao: int
    alpha_burned_rao: int
    remark_hash: str

    def __post_init__(self) -> None:
        parsed = parse_extrinsic_id(self.extrinsic_id)
        if parsed != (self.block, self.extrinsic_idx):
            raise ValueError("extrinsic_id does not match (block, extrinsic_idx)")
        uint(self.block)
        uint(self.extrinsic_idx)
        hash256(self.block_hash)
        if type(self.netuid) is not int or not 0 <= self.netuid <= 65535:
            raise ValueError("invalid netuid")
        identifier(self.hotkey)
        identifier(self.payer)
        if type(self.amount_rao) is not int or self.amount_rao <= 0:
            raise ValueError("amount_rao must be positive")
        if type(self.alpha_burned_rao) is not int or self.alpha_burned_rao <= 0:
            raise ValueError("alpha_burned_rao must be positive")
        hash256(self.remark_hash)


def _encode_ss58_42(pubkey: bytes) -> str:
    """Pure-stdlib Substrate SS58 (network prefix 42) encoder for a 32-byte AccountId."""
    payload = b"\x2a" + pubkey
    checksum = hashlib.blake2b(b"SS58PRE" + payload, digest_size=64).digest()[:2]
    data = payload + checksum
    num = int.from_bytes(data, "big")
    chars = bytearray()
    while num > 0:
        num, rem = divmod(num, 58)
        chars.append(_B58_ALPHABET[rem])
    chars.reverse()
    leading_zeros = len(data) - len(data.lstrip(b"\x00"))
    return (b"1" * leading_zeros + bytes(chars)).decode("ascii")


def _decode_ss58_42(address: object) -> bytes | None:
    """Decode and verify a Substrate SS58 (prefix 42) address, or return None."""
    if type(address) is not str or _SS58.fullmatch(address) is None:
        return None
    num = 0
    for ch in address:
        idx = _B58_INDEX.get(ch)
        if idx is None:
            return None
        num = num * 58 + idx
    leading_zeros = len(address) - len(address.lstrip("1"))
    body = num.to_bytes((num.bit_length() + 7) // 8, "big") if num else b""
    raw = b"\x00" * leading_zeros + body
    if len(raw) != 35 or raw[0] != 42:
        return None
    pubkey, checksum = raw[1:33], raw[33:35]
    expected = hashlib.blake2b(b"SS58PRE" + raw[:33], digest_size=64).digest()[:2]
    if checksum != expected:
        return None
    return pubkey


def parse_extrinsic_id(value: object) -> tuple[int, int] | None:
    """Parse ``"<block>-<extrinsic_idx>"`` into ``(block, extrinsic_idx)``, or None."""
    if type(value) is not str:
        return None
    match = EXTRINSIC_ID.fullmatch(value)
    if match is None:
        return None
    block_s, idx_s = match.groups()
    if (len(block_s) > 1 and block_s.startswith("0")) or (
        len(idx_s) > 1 and idx_s.startswith("0")
    ):
        return None
    return int(block_s), int(idx_s)


def fee_remark(netuid: int, challenge_id: str, receiver: str, hotkey: str) -> bytes:
    """Canonical ASCII v2 remark bytes bound inside ``Utility.batch_all``.

    Binds ``(netuid, challenge_id, receiver, hotkey)`` while keeping Challenge
    ``version`` out of the remark so an unspent burn carries cleanly across a
    version flip on the same validator receiver while remaining unreplayable
    across different validator hosts.
    """
    if type(netuid) is not int or isinstance(netuid, bool) or not 0 <= netuid <= 65535:
        raise ValueError("invalid netuid")
    if type(challenge_id) is not str or _CHALLENGE_ID.fullmatch(challenge_id) is None:
        raise ValueError("invalid challenge_id")
    if _decode_ss58_42(receiver) is None:
        raise ValueError("invalid receiver ss58")
    if _decode_ss58_42(hotkey) is None:
        raise ValueError("invalid hotkey ss58")
    return f"{REMARK_VERSION}|{netuid}|{challenge_id}|{receiver}|{hotkey}".encode(
        "ascii"
    )


def fee_remark_hash(netuid: int, challenge_id: str, receiver: str, hotkey: str) -> str:
    """Substrate ``System.Remarked`` 32-byte BLAKE2b-256 digest (``0x<64 hex>``)."""
    raw = fee_remark(netuid, challenge_id, receiver, hotkey)
    return "0x" + hashlib.blake2b(raw, digest_size=32).hexdigest()


def parse_fee_remark(raw: object) -> dict[str, object] | None:
    """Parse canonical ``carbon.fee.v2|<netuid>|<challenge_id>|<receiver>|<hotkey>``."""
    if isinstance(raw, (bytes, bytearray)):
        try:
            text = bytes(raw).decode("ascii")
        except UnicodeDecodeError:
            return None
    elif type(raw) is str:
        if raw.startswith("0x"):
            try:
                text = bytes.fromhex(raw[2:]).decode("ascii")
            except (ValueError, UnicodeDecodeError):
                return None
        else:
            text = raw
    else:
        return None
    parts = text.split("|")
    if len(parts) != 5 or parts[0] != REMARK_VERSION:
        return None
    netuid_s, challenge_id, receiver, hotkey = parts[1], parts[2], parts[3], parts[4]
    if not netuid_s.isdigit() or (len(netuid_s) > 1 and netuid_s.startswith("0")):
        return None
    netuid = int(netuid_s)
    if (
        not 0 <= netuid <= 65535
        or _CHALLENGE_ID.fullmatch(challenge_id) is None
        or _decode_ss58_42(receiver) is None
        or _decode_ss58_42(hotkey) is None
    ):
        return None
    return {
        "netuid": netuid,
        "challenge_id": challenge_id,
        "receiver": receiver,
        "hotkey": hotkey,
    }


def _get(mapping: object, *keys: str) -> object:
    if isinstance(mapping, dict):
        for key in keys:
            if key in mapping:
                return mapping[key]
    return None


def _rao_int(value: object) -> int | None:
    if type(value) is int and not isinstance(value, bool) and value >= 0:
        return value
    if not isinstance(value, bool) and hasattr(value, "rao"):
        rao = getattr(value, "rao", None)
        if type(rao) is int and not isinstance(rao, bool) and rao >= 0:
            return rao
    return None


def _account_ss58(raw: object) -> str | None:
    if isinstance(raw, (list, tuple)) and len(raw) == 1:
        raw = raw[0]
    if type(raw) is str:
        if _decode_ss58_42(raw) is not None:
            return raw
        if _HEX32.fullmatch(raw.lower()) is not None:
            encoded = _encode_ss58_42(bytes.fromhex(raw[2:]))
            return encoded if _decode_ss58_42(encoded) is not None else None
    elif (isinstance(raw, (bytes, bytearray)) and len(raw) == 32) or (
        isinstance(raw, (list, tuple))
        and len(raw) == 32
        and all(
            type(b) is int and not isinstance(b, bool) and 0 <= b <= 255 for b in raw
        )
    ):
        encoded = _encode_ss58_42(bytes(raw))
        return encoded if _decode_ss58_42(encoded) is not None else None
    return None


def _hash_hex(raw: object) -> str | None:
    if isinstance(raw, (list, tuple)) and len(raw) == 1:
        raw = raw[0]
    if type(raw) is str:
        candidate = raw.lower() if raw.startswith("0x") else "0x" + raw.lower()
        return candidate if _HEX32.fullmatch(candidate) is not None else None
    if isinstance(raw, (bytes, bytearray)) and len(raw) == 32:
        return "0x" + bytes(raw).hex()
    if (
        isinstance(raw, (list, tuple))
        and len(raw) == 32
        and all(
            type(b) is int and not isinstance(b, bool) and 0 <= b <= 255 for b in raw
        )
    ):
        return "0x" + bytes(raw).hex()
    return None


def _extrinsic_index(record: object) -> int | None:
    if not isinstance(record, dict):
        return None
    idx = record.get("extrinsic_idx")
    if idx is None:
        phase = record.get("phase")
        if isinstance(phase, dict):
            idx = phase.get("ApplyExtrinsic")
    return idx if type(idx) is int and not isinstance(idx, bool) and idx >= 0 else None


def _decode_add_stake_burn(attrs: object) -> tuple[int, str, int, int] | None:
    """Decode ``SubtensorModule.AddStakeBurn`` from named dict attributes ONLY.

    Verified against live Subtensor runtime 497 (Testnet #8,536,949-6):
    ``{"netuid": u16, "hotkey": AccountId32, "amount": u64, "alpha": u64}``.
    Positional list/tuple decoding is intentionally forbidden so a future field
    reordering can never swap ``amount`` and ``alpha`` fail-open.
    """
    if not isinstance(attrs, dict):
        return None
    netuid = attrs.get("netuid")
    hotkey = _account_ss58(attrs.get("hotkey"))
    amount = _rao_int(attrs.get("amount"))
    alpha = _rao_int(attrs.get("alpha"))
    if (
        type(netuid) is not int
        or isinstance(netuid, bool)
        or not 0 <= netuid <= 65535
        or hotkey is None
        or amount is None
        or amount <= 0
        or alpha is None
        or alpha <= 0
    ):
        return None
    return netuid, hotkey, amount, alpha


def _decode_remarked(attrs: object) -> tuple[str, str] | None:
    if isinstance(attrs, dict):
        sender = _account_ss58(_get(attrs, "sender", "who", "account"))
        digest = _hash_hex(_get(attrs, "hash", "remark_hash"))
    elif isinstance(attrs, (list, tuple)) and len(attrs) == 2:
        sender = _account_ss58(attrs[0])
        digest = _hash_hex(attrs[1])
    else:
        return None
    if sender is None or digest is None:
        return None
    return sender, digest


def _proxy_failed(attrs: object) -> bool:
    if isinstance(attrs, dict):
        result = _get(attrs, "result")
    elif isinstance(attrs, (list, tuple)) and len(attrs) == 1:
        result = attrs[0]
    else:
        return True
    if isinstance(result, dict):
        return (
            "Err" in result
            or "err" in result
            or ("Ok" not in result and "ok" not in result)
        )
    if type(result) is str:
        return result.lower() != "ok"
    return False


def extract_block_fee_burns(
    records: object,
    *,
    block: int,
    block_hash: str,
    netuid: int,
) -> tuple[ObservedFeeBurn, ...]:
    """Extract all valid atomic ``AddStakeBurn`` + ``Remarked`` extrinsics in ``block``."""
    uint(block)
    normalized_bhash = hash256(block_hash)
    if type(netuid) is not int or isinstance(netuid, bool) or not 0 <= netuid <= 65535:
        raise ValueError("invalid netuid")
    if not isinstance(records, list):
        raise FeeBurnUnavailable("fee_events_malformed")

    grouped: dict[int, list[dict]] = {}
    for record in records:
        idx = _extrinsic_index(record)
        if idx is not None:
            grouped.setdefault(idx, []).append(record)

    found: list[ObservedFeeBurn] = []
    for idx in sorted(grouped):
        succeeded = False
        aborted = False
        burns: list[tuple[int, str, int, int]] = []
        remarks: list[tuple[str, str]] = []

        for record in grouped[idx]:
            inner = _get(record, "event")
            ev = inner if isinstance(inner, dict) else record
            module = _get(ev, "module_id", "pallet", "module")
            name = _get(ev, "event_id", "event", "name")
            attrs = _get(ev, "attributes", "params", "data")

            if module == "System" and name == "ExtrinsicSuccess":
                succeeded = True
            elif (
                (module == "System" and name == "ExtrinsicFailed")
                or (module == "Utility" and name in ("BatchInterrupted", "ItemFailed"))
                or (
                    module == "Proxy"
                    and name == "ProxyExecuted"
                    and _proxy_failed(attrs)
                )
            ):
                aborted = True
            elif module == "SubtensorModule" and name == "AddStakeBurn":
                decoded_burn = _decode_add_stake_burn(attrs)
                if decoded_burn is None:
                    aborted = True
                elif decoded_burn[0] == netuid:
                    burns.append(decoded_burn)
                else:
                    aborted = True
            elif module == "System" and name == "Remarked":
                decoded_remark = _decode_remarked(attrs)
                if decoded_remark is None:
                    aborted = True
                else:
                    remarks.append(decoded_remark)

        if not succeeded or aborted or len(burns) != 1 or len(remarks) != 1:
            continue

        burn_netuid, hotkey, amount_rao, alpha_rao = burns[0]
        payer, remark_digest = remarks[0]
        found.append(
            ObservedFeeBurn(
                extrinsic_id=f"{block}-{idx}",
                block=block,
                extrinsic_idx=idx,
                block_hash=normalized_bhash,
                netuid=burn_netuid,
                hotkey=hotkey,
                payer=payer,
                amount_rao=amount_rao,
                alpha_burned_rao=alpha_rao,
                remark_hash=remark_digest,
            )
        )
    return tuple(found)


@contextlib.contextmanager
def exclusive_file_lock(lock_path: Path, *, blocking: bool = True):
    """Cross-process exclusive file lock (`fcntl.flock` on POSIX, `msvcrt` on Windows)."""
    lock_path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd = os.open(lock_path, os.O_RDWR | os.O_CREAT, 0o600)
    locked = False
    try:
        if _fcntl is not None:
            flags = _fcntl.LOCK_EX | (0 if blocking else _fcntl.LOCK_NB)
            _fcntl.flock(fd, flags)
            locked = True
        elif _msvcrt is not None:  # pragma: no cover - Windows fallback
            os.lseek(fd, 0, os.SEEK_SET)
            if os.fstat(fd).st_size == 0:
                os.write(fd, b"\0")
                os.lseek(fd, 0, os.SEEK_SET)
            mode = _msvcrt.LK_LOCK if blocking else _msvcrt.LK_NBLCK
            try:
                _msvcrt.locking(fd, mode, 1)
            except OSError as exc:
                raise BlockingIOError("file lock busy") from exc
            locked = True
        yield fd
    finally:
        if locked:
            with contextlib.suppress(OSError):
                if _fcntl is not None:
                    _fcntl.flock(fd, _fcntl.LOCK_UN)
                elif _msvcrt is not None:  # pragma: no cover
                    os.lseek(fd, 0, os.SEEK_SET)
                    _msvcrt.locking(fd, _msvcrt.LK_UNLCK, 1)
        os.close(fd)


async def _verify_runtime_once(substrate, endpoint: str) -> None:
    """Verify runtime spec_version and SDK call descriptors once per (endpoint, substrate_cls)."""
    from bittensor._generated import calls

    if not hasattr(calls, "SubtensorModule") or not hasattr(
        calls.SubtensorModule, "add_stake_burn"
    ):
        raise ChainFailure(FailureCode.UNSUPPORTED)
    spec_attr = getattr(substrate, "spec_version", None)
    if type(spec_attr) is int:
        if spec_attr < MIN_RUNTIME_SPEC_VERSION:
            raise ChainFailure(FailureCode.UNSUPPORTED)
        with _VERIFIED_RUNTIME_GUARD:
            _VERIFIED_RUNTIMES.add((endpoint, spec_attr))
        return
    with _VERIFIED_RUNTIME_GUARD:
        if any(
            ep == endpoint and sp >= MIN_RUNTIME_SPEC_VERSION
            for ep, sp in _VERIFIED_RUNTIMES
        ):
            return
    spec_val = None
    if callable(spec_attr):
        maybe = spec_attr()
        spec_val = await maybe if asyncio.iscoroutine(maybe) else maybe
    if spec_val is not None:
        if type(spec_val) is not int or spec_val < MIN_RUNTIME_SPEC_VERSION:
            raise ChainFailure(FailureCode.UNSUPPORTED)
        with _VERIFIED_RUNTIME_GUARD:
            _VERIFIED_RUNTIMES.add((endpoint, spec_val))


def _resolve_archive_endpoints(
    context: ChainContext, archive_endpoints: Sequence[str] | None
) -> list[str]:
    if archive_endpoints is None:
        return list(DEFAULT_ARCHIVE_ENDPOINTS.get(context.network, ()))
    if isinstance(archive_endpoints, (str, bytes, bytearray)) or not isinstance(
        archive_endpoints, (list, tuple)
    ):
        raise TypeError(
            "archive_endpoints must be a list or tuple of ws/wss URLs, not a scalar/string"
        )
    resolved: list[str] = []
    for ep in archive_endpoints:
        if type(ep) is not str or not ep.strip():
            raise ValueError("archive_endpoints entries must be non-empty strings")
        cleaned = ep.strip()
        if not cleaned.startswith(("wss://", "ws://")):
            raise ValueError(
                f"archive endpoint must start with ws:// or wss://: {ep!r}"
            )
        resolved.append(cleaned)
    return resolved


async def _close_quietly(obj) -> None:
    with contextlib.suppress(Exception):
        await asyncio.wait_for(obj.close(), timeout=3.0)


async def _fetch_finalized_head(
    context: ChainContext,
    *,
    archive_endpoints: tuple[str, ...] = (),
) -> int:
    if version("bittensor") != SDK_VERSION:
        raise ChainFailure(FailureCode.UNSUPPORTED)
    import bittensor as bt

    substrate = bt.RpcSubstrate(
        context.endpoint,
        fallback_endpoints=[],
        archive_endpoints=_resolve_archive_endpoints(context, archive_endpoints),
        retry_forever=False,
    )
    client = bt.Client(context.endpoint, substrate=substrate)
    try:
        await substrate.connect()
        if hash256(await substrate.block_hash(0)) != context.genesis_hash:
            raise ChainFailure(FailureCode.IDENTITY)
        await _verify_runtime_once(substrate, context.endpoint)
        async with aclosing(client.blocks(finalized=True)) as headers:
            header = await anext(headers)
        return uint(header.number)
    finally:
        await _close_quietly(client)


async def _fetch_finalized_block_events(
    context: ChainContext,
    block: int,
    *,
    archive_endpoints: tuple[str, ...] = (),
) -> tuple[int, str, list]:
    """Return ``(finalized_head, block_hash, events)`` at finalized ``block``."""
    uint(block)
    if version("bittensor") != SDK_VERSION:
        raise ChainFailure(FailureCode.UNSUPPORTED)
    import bittensor as bt

    substrate = bt.RpcSubstrate(
        context.endpoint,
        fallback_endpoints=[],
        archive_endpoints=_resolve_archive_endpoints(context, archive_endpoints),
        retry_forever=False,
    )
    client = bt.Client(context.endpoint, substrate=substrate)
    try:
        await substrate.connect()
        genesis = hash256(await substrate.block_hash(0))
        if genesis != context.genesis_hash:
            raise ChainFailure(FailureCode.IDENTITY)
        await _verify_runtime_once(substrate, context.endpoint)
        async with aclosing(client.blocks(finalized=True)) as headers:
            header = await anext(headers)
        finalized_head = uint(header.number)
        if block > finalized_head:
            raise FeeBurnNotFinalized(f"block {block} > finalized {finalized_head}")
        raw_bhash = await substrate.block_hash(block)
        if raw_bhash is None:
            raise ChainFailure(FailureCode.UNAVAILABLE)
        bhash = hash256(raw_bhash)
        events = await substrate.events(bhash)
        if events is None:
            # Pruned non-archive state must fail closed (503), never look empty.
            raise ChainFailure(FailureCode.UNAVAILABLE)
        if (
            hash256(await substrate.block_hash(block)) != bhash
            or hash256(await substrate.block_hash(0)) != genesis
        ):
            raise ChainFailure(FailureCode.IDENTITY)
        if not isinstance(events, list):
            raise ChainFailure(FailureCode.MALFORMED)
        return finalized_head, bhash, events
    finally:
        await _close_quietly(client)


async def _fetch_finalized_range_events(
    context: ChainContext,
    start_block: int,
    end_block: int,
    *,
    archive_endpoints: tuple[str, ...] = (),
) -> tuple[int, dict[int, tuple[str, list]]]:
    """Fetch finalized ``(block_hash, events)`` across ``[start_block, min(end_block, head)]``
    over a single WebSocket session so mortal-era reconciliation never opens 128 sockets.
    """
    uint(start_block)
    uint(end_block)
    if version("bittensor") != SDK_VERSION:
        raise ChainFailure(FailureCode.UNSUPPORTED)
    import bittensor as bt

    substrate = bt.RpcSubstrate(
        context.endpoint,
        fallback_endpoints=[],
        archive_endpoints=_resolve_archive_endpoints(context, archive_endpoints),
        retry_forever=False,
    )
    client = bt.Client(context.endpoint, substrate=substrate)
    try:
        await substrate.connect()
        genesis = hash256(await substrate.block_hash(0))
        if genesis != context.genesis_hash:
            raise ChainFailure(FailureCode.IDENTITY)
        await _verify_runtime_once(substrate, context.endpoint)
        async with aclosing(client.blocks(finalized=True)) as headers:
            header = await anext(headers)
        finalized_head = uint(header.number)
        upper = min(end_block, finalized_head)
        results: dict[int, tuple[str, list]] = {}
        for blk in range(start_block, upper + 1):
            raw_bhash = await substrate.block_hash(blk)
            if raw_bhash is None:
                raise ChainFailure(FailureCode.UNAVAILABLE)
            bhash = hash256(raw_bhash)
            events = await substrate.events(bhash)
            if events is None:
                raise ChainFailure(FailureCode.UNAVAILABLE)
            if not isinstance(events, list):
                raise ChainFailure(FailureCode.MALFORMED)
            results[blk] = (bhash, events)
        if hash256(await substrate.block_hash(0)) != genesis:
            raise ChainFailure(FailureCode.IDENTITY)
        if upper >= start_block:
            last_bhash = results[upper][0]
            if hash256(await substrate.block_hash(upper)) != last_bhash:
                raise ChainFailure(FailureCode.IDENTITY)
        return finalized_head, results
    finally:
        await _close_quietly(client)


def _run_coro_bounded(coro, *, timeout_s: float):
    """Run ``coro`` with an ``asyncio.wait_for`` deadline and non-blocking pool exit."""

    async def _wrapped():
        return await asyncio.wait_for(coro, timeout=timeout_s)

    pool = concurrent.futures.ThreadPoolExecutor(max_workers=1)
    try:
        fut = pool.submit(asyncio.run, _wrapped())
        return fut.result(timeout=timeout_s + 5.0)
    finally:
        pool.shutdown(wait=False, cancel_futures=True)


class ChainFeeBurnReader:
    """Synchronous/worker-isolated finalized block reader for submission fee burns."""

    def __init__(
        self,
        context: ChainContext,
        *,
        fetch_block=None,
        fetch_head=None,
        fetch_range=None,
        archive_endpoints: tuple[str, ...] | list[str] | None = None,
        rpc_timeout_s: float = DEFAULT_RPC_TIMEOUT_S,
    ) -> None:
        if type(context) is not ChainContext:
            raise TypeError("a ChainContext is required")
        self.context = context
        self.archive_endpoints = tuple(
            _resolve_archive_endpoints(context, archive_endpoints)
        )
        self.rpc_timeout_s = max(1.0, float(rpc_timeout_s))
        self._custom_fetch_block = fetch_block
        self._custom_fetch_head = fetch_head
        self._custom_fetch_range = fetch_range

    def finalized_head(self) -> int:
        try:
            coro = (
                self._custom_fetch_head(self.context)
                if self._custom_fetch_head is not None
                else _fetch_finalized_head(
                    self.context, archive_endpoints=self.archive_endpoints
                )
            )
            head = _run_coro_bounded(coro, timeout_s=self.rpc_timeout_s)
        except ChainFailure as failure:
            raise FeeBurnUnavailable(str(failure)) from None
        except Exception:  # noqa: BLE001
            raise FeeBurnUnavailable("fee_finalized_head_failed") from None
        if type(head) is not int or isinstance(head, bool) or head < 0:
            raise FeeBurnUnavailable("fee_finalized_head_malformed")
        return head

    def read_block(self, block: int) -> tuple[int, tuple[ObservedFeeBurn, ...]]:
        """Return ``(finalized_head, burns_in_block)`` for finalized ``block``."""
        if type(block) is not int or isinstance(block, bool) or block < 0:
            raise ValueError("block must be a non-negative int")
        try:
            coro = (
                self._custom_fetch_block(self.context, block)
                if self._custom_fetch_block is not None
                else _fetch_finalized_block_events(
                    self.context, block, archive_endpoints=self.archive_endpoints
                )
            )
            finalized_head, bhash, events = _run_coro_bounded(
                coro, timeout_s=self.rpc_timeout_s
            )
        except FeeBurnNotFinalized:
            raise
        except ChainFailure as failure:
            raise FeeBurnUnavailable(str(failure)) from None
        except Exception:  # noqa: BLE001
            raise FeeBurnUnavailable("fee_block_events_failed") from None
        if type(finalized_head) is not int or block > finalized_head:
            raise FeeBurnNotFinalized(f"block {block} > finalized {finalized_head}")
        burns = extract_block_fee_burns(
            events,
            block=block,
            block_hash=bhash,
            netuid=self.context.netuid,
        )
        return finalized_head, burns

    def read_blocks_range(
        self, start_block: int, end_block: int
    ) -> tuple[int, dict[int, tuple[ObservedFeeBurn, ...]]]:
        """Return ``(finalized_head, {block: burns})`` across ``[start_block, min(end_block, head)]``."""
        if (
            type(start_block) is not int
            or isinstance(start_block, bool)
            or start_block < 0
            or type(end_block) is not int
            or isinstance(end_block, bool)
            or end_block < start_block
        ):
            raise ValueError("invalid block range")
        if self._custom_fetch_range is None and self._custom_fetch_block is not None:
            head = self.finalized_head()
            upper = min(end_block, head)
            out: dict[int, tuple[ObservedFeeBurn, ...]] = {}
            for blk in range(start_block, upper + 1):
                _, burns = self.read_block(blk)
                out[blk] = burns
            return head, out

        span = end_block - start_block + 1
        range_timeout = min(60.0, max(self.rpc_timeout_s, 5.0 + 0.35 * span))
        try:
            coro = (
                self._custom_fetch_range(self.context, start_block, end_block)
                if self._custom_fetch_range is not None
                else _fetch_finalized_range_events(
                    self.context,
                    start_block,
                    end_block,
                    archive_endpoints=self.archive_endpoints,
                )
            )
            finalized_head, raw_map = _run_coro_bounded(coro, timeout_s=range_timeout)
        except ChainFailure as failure:
            raise FeeBurnUnavailable(str(failure)) from None
        except Exception:  # noqa: BLE001
            raise FeeBurnUnavailable("fee_range_events_failed") from None
        decoded: dict[int, tuple[ObservedFeeBurn, ...]] = {}
        for blk, (bhash, events) in raw_map.items():
            decoded[int(blk)] = extract_block_fee_burns(
                events,
                block=int(blk),
                block_hash=bhash,
                netuid=self.context.netuid,
            )
        return int(finalized_head), decoded


class FinalizedBurnIndexer:
    """Background finalized-block tailer + bounded semaphore-guarded catch-up."""

    def __init__(
        self,
        reader: ChainFeeBurnReader,
        ledger,
        *,
        max_lookback_blocks: int = DEFAULT_MAX_LOOKBACK_BLOCKS,
        max_batch_blocks: int = 32,
        poll_interval_s: float = 12.0,
        log_fn=None,
    ) -> None:
        if type(reader) is not ChainFeeBurnReader:
            raise TypeError("a ChainFeeBurnReader is required")
        if type(max_lookback_blocks) is not int or max_lookback_blocks < 1:
            raise ValueError("max_lookback_blocks must be >= 1")
        self.reader = reader
        self.ledger = ledger
        self.max_lookback_blocks = max_lookback_blocks
        self.max_batch_blocks = max_batch_blocks
        self.poll_interval_s = poll_interval_s
        self._log_fn = log_fn
        self._backfill_slots = threading.BoundedSemaphore(MAX_CONCURRENT_BACKFILLS)
        self._poll_lock = threading.Lock()
        self._lifecycle_lock = threading.Lock()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self.last_ok_monotonic: float | None = None
        self.consecutive_failures: int = 0
        self.last_error: str | None = None

    def update_lookback(self, max_lookback_blocks: int) -> None:
        if type(max_lookback_blocks) is int and max_lookback_blocks >= 1:
            self.max_lookback_blocks = max_lookback_blocks

    def _emit_log(self, event: str, **fields: object) -> None:
        if callable(self._log_fn):
            with contextlib.suppress(Exception):
                self._log_fn(event, **fields)

    def poll_once(self, *, known_finalized_head: int | None = None) -> int:
        """Advance sequential finalized indexing by up to ``max_batch_blocks``."""
        if not self._poll_lock.acquire(blocking=False):
            return 0
        try:
            head = (
                self.reader.finalized_head()
                if known_finalized_head is None
                else known_finalized_head
            )
            cursor = self.ledger.indexer_cursor()
            if cursor is None:
                self.ledger.advance_indexer_cursor(head)
                self.last_ok_monotonic = time.monotonic()
                self.consecutive_failures = 0
                self.last_error = None
                return 0
            start = max(cursor + 1, head - self.max_lookback_blocks)
            end = min(head, start + self.max_batch_blocks - 1)
            indexed = 0
            for block in range(start, end + 1):
                if not self.ledger.is_block_indexed(block):
                    _, burns = self.reader.read_block(block)
                    self.ledger.record_indexed_block(block, burns)
                self.ledger.advance_indexer_cursor(block)
                indexed += 1
            prune_fn = getattr(self.ledger, "prune_indexed_blocks", None)
            eff_fn = getattr(self.ledger, "effective_prune_lookback", None)
            prune_span = (
                eff_fn(self.max_lookback_blocks)
                if callable(eff_fn)
                else self.max_lookback_blocks
            )
            if callable(prune_fn) and head > 2 * prune_span:
                prune_fn(head - 2 * prune_span)
            self.last_ok_monotonic = time.monotonic()
            self.consecutive_failures = 0
            self.last_error = None
            return indexed
        finally:
            self._poll_lock.release()

    def ensure_block(
        self,
        block: int,
        *,
        known_finalized_head: int | None = None,
        min_allowed_block: int = 0,
        max_lookback_blocks: int | None = None,
    ) -> None:
        """Ensure finalized ``block`` has been indexed into ``self.ledger``."""
        if type(block) is not int or isinstance(block, bool) or block < 0:
            raise ValueError("invalid block")
        self.ensure_running()
        effective_lookback = (
            self.max_lookback_blocks
            if max_lookback_blocks is None
            else max(1, int(max_lookback_blocks))
        )
        if block < min_allowed_block:
            return
        if self.ledger.is_block_indexed(block):
            return
        if known_finalized_head is not None and block > known_finalized_head:
            raise FeeBurnNotFinalized(
                f"block {block} > finalized {known_finalized_head}"
            )
        if (
            known_finalized_head is not None
            and known_finalized_head - block > effective_lookback
        ):
            return
        acquired = self._backfill_slots.acquire(timeout=5.0)
        if not acquired:
            raise FeeBurnUnavailable("fee_backfill_busy")
        try:
            if self.ledger.is_block_indexed(block):
                return
            finalized_head, burns = self.reader.read_block(block)
            if finalized_head - block > effective_lookback:
                return
            self.ledger.record_indexed_block(block, burns)
        finally:
            self._backfill_slots.release()

    def health(self) -> dict[str, object]:
        """Return live indexer health snapshot (`H4`)."""
        thread = self._thread
        alive = bool(thread is not None and thread.is_alive())
        now = time.monotonic()
        age_s = (
            None
            if self.last_ok_monotonic is None
            else round(max(0.0, now - self.last_ok_monotonic), 3)
        )
        stale_limit = max(60.0, 5.0 * self.poll_interval_s)
        degraded = (
            self.consecutive_failures >= 3
            or (not alive and not self._stop.is_set() and thread is not None)
            or (age_s is not None and age_s > stale_limit)
        )
        return {
            "alive": alive,
            "degraded": degraded,
            "consecutive_failures": self.consecutive_failures,
            "last_ok_age_s": age_s,
            "last_error": self.last_error,
        }

    def ensure_running(self) -> dict[str, object]:
        """Watchdog: restart a dead daemon thread and emit degraded health alerts (`H4`)."""
        with self._lifecycle_lock:
            if (
                self._thread is not None
                and not self._thread.is_alive()
                and not self._stop.is_set()
            ):
                self._emit_log("fee_indexer_watchdog_restart")
                thread = threading.Thread(
                    target=self._loop, name="carbon-fee-burn-indexer", daemon=True
                )
                self._thread = thread
                thread.start()
        snap = self.health()
        if snap["degraded"]:
            self._emit_log(
                "fee_indexer_degraded",
                consecutive_failures=snap["consecutive_failures"],
                last_ok_age_s=snap["last_ok_age_s"],
                last_error=snap["last_error"],
            )
        return snap

    def start(self) -> FinalizedBurnIndexer:
        with self._lifecycle_lock:
            if self._thread is not None and self._thread.is_alive():
                return self
            self._stop.clear()
            thread = threading.Thread(
                target=self._loop, name="carbon-fee-burn-indexer", daemon=True
            )
            self._thread = thread
            thread.start()
            return self

    def stop(self, timeout: float = 5.0) -> None:
        with self._lifecycle_lock:
            self._stop.set()
            thread, self._thread = self._thread, None
        if thread is not None:
            thread.join(timeout=timeout)

    def _loop(self) -> None:
        while not self._stop.is_set():
            try:
                self.poll_once()
            except Exception as exc:  # noqa: BLE001 - logged & retried next tick
                self.consecutive_failures += 1
                self.last_error = f"{type(exc).__name__}:{exc}"
                self._emit_log(
                    "fee_indexer_poll_error",
                    consecutive_failures=self.consecutive_failures,
                    error=self.last_error,
                )
            self._stop.wait(self.poll_interval_s)


__all__ = [
    "DEFAULT_ARCHIVE_ENDPOINTS",
    "DEFAULT_MAX_LOOKBACK_BLOCKS",
    "DEFAULT_RPC_TIMEOUT_S",
    "EXTRINSIC_ID",
    "MAX_CONCURRENT_BACKFILLS",
    "MIN_RUNTIME_SPEC_VERSION",
    "REMARK_VERSION",
    "ChainFeeBurnReader",
    "FeeBurnNotFinalized",
    "FeeBurnUnavailable",
    "FinalizedBurnIndexer",
    "ObservedFeeBurn",
    "exclusive_file_lock",
    "extract_block_fee_burns",
    "fee_remark",
    "fee_remark_hash",
    "parse_extrinsic_id",
    "parse_fee_remark",
]
