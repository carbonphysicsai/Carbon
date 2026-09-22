"""A server whose capacity refusal will not say that nothing was dispatched.

VIOLATION: refusing for want of capacity happens before any work is handed on,
so `dispatch_may_have_occurred=false` is the whole content of the refusal. This
server says `true`, which tells a client that a charge may exist for an
operation that never started - the reconciliation-required state the campaign
model exists to avoid, manufactured by the transport rather than by any real
consumption.

Must fail: capacity_bound_is_declared_and_honoured
"""

from __future__ import annotations

import scaffold


def handler(operation, operation_id, arguments):
    # Only the operation the capacity probe uses, so this stub fails the
    # capacity check and not every other check by refusing everything.
    if operation == "dry_validate":
        scaffold.refuse("CAPACITY_UNAVAILABLE", True)
    return {"stub": operation}


if __name__ == "__main__":
    scaffold.serve(scaffold.build(handler, name="carbon-stub-capacity-claims-dispatch"))
