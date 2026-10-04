## 2026-10-04 — OWNER-GRAPHITE-ATTACKER-01: a general Graphite attack engine, and its phase-4 grant

**Owner, verbatim, 2026-10-04:**
- To the Test Lead: "We want to build and use Graphites Attacker".
- In the engineering session, setting the scope: "Build a general attack capability that generalizes to any challenge at any construction level and improves as it goes".
- On the build: "Multi-agent workflow".
- On the proposed live grant: "Approve now".

**Decision.**
1. **A general attack engine.** Carbon builds a challenge-neutral attack engine, with one adapter per Challenge and per construction level. Graphite's Attacker role drives it in phase 4.
   - Battery Level 0, declarative recipes, is the first adapter.
   - Every adapter supplies the eight shared Track A checks (`challenge_readiness/admission.py` CHECKS), each with an attack example and a valid control.
   - Higher-level families, such as participant code, child processes and solver hybrids, are declared seams and reported NOT_RUN.
   - Executing hostile code needs the security owner's isolation decision. That decision is reserved and is not built here.
2. **It improves as it goes.** A durable, content-addressed, append-only attack-knowledge store holds:
   - attempts, verified findings and near-misses;
   - the strategies that found them;
   - per-Challenge and cross-Challenge priors;
   - a regression specimen for every verified finding.

   It learns only from Carbon's own attack runs and public material. Each frozen admission run pins a store snapshot by digest as part of its suite version, and specimens added later belong to the next suite version (invariant 10).
3. **Evidence rules** (from the Test Lead's requirements):
   - The store and attack modules are unreachable from anything miners receive. An import-closure invariant test enforces this.
   - They never read, derive from or record sealed or confirmation material.
   - The engine never tunes against held-out controls. The wrongful-rejection rate is reported on those controls.
   - A timeout is never a pass, and zero findings is reported as attempted coverage, never as a bound.
   - Findings use only the existing CONDITIONS vocabulary and stop expansion through `admission_expansion_after_finding`.
   - Carbon rebuilds every attack construction it scores, and refuses with a typed code any it cannot.
4. **Benchmark B2** compares the Attacker with battery's deterministic harness (`carbon/battery/track_a.py`) at an equal attempt budget, per family, and is recorded per store snapshot.
5. **The live grant, GRAPHITE-GRANT-PHASE4, is approved as proposed.**
   - Account `Carbon-Account`.
   - Monetary ceiling USD 10.50, cleanup allowance USD 0.25.
   - Worst-case run cost USD 3.41: six A30 pod-hours at USD 0.2464, plus about 40 glm-5.2 calls. Money binds, not call counts.
   - 3 permitted runs, max concurrency 1, max runtime 15,600 s, expiry 2026-12-31.
   - No live run takes place until the engine merges and its scripted dry run passes.
   - The Test Lead's record, OWNER-GRAPHITE-TEST-WAVE-01 §2 (carbonphysicsai/Carbon#556), records the same approval.

**Unchanged.**
- EV5 and its sealed batch.
- Every sealed or confirmation material.
- The live construction contract and the expansion records.
- Every scientific value, threshold and gate.
- No chain writes and no weights.
