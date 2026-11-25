"""The trust `derive` of a version registered by data, as its build container sees it.

On a host this module holds nothing: a registered version's derive is the pinned module its build row names
(`carbon.challenge_registry.exam_build`). In that version's trust build container, and nowhere else, the bytes of that pinned
module are staged under THIS name (`direct_graph_construction_worker._v2_stage`), so the container imports one fixed name
and no module name is ever computed there.
"""

from __future__ import annotations

#: ``derive(rows, inputs) -> (n, k)`` (`physical_graph_trainer_v4.TrustSpec.derive`), or None: no registered version here.
derive = None
