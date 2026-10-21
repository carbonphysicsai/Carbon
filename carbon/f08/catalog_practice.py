"""F08 (Ribbed Bracket)'s direct practice: catalog and graph recipes, built as the receiver
builds them (`carbon.direct_campaign.practice`), scored under the Validator's
practice rulings (aggregate errors on its registered scale)."""

from __future__ import annotations

from carbon.direct_campaign.practice import DirectPractice

from .contracts import SPEC

PROVENANCE = SPEC.practice_provenance
FEEDBACK_SCHEMA = SPEC.practice_schema


class F08DirectPractice(DirectPractice):
    def __init__(self, **kwargs):
        super().__init__(SPEC, **kwargs)
