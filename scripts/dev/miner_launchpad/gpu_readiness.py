"""Which catalog backbones the validator can grade officially (OWNER-GPU-OPEN-WITH-READY-01).

Official readiness lives only in the validator's on-box receipt store, so it is read from the receiver's public
intake document (``GET /carbon/v1/construction/intake``, key ``official_gpu``); never from the repository's own
receipts, which cannot see what the validator certified. Display only: practice stays open for every entry and
nothing is hidden.

The document says ``{"status", "ready": [catalog_id, ...], "log_head"}``. ``ready`` is for the one Challenge version
that receiver serves. Anything but status ``OK`` (``STORE_ABSENT``, ``STORE_UNREADABLE``, ``UNAVAILABLE``), a
missing key (an older receiver), another version, an unreachable intake or a malformed answer is **unknown**
(``None``), shown as nothing at all and never as "nothing is ready".

A read answers at once with the last result and, when that is older than ``TTL`` seconds, starts one fresh read in
the background, so a Control Center read never waits for a remote validator.
"""

from __future__ import annotations

import threading
import time

TTL = 10.0
TIMEOUT = 3.0
_CACHE: dict = {}
_LOCK = threading.Lock()


def parse(facts, challenge_id, version):
    """The set of ready catalog ids for `challenge_id` at `version`, or None when it cannot be known."""
    if type(facts) is not dict:
        return None
    if facts.get("challenge") != {"id": challenge_id, "version": version}:
        return None
    official = facts.get("official_gpu")
    if type(official) is not dict or official.get("status") != "OK":
        return None
    ready = official.get("ready")
    if type(ready) is not list or not all(type(item) is str for item in ready):
        return None
    return frozenset(ready)


def target_url(cfg, challenge_id, version):
    """The intake URL this profile submits `challenge_id` at `version` to, or None."""
    if type(cfg) is not dict:
        return None
    from carbon.development_session import intake_targets

    try:
        found = intake_targets.for_version(cfg, challenge_id, version)
    except (ValueError, TypeError, AttributeError):
        return None
    intakes = found.get("intakes")
    url = intakes.get(challenge_id) if type(intakes) is dict else None
    if type(url) is str:
        return url
    direct, serves = cfg.get("direct_intake_target"), cfg.get("direct_intake_serves")
    if (
        type(direct) is dict
        and type(serves) is dict
        and (serves.get("id"), serves.get("version")) == (challenge_id, version)
        and type(direct.get("intake_url")) is str
    ):
        return direct["intake_url"]
    return None


def _fetch(url):
    from carbon.development_session import direct_submission

    return direct_submission.read_intake(url, timeout=TIMEOUT)


def _refresh(key, fetch):
    url, challenge_id, version = key
    try:
        value = parse(fetch(url), challenge_id, version)
    # Unreachable or malformed is unknown, never a stale "ready".
    except Exception:  # noqa: BLE001
        value = None
    with _LOCK:
        slot = _CACHE.setdefault(key, {"value": None, "at": 0.0})
        slot["running"] = False
        slot["value"], slot["at"] = value, time.monotonic()


def lookup(url, challenge_id, version, *, fetch=None, background=True):
    """The ready ids as last read (None while unknown), refreshing in the background when stale.
    With ``background=False`` the refresh runs here (tests)."""
    if type(url) is not str:
        return None
    key = (url, challenge_id, version)
    fetch = fetch or _fetch
    with _LOCK:
        slot = _CACHE.setdefault(key, {"value": None, "at": 0.0})
        stale = time.monotonic() - slot["at"] >= TTL
        start = stale and not slot.get("running")
        if start:
            slot["running"] = True
    if start:
        if background:
            threading.Thread(target=_refresh, args=(key, fetch), daemon=True).start()
        else:
            _refresh(key, fetch)
    with _LOCK:
        return _CACHE[key]["value"]


def mark(recipes, ready):
    """`recipes` (the picker's entries) with ``officially_gradable``: True or False once the validator's list is
    known, None when it is not."""
    return [
        {
            **recipe,
            "officially_gradable": (
                None if ready is None else recipe.get("catalog_id") in ready
            ),
        }
        for recipe in recipes
    ]
