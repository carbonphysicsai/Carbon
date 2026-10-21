"""F02 (Burst Thermal)'s direct practice: catalog and graph recipes, built as the receiver
builds them (`carbon.direct_campaign.practice`), scored under the Validator's
practice ruling (structural facts only; the error scale is HUMAN_INPUT)."""

from __future__ import annotations

from carbon.direct_campaign.practice import DirectPractice

from .contracts import SPEC

PROVENANCE = SPEC.practice_provenance
FEEDBACK_SCHEMA = SPEC.practice_schema


class F02DirectPractice(DirectPractice):
    def __init__(self, **kwargs):
        super().__init__(SPEC, **kwargs)
