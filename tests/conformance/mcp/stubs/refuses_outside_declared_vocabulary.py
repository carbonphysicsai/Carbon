"""A server that refuses with a code its own catalogue never declared.

VIOLATION: the catalogue publishes a closed refusal vocabulary and this server
refuses with `PROVIDER_ERROR`, which is not in it. A client branches on that
vocabulary; a code outside it lands in whatever the client does with the
unexpected, which is the path nobody designed. The refusal envelope itself is
well formed, which is what makes this worth a stub: everything looks right
except the one thing a client would key on.

Must fail: refusal_vocabulary_is_declared
"""

from __future__ import annotations

import scaffold


def handler(operation, operation_id, arguments):
    if operation == "start_research_task":
        # Shaped exactly like a conforming refusal, including a next step.
        scaffold.refuse(
            "PROVIDER_ERROR",
            False,
            next_action="Retry the operation with the same operation_id.",
        )
    return {"stub": operation}


if __name__ == "__main__":
    scaffold.serve(
        scaffold.build(handler, name="carbon-stub-undeclared-code", identity=False)
    )
