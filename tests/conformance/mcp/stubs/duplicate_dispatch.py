"""VIOLATION: repeats dispatch for a repeated operation identity.

The contract says one business operation identity means one dispatch, including
on retry. This stub returns a fresh task for every call, so a client that
retried after a lost response would silently pay twice.

Target check: operation_identity_replay_does_not_redispatch
"""

import scaffold

counter = {"n": 0}


seen_input = {}


def handler(operation, operation_id, arguments):
    if operation == "start_research_task":
        # Conflict handling is correct here on purpose: this stub's violation is
        # about identity across retry, not about accepting changed input.
        import json as _json

        fingerprint = _json.dumps(arguments, sort_keys=True, default=str)
        if seen_input.setdefault(operation_id, fingerprint) != fingerprint:
            scaffold.refuse("INVALID_ARGUMENT", False)
        counter["n"] += 1
        return {"task_id": f"rtsk_{counter['n']:064x}", "used_trials": counter["n"]}
    return {"ok": True}


if __name__ == "__main__":
    scaffold.serve(
        scaffold.build(handler, identity=False, name="stub-duplicate-dispatch")
    )
