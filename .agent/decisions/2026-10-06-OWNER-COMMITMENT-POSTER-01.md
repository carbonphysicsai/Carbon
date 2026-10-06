## 2026-10-06 — OWNER-COMMITMENT-POSTER-01: miners' on-chain strategy commitments (D1 to D10)

**Authority.** The owner, 2026-10-06, in the Test Lead session. The owner was
answering the ten decisions in the COMMITMENT-POSTER scope (Test Engineer;
`/home/carbon/shared/tickets-draft/COMMITMENT-POSTER-scope.md`, committed with
the ticket):

> Answer D1-D10 with whatever is the bittensor standard and easiest and best for all parties (Miners, Valis, Us)

The Test Lead answers each decision under that delegation, as follows.

**The standard this follows.** On Bittensor, a miner commits with its own
hotkey through the chain's commitments pallet. The SDK's `set_commitment`
does this, and validators read it back with `get_commitment`, by block. The
validator checks only what is on chain. It never cares which tool posted it.

| # | Decision | Answer |
|---|---|---|
| D1 | Signer scope | **Yes.** `carbon-miner-signer` gains exactly one extrinsic op, `Commitments.set_commitment`, carrying the pinned `sha256:<hex>` digest, with confirmation on the signer's TTY (the last 8 characters typed). It signs no other extrinsic. **Miners may equally post with standard tooling** (the Bittensor SDK); validators accept any valid on-chain commitment. Carbon's signer is the easy path, not the only path. |
| D2 | Chain access | **S-offline.** The signer signs; the Launchpad broadcasts. The key-holding process never opens a network connection. |
| D3 | Fee ceiling | **The hotkey's own chain fee (and any deposit) is the miner's, as on every subnet.** The signer refuses a transaction whose quoted fee exceeds a ceiling. The ceiling is the fee measured in a localnet round trip, times 2, recorded with its measurement. For Carbon's own testnet rehearsal hotkeys, the fee is test TAO only. OD-4a's zero-spend rule still governs Carbon's own mainnet keys. |
| D4 | Count, window, expiry | **At most one commitment per hotkey per tempo,** matching rule v2's one scored submission per tempo. Any stricter chain rate limit still applies. |
| D5 | Mainnet | **Deferred** to the mainnet launch record. The same code path is used, with the netuid and genesis set per network. Mainnet commitment writes need that record. |
| D6 | Freshness | **Yes.** A submission is admitted only against a commitment posted after the hotkey's previous admitted submission and before this one. Where two hotkeys commit the same digest, the earliest commitment block has priority, as in standard first-commit practice. |
| D7 | Approval sequence | **No per-post owner approval.** This record plus the miner's TTY confirmation is the whole authority for a miner's own post. |
| D8 | Key-file hygiene | **Yes,** at every signer start. A key file readable by others is refused, with a one-line fix message (`chmod 600 <file>`). |
| D9 | Mortality | **The SDK's default mortal era,** capped at one tempo. |
| D10 | Agent initiation | **Yes.** An agent (Carbon's, or the miner's MCP client) may request the commitment. Only the human confirms, on the signer's TTY, and an agent can never confirm. |

**Build order.**
1. Pin the call composition and fee from the SDK.
2. Run a localnet round trip.
3. Run a testnet 567 trial on the rehearsal hotkeys.

Every bound in the scope's §2 is tested to fail closed.

**Not decided here:**
- mainnet netuid, genesis and launch;
- the fee ceiling's number, which is recorded after measurement;
- security acceptance of the signer change.

**No execution** happens through this record.
