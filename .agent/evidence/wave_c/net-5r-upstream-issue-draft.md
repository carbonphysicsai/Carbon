# Draft upstream issue — shielded success leaves a later plain SDK intent stale

**Prepared locally only:** do not submit without maintainer-contact authorization.

## Suggested title

`submit_shielded` success can regress the per-transport nonce cache before a
later plain `execute`

## Environment

- `bittensor==11.1.0`, wheel SHA-256
  `d84e33169249c56c41b4b43f6b2f4ed80bc2fd98afcb69a3d5844720a4d72b58`;
- subtensor v445 source commit
  `d3f40e44bda9019c606aeb0c907bb52ba7fe386c`;
- pinned standard/non-fast localnet image
  `ghcr.io/raofoundation/subtensor-localnet@sha256:bb762bf7a88502e0e21f76a1e6615ad4c00316f6b0e988dba2e59035c015aa86`;
- Ubuntu 24.04, linux/amd64 Docker; standard 12-second runtime.

## Minimal sequence

1. On one `Client` / `RpcSubstrate`, submit a required shielded intent for an
   account with next nonce `n` and wait for its carrier and inner extrinsic.
2. Confirm the carrier at nonce `n` and decrypted inner at nonce `n+1` both
   finalize successfully.
3. On the same transport, submit a plain policy-approved intent for that
   account with `Client.execute(..., retries=0)`.
4. The plain transaction is rejected by the pool as `Stale/expired` and is not
   included.

Canonical disposable run 34474220953 observed this sequence with `n=0` for the
account. Carrier `0x8550b3e0d889362cbd2149a7975d6ea2144398d23a077d90fb6fdcb3eab08229`
and inner `0x7180b60d4d2619237dcd316a1b9874eb7ddd98d9420d226ca427d870a8f7c170`
both finalized at block 79. The later plain transaction
`0x391e2b0c99adf161abc20aaa1133a1cef797df624a9e76b9a9defe35141a7429`
was rejected `Stale/expired` with no inclusion.

## Source-backed hypothesis

In the exact 11.1.0 wheel:

- `Executor.submit_shielded` fetches `n`, signs the inner with `n+1`, then calls
  `substrate.submit(..., nonce=n)` for the carrier;
- `SubstrateConnection.create_signed_extrinsic` pins every explicit nonce into
  its `NonceCache`; consequently the inner signing pins `n+1`, then the carrier
  signing pins the lower value `n`;
- a later plain `execute` omits an explicit nonce, so the same cache increments
  the retained `n` to `n+1`, which the successful inner already consumed.

This is a hypothesis tied to the observed source sequence and pool result. The
run does not establish a timing, proposer-keystore or standard-versus-fast root
cause.

## Expected behavior

After the shield carrier and inner resolve successfully, the SDK transport
should make the next plain submission use the chain/pool next index (`n+2` in
this sequence). A supported repair could advance the cache through the inner
nonce or invalidate/refetch it after the shielded outcome. Failed and ambiguous
shield outcomes still need fail-closed nonce handling.

## Local compatibility workaround under test

Carbon verifies the finalized public `System.Account` nonce is exactly
`inner_nonce+1`, then retires and recreates the public `Client` / `RpcSubstrate`
with the same strict endpoint/genesis/runtime/policy checks before any later
plain intent. It does not access the private nonce cache, inject an unchecked
nonce, retry the rejected transaction, submit a raw call or change network.
