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

## Password entry: the design's Q2 (owner, 2026-10-21)

- **The relay:** the owner first answered "whatever is easiest" in the Test Lead's session. The Test Lead relayed that as browser entry through the Control Center.
- **Confirmed directly in the Carbon Validator's session:** the password is typed in the browser, in **the helper's own page only**.
  - Only the helper process handles it, and passes it to the Bittensor SDK's encryption call.
  - The Control Center never receives it.
  - It is never stored, logged or transmitted.
- **Not accepted:** browser entry routed through the Control Center.
- **The ship gate stays:** the secret-sentinel search, covering the controller and helper state, the logs, every response and the page storage.

## Separate passwords (owner, 2026-10-21, directly in the Carbon Validator's session)

- **The reason:** the Validator's code review of `3ed1e5255fa0e2d0889075f715582861a1f6ea05` found that the coldkey and hotkey were locked with one password. The hotkey password is typed every time the signer starts, so that would expose the coldkey's password.
- **The owner's choice: "Two passwords."** The wizard asks for a separate hotkey (mining) password and a coldkey (money) password.
- **The code-level security acceptance follows the fixed head.**
