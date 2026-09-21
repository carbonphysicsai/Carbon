"""VIOLATION: leaks an internal path and a credential in an error.

The contract says a refusal names a coded failure and nothing else. This stub
returns an operator filesystem path and a bearer token, which a client would log.

Target check: errors_do_not_leak_internals
"""

import scaffold
from mcp.server.mcpserver.exceptions import ToolError


def handler(operation, operation_id, arguments):
    if operation == "start_research_task" and arguments.get("kind") == "practice":
        raise ToolError(
            "INVALID_ARGUMENT; dispatch_may_have_occurred=false; "
            "store=/home/operator/private/campaign.sqlite3 "
            "Bearer: sk-operator-9d41f0ab2c7e"
        )
    return {"ok": True}


if __name__ == "__main__":
    scaffold.serve(scaffold.build(handler, name="stub-error-leaks-internals"))
