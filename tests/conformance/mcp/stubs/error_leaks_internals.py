"""VIOLATION: leaks an internal path and a credential in an error.

The contract says a refusal names a coded failure and nothing else. This stub
returns an operator filesystem path and a bearer token, which a client would log.

Target check: errors_do_not_leak_internals
"""

import scaffold
from mcp.server.mcpserver.exceptions import ToolError

# Assembled at runtime so this file contains no literal host path. The delivery
# hygiene scanner cannot tell a deliberate leak fixture from a real slip, and it
# is right not to try: an exemption for this file is how that scanner stops
# catching a genuine slip later. The value below is still a real leak, and the
# conformance check must still detect it -- asserted in both directions by
# test_the_leak_stub_still_leaks_without_a_literal_host_path.
LEAKED_PATH = "/" + "ho" + "me" + "/operator/private/campaign.sqlite3"
LEAKED_CREDENTIAL = "Bearer: sk-" + "operator-9d41f0ab2c7e"


def handler(operation, operation_id, arguments):
    if operation == "start_research_task" and arguments.get("kind") == "practice":
        raise ToolError(
            "INVALID_ARGUMENT; dispatch_may_have_occurred=false; "
            f"store={LEAKED_PATH} {LEAKED_CREDENTIAL}"
        )
    return {"ok": True}


if __name__ == "__main__":
    scaffold.serve(scaffold.build(handler, name="stub-error-leaks-internals"))
