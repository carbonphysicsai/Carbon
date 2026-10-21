# OWNER-LAUNCHPAD-SESSION-AND-WALLET-01: tab session persistence and the local-key wallet wizard

Date: 2026-10-21
Status: APPROVED by the owner as security decisions.
- **First:** given in the Test Lead's session ("1. stay connected 2. yes as well").
- **Then:** confirmed directly in the Carbon Validator's session, both items selected.

## Accepted

1. **Launchpad keeps its session across a page reload** (commit `6d3f1bd6a56b281c9027a811f0270fd3c3e31845` on `claude/graphite-ui-cleanup`).
   - The sign-in token is held in that tab's `sessionStorage` until the tab closes.
   - This deliberately relaxes LP-PROD-C D14 ("read once, kept nowhere").
2. **The mining-identity (wallet) wizard design** (`codex-queue/reports/MINING_IDENTITY_HELPER_DESIGN_20261021.md`, sha256 `0a707608d91785a3709baceb1cb353d10504e1538b12a183d9053c585f3c3039`).
   - Miners' keys are created locally.
   - Carbon never sees, stores, logs or transmits them.

## Conditions

- **The Validator's review findings apply before either ships.**
  - A material issue goes back to the owner; it isn't rewritten unilaterally.
- **These accept the design and the named commit only.**
  - A later change to token handling or key handling is a new acceptance.
