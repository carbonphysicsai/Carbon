# Authenticated Carbon application transport v1

NET-2 wraps the unchanged A9 MCP core in `carbon.transport`. It adds no public
listener. The trusted composition root constructs a ChainContext, ChallengeKey,
NET-1 adapter, ReceiptJournal, BittensorHotkeyVerifier and AuthenticatedGateway.
No import opens a database, wallet, socket or SDK client. `carbon.chain.auth`
owns the exact Bittensor 11.1.0 `btauth/1` API and optional explicit message signer.

The canonical request is ASCII-escaped UTF-8 JSON, sorted keys, compact separators,
finite JSON numbers, no duplicate keys. Its exact allow-list is protocol, network,
genesis, netuid, challenge_id, challenge_version, snapshot, session, request, tool
and fields. The signed method/path are POST /carbon/v1/mcp. Both receiver and the
canonical body are authenticated by the SDK; sender identity comes from the
verified signature, never a caller identity field. Challenge fields cannot
contradict their envelope. Unknown tool/field behavior remains MCP-owned.

Client construction uses `carbon.transport.models.message(context, snapshot_id,
challenge, session=..., request=..., tool=..., fields=...)`. Explicitly supplied
hotkey signers use `carbon.chain.auth.BittensorMessageSigner.sign`. The server
refreshes its finalized provider snapshot, checks its exact identity and age,
then commits verification and receipt order in a SQLite transaction.

Development bounds: 64 KiB body, 4 KiB headers, 16 levels, 4,096 JSON nodes,
10-second nonce age with 2-second forward skew, 60-second snapshot age,
32 accepted requests/hotkey/second and at most 100,000 retained receipts.
These settings are development limits, not approved production SLOs or security.
Journal exhaustion fails closed; it does not erase replay evidence to keep serving.
Receipts contain only public request digests and identity/provenance, no signatures,
keys, raw strategies, results or evaluator-held data. The journal has indexed
nonce/request lookups and bounded total capacity. It persists provider context,
clock/block/snapshot watermarks and original authenticated commit order.

A ReceiptRef is only a reference: NET-3 must resolve it from the journal and bind
its body digest/context. Receipt construction by a caller grants no authority.
Exact duplicate signed nonces fail AUTH_REPLAY. A freshly signed duplicate request
ID fails TRANSPORT_REPLAY; different bytes under that request ID fail
TRANSPORT_CONFLICT. None dispatches again. Failed verification/insertion rolls back
both nonce and receipt. The caller may not refresh receipt age with a body timestamp.
Old nonces are pruned only below the verified freshness window, atomically with
an advancing durable watermark. Restore must preserve the journal; replacing it
with an empty file is not safe replay recovery.

`gateway.dispatch` returns the retained reference plus the existing MCP result
object for the authenticated requester. It does not generically serialize results.
A6 owns disclosure; NET-5/NET-6 own the bounded listener and explicit wire projection.
Authentication proves a registered hotkey supplied these bytes in this context.
Submission, admission, evaluation, acceptance and disclosure remain separate.

A crash after the durable receipt but before application dispatch leaves a receipt,
not evidence of admission. NET-3 must reconcile it with the existing lifecycle;
blind redispatch is forbidden. NET-1 finality remains provider-reported, not an
independent quorum proof. Real TLS, deployment, custody, traffic defence and security
qualification remain later operation-specific requirements. No public service,
public-network transaction, scientific or LIVE authority is created here.

Canonical focused validation: `./scripts/dev/canonical.sh ./scripts/dev/ci.sh`.
NET-2 includes all NET-1 contracts, the existing MCP suite, new auth/journal tests,
all invariant and package lanes. Native Windows cannot execute the existing secure
A3 descriptor-relative registry; it cannot replace Linux integration acceptance.
