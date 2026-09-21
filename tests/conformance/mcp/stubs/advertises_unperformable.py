"""VIOLATION: advertises a capability it cannot perform.

The contract says discovery describes what the endpoint can actually do. This
stub lists a resource whose read fails, so a client planning against discovery
would build on a capability that does not exist.

Target check: capability_discovery_is_performable
"""

import scaffold
from mcp.server.mcpserver.resources import FunctionResource


def handler(operation, operation_id, arguments):
    return {"ok": True}


def unavailable():
    raise RuntimeError("this advertised capability is not implemented")


if __name__ == "__main__":
    server = scaffold.build(handler, name="stub-advertises-unperformable")
    server.add_resource(
        FunctionResource(
            uri="carbon://research/v1/guidance",
            name="carbon://research/v1/guidance",
            mime_type="text/plain",
            fn=unavailable,
        )
    )
    scaffold.serve(server)
