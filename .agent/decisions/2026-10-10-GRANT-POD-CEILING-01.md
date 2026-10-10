## 2026-10-10 — GRANT-POD-CEILING-01: the pod rate ceiling becomes a grant field

**Authority.**
- **The direction.** OWNER-DEV-AUTONOMY-01, through the Test Lead.
- **The cause.** Stage A was refused at launch because the pod rate ceiling
  is a global constant (`pod_control.MAX_RATE`) that no grant and no
  preflight could see.
- **The scope.** This is an engineering change. No grant's figures change
  here.

**Decision.**
- **The grant field.** `SpendingGrant` accepts an optional
  `pod_rate_ceiling_usd_per_hr` (a positive money string). It is emitted only
  when set, so every existing grant's document and digest are unchanged; a
  test re-reads every committed grant.
- **Where the ceiling applies.** The grant's ceiling, when set, prices its
  pods:
  - `pods.prices(rate_ceiling)`;
  - `RunPodPods(rate_ceiling=...)`, from both phase-3 constructions;
  - `phase3_budget`'s hourly reservation.

  Absent, `MAX_RATE` applies as before.
- **The preflight with `--key-file`** (no spend):
  - checks that `~/.runpod/campaigns.json` exists in the lane distro and
    names a balance floor, which it never prints;
  - checks the live offer against the grant's ceiling, failing with
    `owner decision: offer X/h > grant ceiling Y/h` as an owner need.

  The probe reuses the same offer check.
- **Found while testing.** Stage A's Constructor grant keeps R4's 11.93
  token share of a 14.91 run. At 0.65 an hour the session's pods need more
  than the 2.98 left, so the run is refused, typed. Raising stage A's ceiling
  needs its token share or worst case re-set too, which is an owner figure. A
  test pins this.

**Not done here.**
- **No grant figure changes.** In particular, stage A's 0.65/h approval is
  recorded in its run record (the Test Lead), not in its grant file.
