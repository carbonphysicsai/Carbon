"""The exam allowance shared per FUNDER (OWNER-PROBING-COUNTERS-01 (a); TE scope be9aed9a section 2).

The exam cap (`exam_cap`) keys a graded submission's epoch slot and daily allowance by an ALLOWANCE GROUP instead of
the hotkey, and its ``M`` counts groups, once this receiver installs a grouping (`install`). The group of a hotkey is
``funder_map.group(coldkey)``, the same function and the same in-memory map that key R89's verified request bucket
(Release Architect 11:31, Validator-2 11:32). The coldkey is read from the receiver's own latest chain snapshot
(``snapshot.resolve(hotkey).coldkey``), never from anything a miner sends. So every hotkey of one coldkey is always one
group, and the Chain Auditor's map joins the coldkeys of one funder.

Every policy value is the owner's (or the Chain Auditor's). None is defaulted here. The configured block is
``{"unmapped_coldkey": "per_coldkey" | "refuse", "unresolved_hotkey": "per_hotkey" | "refuse",
"max_map_age_blocks": <int > 0>}``:

- ``unmapped_coldkey``: a coldkey a USABLE map does not name (TE scope edge case 1: per-coldkey, recommended, or
  refuse until mapped). With no usable map (none configured, unreadable, malformed or older than
  ``max_map_age_blocks``), every coldkey is its own group: grading never refuses everyone, and never widens to
  per-hotkey (edge case 4).
- ``unresolved_hotkey``: a hotkey whose coldkey the latest snapshot cannot give (no fresh snapshot, or not
  registered): its own hotkey (today's rule) or refuse.

A block with any value missing, null, ``"HUMAN_INPUT"`` or out of range refuses to start the receiver
(`AllowanceGroupsUnset`). No block means no grouping: the cap is per hotkey exactly as before.

A group id is opaque: ``f:<map id>`` (a funder), ``c:<digest of the coldkey>`` (a coldkey alone) or ``h:<hotkey>``
(today's key, also every row the cap filed before the release). It lives only in the owner-only attempt ledger and is
never served.
"""

from __future__ import annotations

import threading
import time

from .exam_cap import ExamCapRefused

UNMAPPED = ("per_coldkey", "refuse")
UNRESOLVED = ("per_hotkey", "refuse")
KEYS = ("unmapped_coldkey", "unresolved_hotkey", "max_map_age_blocks")
COUNTS = ("funder", "coldkey", "own_hotkey", "map_unusable", "refused_unmapped", "refused_unresolved")
COUNTS_EVENT = "allowance_groups_hourly"
COUNTS_PERIOD_S = 3600.0


class AllowanceGroupsUnset(ValueError):
    """The configured block does not carry every value the owner sets."""

    code = "allowance_groups_unset"


def policy(block):
    """The validated policy of a configured block, or `AllowanceGroupsUnset`."""
    if (
        type(block) is not dict
        or set(block) != set(KEYS)
        or block["unmapped_coldkey"] not in UNMAPPED
        or block["unresolved_hotkey"] not in UNRESOLVED
        or type(block["max_map_age_blocks"]) is not int
        or block["max_map_age_blocks"] <= 0
    ):
        raise AllowanceGroupsUnset(
            "allowance_groups needs the owner's unmapped_coldkey (per_coldkey | refuse), unresolved_hotkey "
            "(per_hotkey | refuse) and max_map_age_blocks (> 0)"
        )
    return dict(block)


class Grouping:
    """``hotkey -> group id`` for the exam cap, or `ExamCapRefused` under a ``refuse`` policy."""

    def __init__(self, configured, window, funder_map, *, clock=time.monotonic, emit=None):
        self.policy = policy(configured)
        self.window = window
        #: () -> the current `funder_map.FunderMap` (the door's own copy, swapped whole on a reload).
        self.funder_map = funder_map
        self._lock = threading.Lock()
        self._clock, self._emit = clock, emit
        self._counts = dict.fromkeys(COUNTS, 0)
        self._since = clock()

    def _count(self, name):
        with self._lock:
            self._counts[name] += 1
            now = self._clock()
            if now - self._since >= COUNTS_PERIOD_S:
                emit = self._emit
                if emit is None:
                    from carbon.battery.intake import log as emit
                emit(COUNTS_EVENT, period_s=round(now - self._since), **self._counts)
                self._counts = dict.fromkeys(COUNTS, 0)
                self._since = now

    def __call__(self, hotkey):
        snapshot = self.window.latest()
        member = None if snapshot is None else snapshot.resolve(hotkey)
        if member is None:
            if self.policy["unresolved_hotkey"] == "refuse":
                self._count("refused_unresolved")
                raise ExamCapRefused("allowance_group_unresolved")
            self._count("own_hotkey")
            return "h:" + hotkey
        current = self.funder_map()
        usable = current is not None and current.problem is None and current.block is not None
        if usable and snapshot.finalized_block - current.block > self.policy["max_map_age_blocks"]:
            usable = False
        if not usable:
            if current is not None and (current.problem is not None or current.block is not None):
                self._count("map_unusable")  # configured but unreadable, malformed or stale: alert, never refuse
            from .funder_map import FunderMap

            self._count("coldkey")
            return FunderMap.empty().group(member.coldkey)
        if member.coldkey in current.groups:
            self._count("funder")
            return current.group(member.coldkey)
        if self.policy["unmapped_coldkey"] == "refuse":
            self._count("refused_unmapped")
            raise ExamCapRefused("allowance_group_unmapped")
        self._count("coldkey")
        return current.group(member.coldkey)


def from_config(cfg, window, funder_map):
    """The receiver's `Grouping` when its configuration carries ``allowance_groups``, else None (per hotkey)."""
    block = cfg.get("allowance_groups")
    return None if block is None else Grouping(block, window, funder_map)
