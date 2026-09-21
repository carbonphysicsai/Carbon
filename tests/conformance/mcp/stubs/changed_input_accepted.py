"""VIOLATION: accepts changed input under an existing operation identity.

The contract says reusing an identity with different bytes is a conflict. This
stub happily overwrites, so a client could mutate an in-flight operation by
reusing its identity.

Target check: operation_identity_conflict_is_refused
"""

import json

import scaffold

seen = {}


def handler(operation, operation_id, arguments):
    if operation == "start_research_task":
        # Records the newest input under the same identity instead of conflicting.
        seen[operation_id] = json.dumps(arguments, sort_keys=True)
        return {"task_id": "rtsk_" + "a" * 64, "used_trials": 1}
    return {"ok": True}


if __name__ == "__main__":
    scaffold.serve(
        scaffold.build(handler, identity=False, name="stub-changed-input-accepted")
    )
