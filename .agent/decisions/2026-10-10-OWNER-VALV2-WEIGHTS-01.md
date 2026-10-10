## 2026-10-10 — OWNER-VALV2-WEIGHTS-01: valV2 sets testnet 567 weights from its own incumbent

**Authority.** The owner, 2026-10-10, directly in the Carbon Validator
session, approving the one-line proposal of
`WEIGHTS_POLICY_VALV2.md` (the shared operator sheet) after the Test Lead
relayed "get valV2 setting weights asap":

> Approve testnet weights from valV2: valV2 signs; pays its live incumbent;
> incumbent takes, rest burns; margin 0.0570; Q12 24-hour halving; D6
> exact-digest dedup, no radius; testnet-winner-v1 (battery 1/3, rest burns);
> UID 0 and UID 12 set no weights.

**Applies** OWNER-TESTNET-WEIGHTS-01 (the winner rule and its standing
approval) and OWNER-VALIDATOR-MAINNET-PARITY-01 item 1 (real testnet weights
from hidden-batch outcomes). Testnet 567 only; DEVELOPMENT.

### What it decides

1. **Signer.** valV2's own hotkey (UID 6,
   `5CtxhYH5Qqv8EcqC8ffGsUcyaQe4ojNRtsQqTbWyhbu1CMHf`) publishes, through
   `carbon.rewards.testnet_winner_publication`, with a standing authorization
   that names it. UID 0 and UID 12 set no weights while it does: under
   Yuma, an active validator's stake decides, and UID 0 holds about 98% of
   it.
2. **Source.** valV2's live incumbent: its own hidden-batch promotion, read
   read-only from its deployment. Not gated on release: valV2 has no
   `retire_at`, so no window would ever release.
3. **Weight rule.** Direct winner plus burn: the incumbent takes its
   Challenge's share, everything unpaid burns to UID 0. A canary or an owner
   hotkey never receives weight; its share burns.
4. **Margin.** The v2 rule's registered `equivalence_margin_rel`
   (0.056993107446249414), unchanged.
5. **Decay.** The registered Q12 schedule: full for 24 hours, then half
   every 24 hours; a same-hotkey or same-coldkey promotion never resets the
   clock.
6. **Dedup.** D6 as built: the first on-chain committer of a recipe digest
   owns it; another hotkey's same digest is refused (`commitment_contested`).
   No near-duplicate radius.
7. **Shares.** The registered `testnet-winner-v1` (N = 3): battery's
   winner gets 1/3; the other two Challenges' shares burn until they have a
   serving validator.

### Runtime and window (the owner's answers, same session)

Asked whether to adopt testnet runtime spec 477 (the read-only runtime probe
reports `COMPATIBLE_USED_SURFACE` at 477, surface digest
`sha256:d591966daa62570c986d06f7c1e95cb4400c02ad2bba55af27a20df3034cf167`;
it establishes names and types, not behaviour), the owner chose
**"Adopt 477"**, whose description read:

> Write expected_runtime_spec 477 in valV2's standing file and operator
> config. The probe must still pass on the AX42 before the first run; any
> later runtime upgrade fails closed again until rechecked.

Asked how long valV2's standing authorization stays valid, the owner chose
**"14 days"**: 100,800 blocks from the first run, then renewed.

### Not decided here

- Security qualification: the publisher is security-sensitive (AGENTS.md
  §13) and not SECURITY_QUALIFIED.
- Any mainnet value, settlement amount or transfer.

**Evidence cited:** INCENTIVE-MECHANISM-SIM-01 (#974) and
INCENTIVE-POLICY-OPTIONS-01 (#989), both DEVELOPMENT analyses on synthetic
assumptions.
