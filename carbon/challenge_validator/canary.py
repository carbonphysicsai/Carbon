"""The registered canary hotkeys (CANARY-01; OWNER-CANARY-LIST-01).

A canary's submissions are admitted and scored normally (the liveness check),
and never become incumbent, never enter standing or finals, are never
weighted or promoted, and are excluded from leak detection's baselines and
from every report and feed. The list is registered and versioned: it changes
only with the owner's record naming each hotkey.

OWNER-CANARY-LIST-01 names the first: `carbon-canary`, UID 13 on testnet 567,
on its own coldkey (owner-created).
"""

#: The list's version; it increments with every change.
CANARY_LIST_VERSION = 1
#: The owner's record that names the hotkeys (None while the list is empty).
CANARY_LIST_RECORD = "OWNER-CANARY-LIST-01"
#: Public ss58 hotkeys.
CANARY_HOTKEYS = ("5GBmHPBLwyKheugbtAVgxtWdX9YmWjfeCaBwmeFHr4rEWiB5",)


def canary_hotkeys():
    """The registered canary hotkeys, as a frozen set."""
    return frozenset(CANARY_HOTKEYS)


def is_canary(hotkey):
    """Whether `hotkey` is a registered canary."""
    return hotkey in canary_hotkeys()
