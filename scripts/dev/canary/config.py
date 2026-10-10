"""The canary runner's configuration (CANARY-01 S1): strict JSON, owner-only.

The owner writes one file. It names public values and paths only:

- the canary's public ss58 hotkey, which must be a registered canary
  (`carbon.challenge_validator.canary.CANARY_HOTKEYS`, OWNER-CANARY-LIST-01);
- the canary's own Launchpad install: its state directory, and the Python
  and checkout its MCP door runs from, as setup's snippets name them;
- the Challenge id and version;
- the validator intake's URL and its public receiver hotkey;
- the variant list, and the runner's own cursor and journal paths;
- `deadlines`, one per stage, each seconds or null. They are HUMAN_INPUT: the
  owner sets them from measured runs. A null deadline only measures and never
  alerts on time;
- `poll`: how often the runner observes, and how long one run waits before it
  leaves the cycle for the next run. Neither is a deadline, and neither alerts;
- `healthcheck_env_file`: the path of an owner-only file holding
  `HC_CANARY=<ping url>`, or null for no pings. The URL is read from there by
  path, and never logged.

No key, password, token or ping URL is ever in the config. The file itself
must be an owner-only regular file (no symlink, no group or world access).
Every refusal is a closed code, never the file's content.
"""

from __future__ import annotations

import json
import math
import os
import re
import stat
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit

SCHEMA = "carbon.canary.config.v1"
#: The stages a cycle measures, in order (plan §1). `weights` is S2.
STAGES = ("door", "window", "commit", "admission", "scoring", "verdict", "weights")
MAX_BYTES = 16384
#: The longest deadline or wait a config may name: a week, in seconds.
MAX_SECONDS = 7 * 24 * 3600
_SS58 = re.compile(r"[1-9A-HJ-NP-Za-km-z]{46,48}")
_TEXT = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}")
_LOOPBACK = {"127.0.0.1", "localhost", "::1"}
_FIELDS = frozenset(
    {
        "schema",
        "hotkey",
        "launchpad",
        "challenge",
        "intake",
        "variants",
        "cursor",
        "journal",
        "deadlines",
        "poll",
        "healthcheck_env_file",
    }
)


class ConfigRefused(ValueError):
    """A config, or a file it names, that the runner will not use.

    `code` is closed; `field` names the config field to correct, when one is
    to blame. Neither carries the file's content."""

    def __init__(self, code, field=None):
        super().__init__(code if field is None else f"{code}: {field}")
        self.code = code
        self.field = field


def owner_only_bytes(path, *, limit, code):
    """The bytes of an owner-only regular file, or `ConfigRefused(code)`.

    Refused: a missing file, a symlink, anything but a regular file, a file
    another user owns, any group or world permission bit, or more than
    `limit` bytes."""
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | getattr(os, "O_CLOEXEC", 0))
    except OSError:
        raise ConfigRefused(code) from None
    try:
        info = os.fstat(fd)
        if (
            not stat.S_ISREG(info.st_mode)
            or info.st_uid != os.geteuid()
            or info.st_mode & 0o077
            or info.st_size > limit
        ):
            raise ConfigRefused(code)
        data = os.read(fd, limit + 1)
    finally:
        os.close(fd)
    if len(data) > limit:
        raise ConfigRefused(code)
    return data


@dataclass(frozen=True)
class Config:
    hotkey: str
    state_dir: Path
    python: Path
    checkout: Path
    challenge_id: str
    challenge_version: str
    intake_url: str
    receiver: str
    variants: Path
    cursor: Path
    journal: Path
    #: stage -> seconds, or None (HUMAN_INPUT: measure only, never alert).
    deadlines: dict
    poll_interval: float
    max_wait: float
    healthcheck_env_file: Path | None


def _object(value, keys, field):
    if type(value) is not dict or set(value) != set(keys):
        raise ConfigRefused("config_closed_object_required", field)
    return value


def _path(value, field):
    if type(value) is not str or not value or "\x00" in value:
        raise ConfigRefused("config_absolute_path_required", field)
    path = Path(value)
    if not path.is_absolute() or ".." in path.parts:
        raise ConfigRefused("config_absolute_path_required", field)
    return path


def _ss58(value, field):
    if type(value) is not str or not _SS58.fullmatch(value):
        raise ConfigRefused("config_ss58_required", field)
    return value


def _text(value, field):
    if type(value) is not str or not _TEXT.fullmatch(value):
        raise ConfigRefused("config_identifier_required", field)
    return value


def _seconds(value, field, *, low):
    if (
        type(value) not in (int, float)
        or not math.isfinite(value)
        or not low <= value <= MAX_SECONDS
    ):
        raise ConfigRefused("config_seconds_out_of_bounds", field)
    return float(value)


def _intake_url(value, field):
    """An https URL, or http on this machine's loopback (a tunnel to the
    validator), as the Launchpad's own profile accepts an intake."""
    if type(value) is not str or len(value) > 512:
        raise ConfigRefused("config_intake_url_invalid", field)
    try:
        parts = urlsplit(value)
        host = parts.hostname
        _ = parts.port  # a malformed port raises here
    except ValueError:
        raise ConfigRefused("config_intake_url_invalid", field) from None
    if (
        parts.username is not None
        or parts.password is not None
        or parts.query
        or parts.fragment
        or host is None
        or not (
            parts.scheme == "https" or (parts.scheme == "http" and host in _LOOPBACK)
        )
    ):
        raise ConfigRefused("config_intake_url_invalid", field)
    return value.rstrip("/")


def parse(document):
    """A `Config` from the parsed JSON document, or `ConfigRefused`.

    The hotkey must be a registered canary, or one of INCENTIVE-CANARY-01's
    registered role miners (`roles.ROLES`): a config naming any other hotkey
    is refused here, before the runner reads, launches or sends anything."""
    from carbon.challenge_validator.canary import is_canary
    from scripts.dev.canary import roles

    if type(document) is not dict or set(document) != _FIELDS:
        raise ConfigRefused("config_closed_object_required")
    if document["schema"] != SCHEMA:
        raise ConfigRefused("config_schema_unknown", "schema")
    hotkey = _ss58(document["hotkey"], "hotkey")
    if not is_canary(hotkey) and roles.role_of(hotkey) is None:
        raise ConfigRefused("hotkey_not_registered_canary", "hotkey")
    launchpad = _object(
        document["launchpad"], ("state_dir", "python", "checkout"), "launchpad"
    )
    challenge = _object(document["challenge"], ("id", "version"), "challenge")
    intake = _object(document["intake"], ("url", "receiver"), "intake")
    deadlines = _object(document["deadlines"], STAGES, "deadlines")
    poll = _object(document["poll"], ("interval_seconds", "max_wait_seconds"), "poll")
    interval = _seconds(poll["interval_seconds"], "poll.interval_seconds", low=1)
    max_wait = _seconds(poll["max_wait_seconds"], "poll.max_wait_seconds", low=1)
    if max_wait < interval:
        raise ConfigRefused("config_seconds_out_of_bounds", "poll.max_wait_seconds")
    env_file = document["healthcheck_env_file"]
    paths = {
        "launchpad.state_dir": _path(launchpad["state_dir"], "launchpad.state_dir"),
        "launchpad.python": _path(launchpad["python"], "launchpad.python"),
        "launchpad.checkout": _path(launchpad["checkout"], "launchpad.checkout"),
        "variants": _path(document["variants"], "variants"),
        "cursor": _path(document["cursor"], "cursor"),
        "journal": _path(document["journal"], "journal"),
    }
    if paths["cursor"] == paths["journal"]:
        raise ConfigRefused("config_paths_must_differ", "journal")
    return Config(
        hotkey=hotkey,
        state_dir=paths["launchpad.state_dir"],
        python=paths["launchpad.python"],
        checkout=paths["launchpad.checkout"],
        challenge_id=_text(challenge["id"], "challenge.id"),
        challenge_version=_text(challenge["version"], "challenge.version"),
        intake_url=_intake_url(intake["url"], "intake.url"),
        receiver=_ss58(intake["receiver"], "intake.receiver"),
        variants=paths["variants"],
        cursor=paths["cursor"],
        journal=paths["journal"],
        deadlines={
            stage: (
                None
                if deadlines[stage] is None
                else _seconds(deadlines[stage], "deadlines." + stage, low=1)
            )
            for stage in STAGES
        },
        poll_interval=interval,
        max_wait=max_wait,
        healthcheck_env_file=(
            None if env_file is None else _path(env_file, "healthcheck_env_file")
        ),
    )


def load(path):
    """The config at `path`: an owner-only file, strictly parsed."""
    raw = owner_only_bytes(path, limit=MAX_BYTES, code="config_file_unusable")
    try:
        document = json.loads(raw)
    except ValueError:
        raise ConfigRefused("config_json_invalid") from None
    return parse(document)
