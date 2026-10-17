"""Prospective launch-bound restriction on validator and commitment effects.

Public practice and its local authentication remain available. The policy is
not a qualification or deployment grant; absence preserves historical behavior.
"""

import json
import sqlite3
from contextlib import closing
from pathlib import Path

from .profile import canonical, digest

FIELD = "submission_policy"
RETAIN_ONLY = "retain_only_v1"
INVALID = "submission_policy_invalid"
RETAINED = "submission_retained_by_policy"


class PolicyInvalid(ValueError):
    code = INVALID

    def __init__(self):
        super().__init__(self.code)


def launch_fields(fields):
    """Closed optional versioned field; explicit null is never omission."""
    if FIELD not in fields:
        return {}
    if type(fields[FIELD]) is not str or fields[FIELD] != RETAIN_ONLY:
        raise PolicyInvalid()
    return {FIELD: RETAIN_ONLY}


def _choice(manifest):
    if type(manifest) is not dict:
        raise PolicyInvalid()
    provider = manifest.get("provider")
    block = provider.get("graphite") if type(provider) is dict else None
    if type(block) is dict:
        choice = launch_fields(block)
        if choice and (
            provider.get("agent") != "graphite" or manifest.get("agent") != "graphite"
        ):
            raise PolicyInvalid()
        return choice
    return {}


def retains(manifest, *, root=None):
    """Validate available frozen authorities before deciding any effect.

    Restricted execution requires the manifest, write-once ledger and original
    launch digest. Comparing each also catches removal of the policy at resume.
    Reads use SQLite's read-only mode and never create campaign state.
    """
    choice = _choice(manifest)
    provider = manifest.get("provider")
    graphite = manifest.get("agent") == "graphite" or (
        type(provider) is dict and provider.get("agent") == "graphite"
    )
    required = bool(choice) or graphite
    if root is None:
        return bool(choice)
    root = Path(root)
    manifest_path = root / "campaign-manifest.json"
    ledger_path = root / "campaign.sqlite3"
    launch_path = root / "graphite" / "launch.json"
    try:
        if manifest_path.exists():
            if _choice(json.loads(manifest_path.read_bytes())) != choice:
                raise PolicyInvalid()
        elif required:
            raise PolicyInvalid()
        if ledger_path.exists():
            with closing(
                sqlite3.connect(ledger_path.resolve().as_uri() + "?mode=ro", uri=True)
            ) as db:
                row = db.execute("SELECT manifest FROM campaign WHERE id=1").fetchone()
            if row is not None and _choice(json.loads(row[0])) != choice:
                raise PolicyInvalid()
            if required and row is None:
                raise PolicyInvalid()
        elif required:
            raise PolicyInvalid()
        if launch_path.exists():
            provider = manifest.get("provider")
            block = provider.get("graphite") if type(provider) is dict else None
            launch = json.loads(launch_path.read_bytes())
            if launch.get("block_digest") != digest(canonical(block)):
                raise PolicyInvalid()
        elif required:
            raise PolicyInvalid()
    except (OSError, sqlite3.Error, ValueError, TypeError, AttributeError) as exc:
        if isinstance(exc, PolicyInvalid):
            raise
        raise PolicyInvalid() from None
    return bool(choice)


def from_root(root):
    path = Path(root) / "campaign-manifest.json"
    try:
        manifest = json.loads(path.read_bytes()) if path.exists() else {}
    except (OSError, ValueError):
        raise PolicyInvalid() from None
    return retains(manifest, root=root)


def require_submission(prepared):
    """Refuse before any validator/chain discovery, signing or evaluation."""
    from .research_campaign import OperationRefused

    try:
        restricted = retains(prepared.manifest, root=prepared.ledger.root)
    except PolicyInvalid:
        raise OperationRefused(INVALID) from None
    if restricted:
        raise OperationRefused(RETAINED)
