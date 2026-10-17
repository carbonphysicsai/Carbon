"""Truthful direct construction availability for both Launchpad doors.

This is a status projection, not an admission table. A public worker being
installed says nothing about official validator serving or scientific
qualification. Recipe source, architecture and library names are not choices
in this projection.
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
        public = kit is not None and callable(
            getattr(campaign, "construction_reconstruct", None)
        )
        found[entry.challenge_id] = {
            "schema": "carbon.launchpad.construction-paths.v1",
            "challenge": {"id": entry.challenge_id, "version": entry.version},
            "construction_kit": kit,
            "paths": [
                {
                    "id": "public_reconstruction",
                    "availability": "available" if public else "unserved",
                    "reason": (
                        "isolated_public_worker_served_for_supported_recipe_operations"
                        if public
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
