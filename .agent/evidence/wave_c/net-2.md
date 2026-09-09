# NET-2 evidence

Status: selected; implementation and canonical acceptance pending.
Base: 6dad22db26e4b8babadf73c4de2527a17485a2b1, PR #120.
Contract/plan: `.agent/tickets/NET-2_authenticated_transport.md`.
Primary map_ref: WAVE-C/NET-2 (Hub structural update required).

Baseline: predecessor NET-1 exact head 528213a passed run 34405478897,
including 169 invariants, 352 network/tooling tests, 86 package and 17 authority
checks. No post-merge full rerun. Native diagnostics are not canonical evidence.

Maturity ceiling: SPECIFIED/IMPLEMENTED/TESTED local development transport.
No public deployment, independent finality, scientific/security qualification,
frontier, settlement, LIVE or production authority.

## Candidate diagnostics

127 native tests passed / 10 explicit Linux SDK/MCP skips across NET-1,
NET-2, both network invariants, selector and retained A9 source boundary.
Ruff/Black pass. The unmodified full MCP native baseline failed because secure
descriptor-relative registry access is unavailable on Windows (102 failures,
41 passed); the first failure was isolated and the boundary was not changed.
Linux MCP baseline passed in NET-1's broad run. Current canonical NET-2 tests
and exact-head acceptance remain pending. No localnet service was started.

NET-2-D1 selects the SDK btauth/1 wrapper plus a bounded durable receipt journal.
The receipt grants no admission/acceptance authority; NET-3 resolves retained
references and reconciles crashes before application dispatch. The synthetic
prototype's 51 tests passed natively as reference diagnostics only; its caller
flags and unbounded history are not adopted as authority or persistence.
