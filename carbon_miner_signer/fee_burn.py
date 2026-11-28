"""The signer's atomic TAO->Alpha submission burn extrinsic (`fee_burn`).

Reconstructs and checks ``Utility.batch_all([SubtensorModule.add_stake_burn,
System.remark_with_event])`` from structured fields offline without importing
``carbon``, opening a network connection, or requiring package-data files
(`B1`: `DEFAULT_RECORD` is embedded directly in-module so `pyproject.toml` and
worker `build_inputs.txt` hashes never move):

- Verifies the 32-byte ``AccountId32`` inside ``add_stake_burn`` matches the
  signer's ``hotkey`` and validates both ``receiver`` and ``hotkey`` SS58
  checksums inside ``carbon.fee.v2|<netuid>|<challenge_id>|<receiver>|<hotkey>``.
- Reconstructs exact SCALE bytes for ``Utility.batch_all`` (``0x0b02``),
  ``SubtensorModule.add_stake_burn`` (``0x0784``), and
  ``System.remark_with_event`` (``0x0007``), refusing unless ``unsigned.call_data``,
  pinned ``transaction_version``, ``min_spec_version``, and signed extension bytes
  match byte-for-byte.
- Enforces ``min_burn_rao <= amount_rao <= max_single_burn_rao`` (`1.0 TAO`
  hard ceiling aligned with validator `MAX_SUBMISSION_BURN_RAO`; CLI default
  `--max-single-fee-tao 0.10`) and
  ``partial_fee_rao + deposit_rao <= tx_fee_ceiling_rao`` with ``tip == 0``.
- Derives the 8-hex interactive TTY confirmation code from
  ``blake2b_256(signing_preimage)[-8:]`` so it cryptographically binds the exact
  TAO amount, limit price, receiver, challenge, nonce, and era.

This module imports nothing from ``carbon``.
"""

from __future__ import annotations

import copy
import datetime
import json
import os
import re
from dataclasses import dataclass
from enum import Enum
from hashlib import blake2b
from pathlib import Path

from .commitment import (
    CONFIRM_SECONDS,
    FEE_FIELDS,
    STANDARD_EXTENSIONS,
    UNSIGNED_FIELDS,
    _extension_parts,
    _int,
    compact,
)

OP = "fee_burn"
RECORD_SCHEMA = "carbon.miner-signer.fee-burn-record.v2"
LEDGER_SCHEMA = "carbon.miner-signer.fee-burn-ledger.v1"
REMARK_VERSION = "carbon.fee.v2"
AUTO_BUDGET_MARK = "DAILY_BUDGET_AUTO_CONFIRMED"

#: Embedded runtime-497 pinned record (`B1`: zero `pyproject.toml` edit).
DEFAULT_RECORD: dict[str, object] = {
    "schema": RECORD_SCHEMA,
    "authority": (
        "Pinned TAO->Alpha buyback-and-burn record (measured on Finney #9597065 "
        "spec 497 and Testnet #8536949 spec 497; OWNER-SUBMISSION-FEE-01)"
    ),
    "sdk": {"package": "bittensor", "version": "11.1.0"},
    "runtime": {
        "min_spec_version": 497,
        "transaction_version": 1,
    },
    "calls": {
        "batch_all": {
            "pallet": "Utility",
            "function": "batch_all",
            "pallet_index": 11,
            "call_index": 2,
        },
        "add_stake_burn": {
            "pallet": "SubtensorModule",
            "function": "add_stake_burn",
            "pallet_index": 7,
            "call_index": 132,
        },
        "remark_with_event": {
            "pallet": "System",
            "function": "remark_with_event",
            "pallet_index": 0,
            "call_index": 7,
        },
    },
    "extensions": [
        "CheckNonZeroSender",
        "CheckSpecVersion",
        "CheckTxVersion",
        "CheckGenesis",
        "CheckMortality",
        "CheckNonce",
        "CheckWeight",
        "ChargeTransactionPayment",
        "SudoTransactionExtension",
        "CheckShieldedTxValidity",
        "SubtensorTransactionExtension",
        "DrandPriority",
        "CheckMetadataHash",
    ],
    "zero_sized_extensions": [
        "SudoTransactionExtension",
        "CheckShieldedTxValidity",
        "SubtensorTransactionExtension",
        "DrandPriority",
    ],
    "networks": {
        "testnet": {
            "name": "testnet",
            "genesis_hash": "0x8f9cf856bf558a14440e75569c9e58594757048d7b3a84b5d25f6bd978263105",
            "netuid": 567,
            "tempo_blocks": 360,
        },
        "finney": {
            "name": "finney",
            "genesis_hash": "0x2f0555cc76fc2840a25a6ea3b9637146806f1f44b090c175ffde2a7e5ab36c03",
            "netuid": 116,
            "tempo_blocks": 360,
        },
    },
    "era": {"sdk_default_period": 128, "max_period": 128},
    "bounds": {
        "min_burn_rao": 2_100_000,
        "max_single_burn_rao": 1_000_000_000,
        "tx_fee_ceiling_rao": 5_000_000,
    },
}

#: Default CLI per-submission cap (`0.10 TAO`, `OWNER-SUBMISSION-FEE-01` A2 / `M4`).
DEFAULT_CLI_SINGLE_BURN_RAO = 100_000_000

_CHALLENGE_ID = re.compile(r"[a-z0-9][a-z0-9-]{0,63}\Z", re.ASCII)
_SS58 = re.compile(r"[1-9A-HJ-NP-Za-km-z]{46,48}\Z", re.ASCII)
_HASH = re.compile(r"0x[0-9a-f]{64}\Z", re.ASCII)
_HEX = re.compile(r"0x(?:[0-9a-f]{2})*\Z", re.ASCII)
_BASE58_ALPHABET = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
_BASE58_INDEX = {ch: idx for idx, ch in enumerate(_BASE58_ALPHABET)}

REQUEST_FIELDS = frozenset(
    {
        "protocol",
        "op",
        "netuid",
        "challenge_id",
        "receiver",
        "amount_rao",
        "limit_price_rao",
        "unsigned",
        "fee",
    }
)


class FeeBurnRefusal(str, Enum):
    """Closed refusal vocabulary for ``op == 'fee_burn'``."""

    MALFORMED_REQUEST = "MALFORMED_REQUEST"
    FEE_BURN_DISABLED = "FEE_BURN_DISABLED"
    NOT_A_FEE_BURN = "NOT_A_FEE_BURN"
    BAD_CHALLENGE = "BAD_CHALLENGE"
    BAD_RECEIVER = "BAD_RECEIVER"
    BAD_AMOUNT = "BAD_AMOUNT"
    AMOUNT_OVER_MAX = "AMOUNT_OVER_MAX"
    WRONG_NETUID = "WRONG_NETUID"
    WRONG_NETWORK = "WRONG_NETWORK"
    NONZERO_TIP = "NONZERO_TIP"
    IMMORTAL_ERA = "IMMORTAL_ERA"
    ERA_TOO_LONG = "ERA_TOO_LONG"
    PAYLOAD_MISMATCH = "PAYLOAD_MISMATCH"
    FEE_UNKNOWN = "FEE_UNKNOWN"
    FEE_OVER_CEILING = "FEE_OVER_CEILING"
    DAILY_BUDGET_EXCEEDED = "DAILY_BUDGET_EXCEEDED"
    STALE_CHAIN_CONTEXT = "STALE_CHAIN_CONTEXT"
    FEE_BURN_IN_FLIGHT = "FEE_BURN_IN_FLIGHT"
    NOT_CONFIRMED = "NOT_CONFIRMED"
    LEDGER_UNAVAILABLE = "LEDGER_UNAVAILABLE"


class FeeBurnRefused(Exception):
    def __init__(self, refusal: FeeBurnRefusal):
        self.refusal = refusal
        super().__init__(refusal.value)


@dataclass(frozen=True)
class FeeBurnPolicy:
    """Immutable startup configuration for ``fee_burn`` signing."""

    network: str
    genesis_hash: str
    netuid: int
    tempo_blocks: int
    max_era_period: int
    min_spec_version: int
    transaction_version: int
    batch_pallet_index: int
    batch_call_index: int
    burn_pallet_index: int
    burn_call_index: int
    remark_pallet_index: int
    remark_call_index: int
    extensions: tuple[str, ...]
    zero_sized_extensions: frozenset[str]
    min_burn_rao: int
    max_single_burn_rao: int
    tx_fee_ceiling_rao: int
    daily_budget_rao: int | None = None


def decode_ss58_account_id(address: str) -> bytes:
    """Decode a Substrate SS58 address (prefix 42) to its 32-byte AccountId32."""
    if type(address) is not str or _SS58.fullmatch(address) is None:
        raise ValueError("invalid ss58 address")
    num = 0
    for ch in address:
        num = num * 58 + _BASE58_INDEX[ch]
    leading_zeros = len(address) - len(address.lstrip("1"))
    body = num.to_bytes((num.bit_length() + 7) // 8, "big") if num else b""
    raw = b"\x00" * leading_zeros + body
    if len(raw) != 35 or raw[0] != 42:
        raise ValueError("unsupported ss58 prefix or length")
    pubkey, checksum = raw[1:33], raw[33:35]
    expected = blake2b(b"SS58PRE" + raw[:33], digest_size=64).digest()[:2]
    if checksum != expected:
        raise ValueError("ss58 checksum mismatch")
    return pubkey


def load_fee_burn_policy(
    network_name: str,
    *,
    record: dict | None = None,
    daily_budget_rao: int | None = None,
    max_single_burn_rao: int | None = None,
) -> FeeBurnPolicy:
    """Load pinned ``FeeBurnPolicy`` for ``network_name`` ('testnet' or 'finney')."""
    if record is None:
        record = copy.deepcopy(DEFAULT_RECORD)
    if type(record) is not dict or record.get("schema") != RECORD_SCHEMA:
        raise ValueError("unknown fee burn record schema")
    networks = record.get("networks") or {}
    if network_name not in networks:
        raise ValueError(f"unknown fee burn network {network_name!r}")
    net = networks[network_name]
    runtime = record.get("runtime") or {}
    min_spec = runtime.get("min_spec_version", 497)
    tx_ver = runtime.get("transaction_version", 1)
    if not _int(min_spec, 1, 2**32 - 1) or not _int(tx_ver, 1, 2**32 - 1):
        raise ValueError("invalid runtime version pins")
    calls = record["calls"]
    era = record["era"]
    bounds = record["bounds"]
    extensions = tuple(record["extensions"])
    zero = frozenset(record["zero_sized_extensions"])
    unknown = [
        name
        for name in extensions
        if name not in STANDARD_EXTENSIONS and name not in zero
    ]
    if unknown:
        raise ValueError("unrecorded signed extensions: " + ", ".join(unknown))
    if not _HASH.fullmatch(net["genesis_hash"]):
        raise ValueError("pinned genesis hash is malformed")
    period = era["max_period"]
    if not _int(period, 4, 65536) or period & (period - 1):
        raise ValueError("max_period must be a power of two")
    hard_max = bounds["max_single_burn_rao"]
    if not _int(hard_max, bounds["min_burn_rao"], 1_000_000_000):
        raise ValueError("invalid hard max_single_burn_rao bound")
    single_cap = hard_max if max_single_burn_rao is None else max_single_burn_rao
    if not _int(single_cap, bounds["min_burn_rao"], hard_max):
        raise ValueError("invalid burn bounds")
    if daily_budget_rao is not None and not _int(
        daily_budget_rao, bounds["min_burn_rao"], 10_000 * 10**9
    ):
        raise ValueError("daily_budget_rao out of range")
    return FeeBurnPolicy(
        network=net["name"],
        genesis_hash=net["genesis_hash"],
        netuid=net["netuid"],
        tempo_blocks=net["tempo_blocks"],
        max_era_period=period,
        min_spec_version=min_spec,
        transaction_version=tx_ver,
        batch_pallet_index=calls["batch_all"]["pallet_index"],
        batch_call_index=calls["batch_all"]["call_index"],
        burn_pallet_index=calls["add_stake_burn"]["pallet_index"],
        burn_call_index=calls["add_stake_burn"]["call_index"],
        remark_pallet_index=calls["remark_with_event"]["pallet_index"],
        remark_call_index=calls["remark_with_event"]["call_index"],
        extensions=extensions,
        zero_sized_extensions=zero,
        min_burn_rao=bounds["min_burn_rao"],
        max_single_burn_rao=single_cap,
        tx_fee_ceiling_rao=bounds["tx_fee_ceiling_rao"],
        daily_budget_rao=daily_budget_rao,
    )


def build_remark_bytes(
    netuid: int, challenge_id: str, receiver: str, hotkey: str
) -> bytes:
    decode_ss58_account_id(receiver)
    decode_ss58_account_id(hotkey)
    return f"{REMARK_VERSION}|{netuid}|{challenge_id}|{receiver}|{hotkey}".encode(
        "ascii"
    )


def fee_burn_call(
    policy: FeeBurnPolicy,
    *,
    hotkey: str,
    receiver: str,
    challenge_id: str,
    amount_rao: int,
    limit_price_rao: int | None,
) -> tuple[bytes, str, str]:
    """Reconstruct ``Utility.batch_all([add_stake_burn, remark_with_event])`` bytes.

    Returns ``(call_bytes, remark_ascii, remark_hash_hex)``.
    """
    if type(challenge_id) is not str or _CHALLENGE_ID.fullmatch(challenge_id) is None:
        raise FeeBurnRefused(FeeBurnRefusal.BAD_CHALLENGE)
    try:
        receiver_pubkey = decode_ss58_account_id(receiver)
    except ValueError:
        raise FeeBurnRefused(FeeBurnRefusal.BAD_RECEIVER) from None
    pubkey = decode_ss58_account_id(hotkey)
    # `N4`: Always validate receiver identity even when `--receiver` allowlist is unset
    # (forbid zero AccountId32 and forbid passing miner's own hotkey as validator receiver).
    if receiver_pubkey == b"\x00" * 32 or receiver_pubkey == pubkey:
        raise FeeBurnRefused(FeeBurnRefusal.BAD_RECEIVER)
    if not _int(amount_rao, policy.min_burn_rao, 2**64 - 1):
        raise FeeBurnRefused(FeeBurnRefusal.BAD_AMOUNT)
    if amount_rao > policy.max_single_burn_rao:
        raise FeeBurnRefused(FeeBurnRefusal.AMOUNT_OVER_MAX)
    if limit_price_rao is not None and not _int(limit_price_rao, 1, 2**64 - 1):
        raise FeeBurnRefused(FeeBurnRefusal.BAD_AMOUNT)
    limit_bytes = (
        b"\x00"
        if limit_price_rao is None
        else b"\x01" + limit_price_rao.to_bytes(8, "little")
    )
    stake_burn_call = (
        bytes([policy.burn_pallet_index, policy.burn_call_index])
        + pubkey
        + policy.netuid.to_bytes(2, "little")
        + amount_rao.to_bytes(8, "little")
        + limit_bytes
    )

    remark_raw = build_remark_bytes(policy.netuid, challenge_id, receiver, hotkey)
    remark_hash = "0x" + blake2b(remark_raw, digest_size=32).hexdigest()
    remark_call = (
        bytes([policy.remark_pallet_index, policy.remark_call_index])
        + compact(len(remark_raw))
        + remark_raw
    )

    batch_call = (
        bytes([policy.batch_pallet_index, policy.batch_call_index])
        + compact(2)
        + stake_burn_call
        + remark_call
    )
    return batch_call, remark_raw.decode("ascii"), remark_hash


def _hex(
    value: object, refusal: FeeBurnRefusal = FeeBurnRefusal.MALFORMED_REQUEST
) -> bytes:
    if type(value) is not str or _HEX.fullmatch(value) is None:
        raise FeeBurnRefused(refusal)
    return bytes.fromhex(value[2:])


def check_request(
    policy: FeeBurnPolicy | None,
    hotkey: str,
    request: object,
    *,
    allowed_receivers: frozenset[str] | set[str] | tuple[str, ...] | None = None,
) -> dict[str, object]:
    """Pure validation & SCALE reconstruction of a ``fee_burn`` request."""
    if type(request) is not dict or set(request) != REQUEST_FIELDS:
        raise FeeBurnRefused(FeeBurnRefusal.MALFORMED_REQUEST)
    unsigned, fee = request["unsigned"], request["fee"]
    if type(unsigned) is not dict or set(unsigned) != UNSIGNED_FIELDS:
        raise FeeBurnRefused(FeeBurnRefusal.MALFORMED_REQUEST)
    if type(fee) is not dict or set(fee) != FEE_FIELDS:
        raise FeeBurnRefused(FeeBurnRefusal.MALFORMED_REQUEST)
    if policy is None:
        raise FeeBurnRefused(FeeBurnRefusal.FEE_BURN_DISABLED)
    if type(request["netuid"]) is not int or request["netuid"] != policy.netuid:
        raise FeeBurnRefused(FeeBurnRefusal.WRONG_NETUID)
    if unsigned["genesis_hash"] != policy.genesis_hash:
        raise FeeBurnRefused(FeeBurnRefusal.WRONG_NETWORK)
    if unsigned["tip"] != 0 or type(unsigned["tip"]) is not int:
        raise FeeBurnRefused(FeeBurnRefusal.NONZERO_TIP)

    receiver = request["receiver"]
    if type(receiver) is not str:
        raise FeeBurnRefused(FeeBurnRefusal.BAD_RECEIVER)
    if allowed_receivers and receiver not in allowed_receivers:
        raise FeeBurnRefused(FeeBurnRefusal.BAD_RECEIVER)

    era = unsigned["era"]
    if type(era) is not dict:
        raise FeeBurnRefused(FeeBurnRefusal.IMMORTAL_ERA)
    if set(era) != {"period", "current"}:
        raise FeeBurnRefused(FeeBurnRefusal.MALFORMED_REQUEST)
    period = era["period"]
    if not _int(period, 4, 65536) or period & (period - 1):
        raise FeeBurnRefused(FeeBurnRefusal.MALFORMED_REQUEST)
    if period > policy.max_era_period:
        raise FeeBurnRefused(FeeBurnRefusal.ERA_TOO_LONG)
    if (
        not _int(era["current"], 0, 2**32 - 1)
        or not _int(unsigned["nonce"], 0, 2**32 - 1)
        or not _int(unsigned["spec_version"], 0, 2**32 - 1)
        or not _int(unsigned["transaction_version"], 0, 2**32 - 1)
        or type(unsigned["era_block_hash"]) is not str
        or _HASH.fullmatch(unsigned["era_block_hash"]) is None
        or unsigned["metadata_hash"] is not None
    ):
        raise FeeBurnRefused(FeeBurnRefusal.MALFORMED_REQUEST)
    if (
        unsigned["transaction_version"] != policy.transaction_version
        or unsigned["spec_version"] < policy.min_spec_version
    ):
        raise FeeBurnRefused(FeeBurnRefusal.PAYLOAD_MISMATCH)

    call, remark_ascii, remark_hash = fee_burn_call(
        policy,
        hotkey=hotkey,
        receiver=receiver,
        challenge_id=request["challenge_id"],
        amount_rao=request["amount_rao"],
        limit_price_rao=request["limit_price_rao"],
    )
    if _hex(unsigned["call_data"], FeeBurnRefusal.NOT_A_FEE_BURN) != call:
        raise FeeBurnRefused(FeeBurnRefusal.NOT_A_FEE_BURN)

    extra, additional = _extension_parts(policy, unsigned)
    if (
        _hex(unsigned["included_in_extrinsic"]) != extra
        or _hex(unsigned["included_in_signed_data"]) != additional
    ):
        raise FeeBurnRefused(FeeBurnRefusal.PAYLOAD_MISMATCH)

    partial, deposit = fee["partial_fee_rao"], fee["deposit_rao"]
    if not _int(partial, 0, 2**128 - 1) or not _int(deposit, 0, 2**128 - 1):
        raise FeeBurnRefused(FeeBurnRefusal.FEE_UNKNOWN)
    if partial + deposit > policy.tx_fee_ceiling_rao:
        raise FeeBurnRefused(FeeBurnRefusal.FEE_OVER_CEILING)

    preimage = call + extra + additional
    confirm_code = blake2b(preimage, digest_size=32).hexdigest()[-8:]
    payload = (
        blake2b(preimage, digest_size=32).digest() if len(preimage) > 256 else preimage
    )

    return {
        "challenge_id": request["challenge_id"],
        "receiver": receiver,
        "amount_rao": request["amount_rao"],
        "limit_price_rao": request["limit_price_rao"],
        "remark": remark_ascii,
        "remark_hash": remark_hash,
        "confirm_code": confirm_code,
        "call": call,
        "payload": payload,
        "era_period": period,
        "era_current": era["current"],
        "nonce": unsigned["nonce"],
        "tx_fee_rao": partial + deposit,
    }


class FeeBurnLedger:
    """Append-only local record of signed ``fee_burn`` extrinsics (`0600`)."""

    def __init__(self, path: Path) -> None:
        self.path = Path(path)

    def entries(self) -> list[dict]:
        try:
            text = self.path.read_text(encoding="utf-8")
        except FileNotFoundError:
            return []
        except OSError:
            raise FeeBurnRefused(FeeBurnRefusal.LEDGER_UNAVAILABLE) from None
        try:
            rows = [json.loads(line) for line in text.splitlines() if line.strip()]
        except ValueError:
            raise FeeBurnRefused(FeeBurnRefusal.LEDGER_UNAVAILABLE) from None
        if any(
            type(row) is not dict or row.get("schema") != LEDGER_SCHEMA for row in rows
        ):
            raise FeeBurnRefused(FeeBurnRefusal.LEDGER_UNAVAILABLE)
        return rows

    def check_context_and_budget(
        self,
        policy: FeeBurnPolicy,
        *,
        era_current: int,
        amount_rao: int,
        now: datetime.datetime,
    ) -> tuple[int, int]:
        """Verify monotonic block context and rolling 24h budget cap if configured."""
        cutoff = now.astimezone(datetime.UTC) - datetime.timedelta(hours=24)
        spent_24h = 0
        count_24h = 0
        for row in self.entries():
            if row.get("genesis_hash") != policy.genesis_hash:
                continue
            if row.get("netuid") != policy.netuid:
                continue
            if type(row.get("era_current")) is int and row["era_current"] > era_current:
                raise FeeBurnRefused(FeeBurnRefusal.STALE_CHAIN_CONTEXT)
            signed_at_s = row.get("signed_at")
            if type(signed_at_s) is str:
                try:
                    ts = datetime.datetime.fromisoformat(signed_at_s)
                    if ts.astimezone(datetime.UTC) >= cutoff:
                        count_24h += 1
                        spent_24h += int(row.get("amount_rao", 0))
                except ValueError:
                    raise FeeBurnRefused(FeeBurnRefusal.LEDGER_UNAVAILABLE) from None

        if (
            policy.daily_budget_rao is not None
            and spent_24h + amount_rao > policy.daily_budget_rao
        ):
            raise FeeBurnRefused(FeeBurnRefusal.DAILY_BUDGET_EXCEEDED)
        return count_24h, spent_24h

    def append(self, row: dict) -> None:
        line = json.dumps({"schema": LEDGER_SCHEMA, **row}, sort_keys=True) + "\n"
        try:
            descriptor = os.open(
                self.path, os.O_WRONLY | os.O_APPEND | os.O_CREAT | os.O_NOFOLLOW, 0o600
            )
            try:
                os.write(descriptor, line.encode("utf-8"))
                os.fsync(descriptor)
            finally:
                os.close(descriptor)
        except OSError:
            raise FeeBurnRefused(FeeBurnRefusal.LEDGER_UNAVAILABLE) from None


def prompt_lines(
    policy: FeeBurnPolicy,
    hotkey: str,
    checked: dict[str, object],
    count_24h: int,
    spent_24h_rao: int,
) -> str:
    genesis = policy.genesis_hash
    limit_str = (
        "none (market)"
        if checked["limit_price_rao"] is None
        else f"{int(checked['limit_price_rao']) / 1e9:.9f} TAO/Alpha"
    )
    return (
        f"  network    {policy.network} (genesis {genesis[:6]}...{genesis[-4:]})\n"
        f"  netuid     {policy.netuid}\n"
        f"  challenge  {checked['challenge_id']}\n"
        f"  receiver   {checked['receiver']}\n"
        f"  burn       {int(checked['amount_rao']) / 1e9:.9f} TAO -> SN{policy.netuid} Alpha (100% burned)\n"
        f"  limit      {limit_str}\n"
        f"  remark     {checked['remark']} (blake2b {str(checked['remark_hash'])[-8:]})\n"
        f"  tx fee     {int(checked['tx_fee_rao']) / 1e9:.9f} TAO est. (ceiling {policy.tx_fee_ceiling_rao / 1e9:.9f} TAO); tip 0\n"
        f"  last 24h   {count_24h} signed ({spent_24h_rao / 1e9:.9f} TAO)\n"
        f"  hotkey     {hotkey}\n"
    )


def prompt_text(
    policy: FeeBurnPolicy,
    hotkey: str,
    checked: dict[str, object],
    count_24h: int,
    spent_24h_rao: int,
) -> str:
    code8 = str(checked["confirm_code"])
    return (
        f"\nCarbon asks to sign a submission TAO->Alpha burn with hotkey {hotkey}\n"
        + prompt_lines(policy, hotkey, checked, count_24h, spent_24h_rao)
        + f"Type {code8} (payload confirmation code) to burn, anything else to refuse: "
    )


__all__ = [
    "AUTO_BUDGET_MARK",
    "CONFIRM_SECONDS",
    "DEFAULT_CLI_SINGLE_BURN_RAO",
    "DEFAULT_RECORD",
    "LEDGER_SCHEMA",
    "OP",
    "RECORD_SCHEMA",
    "REMARK_VERSION",
    "FeeBurnLedger",
    "FeeBurnPolicy",
    "FeeBurnRefusal",
    "FeeBurnRefused",
    "build_remark_bytes",
    "check_request",
    "decode_ss58_account_id",
    "fee_burn_call",
    "load_fee_burn_policy",
    "prompt_lines",
    "prompt_text",
]
