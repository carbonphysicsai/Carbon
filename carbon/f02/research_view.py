"""F02 (Burst Thermal)'s public-practice declaration for the research view
(`carbon.direct_campaign.research_view`), read under F02 (Burst Thermal)'s research key.
"""

from __future__ import annotations

from carbon.direct_campaign import research_view as _shared

from .contracts import SPEC


def research_view():
    return _shared.research_view(SPEC)
