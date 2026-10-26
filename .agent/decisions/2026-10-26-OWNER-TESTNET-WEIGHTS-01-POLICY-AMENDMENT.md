# Amendment to OWNER-TESTNET-WEIGHTS-01 (2026-10-23): the standing authorization names the launch policy

- **Basis:** OWNER-WEIGHTS-POLICY-V4-LAUNCH-01 (owner, 2026-10-26, "Approve").
- **Amendment:** the standing authorization to run `weights run` (set_weights) on **testnet netuid 567 only** applies to weights computed under policy `testnet-winner-v4-launch`, `policy_digest sha256:b26fed6c50229413223b3c785bc0439b66094e60b9af1afad2dce406fe41c325`, and no other policy bytes. Everything else in OWNER-TESTNET-WEIGHTS-01 is unchanged: no mainnet, no other netuid, no registration/staking/transfer, the signer password is entered only by the owner, keys by file path only.
