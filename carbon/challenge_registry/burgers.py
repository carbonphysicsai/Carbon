"""The Burgers adapter: a description over the existing, unchanged Burgers path.

Nothing about Burgers research or evaluation moves here. This reads the
registrations the Burgers campaign already executes, so discovery describes
exactly what runs.
"""

from __future__ import annotations


def describe():
    from carbon.development_session.research_material import capabilities, objective
    from carbon.development_session.research_service import BURGERS_SCAFFOLD
    from carbon.reconstruction.capability_registry import (
        BURGERS_CHALLENGE,
        contract,
        public_registry,
    )

    from .battery import _verdict

    registered = contract(BURGERS_CHALLENGE)
    listed = public_registry(BURGERS_CHALLENGE)["capabilities"]
    return {
        "identity": registered.identity,
        "contract_digest": registered.digest,
        "objective": objective(),
        "capabilities": capabilities(),
        "public_material": {
            "names": [
                "objective",
                "capabilities",
                "training_data",
                "practice_data",
                "reference_method",
            ],
            "access": (
                "start_research_task kind=workspace action=public_material "
                'arguments={"name": ...}'
            ),
        },
        "lanes": {name: list(families) for name, families in registered.lanes},
        "envelope": registered.document()["envelope"],
        "examples": [
            {"strategy": BURGERS_SCAFFOLD, "admission": _verdict(BURGERS_SCAFFOLD)}
        ],
        "unsupported": [
            {"id": c["id"], "status": c["status"], "blocker": c["blocker"]}
            for c in listed
            if c["status"] != "rebuildable_development"
        ],
        "authority": "DEVELOPMENT; historical Burgers path, unchanged",
    }
