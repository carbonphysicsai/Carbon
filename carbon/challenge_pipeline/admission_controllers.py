"""Which campaign controller is the LOCK authority for each (Challenge, level).

GRAPHITE-ADMISSION-CONTROLLER-01, under OWNER-GRAPHITE-TEST-WAVE-03 §2 (W2: an
open finding blocks LOCK of the affected level). Each phase-3 root has its own
campaign controller, and `CampaignController.check_lock` cross-checks a LOCK
only against the controller it is handed. Without a designation, a LOCK could
be checked against a fresh controller that never consumed the findings. This
file names, per (Challenge, construction level), the one controller whose
findings ledger a LOCK binds, by identity (`CampaignController.identity()`:
the bound grant's digest and the store's write-once random id). It never
names a host path.

`admission_controllers.json` (`carbon.admission-controllers.v1`) holds one
entry per (Challenge, level):

    {"challenge", "level", "name", "identity", "status"}

- `status: "DESIGNATED"` with `identity` a `sha256:` digest;
- `status: "PENDING_OPERATOR_IDENTITY"` with `identity: null`, a fail-closed
  placeholder: the designated controller exists only on an operator's host,
  and a LOCK is refused until a follow-up records its identity.

A missing or malformed file refuses every LOCK. Internal development only:
nothing here is scientific or security acceptance.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

SCHEMA = "carbon.admission-controllers.v1"
PATH = Path(__file__).with_name("admission_controllers.json")
DESIGNATED = "DESIGNATED"
PENDING = "PENDING_OPERATOR_IDENTITY"
NOT_DESIGNATED = "admission_controller_not_designated"
MISMATCH = "admission_controller_mismatch"
IDENTITY_PENDING = "admission_controller_identity_pending"
MALFORMED = "admission_controllers_malformed"
_KEYS = {"challenge", "level", "name", "identity", "status"}
_DIGEST = re.compile(r"sha256:[0-9a-f]{64}\Z")
#: A name is a label, never a host path.
_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,99}\Z")
_CHALLENGE = re.compile(r"[a-z0-9][a-z0-9._-]{0,99}\Z")


class DesignationRefused(ValueError):
    """A LOCK or a consumption is not bound to the designated controller."""

    def __init__(self, code, detail=""):
        super().__init__(f"{code}: {detail}" if detail else code)
        self.code = code


def _entry(entry):
    if type(entry) is not dict or set(entry) != _KEYS:
        raise DesignationRefused(
            MALFORMED, "entry keys are " + ", ".join(sorted(_KEYS))
        )
    if type(entry["challenge"]) is not str or not _CHALLENGE.fullmatch(
        entry["challenge"]
    ):
        raise DesignationRefused(MALFORMED, "challenge is a Challenge token")
    level = entry["level"]
    if type(level) is not int or level < 0:
        raise DesignationRefused(MALFORMED, "level is a ladder level")
    if type(entry["name"]) is not str or not _NAME.fullmatch(entry["name"]):
        raise DesignationRefused(MALFORMED, "name is a label, never a host path")
    if entry["status"] == DESIGNATED:
        if type(entry["identity"]) is not str or not _DIGEST.fullmatch(
            entry["identity"]
        ):
            raise DesignationRefused(MALFORMED, "a designated identity is a digest")
    elif entry["status"] == PENDING:
        if entry["identity"] is not None:
            raise DesignationRefused(MALFORMED, "a pending identity is null")
    else:
        raise DesignationRefused(MALFORMED, "status is DESIGNATED or " + PENDING)


def load(path=None):
    """The validated designation document. Any defect refuses (fail closed)."""
    path = PATH if path is None else Path(path)
    try:
        document = json.loads(path.read_bytes())
    except (OSError, ValueError) as error:
        raise DesignationRefused(MALFORMED, type(error).__name__) from None
    if type(document) is not dict or set(document) != {"schema", "controllers"}:
        raise DesignationRefused(MALFORMED, "keys are schema, controllers")
    if document["schema"] != SCHEMA:
        raise DesignationRefused(MALFORMED, "schema is " + SCHEMA)
    if type(document["controllers"]) is not list:
        raise DesignationRefused(MALFORMED, "controllers is a list")
    seen = set()
    for entry in document["controllers"]:
        _entry(entry)
        key = (entry["challenge"], entry["level"])
        if key in seen:
            raise DesignationRefused(MALFORMED, "one entry per (challenge, level)")
        seen.add(key)
    return document


def designation(challenge, level, path=None):
    """The entry for (challenge, level), or None when none is designated."""
    for entry in load(path)["controllers"]:
        if entry["challenge"] == challenge and entry["level"] == level:
            return entry
    return None


def pending(entry):
    """Whether the entry still waits for its operator-reported identity."""
    return entry["status"] == PENDING


def _same_identity(entry, identity):
    return entry["identity"] == identity


def require(challenge, level, identity, path=None):
    """The entry when `identity` is the designated controller's for
    (challenge, level); otherwise refused, typed:
    - `admission_controller_not_designated`: no entry;
    - `admission_controller_identity_pending`: the entry's identity is null;
    - `admission_controller_mismatch`: another controller is designated."""
    entry = designation(challenge, level, path)
    where = f"{challenge} level {level}"
    if entry is None:
        raise DesignationRefused(NOT_DESIGNATED, where)
    if pending(entry):
        raise DesignationRefused(IDENTITY_PENDING, where)
    if not _same_identity(entry, identity):
        raise DesignationRefused(MISMATCH, where)
    return entry
