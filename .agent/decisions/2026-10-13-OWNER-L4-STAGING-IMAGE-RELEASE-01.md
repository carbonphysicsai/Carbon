## 2026-10-13 — OWNER-L4-STAGING-IMAGE-RELEASE-01: the analysis-image release carrying the Level 4 lowering tooling, accepted into testing

**Authority.** This is the owner's own decision, given directly in the coordinating session on 2026-10-13. He was shown the
one-page summary `docs/development/graphite/level4/L4_STAGING_IMAGE_RELEASE_SUMMARY.md` (#1179) and asked to choose between:
accepting, for development and testnet only, the isolation of lowering untrusted model source in the existing analysis
container together with the envelope transport; running the containment check on the new image first; or declining. His answer,
verbatim:

> I fully accept it into testing. We will analyze it there

**What it answers.** #1098 (GRAPHITE-L4-STAGING-01, route R1) reserved two things to the owner: the isolation review of
lowering untrusted model source in the agent's own sandbox and of the envelope transport, and the word for the analysis-image
release that carries the tooling (slice 1). This record is that word, for testing.

**Decided.**
1. **The release is given.** The analysis image may be rebuilt at the current main, with a new manifest the readiness gate
   reads, carrying the Level 4 lowering tooling.
2. **Scope: testing, which means development and testnet only.** Mainnet is outside this record and needs its own security
   review before any LIVE use.
3. **Analysis happens during testing.** The owner accepted it into testing so it can be analysed there; this is not a claim that
   the isolation has been audited.

**What this does NOT say.**
- **No security audit was done, and none is claimed.** The "not verified" list in the summary stays attached to this record:
  - no live lowering has yet run in the real miner container;
  - the lowering of hostile model source (memory, time, scratch-flooding) has not been tried;
  - graph training of a lowered graph on a real pod has not been run;
  - G5 (compile in isolation) is not wired into this path;
  - the fixed containment check has not yet run on an image carrying the new code.
- It changes no scientific, LIVE, economic or launch authority.
- It does not replace OWNER-L4-G5-COMPILE-ISOLATION-01, which stays as it was.

**Conditions the testing plan attaches (not the owner's words).** The Test Lead's rulings, relayed 2026-10-13: the containment
check on the rebuilt image is the first step after the rebuild and must pass before any Level 4 lowering runs, Graphite's own
included; a hostile-model lowering probe (memory, time, scratch-flood) goes in the first Level 4 test batch. The plan carries both
(`GRAPHITE_OPEN_SAFE_01_PLAN.md`, section 1).

**Recorded by** the Graphite Testing Manager session at the coordinator's request, from the owner's words as relayed in the
coordinating session.
