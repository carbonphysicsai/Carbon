## 2026-10-08 — OWNER-RATE-STUDY-D1-01: SUBMISSION-RATE-STUDY-01 may include a revealed-score arm on a sacrificial study bank

**Authority.** The owner, 2026-10-08, relayed by the Test Lead (not given to this
session directly): "approve D1".

D1 is the question in `docs/development/graphite/SUBMISSION_RATE_STUDY_01.md`
section 11: may the study include an arm that shows the agent the hidden-batch
score?

**Decision.** Yes, with these limits:
1. The revealed-score arm (S-revealed) runs only on a **study-only, sacrificial
   bank**.
2. That bank **never serves a real window** and never feeds a production batch,
   the release queue or training during the study.
3. After the study the bank is **retired or published**.
4. Every sealed arm (honest control, sealed scripted prober, Graphite
   adversary) still sees only the mainnet allow-list; no production hidden
   material appears in any agent-visible output.

**Use of the result.** The arm's result sets the **leak bound** for the owner's
later decision on live per-section scores (VALIDATOR-29 item 1). It is a
measurement, not a rate, not a qualification and not a LIVE claim.

**Not granted here.** No run, spend or grant. Stage 0 needs its own operator-compute
approval, and the token grant for the Graphite adversary arm stays the owner's
(proposal in the plan, section 9). The freeze procedure is plan section 12.

**Supplements** OWNER-BANK-ARCHITECTURE-01, OWNER-VALIDATOR-MAINNET-PARITY-01 and
OWNER-GRAPHITE-TEST-WAVE-08.
