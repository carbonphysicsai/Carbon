## 2026-10-05 — OWNER-GRAPHITE-TEST-WAVE-07: missing predictions charged in the deployed battery validator; refined references for development evidence; the EV5 run go

**Authority.** The owner, 2026-10-05, in the Test Lead session. The open
decisions were:
1. whether the deployed, miner-facing battery validator should charge
   missing predictions;
2. whether refined references may settle unresolved cases for testing;
3. the EV5 run blockers.

The owner answered: "for the blockers. make your best decision". The
decisions below are the Test Lead's, made under that explicit delegation. The
owner may supersede any of them.

**Supplements** OWNER-GRAPHITE-TEST-WAVE-01 to -06, OWNER-EV5-FREEZE-01 and
OWNER-EV5-CAP-01.

1. **The deployed battery validator charges missing predictions (#613).**
   - **The hole.** Today the miner-facing battery validator (`battery/daemon.py`,
     Interface v1) excludes a case with no prediction as infrastructure
     failure. A submission could omit its worst cases and improve its score.
     The Test Engineer's omission probe found this (`prediction_omission`,
     #602/#613).
   - **Decision.** A missing or null prediction for any scored case is a
     schema-gate failure (`prediction_cases_differ`), charged to the
     candidate and never excluded. The same rule applies on Graphite's host.
   - **Invariant 10.** Every new outcome records the coverage rule's identity
     (`COVERAGE_RULE`). `RULE` and `rule_digest` stay pinned, and earlier
     records keep their meaning.
   - **Deployment.** #613 does not merge while a live battery Graphite session
     is running. The validator service is upgraded through its normal operator
     path.

2. **Refined references may settle unresolved cases, for DEVELOPMENT evidence
   only.**
   - **Scope.** A refined reference solve, a pinned refinement of the same
     solver and model, may settle a case left UNRESOLVED inside the contract's
     band. This is a registered, versioned reference-resolution policy for
     development studies (Track B diagnosis and score-candidate studies).
   - **Recording.** The original record is kept, and the settling solve is
     recorded beside it with its refinement settings and digest.
   - **Exclusions.** It never applies to frozen studies (EV4, EV5), their
     contracts or any confirmation evidence. Applying it to confirmation
     needs a science-owner decision.
   - **Budget.** About 1–3 core-hours on the operator host CPU, scheduled
     around the live Graphite and EV5 host windows.

3. **EV5 runs as frozen.**
   - **Go and cap.** The owner's go ("Lets run it now") and the
     OWNER-EV5-CAP-01 cap (USD 6, A40 at no more than USD 0.49/h) stand.
   - **Run commands.** Commands built now to execute EV5 must implement the
     frozen pre-registration exactly: the plans, the hypotheses and H3's
     module as frozen. Any difference is reported as a change, never applied
     silently.
   - **The sealed confirmation step stays an operator action.** No agent
     searches for deployment, root or journal files. The owner runs the
     regenerate-and-solve step on the validator host, or supplies the exact
     paths for it.

**No execution** happens through this record itself. EV5's spend is the
already-approved OWNER-EV5-CAP-01.
