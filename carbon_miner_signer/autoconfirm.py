"""Opt-in, testnet-only auto-confirm of strategy commitments.

OWNER-SIGNER-TESTNET-AUTOCONFIRM-01 amends OWNER-COMMITMENT-POSTER-01 D10
prospectively, for testnet 567 only and only for hotkeys in an owner-written
allow-list: a signer started with ``--auto-confirm-commitments <file>`` signs
a strategy commitment without the terminal prompt when every one of these
holds:

- the request is the one ``commit`` op and passes every existing bound
  (``commitment.check_request``: the pinned call, digest, netuid, genesis,
  tip 0, era cap and fee ceiling);
- the chain genesis is testnet 567's, :data:`TESTNET_GENESIS`, hard-coded
  here: checked at start and again on every request;
- the signer's own hotkey is in the allow-list;
- the per-tempo ledger check (D4) passes.

Anything else is refused with a closed code. The auto path never falls back
to the terminal prompt: an unattended signer has no terminal to ask.

The allow-list is read once, at start. A change takes effect only after a
restart.

This module imports nothing from ``carbon``.
"""

from __future__ import annotations

import json
import os
import re
import stat
from dataclasses import dataclass
from pathlib import Path

from . import commitment as cm

ALLOWLIST_SCHEMA = "carbon.signer.autoconfirm-allowlist.v1"
#: Testnet 567, hard-coded. With any other genesis (mainnet especially) the
#: flag is refused at start, and an auto-confirm is refused per request.
TESTNET_NETWORK = "testnet"
TESTNET_NETUID = 567
TESTNET_GENESIS = "0x8f9cf856bf558a14440e75569c9e58594757048d7b3a84b5d25f6bd978263105"
#: What the terminal shows and the ledger row carries for each one.
MARK = "AUTO-CONFIRMED (allow-listed testnet hotkey)"
ALLOWLIST_FIELDS = frozenset({"schema", "network", "netuid", "hotkeys"})
MAX_ALLOWLIST_BYTES = 4096
MAX_HOTKEYS = 16
_SS58 = re.compile(r"[1-9A-HJ-NP-Za-km-z]{46,48}")


class AllowListProblem(ValueError):
    """Why the signer will not start with this allow-list. One line."""


@dataclass(frozen=True)
class AutoConfirm:
    """The allow-list as read at start. Fixed for the signer's lifetime."""

    path: str
    hotkeys: frozenset

    def startup_problem(self, policy: cm.CommitPolicy | None, hotkey: str):
        """Why this signer may not run with the flag, or None."""
        if policy is None:
            return "auto-confirm needs a complete commitment record; it is not pinned"
        if (
            policy.genesis_hash != TESTNET_GENESIS
            or policy.network != TESTNET_NETWORK
            or policy.netuid != TESTNET_NETUID
        ):
            return (
                "auto-confirm is for testnet netuid 567 only; this signer's "
                "commitment record names another network"
            )
        if hotkey not in self.hotkeys:
            return f"hotkey {hotkey} is not in the auto-confirm allow-list {self.path}"
        return None

    def check(self, policy: cm.CommitPolicy, hotkey: str, genesis_hash) -> None:
        """Per request, after ``check_request``: refuse unless still testnet
        567 and still this allow-listed hotkey."""
        if (
            genesis_hash != TESTNET_GENESIS
            or self.startup_problem(policy, hotkey) is not None
        ):
            raise cm.Refused(cm.CommitRefusal.AUTO_CONFIRM_NOT_ALLOWED)


def _no_duplicates(pairs):
    keys = [key for key, _ in pairs]
    if len(keys) != len(set(keys)):
        raise AllowListProblem("duplicate key")
    return dict(pairs)


def load_allowlist(path) -> AutoConfirm:
    """The allow-list at ``path``, or ``AllowListProblem``.

    It must be a regular file, not a symlink, owned by this user and readable
    or writable by no one else (the D8 rule), at most 4096 bytes, and exactly
    ``{"schema", "network": "testnet", "netuid": 567, "hotkeys": [ss58...]}``.
    """
    path = Path(path).expanduser()
    try:
        descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    except FileNotFoundError:
        raise AllowListProblem(f"no auto-confirm allow-list at {path}") from None
    except OSError:
        # O_NOFOLLOW on a symlink is ELOOP; anything else is unreadable.
        if path.is_symlink():
            raise AllowListProblem(
                f"the auto-confirm allow-list {path} is a symlink; "
                "point the signer at the file itself"
            ) from None
        raise AllowListProblem(
            f"cannot open the auto-confirm allow-list {path}"
        ) from None
    try:
        info = os.fstat(descriptor)
        if not stat.S_ISREG(info.st_mode):
            raise AllowListProblem(
                f"the auto-confirm allow-list {path} is not a regular file"
            )
        if info.st_uid != os.getuid():
            raise AllowListProblem(
                f"the auto-confirm allow-list {path} belongs to another user"
            )
        if info.st_mode & 0o077:
            raise AllowListProblem(
                f"the auto-confirm allow-list {path} is readable or writable by "
                f"others; fix it with: chmod 600 {path}"
            )
        if info.st_size > MAX_ALLOWLIST_BYTES:
            raise AllowListProblem(f"the auto-confirm allow-list {path} is too large")
        data = os.read(descriptor, MAX_ALLOWLIST_BYTES + 1)
    finally:
        os.close(descriptor)
    if len(data) > MAX_ALLOWLIST_BYTES:
        raise AllowListProblem(f"the auto-confirm allow-list {path} is too large")
    try:
        record = json.loads(data.decode("utf-8"), object_pairs_hook=_no_duplicates)
    except (UnicodeDecodeError, ValueError):
        raise AllowListProblem(
            f"the auto-confirm allow-list {path} is not valid JSON"
        ) from None
    if type(record) is not dict or set(record) != ALLOWLIST_FIELDS:
        raise AllowListProblem(
            f"the auto-confirm allow-list {path} must hold exactly: "
            + ", ".join(sorted(ALLOWLIST_FIELDS))
        )
    if record["schema"] != ALLOWLIST_SCHEMA:
        raise AllowListProblem(
            f"the auto-confirm allow-list {path} is not {ALLOWLIST_SCHEMA}"
        )
    if (
        record["network"] != TESTNET_NETWORK
        or type(record["netuid"]) is not int
        or record["netuid"] != TESTNET_NETUID
    ):
        raise AllowListProblem(
            f"the auto-confirm allow-list {path} must name network testnet, netuid 567"
        )
    hotkeys = record["hotkeys"]
    if (
        type(hotkeys) is not list
        or not 1 <= len(hotkeys) <= MAX_HOTKEYS
        or not all(type(key) is str and _SS58.fullmatch(key) for key in hotkeys)
        or len(set(hotkeys)) != len(hotkeys)
    ):
        raise AllowListProblem(
            f"the auto-confirm allow-list {path} must list 1 to {MAX_HOTKEYS} "
            "distinct ss58 hotkeys"
        )
    return AutoConfirm(path=str(path), hotkeys=frozenset(hotkeys))


def shown_text(policy: cm.CommitPolicy, hotkey: str, checked: dict, today: int) -> str:
    """What the signer's terminal shows for an auto-confirm: the manual
    prompt's own lines, marked, with no question."""
    return f"{MARK}: on-chain commitment with hotkey {hotkey}\n" + cm.prompt_lines(
        policy, checked, today
    )
