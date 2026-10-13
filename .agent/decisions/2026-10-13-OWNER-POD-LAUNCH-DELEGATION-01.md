## 2026-10-13 — OWNER-POD-LAUNCH-DELEGATION-01: Data Collection may launch pod jobs itself, on public data, inside the standing test grant

**Authority.** The owner, 2026-10-13. He answered the Test Lead's direct question
in that session, choosing "Yes, public-data jobs". The PR Head then put the same
terms to him directly and he confirmed them in the PR Head session before this
record was merged: this delegation changes who may cause spend, and such a
decision is not recorded on a relay alone.

**What is delegated.** Data Collection may launch pod jobs itself, without a
per-run approval, on these terms:

- **Public data only.**
- **At most USD 50 per run**, inside `OWNER-TEST-GRANT-01` (USD 300 per rolling
  seven days, with the CONFIRM-02 reserve held back — see
  `carbon/agent_campaign/grant_runs.py`, `HELD_RESERVES`).
- **The RunPod key by file path, never printed.**
- **Self-terminating, capped pods.**

**What stays with the owner.** Sealed or hidden jobs, any run above the per-run
cap, and every new grant figure. Mainnet and LIVE are untouched by this record.

**What this does not change.** No cap, reserve or rate is altered: the per-run
and weekly limits are the owner's existing figures, and this record creates no
new money authority. It moves *who may trigger* a launch inside those limits,
nothing else. The ledger still binds every claim — `claim()` resolves the
effective weekly cap, and `pod_jobs.run` refuses unless the ledger exposes both
`claim_pod_job` and `settle_pod_job` and the owner's enabling file is present
beside the key (`require_enabled`).

**Maturity.** DEVELOPMENT and testnet. This is an operating delegation, not a
security acceptance, a scientific qualification or a launch authorization.
