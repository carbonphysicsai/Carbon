"""A server whose next step is a provider message rather than a fixed one.

VIOLATION: the refusal's `next_action` differs on every call and disagrees with
the text its own catalogue declares. Two failures in one habit: a client cannot
pin the guidance it was promised, and provider text on the wire is the route by
which unbounded internal detail leaves the process. Nothing here leaks - the
point is that the shape permits it, and that a client reading `next_action`
gets a different answer each time it asks.

Must fail: refusal_next_action_is_fixed_and_declared
"""

from __future__ import annotations

import itertools

import scaffold

attempt = itertools.count(1)


def handler(operation, operation_id, arguments):
    if operation == "start_research_task":
        scaffold.refuse(
            "INVALID_ARGUMENT",
            False,
            next_action=f"upstream retry loop reported attempt {next(attempt)}",
        )
    return {"stub": operation}


if __name__ == "__main__":
    scaffold.serve(
        scaffold.build(handler, name="carbon-stub-varying-next-action", identity=False)
    )
