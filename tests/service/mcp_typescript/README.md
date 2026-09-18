# Independent MCP client fixture

The pinned official TypeScript client is `@modelcontextprotocol/client` 2.0.0
(Node >=20), with transitive versions and integrity values in `pnpm-lock.yaml`.
This is the stable split v2 package, rather than the historical combined
`@modelcontextprotocol/sdk` package. The tested server uses Python `mcp` 2.2.0.
The versioned [upstream stdio implementation](https://github.com/modelcontextprotocol/typescript-sdk/blob/%40modelcontextprotocol%2Fclient%402.0.0/packages/client/src/client/stdio.ts)
defines the transport used here.

From the repository root, with the Carbon MCP Python test environment active:

```sh
pnpm --dir tests/service/mcp_typescript install --frozen-lockfile --ignore-scripts
CARBON_REQUIRE_TYPESCRIPT_INTEROP=1 python -m pytest tests/service/test_standard_mcp_typescript.py -q
```

`CARBON_MCP_TYPESCRIPT_NODE` selects an explicit Node executable. The Python
wrapper also supports an installed Windows Node executable from WSL, using the
current distro and existing Python environment. It does not change MCP host
configuration or install dependencies during a test run. Required acceptance
must set `CARBON_REQUIRE_TYPESCRIPT_INTEROP=1`; without it, an environment lacking
the optional JavaScript client or Node reports a skip, never a pass.

The client starts the same trusted fixture server used by the Python SDK tests.
The fixture retains real adapter validation, proposal admission and durable
ledger behavior; only the domain execution response is deterministic fixture
data. Assertions cover discovery, versioned resources/prompts, typed structured
results with text fallback, invalid input and principal rejection, error
redaction, stable business identity, changed-input conflict, and a second server
process reusing the ledger without spending another trial.

This is evidence from two independently implemented protocol clients when
combined with the Python SDK tests. It is not an agent-host session, paid model
experiment, scientific trial, or production security acceptance.
