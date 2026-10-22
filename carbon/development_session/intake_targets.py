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


#: The profile field holding intakes named per Challenge version
#: (published-endpoints v2): {challenge_id: {version: [receiver-paired
#: targets]}}, the first target the primary.
VERSION_INTAKES = "version_intakes"
#: The id-keyed profile fields a Challenge's campaign reads its intake from.
_ID_FIELDS = ("intakes", "receivers", "intake_targets")


def versioned(profile):
    """The profile's per-version intakes, validated: {challenge_id: {version:
    [targets]}}, empty when it names none."""
    value = profile.get(VERSION_INTAKES) or {}
    if type(value) is not dict:
        raise ValueError("version_intakes must map Challenge ids to versions")
    found = {}
    for challenge, versions in value.items():
        if type(challenge) is not str or type(versions) is not dict or not versions:
            raise ValueError("version_intakes must map Challenge ids to versions")
        found[challenge] = {}
        for version, targets in versions.items():
            if type(version) is not str or not version:
                raise ValueError("version_intakes must map Challenge ids to versions")
            found[challenge][version] = validate(targets)
    return found


def for_version(profile, challenge, version):
    """A profile's id-keyed intake fields as the campaign of exactly
    `challenge` at `version` reads them.

    A Challenge whose intakes are named per version (`version_intakes`) gets
    its own version's endpoint only, and none when its version has none: an
    endpoint published for one version never reaches another version's
    submit. A Challenge named by id alone is read exactly as before."""
    table = versioned(profile)
    if challenge not in table:
        return dict(profile)
    found = dict(profile)
    for field in _ID_FIELDS:
        mapping = dict(found.get(field) or {})
        mapping.pop(challenge, None)
        found[field] = mapping
    targets = table[challenge].get(version)
    if targets is not None:
        found["intakes"][challenge] = targets[0]["intake_url"]
        found["receivers"][challenge] = targets[0]["receiver_hotkey"]
        if len(targets) > 1:
            found["intake_targets"][challenge] = targets
    return found


def args_for_version(args, challenge, version):
    """`for_version` for a campaign's arguments: the same object when the
    Challenge is not named per version, else a copy reading only its own
    version's endpoint."""
    fields = vars(args)
    if challenge not in versioned(fields):
        return args
    return type(args)(**for_version(fields, challenge, version))


def journal(root, target):
    """Stable private journal identity, independent of list order."""
    identity = json.dumps(target, sort_keys=True, separators=(",", ":")).encode()
    return Path(root) / "intake-targets" / hashlib.sha256(identity).hexdigest()


def result_path(root, target, epoch):
    """A generic per-validator permitted-result pointer, never a raw path."""
    return journal(root, target) / f"permitted-result-epoch-{epoch}.json"
