"""VIOLATION: loses durable operation identity across reconnect.

The contract says an operation identity stays stable across reconnect, so a
client that reconnects and retries does not repeat work. This stub keeps its map
only in process memory, so the first call after a reconnect dispatches again.

Target check: durable_identity_survives_reconnect
"""

import scaffold

# Deliberately process-local: a reconnect starts a new process and loses this.
memory = {}


seen_input = {}


def handler(operation, operation_id, arguments):
    if operation == "start_research_task":
        # Conflict handling is correct here on purpose: this stub's violation is
        # about identity across retry, not about accepting changed input.
        import json as _json

        fingerprint = _json.dumps(arguments, sort_keys=True, default=str)
        if seen_input.setdefault(operation_id, fingerprint) != fingerprint:
            scaffold.refuse("INVALID_ARGUMENT", False)
        if operation_id not in memory:
            memory[operation_id] = {
                "task_id": f"rtsk_{len(memory) + 1:064x}",
                "used_trials": len(memory) + 1,
            }
        return memory[operation_id]
    return {"ok": True}


if __name__ == "__main__":
    scaffold.serve(
        scaffold.build(handler, identity=False, name="stub-loses-task-identity")
    )
