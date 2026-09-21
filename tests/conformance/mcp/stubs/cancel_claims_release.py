"""VIOLATION: reports cancellation as resources released.

The contract says cancellation is a request, and that only controller-observed
cleanup establishes release. This stub asserts release immediately, which would
let a client believe workers stopped and capacity returned when neither is known.

Target check: cancellation_is_a_request_not_a_release
"""

import scaffold


def handler(operation, operation_id, arguments):
    if operation == "cancel_research_task":
        return {
            "state": "CANCELLED",
            "resources_released": True,
            "detail": "workers stopped and cleanup confirmed",
        }
    return {"ok": True}


if __name__ == "__main__":
    scaffold.serve(scaffold.build(handler, name="stub-cancel-claims-release"))
