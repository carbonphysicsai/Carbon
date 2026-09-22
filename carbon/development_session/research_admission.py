"""Trusted single-campaign admission, separate from D4's original authority.

This record grants no resources by being present: only an explicitly approved,
operator-installed record is admissible. Consumption remains CampaignLedger's
responsibility. One grant has one immutable root; copying it cannot fund another
campaign. No browser or miner API writes these records.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path

from .profile import canonical, digest
from .research_ledger import (
    DEVELOPMENT_CEILINGS,
    DEVELOPMENT_ELAPSED_SECONDS,
    SUGGESTED_FINAL_RESERVE,
)

SCHEMA = "carbon.launchpad.research-grant.v1"
MANIFEST = "carbon.autoresearch.campaign.v2"
PROFILE = "carbon.burgers-autoresearch-development.v1"


def private_json(path):
    if (
        not path.is_absolute()
        or path.resolve() != path
        or not path.is_file()
        or path.stat().st_size > 65536
        or path.stat().st_mode & 0o077
        or path.parent.stat().st_mode & 0o077
    ):
        raise ValueError("private bounded operator record required")
    raw = path.read_bytes()
    value = json.loads(raw)
    if canonical(value) != raw:
        raise ValueError("canonical operator record required")
    return value


@dataclass(frozen=True)
class Admission:
    path: Path
    pin: str
    document: dict

    @classmethod
    def load(cls, path):
        doc = private_json(path)
        return cls(path, digest(canonical(doc)), doc)

    def verify(self, *, root, principal, runtime, now):
        doc = private_json(self.path)
        if digest(canonical(doc)) != self.pin or doc != self.document:
            raise ValueError("grant changed or revoked")
        fields = {
            "schema",
            "status",
            "authority",
            "grant_id",
            "campaign_id",
            "root",
            "principal",
            "miner_identity",
            "profile",
            "runtime",
            "provider",
            "account_ref",
            "campaign_count",
            "ceilings",
            "elapsed_seconds",
            "expires_unix",
            "cleanup",
            "retry_allowance",
        }
        if set(doc) != fields or doc["schema"] != SCHEMA:
            raise ValueError("closed grant required")
        if (
            doc["status"] != "APPROVED"
            or doc["authority"] == "OWNER-C-W1-D4-AUTORESEARCH-01"
        ):
            raise ValueError("separate explicit Launchpad grant required")
        for key in (
            "authority",
            "grant_id",
            "campaign_id",
            "principal",
            "miner_identity",
            "account_ref",
        ):
            if type(doc[key]) is not str or not 1 <= len(doc[key]) <= 128:
                raise ValueError("bounded grant identity required")
        if (
            root.resolve() != root
            or str(root) != doc["root"]
            or doc["principal"] != principal
            or doc["runtime"] != runtime
            or doc["profile"] != PROFILE
            or doc["provider"] != "openai-responses"
            or type(doc["campaign_count"]) is not int
            or doc["campaign_count"] != 1
            or doc["retry_allowance"] != 0
            or doc["cleanup"]
            != "all-campaign-owned-work; unresolved-reservations-retained"
        ):
            raise ValueError("grant binding mismatch")
        expires = doc["expires_unix"]
        if (
            type(expires) not in (int, float)
            or not math.isfinite(expires)
            or not math.isfinite(now)
            or now >= expires
        ):
            raise ValueError("grant expired or invalid")
        caps = doc["ceilings"]
        if type(caps) is not dict or set(caps) != set(DEVELOPMENT_CEILINGS):
            raise ValueError("all resource dimensions required")
        for key, maximum in DEVELOPMENT_CEILINGS.items():
            if (
                type(caps[key]) is not int
                or not SUGGESTED_FINAL_RESERVE.get(key, 0) <= caps[key] <= maximum
            ):
                raise ValueError("grant outside supported envelope")
        if (
            type(doc["elapsed_seconds"]) is not int
            or not 1 <= doc["elapsed_seconds"] <= DEVELOPMENT_ELAPSED_SECONDS
        ):
            raise ValueError("bounded original deadline required")
        return doc

    def binding(self):
        return {"path": str(self.path), "digest": self.pin}


def verify_cleanup_owner(ledger, owner, *, db=None):
    """Authenticate retained campaign ownership without admitting further work.

    Expiration ends spending authority, not responsibility for already-owned
    cleanup. This proof never reserves resources, restarts a task, changes a
    grant, or substitutes for the caller's fresh external authentication.
    """
    admission = ledger.admission
    if type(admission) is not Admission:
        raise ValueError("explicit retained campaign authority required")
    doc = private_json(admission.path)
    if db is None:
        with ledger.db() as connection:
            return verify_cleanup_owner(ledger, owner, db=connection)
    row = db.execute("SELECT manifest FROM campaign WHERE id=1").fetchone()
    control = db.execute(
        "SELECT generation FROM launchpad_control WHERE id=1"
    ).fetchone()
    if row is None:
        raise ValueError("frozen campaign required for cleanup")
    manifest = json.loads(row[0])
    if (
        doc != admission.document
        or digest(canonical(doc)) != admission.pin
        or doc.get("schema") != SCHEMA
        or doc.get("status") != "APPROVED"
        or doc.get("profile") != PROFILE
        or manifest.get("schema") != MANIFEST
        or manifest.get("owner") != owner
        or manifest.get("grant") != admission.binding()
        or manifest.get("principal") != doc.get("principal")
        or manifest.get("runtime") != doc.get("runtime")
        or manifest.get("campaign_id") != doc.get("campaign_id")
        or manifest.get("authority") != doc.get("authority")
        or str(ledger.root) != doc.get("root")
        or ledger.root.resolve() != ledger.root
        or ledger.generation is None
        or control is None
        or control[0] != ledger.generation
    ):
        raise ValueError("retained campaign ownership changed")
    return manifest
