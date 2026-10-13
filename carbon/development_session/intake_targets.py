"""Receiver-paired multi-validator profile data; no network or signer access."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from urllib.parse import urlsplit

ADDRESS = re.compile(r"[1-9A-HJ-NP-Za-km-z]{47,48}\Z")
FIELDS = {"intake_url", "receiver_hotkey"}
# A configuration resource bound, not a scientific or economic parameter.
MAX_TARGETS = 32


def intake_url(value):
    """The retained HTTPS/own-loopback URL rule."""
    if type(value) is not str or len(value) > 512:
        return False
    try:
        url = urlsplit(value)
    except ValueError:
        return False
    if url.query or url.fragment or not url.hostname:
        return False
    return url.scheme == "https" or (
        url.scheme == "http" and url.hostname in ("127.0.0.1", "localhost")
    )


def validate(value):
    """Fresh closed pairs; conflicting URLs/receivers cannot enter a profile."""
    if type(value) is not list or not 1 <= len(value) <= MAX_TARGETS:
        raise ValueError("intake_targets must contain receiver-paired validators")
    urls, receivers, result = set(), set(), []
    for item in value:
        if (
            type(item) is not dict
            or set(item) != FIELDS
            or not intake_url(item["intake_url"])
            or type(item["receiver_hotkey"]) is not str
            or not ADDRESS.fullmatch(item["receiver_hotkey"])
            or item["intake_url"] in urls
            or item["receiver_hotkey"] in receivers
        ):
            raise ValueError("intake_targets must name distinct pinned validators")
        urls.add(item["intake_url"])
        receivers.add(item["receiver_hotkey"])
        result.append(dict(item))
    return result


def for_challenge(profile, challenge):
    """None denotes the historical single-target path, never a guessed pin."""
    targets = profile.get("intake_targets", {})
    if type(targets) is not dict:
        raise ValueError("intake_targets must map Challenge ids to validator lists")
    return validate(targets[challenge]) if challenge in targets else None


def journal(root, target):
    """Stable private journal identity, independent of list order."""
    identity = json.dumps(target, sort_keys=True, separators=(",", ":")).encode()
    return Path(root) / "intake-targets" / hashlib.sha256(identity).hexdigest()
