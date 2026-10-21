"""Truthful direct construction registration for both Launchpad doors.

This is a status projection, not an admission table or a Docker probe. A
registered kit and callback do not prove that this host can run its worker.
Recipe source, architecture and library names are not choices here.
"""

from __future__ import annotations

import re

_DIGEST = re.compile(r"sha256:[0-9a-f]{64}\Z")


def for_challenges():
    from carbon.challenge_registry.campaigns import implemented_campaigns

    found = {}
    for entry, campaign in implemented_campaigns():
        kit = None
        if callable(getattr(campaign, "construction_kit", None)):
            try:
                proposed = campaign.construction_kit()
                if (
                    type(proposed) is dict
                    and set(proposed)
                    == {
                        "id",
                        "version",
                        "train_digest",
                        "interface_digest",
                        "construction_limits_digest",
                    }
                    and proposed["id"] == entry.challenge_id
                    and proposed["version"] == entry.version
                    and all(
                        type(proposed[name]) is str
                        and _DIGEST.fullmatch(proposed[name]) is not None
                        for name in (
                            "train_digest",
                            "interface_digest",
                            "construction_limits_digest",
                        )
                    )
                ):
                    kit = dict(proposed)
            except (ValueError, OSError, TypeError, KeyError):
                pass
        registered = kit is not None and callable(
            getattr(campaign, "construction_reconstruct", None)
        )
        # A Challenge's first registered version keeps its id as the key; a
        # later version (Motor 1.2, the backbone catalog) is "id@version".
        slot = (
            entry.challenge_id
            if entry.challenge_id not in found
            else entry.challenge_id + "@" + entry.version
        )
        found[slot] = {
            "schema": "carbon.launchpad.construction-paths.v1",
            "challenge": {"id": entry.challenge_id, "version": entry.version},
            "construction_kit": kit,
            "paths": [
                {
                    "id": "public_reconstruction",
                    "availability": "unserved",
                    "reason": (
                        "public_reconstruction_registered_host_readiness_unverified"
                        if registered
                        else "isolated_public_worker_unserved"
                    ),
                },
                {
                    "id": "official_submission",
                    "availability": "unserved",
                    "reason": "receiver_paired_direct_reconstruction_unserved",
                },
            ],
            "qualification": False,
        }
    return found
