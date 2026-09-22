"""A server whose catalogue advertises an operation it does not serve.

VIOLATION: the surface catalogue is not a description of this surface. It lists
`carbon_research_v2__reconcile_campaign`, which no tool implements, so a client
that pinned the catalogue and built a call for that operation would find it
missing at the moment it mattered. A catalogue a client cannot rely on is worse
than none, because pinning it is the thing it invites.

Must fail: surface_catalogue_matches_served_tools
"""

from __future__ import annotations

import scaffold

if __name__ == "__main__":
    scaffold.serve(
        scaffold.build(
            lambda operation, operation_id, arguments: {"stub": operation},
            name="carbon-stub-catalogue-drift",
            resources={
                scaffold.CAPABILITIES_URI: "{}",
                scaffold.CATALOGUE_URI: scaffold.catalogue_document(
                    operations=(*scaffold.OPERATIONS, "reconcile_campaign"),
                ),
            },
        )
    )
