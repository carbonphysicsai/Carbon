## 2026-10-08 — OWNER-LA-F9-SECURITY-ACCEPT-01: security acceptance of the LA-F9 public practice path exemption

**Authority.** The owner, as security owner, 2026-10-08, directly in the
Launchpad Acceptance session, verbatim: "I approve the LA-F9 exact-path
exemption for the public practice sets as the security owner. For LA-F8,
default the miner edition to the model's published input window (option a)."
The second sentence is recorded separately as
OWNER-GRAPHITE-MINER-INPUT-WINDOW-01.

**What is accepted.** The LA-F9 exemption merged in #810
(LAUNCHPAD-FINDINGS-F8-F9, decision 1;
`docs/development/evidence/launchpad-acceptance-2026-10-07/FINDINGS.md`,
LA-F9), which that decision marked as needing security review.
- `graphite.protected_material.PUBLIC_PRACTICE_PATHS` names three paths. A
  test holds each to its Challenge's own constant:
  - battery: `battery.practice.PRACTICE_SOURCE_PATH`;
  - motor: `motor.challenge.PRACTICE_PATH`;
  - cold plate: `cold_plate.challenge.PRACTICE_PATH`.
- Only a whole string exactly equal to one of them, case and all, is exempt.
- It is exempt from one rule only: the checkout deny rule that blocks paths
  under `docs/development/evidence/`.

**Unchanged.** Every other protected-material rule still applies, including
to the same string:
- every Graphite marker (seeds, draw ids, hidden cases, the sealed tuning
  set, verification references, validator state, canaries);
- any other path under the evidence prefix, including the battery reference
  pools and EV5;
- a public path with anything before or after it, or in another case;
- every other deny rule.

**Scope of the acceptance.** The tests in #810
(`tests/cpu/test_launchpad_findings_f8_f9.py`) are engineering evidence, not
a security audit. This acceptance is the owner's. It covers this exemption
only. It does not cover the open follow-up that a withheld result still says
`dispatched: false`, which needs its own change and review. No code changes
with this record.
