## 2026-10-03 — OWNER-LAUNCHPAD-PROD-02: the owner's answers to the work list's open decisions

**Owner, verbatim, in session on 2026-10-03**, answering the open decisions
the LP-PROD slices recorded. Numbers follow the questions as they were put:
- 1, the research agent's default output cap of 2,048 tokens: "why would we
  limit an agents output tokens? Don't we want them running the best possible
  agents? It's their economics, compute, and choice!"
- 2, a call answered by a model other than the one selected, booked at the
  selected model's reservation with a caveat: "don't care"
- 3, a 502, 503 or 529 with no usage report booked at zero and retried: "yes"
- 4, whether pre-registered battery agent tiers may run under the v2
  parallel-call rule: "yes new rule obviously"
- 5, whether campaigns pause when the Control Center closes: "Pause"
- 6, narrowing the worker image's source digest: "No, the miners will be
  working on challenge specific images that will not be getting modified, if
  they do, we will notify and update all"
- 7, where the validator and intake run: "dedicated always on server"
- 8, DNS name, TLS certificate and firewall: "dont care whatever is sota for
  an application like this"
- 9, running `operate upgrade` on the real v1 deployment: "yes upgrade"
- 10, which images miners practise against: "practice on validator images as
  long as NO ACCESS to hidden test conditions"
- 11, security review and acceptance of the validator service tooling and the
  intake changes: "Approved"
- Delivery: "yes combined PR"; the live smoke test before Graphite's
  remaining runs: "approve the smoke test"

**Decision.**
1. **No Carbon-imposed output cap.** A research agent may use its selected
   model's full output by default. Only a cap the miner sets binds. Every
   call is still reserved and metered against the miner's own budget, so the
   cap is the miner's economic choice, not Carbon's. `LP-PROD-A`'s open
   question is closed.
2. **model_mismatch booking stands** as `LP-PROD-A` records it: the selected
   model's full reservation, with its caveat.
3. **A 502, 503 or 529 with no usage object and no charge report is booked
   at zero and retried**, as `LP-PROD-A` records it.
4. **Pre-registered battery agent tiers run under PARALLEL_CALLS_V2** from
   their next run. This amends their pre-registered parallel-call rule
   (`FIRST_RUN_REST_REFUSED`) prospectively. Runs already recorded keep the
   rule they were recorded under and are not reinterpreted.
5. **Closing the Control Center pauses its campaigns** (`LP-PROD-C` D4
   unchanged).
6. **The worker image's source digest is unchanged.** Miners work on
   Challenge-specific images that are not modified. If one is, Carbon
   notifies every miner and updates them all. The narrower-digest proposal in
   `LP-PROD-E` is declined.
7. **The validator and its intake run on a dedicated, always-on server**
   operated by Carbon. It is not a pod and not miner compute.
8. **Exposure uses the standard production setup**, within
   OWNER-INTAKE-EXPOSURE-01 (TLS terminated in the intake):
   - a DNS-only (unproxied) name under the owner's domain;
   - an ACME (Let's Encrypt) certificate, renewed automatically, whose deploy
     hook copies the key to its owner-only file and restarts the intake;
   - inbound HTTPS to the intake only, and SSH by key only;
   - automatic security updates.
9. **`operate upgrade` on the real v1 deployment is approved.** A backup of
   its root, journal and state is taken first. It runs at the server
   bring-up, after this work merges, so the deployment is upgraded once.
10. **Miners practise on the validator's own pinned images.** The pinned-image
    parity check treats the validator's images as the standard. Practice
    never gives access to hidden test conditions: no private cases, seeds,
    roots, references or per-case evaluation results.
11. **The owner accepts the security review of the validator service tooling
    and the intake changes** (`LP-PROD-G`) as presented on 2026-10-03. Tests
    are not a security audit, and this acceptance is the owner's.
12. **Delivery.** The work ships as one combined PR, so main moves from the
    old front end to the new one in one step. Before Graphite's remaining
    phase-3 runs, one live smoke test runs: a single-epoch autonomous
    Launchpad campaign on the same model, CPU practice only, with a provider
    cap of about USD 0.50.

**Open, with the owner.** OWNER-EV5-Q3-01 keeps EV5's sealed confirmation
solve on the operator host and off rented compute. The v1 deployment holds
that batch. Before the deployment moves to the dedicated server, either the
solve runs on the current host, or the owner confirms that the server counts
as the operator host.

**Unchanged.** Every scientific value, threshold, gate and tolerance; chain
writes and weights (none); the boundaries OWNER-LAUNCHPAD-PROD-01 lists.
