"""The signer's one chain extrinsic: a miner's strategy commitment.

OWNER-COMMITMENT-POSTER-01 (D1): ``carbon-miner-signer`` signs exactly one
extrinsic, ``Commitments.set_commitment(netuid, info)`` whose ``info`` holds
one ``Raw71`` field, the ASCII ``sha256:<64 lowercase hex>`` digest. It signs
nothing else, and only after the miner types the digest's last 8 characters
on the signer's own terminal.

D2 is S-offline: the signer never opens a network connection. The Launchpad
prepares the unsigned extrinsic with the SDK (``bittensor==11.1.0``,
``RpcSubstrate.prepare``) and sends its parts. This module never signs those
bytes as given. It rebuilds the call from ``(netuid, digest)`` and the signed
extensions from the structured fields, under the pins recorded in
``commitment_record.json``, and refuses unless both equal what was sent. The
bytes it signs are its own reconstruction.

What the SDK source pins (bittensor 11.1.0, site-packages/bittensor/):
- the call: ``_generated/calls.py:862-868`` (``Commitments.set_commitment``,
  params ``netuid: NetUid``, ``info: CommitmentInfo``);
- the pallet index 18: ``_generated/errors.py:243`` (module errors ``(18, n)``
  are the Commitments pallet's);
- the data variant: ``Raw<len>``, read back by concatenating ``Raw*`` fields
  (``reads/identity.py:69-77``, ``:90-101``), so a 71-byte digest is ``Raw71``;
- the default era: ``settings.py:22`` (``DEFAULT_ERA_PERIOD = 128``);
- the fee: ``_substrate.py:538-542`` (``estimate_fee`` -> ``partial_fee``) over
  ``_transport/interface.py:694-711`` (``TransactionPaymentApi_query_info``);
- who pays: ``fee_filters.py:30`` (``set_commitment`` is charged to the
  hotkey's owning coldkey, not the hotkey);
- the payload: ``_transport/extrinsics.py:150-168`` (call ++ extensions ++
  additional signed, blake2b-256 when over 256 bytes).

The SDK source does not carry the runtime's call index, the ``Raw71`` tag or
the signed-extension order: those come from runtime metadata. They stay
``null`` in the record until the localnet round trip
(``scripts/dev/commitment_localnet_roundtrip.py``) measures them, and while
any pin is null every commit request is refused.

This module imports nothing from ``carbon``.
"""

from __future__ import annotations

import datetime
import json
import os
import re
import stat
from dataclasses import dataclass
from enum import Enum
from hashlib import blake2b
from pathlib import Path

RECORD_PATH = Path(__file__).with_name("commitment_record.json")
RECORD_SCHEMA = "carbon.miner-signer.commitment-record.v1"
LEDGER_SCHEMA = "carbon.miner-signer.commitment-ledger.v1"
DIGEST_LENGTH = 71
_DIGEST = re.compile(r"sha256:[0-9a-f]{64}")
_HASH = re.compile(r"0x[0-9a-f]{64}")
_HEX = re.compile(r"0x(?:[0-9a-f]{2})*")
#: How long the miner has to answer the prompt before the request lapses.
CONFIRM_SECONDS = 120
#: The closed request. Everything the Launchpad read from the chain travels
#: in ``unsigned`` (the SDK's ``UnsignedExtrinsic.to_dict()`` minus the bytes
#: the signer recomputes) and ``fee``. Nothing here can confirm, set a tip,
#: or carry bytes the signer would sign as given.
REQUEST_FIELDS = frozenset({"protocol", "op", "netuid", "digest", "unsigned", "fee"})
UNSIGNED_FIELDS = frozenset(
    {
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
    }
)
FEE_FIELDS = frozenset({"partial_fee_rao", "deposit_rao"})
#: Signed extensions whose encoding is standard Substrate. Anything the
#: runtime lists that is neither here nor recorded as zero-sized is refused.
STANDARD_EXTENSIONS = {
    "CheckNonZeroSender": ("", ""),
    "CheckSpecVersion": ("", "spec_version"),
    "CheckTxVersion": ("", "transaction_version"),
    "CheckGenesis": ("", "genesis_hash"),
    "CheckMortality": ("era", "era_block_hash"),
    "CheckEra": ("era", "era_block_hash"),
    "CheckNonce": ("nonce", ""),
    "CheckWeight": ("", ""),
    "ChargeTransactionPayment": ("tip", ""),
    "ChargeTransactionPaymentWrapper": ("tip", ""),
    "CheckMetadataHash": ("mode", "metadata_hash"),
}


class CommitRefusal(str, Enum):
    """Why a commit request was declined. Closed."""

    MALFORMED_REQUEST = "MALFORMED_REQUEST"
    #: The signer's pins are incomplete (HUMAN_INPUT or unmeasured).
    COMMITMENT_NOT_PINNED = "COMMITMENT_NOT_PINNED"
    #: Not the one pinned call: another pallet or call, a wrapper, extra bytes.
    NOT_A_COMMITMENT = "NOT_A_COMMITMENT"
    BAD_DIGEST = "BAD_DIGEST"
    WRONG_NETUID = "WRONG_NETUID"
    WRONG_NETWORK = "WRONG_NETWORK"
    NONZERO_TIP = "NONZERO_TIP"
    IMMORTAL_ERA = "IMMORTAL_ERA"
    ERA_TOO_LONG = "ERA_TOO_LONG"
    #: The extension bytes are not the signer's own reconstruction.
    PAYLOAD_MISMATCH = "PAYLOAD_MISMATCH"
    FEE_UNKNOWN = "FEE_UNKNOWN"
    FEE_OVER_CEILING = "FEE_OVER_CEILING"
    ALREADY_COMMITTED_THIS_TEMPO = "ALREADY_COMMITTED_THIS_TEMPO"
    STALE_CHAIN_CONTEXT = "STALE_CHAIN_CONTEXT"
    COMMIT_IN_FLIGHT = "COMMIT_IN_FLIGHT"
    NOT_CONFIRMED = "NOT_CONFIRMED"
    LEDGER_UNAVAILABLE = "LEDGER_UNAVAILABLE"


class Refused(Exception):
    def __init__(self, refusal: CommitRefusal):
        self.refusal = refusal
        super().__init__(refusal.value)


@dataclass(frozen=True)
class CommitPolicy:
    """Everything a commit is checked against, fixed when the signer starts."""

    network: str
    genesis_hash: str
    netuid: int
    tempo_blocks: int
    max_era_period: int
    pallet_index: int
    call_index: int
    data_tag: int
    extensions: tuple
    zero_sized_extensions: frozenset
    fee_ceiling_rao: int


def _int(value, low=0, high=2**64 - 1):
    return type(value) is int and low <= value <= high


def load_policy(record=None):
    """``(policy, [])`` when every pin is recorded, else ``(None, missing)``.

    A record that is present but inconsistent (a ceiling that is not the
    multiplier times the measurement, a period that is not a power of two
    within one tempo) raises ``ValueError``: it is a broken record, not an
    unset one.
    """
    if record is None:
        record = json.loads(RECORD_PATH.read_text(encoding="utf-8"))
    if record.get("schema") != RECORD_SCHEMA:
        raise ValueError("unknown commitment record schema")
    call, network = record["call"], record["network"]
    era, fee = record["era"], record["fee"]
    missing = [
        name
        for name, value in (
            ("call.call_index", call.get("call_index")),
            ("call.data_tag", call.get("data_tag")),
            ("extensions", record.get("extensions")),
            ("zero_sized_extensions", record.get("zero_sized_extensions")),
            ("fee.measured_fee_rao", fee.get("measured_fee_rao")),
            ("fee.measured_deposit_rao", fee.get("measured_deposit_rao")),
            ("fee.ceiling_rao", fee.get("ceiling_rao")),
        )
        if value is None
    ]
    if missing:
        return None, missing
    measured = fee["measured_fee_rao"] + fee["measured_deposit_rao"]
    if fee["ceiling_rao"] != fee["multiplier"] * measured or measured <= 0:
        raise ValueError("the fee ceiling is not the multiplier times the measurement")
    period = era["max_period"]
    if (
        not _int(period, 4, 65536)
        or period & (period - 1)
        or period > era["sdk_default_period"]
        or period > network["tempo_blocks"]
    ):
        raise ValueError("the era cap must be a power of two within one tempo")
    extensions = tuple(record["extensions"])
    zero = frozenset(record["zero_sized_extensions"])
    unknown = [
        name
        for name in extensions
        if name not in STANDARD_EXTENSIONS and name not in zero
    ]
    if unknown:
        raise ValueError("unrecorded signed extensions: " + ", ".join(unknown))
    if not _HASH.fullmatch(network["genesis_hash"]):
        raise ValueError("the pinned genesis is malformed")
    return (
        CommitPolicy(
            network=network["name"],
            genesis_hash=network["genesis_hash"],
            netuid=network["netuid"],
            tempo_blocks=network["tempo_blocks"],
            max_era_period=period,
            pallet_index=call["pallet_index"],
            call_index=call["call_index"],
            data_tag=call["data_tag"],
            extensions=extensions,
            zero_sized_extensions=zero,
            fee_ceiling_rao=fee["ceiling_rao"],
        ),
        [],
    )


def compact(value: int) -> bytes:
    """SCALE compact encoding of a non-negative integer."""
    if value < 0:
        raise ValueError("compact values are non-negative")
    if value < 1 << 6:
        return bytes([value << 2])
    if value < 1 << 14:
        return ((value << 2) | 1).to_bytes(2, "little")
    if value < 1 << 30:
        return ((value << 2) | 2).to_bytes(4, "little")
    body = value.to_bytes((value.bit_length() + 7) // 8, "little")
    return bytes([((len(body) - 4) << 2) | 3]) + body


def mortal_era(period: int, current: int) -> bytes:
    """The two-byte mortal era for ``period`` (a power of two) from ``current``."""
    if not _int(period, 4, 65536) or period & (period - 1):
        raise ValueError("an era period is a power of two from 4 to 65536")
    quantize = max(period >> 12, 1)
    phase = current % period // quantize * quantize
    low = min(15, max(1, period.bit_length() - 2))
    return (low | (phase // quantize) << 4).to_bytes(2, "little")


def is_digest(value) -> bool:
    return (
        type(value) is str
        and len(value) == DIGEST_LENGTH
        and value.isascii()
        and _DIGEST.fullmatch(value) is not None
    )


def commitment_call(policy: CommitPolicy, netuid: int, digest: str) -> bytes:
    """The exact call bytes: pallet, call, ``NetUid`` (u16), one ``Raw71`` field."""
    if not is_digest(digest):
        raise Refused(CommitRefusal.BAD_DIGEST)
    return (
        bytes([policy.pallet_index, policy.call_index])
        + netuid.to_bytes(2, "little")
        + compact(1)
        + bytes([policy.data_tag])
        + digest.encode("ascii")
    )


def _hex(value, refusal=CommitRefusal.MALFORMED_REQUEST) -> bytes:
    if type(value) is not str or not _HEX.fullmatch(value):
        raise Refused(refusal)
    return bytes.fromhex(value[2:])


def _extension_parts(policy: CommitPolicy, unsigned: dict) -> tuple[bytes, bytes]:
    era = mortal_era(unsigned["era"]["period"], unsigned["era"]["current"])
    extra_of = {
        "": b"",
        "era": era,
        "nonce": compact(unsigned["nonce"]),
        "tip": compact(0),
        "mode": b"\x00",
    }
    additional_of = {
        "": b"",
        "spec_version": unsigned["spec_version"].to_bytes(4, "little"),
        "transaction_version": unsigned["transaction_version"].to_bytes(4, "little"),
        "genesis_hash": bytes.fromhex(policy.genesis_hash[2:]),
        "era_block_hash": bytes.fromhex(unsigned["era_block_hash"][2:]),
        "metadata_hash": b"\x00",
    }
    extra, additional = b"", b""
    for name in policy.extensions:
        extra_kind, additional_kind = STANDARD_EXTENSIONS.get(name, ("", ""))
        extra += extra_of[extra_kind]
        additional += additional_of[additional_kind]
    return extra, additional


def check_request(policy: CommitPolicy | None, request) -> dict:
    """The checked request, or ``Refused``. Pure: no ledger, no prompt.

    Order matters only for which refusal is reported; every check runs before
    anything is shown or signed.
    """
    if type(request) is not dict or set(request) != REQUEST_FIELDS:
        raise Refused(CommitRefusal.MALFORMED_REQUEST)
    unsigned, fee = request["unsigned"], request["fee"]
    if type(unsigned) is not dict or set(unsigned) != UNSIGNED_FIELDS:
        raise Refused(CommitRefusal.MALFORMED_REQUEST)
    if type(fee) is not dict or set(fee) != FEE_FIELDS:
        raise Refused(CommitRefusal.MALFORMED_REQUEST)
    if policy is None:
        raise Refused(CommitRefusal.COMMITMENT_NOT_PINNED)
    if not is_digest(request["digest"]):
        raise Refused(CommitRefusal.BAD_DIGEST)
    if type(request["netuid"]) is not int or request["netuid"] != policy.netuid:
        raise Refused(CommitRefusal.WRONG_NETUID)
    if unsigned["genesis_hash"] != policy.genesis_hash:
        raise Refused(CommitRefusal.WRONG_NETWORK)
    if unsigned["tip"] != 0 or type(unsigned["tip"]) is not int:
        raise Refused(CommitRefusal.NONZERO_TIP)
    era = unsigned["era"]
    if type(era) is not dict:
        raise Refused(CommitRefusal.IMMORTAL_ERA)
    if set(era) != {"period", "current"}:
        raise Refused(CommitRefusal.MALFORMED_REQUEST)
    period = era["period"]
    if not _int(period, 4, 65536) or period & (period - 1):
        raise Refused(CommitRefusal.MALFORMED_REQUEST)
    if period > policy.max_era_period:
        raise Refused(CommitRefusal.ERA_TOO_LONG)
    if (
        not _int(era["current"], 0, 2**32 - 1)
        or not _int(unsigned["nonce"], 0, 2**32 - 1)
        or not _int(unsigned["spec_version"], 0, 2**32 - 1)
        or not _int(unsigned["transaction_version"], 0, 2**32 - 1)
        or type(unsigned["era_block_hash"]) is not str
        or not _HASH.fullmatch(unsigned["era_block_hash"])
        or unsigned["metadata_hash"] is not None
    ):
        raise Refused(CommitRefusal.MALFORMED_REQUEST)
    call = commitment_call(policy, policy.netuid, request["digest"])
    if _hex(unsigned["call_data"], CommitRefusal.NOT_A_COMMITMENT) != call:
        raise Refused(CommitRefusal.NOT_A_COMMITMENT)
    extra, additional = _extension_parts(policy, unsigned)
    if (
        _hex(unsigned["included_in_extrinsic"]) != extra
        or _hex(unsigned["included_in_signed_data"]) != additional
    ):
        raise Refused(CommitRefusal.PAYLOAD_MISMATCH)
    partial, deposit = fee["partial_fee_rao"], fee["deposit_rao"]
    if not _int(partial, 0, 2**128 - 1) or not _int(deposit, 0, 2**128 - 1):
        raise Refused(CommitRefusal.FEE_UNKNOWN)
    if partial + deposit > policy.fee_ceiling_rao:
        raise Refused(CommitRefusal.FEE_OVER_CEILING)
    payload = call + extra + additional
    if len(payload) > 256:
        payload = blake2b(payload, digest_size=32).digest()
    return {
        "digest": request["digest"],
        "call": call,
        "payload": payload,
        "era_period": period,
        "era_current": era["current"],
        "nonce": unsigned["nonce"],
        "fee_rao": partial + deposit,
    }


class CommitLedger:
    """Append-only record of what this signer signed, beside its socket.

    D4: at most one commitment per hotkey per tempo, where the tempo is the
    rule's block window (``tempo_blocks``, aligned to multiples of it). The
    entry is written before the signature is returned: a signature that
    cannot be recorded is not given out, and an entry whose signature was
    then lost only makes the ledger stricter.
    """

    def __init__(self, path: Path):
        self.path = Path(path)

    def entries(self) -> list:
        try:
            text = self.path.read_text(encoding="utf-8")
        except FileNotFoundError:
            return []
        except OSError:
            raise Refused(CommitRefusal.LEDGER_UNAVAILABLE) from None
        try:
            rows = [json.loads(line) for line in text.splitlines() if line.strip()]
        except ValueError:
            raise Refused(CommitRefusal.LEDGER_UNAVAILABLE) from None
        if any(
            type(row) is not dict or row.get("schema") != LEDGER_SCHEMA for row in rows
        ):
            raise Refused(CommitRefusal.LEDGER_UNAVAILABLE)
        return rows

    def check(self, policy: CommitPolicy, era_current: int) -> int:
        """The tempo index for ``era_current``, or ``Refused``."""
        tempo = era_current // policy.tempo_blocks
        for row in self.entries():
            if row.get("genesis_hash") != policy.genesis_hash:
                continue
            if row.get("netuid") != policy.netuid:
                continue
            if row.get("tempo_index") == tempo:
                raise Refused(CommitRefusal.ALREADY_COMMITTED_THIS_TEMPO)
            if type(row.get("era_current")) is int and row["era_current"] > era_current:
                raise Refused(CommitRefusal.STALE_CHAIN_CONTEXT)
        return tempo

    def today(self, now: datetime.datetime) -> int:
        day = now.astimezone(datetime.UTC).date().isoformat()
        return sum(
            1 for row in self.entries() if str(row.get("signed_at", "")).startswith(day)
        )

    def append(self, row: dict) -> None:
        line = json.dumps({"schema": LEDGER_SCHEMA, **row}, sort_keys=True) + "\n"
        try:
            descriptor = os.open(
                self.path, os.O_WRONLY | os.O_APPEND | os.O_CREAT | os.O_NOFOLLOW, 0o600
            )
            try:
                os.write(descriptor, line.encode())
                os.fsync(descriptor)
            finally:
                os.close(descriptor)
        except OSError:
            raise Refused(CommitRefusal.LEDGER_UNAVAILABLE) from None


def prompt_text(policy: CommitPolicy, hotkey: str, checked: dict, today: int) -> str:
    """What the miner reads on the signer's terminal before typing."""
    genesis = policy.genesis_hash
    return (
        f"\nCarbon asks to post an on-chain commitment with hotkey {hotkey}\n"
        f"  network   {policy.network} (genesis {genesis[:6]}...{genesis[-4:]})\n"
        f"  netuid    {policy.netuid}\n"
        f"  digest    {checked['digest']}\n"
        f"  fee       {checked['fee_rao'] / 1e9:.9f} TAO incl. any deposit, "
        f"Carbon's estimate (ceiling {policy.fee_ceiling_rao / 1e9:.9f} TAO), "
        "paid by the hotkey's coldkey; tip 0\n"
        f"  valid for {checked['era_period']} blocks from block "
        f"{checked['era_current']}; today: {today} signed, at most one per tempo\n"
        "  It replaces this hotkey's current commitment on this subnet.\n"
        "Type the last 8 characters of the digest to post, anything else to refuse: "
    )


def tty_confirm(text: str, expected: str, *, seconds: int = CONFIRM_SECONDS) -> bool:
    """Ask on the controlling terminal. Only a typed line can confirm.

    No terminal, a timeout, or any other answer is a refusal. The socket is
    never read here, so nothing a client sends can answer.
    """
    import select

    try:
        terminal = os.open("/dev/tty", os.O_RDWR | os.O_NOCTTY)
    except OSError:
        return False
    try:
        os.write(terminal, text.encode())
        ready, _, _ = select.select([terminal], [], [], seconds)
        if not ready:
            os.write(terminal, b"\nNo answer: refused.\n")
            return False
        answer = os.read(terminal, 256).decode("utf-8", "replace").strip()
    except OSError:
        return False
    finally:
        os.close(terminal)
    return answer == expected


def key_file_problem(path) -> str | None:
    """D8: why the key file must not be used, or None.

    A symlink, anything but a regular file, another user's file, or a file
    group or world can read or write is refused, with a one-line fix.
    """
    path = Path(path).expanduser()
    try:
        info = path.lstat()
    except FileNotFoundError:
        return None  # the SDK's own "no such key file" message follows
    except OSError:
        return f"cannot inspect the key file {path}"
    if stat.S_ISLNK(info.st_mode):
        return f"the key file {path} is a symlink; point the signer at the file itself"
    if not stat.S_ISREG(info.st_mode):
        return f"the key file {path} is not a regular file"
    if info.st_uid != os.getuid():
        return f"the key file {path} belongs to another user; copy it and chmod 600 it"
    if info.st_mode & 0o077:
        return (
            f"the key file {path} is readable or writable by others; "
            f"fix it with: chmod 600 {path}"
        )
    return None
