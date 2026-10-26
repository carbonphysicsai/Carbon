# OWNER-MAINNET-SECURITY-ACCEPT-01: mainnet security acceptance, conditional on testnet testing

- **Received by:** the Lead session, directly from the owner in chat, 2026-10-25.
- **Owner's words:** "I reviewed and accept after testnet testing" (in reply to the mainnet security review item: containment, sandbox-escape review, what testnet acceptance covers).
- **Decided:** the owner is the reviewer and accepts mainnet security, but the acceptance takes effect only AFTER testnet testing passes.
- **Condition (all must hold before it is effective):** the containment checks pass on the testnet build, and the pre-mainnet attack tests (MAINNET_PREP_20261025.md item 5: grading, gaming, feedback-leak and disclosure attacks) pass with no open finding. Until then the testnet/rehearsal-only acceptance (OWNER-CONTAINMENT-ACCEPT-TESTNET-01) stays the only one in force.
- **Not decided here:** reopening miner-authored source bundles (OWNER-LEVEL4-GRAPH-ONLY-01 still needs its own containment VM test + human sandbox-escape review + owner sign-off).
