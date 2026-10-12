## 2026-10-12 — OWNER-BANK-SCHEDULED-ROTATION-SECURITY-01: the scheduled bank rotation's security review is accepted, and the cutover is approved to run

**Authority.** The owner, 2026-10-12. Typed by him in the Test Lead session,
relayed verbatim, and confirmed by him in the PR Head session before this
record was written:

> I accept carbonphysicsai/Carbon#1079's security review (scheduled bank
> draws and publication) and OK running the RELEASE_SCHED cutover this
> morning.

**What it closes.** `OWNER-BANK-SCHEDULED-ROTATION-01` (2026-10-11) listed two
items under "Not decided here". Both are now decided:

1. **"the owner's approval to run the corrected AX42 sheet (he is holding)"** —
   approved. He is running the RELEASE_SCHED cutover this morning.
2. **"security acceptance"** — accepted, for #1079's scheduled bank draws and
   publication.

Everything else that record left open stays open; this closes those two items
and nothing further.

**Scope of the acceptance.** It covers the security review of #1079 — the
scheduled bank draws and the publication path — and the approval to run the
cutover. It is a security acceptance under AGENTS.md §13. It is not a
scientific, network or production qualification of the rotation, of the bank,
or of anything the cutover publishes.

**The release the cutover runs on.** The owner is running it on
`producer-code-r8.1` (commit 038fd2499). That matters, and is recorded here so
the sequencing is not reconstructed later from memory:

- r8.1 predates #1143, so its feed carries **no** `king` field at all. The
  king defect described below therefore cannot affect this cutover.
- `producer-code-r8.2` (commit 8c698a3d4) **does** carry #1143 without its
  fix: its feed takes the king from the ledger's latest record with no
  check that the record is the live deployment's incumbent, so after a
  cutover to a new deployment it would name the archived deployment's last
  winner as king. #1148 is the fix; `R8_2_UPGRADE §2` is gated on it, and the
  owner has approved an r8.3 once #1148 lands.

So: the cutover on r8.1 is unaffected; the exposure is upgrading to r8.2
across a cutover without #1148.

**Maturity.** DEVELOPMENT. Testnet rotation `r360`; mainnet `r1080` remains as
`OWNER-BANK-SCHEDULED-ROTATION-01` records it, and nothing here advances it.
