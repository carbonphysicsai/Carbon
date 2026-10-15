# ScoreLab finish line: handoff for a useful lab and a battery score decision

**Status.** Handoff and plan, not a decision record. The owner decision it
serves is **`.agent/decisions/2026-10-15-OWNER-SCORELAB-FINISH-LINE-01.md`**,
recorded by Research Codex on `codex/scorelab-owner-dev-v1` (commit
`6b5ea3a49`), which carries the owner's D1–D8 and R1–R2 answers verbatim and
names Optimizer, Root and Research's responsibilities. Where this document and
that record differ, the record governs. §3A below repeats the same answers
for reading convenience only.

**Authority for the handoff itself.** The owner, 2026-10-15, in his own Claude
Code session, asked for this handoff and then for the §3 answers ("I need you
to give me optimal answers for that section 3 of the scorelab handoff now.
Whatever gets us to a valuable challenge asap"), and asked for it to be
recorded. Nothing in it creates a grant figure, scientific threshold, security
acceptance, LIVE, reward, mainnet or production authority.

**From:** the owner (Ryan), 2026-10-15. **To:** Optimizer, Root / PR Head, Test Lead,
Data Collection, Carbon Validator, Test Engineer, Graphite Testing Manager.
**Basis:** `origin/main` at `bc465b1d` (#1368). DEVELOPMENT only. This handoff
changes no runtime rule, bank, reference label, holdout or grant on its own;
the owner answers in §3 are what change things, and each lands as its own
decision record under `.agent/decisions/`.

---

## 0. Why this is taking so long

Read `Business/research/score-lab-campaign-01/finish-line/READINESS_STATUS.json`.
Thirteen stages. **Twelve are BLOCKED; one (`interactions`) has evidence.**
Of the twelve, nine are blocked on a *decision or an export from another role*,
not on compute. Total compute spent on the whole campaign is under one CPU-hour.

The pattern that follows from that: the Optimizer can only work alone on the
synthetic side, so the synthetic side has grown (error64, components, combined
matrix, measurement study, robustness, value blocks, outages, Sobol, feedback)
while the real-data path has produced **zero measured rows** (public EV4 replay:
0/12 D and 0/12 V questions admitted). The lab is rigorous and cheap and it is
answering questions nobody is blocked on.

Three things gate the real path, in order:

1. **No registered real job.** Every number in the battery v3 law is a
   HUMAN_INPUT recommendation. The `job_contract` stage's minimum action is
   "Register the first real experiment job and role contract." Owner.
2. **Reference applicability.** `battery-plating-ref-v2` (sealed 2026-10-13,
   VALIDATOR-PLATING-REF-V2-02) claims nothing outside |m20| < 15 mV. 223 of
   840 EV4 action-condition cases sit outside that claim; 9 decision-changing
   mesh-160 cases are pending; 5 original references are missing/failed.
   Under the full 35-action bank rule that admits nothing. Validator/owner +
   Data Collection.
3. **No quiz legs on real models.** All 142 public members have legacy
   accuracy legs on 415 cases; **none** has Q3 or VERIFY-R legs. The one
   signal that looked promising in the toy (Q τ = 0.60 [0.08, 1.00] on the
   tight-boundary profile) has never been computed on a real model.

Everything else in this document exists to clear those three.

---

## 1. What "finished" means

**A useful lab** = given (a) a registered real job, (b) a paired cohort of real
models with score legs and value traces, and (c) a frozen candidate set, the
lab returns per candidate: τ(score, value) on P with cluster-bootstrap interval,
top-k pick regret in buyer units, gamer/probe placement, wrongful-exclusion
counts, and a holdout confirmation, with every identity digest-bound. The
synthetic side is **done** for this purpose. No further synthetic tranche is on
the critical path.

**A solid battery score decision** = a versioned rule v3 record that names
gates + legs + registered weights, chosen by the preregistered procedure in
§4 on real data, confirmed once on the Test Engineer's holdout, adopted
prospectively with shadow value measurement continuing. "Keep v2, quiz stays
shadow" is an allowed outcome of that procedure and still counts as finished.

Not required to finish: optimal weights, a universal score, τ intervals that
exclude zero (see §4 for why), the 5,000–20,000-profile sweep, section G
competition dynamics, any new score wrapper.

---

## 2. Critical path, mapped to the readiness stages

Stage names are the manifest's. Owners are the manifest's. Minimum actions are
restated so that each is one concrete deliverable with a done-check.

| # | Stage | Owner | Deliverable | Done when |
|---|---|---|---|---|
| 1 | `job_contract` | Owner → Test Lead registers | Battery-v3 ambient-indexed charging-time map, **covered pilot support** (SOC 10 %, fresh initial state), 0.01-C lattice, x1/x2/x4 cooling, five mandatory bands, P/Q/w per §3-D2 | A registration JSON with digest exists on main; §3 answers recorded |
| 2 | `references` | Validator/owner decide; Data Collection execute | (a) Applicability contract for the first real fit per §3-D3; (b) the 9 pending mesh-160 and 5 missing/failed references completed under v2's `-r1` rules and stop triggers | `ADMISSION.json` regenerated: SCORED > 0 for the registered cohort; stop-trigger receipt attached |
| 3 | `cohort` | Data Collection / Graphite Testing Manager | Authoritative per-bundle export: recipe, declared architecture, rebuild seed role, training-data cohort identity for the 142 public members (100 EV4 rebuilds + 37 + 5 controls) | Export file with digest; cluster map (recipe family → member IDs) included |
| 4 | `paired_score_inputs` | Data Collection / Validator / Graphite executor | For every cohort member: predictions + reference-bound accuracy, **Q3 and VERIFY-R legs**, margin/gate, uncertainty, neighbour inputs, on the registered job | `score_lab replay` accepts the bundle; no member has a typed-missing leg that the job requires |
| 5 | `value_traces` | Optimizer + Data Collection | Run committed predictions through the registered shortlist/verification workflow; export per-question verified pick, regret, feasibility, abstention | Value panel with common mask; estimand (covered-region conditional) stated in the file |
| 6 | `matched_controls` | Data Collection + Optimizer | Strongest registered cheap method + always-decline / random-feasible / known-bad / path gamers on the same job, costs recorded | Controls present in the same panel; controls gate passes (abstain rank, ceiling capture) |
| 7 | `weight_search` | Optimizer; Test Lead registers | **Frozen**: the ten pinned candidates only (§3-D4). No grid search. | Candidate file committed or digest-pinned in a shared location; no post-hoc additions |
| 8 | `independent_validation` | Test Engineer | One holdout reveal at the final run | Reveal receipt; result recorded whichever way it goes |
| 9 | Decision | Test Lead proposes, Owner adopts | Rule v3 record per §4, or "keep v2 + shadow" record | `.agent/decisions/…-BATTERY-RULE-V3-01.md` merged |

Stages `measurement`, `goodhart`, `competition`, `budget` (large sweep) are
**off the critical path** and parked until stage 9 is done. `interactions` is
complete.

---

## 3. Owner decisions, with recommended answers

Answer each with yes / no / value. Every recommendation below is a value that
already exists in the repository as a documented recommendation; the owner's
answer turns it into a registered DEVELOPMENT value. Nothing here is a
production, LIVE or qualification claim.

**D1. Register the first real job.** Battery-v3 ambient-indexed charging-time
map; covered pilot support only (SOC 10 %, identified fresh initial state);
0.01-C lattice; cooling x1/x2/x4; all five bands mandatory. Expanded support
(SOC 10/20/30 %) stays HOLD per `battery-v3-round2.md` §2.
*Recommended: yes.*

**D2. P / Q / w for that job.** P: mix ~ Dirichlet(2,3,8,5,2); thermal margin
U[0, 2.5] K; plating margin U[0, 2] mV; T ≤ 45 − mT, η ≥ mEta, V ≤ 4.2,
Q30/Q1 ≥ 0.99. Q: 20 % interior / 50 % safety-edge / 30 % pick-edge, bands set
by Test Lead from public/retired diagnostics. w: unit outer weights with bank
clustering; Q reported separately; buyer mix enters the objective only.
Value-equivalence δ_b = 0.5 min; regret r_b = 0 if d_b ≤ δ_b else d_b;
aggregate Σ mix_b · r_b. *Recommended: adopt all as DEVELOPMENT v1.*

**D3. Reference applicability for the first real fit.** Two options:
- **A (now):** register a *covered-region diagnostic cohort*: only action-
  condition cases inside plating-v2's claim (|m20| < 15 mV) and decided or
  completed-pending under `-r1`. Cases outside the claim stay UNRESOLVED and
  are removed by a question-level **EXCLUDE_COMMON** mask. The estimand becomes
  "value conditional on the covered region" and every readout says so.
  Cost: the 9 pending + 5 missing references (inside the D3 grant pattern;
  the last cpu3g run was USD 25 cap, USD 56.56 of 260 weekly used).
- **B (later):** a plating reference v3 that claims |m20| ≥ 15 mV. Separate
  grant and method; do not block the first fit on it.
*Recommended: A now, B as its own ticket after stage 9.*

**D4. Freeze the candidate family.** The ten pinned candidates (INFORCE G-FEAS
/ A-Q; N1–N4; V2 rev2 k1/k3/k5; V9; V10), source sha256
`157b1db5f091910f5602b15c9f5029f0171e6da7e8b6dbc5ffb5aa5c775bd235`. **Commit
the candidate file** (or a byte-identical public copy) so the lab is
reproducible by someone other than the person who has it locally. No new
wrappers (CRPS, cheap-relative, gradient-sign, CVaR) enter the v3 shortlist;
the component tranche showed none of them repairs base-order inversions.
*Recommended: yes.*

**D5. Preregister the selection procedure in §4** before stage 5 runs.
Test Lead registers the k and the "top half" definition. *Recommended: k = 3;
top half = rank ≤ ⌊n/2⌋ of admitted members.*

**D6. Aggregate-proxy comparator (NEW_OWNER_DECISION_REQUIRED from
`2026-10-14-OPT15C-ACCURACY-BRIDGE.md`).** Gain/rank/product aggregates have
no per-case comparator. *Recommended: do not invent one now. Candidates
without a per-case form are compared on τ and pick regret only, not in the
championship frame. Record as deferred.*

**D7. Holdout.** One reveal, at the final run, Test Engineer custody,
receipt/digest only. *Recommended: confirm unchanged.*

**D8. Park, explicitly:** the 5,000–20,000-profile sweep (`POD_JOB_SPEC.md`),
section G competition dynamics, Sobol beyond the four-pair smoke, further
error-structure axes, further robustness arms. *Recommended: yes, until
stage 9. Record the park so nobody has to re-justify not doing them.*

---

## 3A. Owner answers, 2026-10-15

Every value is one that already existed in the repository as a documented
recommendation; the answer makes it a registered DEVELOPMENT v1 value.

- **D1 — Register the first real job: YES.** Battery-v3 ambient-indexed
  charging-time map; covered pilot support only (start SOC 10 %, identified
  fresh initial state, 30-cycle programme); 0.01-C lattice; cooling x1/x2/x4;
  all five bands mandatory, zero-weight bands included. Expanded SOC support
  stays HOLD. Registered as `battery-v3-job-dev-v1`.
- **D2 — P / Q / w: ADOPT ALL as DEVELOPMENT v1.** P: mix ~ Dirichlet(2,3,8,5,2);
  mT ~ U[0, 2.5] K; mEta ~ U[0, 2] mV; T_charge ≤ 45 − mT, η ≥ mEta,
  V ≤ 4.2, Q30/Q1 ≥ 0.99; fresh-state point mass. Q: 20 % interior / 50 %
  safety-edge / 30 % pick-edge, bands set by the Test Lead from public or
  retired diagnostics; NONE_FEASIBLE stays in P; no redraws. w: unit outer
  weights with bank clustering; Q reported separately; buyer mix enters the
  objective only. Value: δ_b = 0.5 min; r_b = 0 if d_b ≤ δ_b else d_b;
  aggregate Σ mix_b · r_b; objective minutes 0→80 % SOC, no 30-min cap.
- **D3 — Reference applicability: OPTION A NOW; Option B is its own ticket
  after stage 9.** Register a covered-region diagnostic cohort: cases with
  |m20| < 15 mV, decided or completed-pending under plating-v2 `-r1`. Cases
  outside the claim stay UNRESOLVED and drop by question-level
  EXCLUDE_COMMON. The estimand is value conditional on the covered region and
  every readout says so in its first line. Data Collection completes the 9
  pending mesh-160 and 5 missing/failed references under the existing D3
  grant pattern and v2's stop triggers; no new grant figure.
- **D4 — Freeze the candidate family: YES, and commit the file.** The ten
  pinned candidates at sha256 `157b1db5…` go into the repository, or a
  byte-identical public copy with the digest asserted by a test. No new
  wrappers in the v3 shortlist. A candidate that cannot be committed because
  it holds Validator-private material is out of the shortlist: a rule nobody
  else can reproduce cannot be adopted.
- **D5 — Preregister the selection procedure: YES.** k = 3; top half =
  rank ≤ ⌊n/2⌋ of admitted members. The Test Lead registers both before
  stage 5 runs; registration digest on main.
- **D6 — Aggregate-proxy comparator: DO NOT BUILD ONE; EXCLUDE.** Candidates
  without a per-case form (gain/rank/product aggregates) are excluded from
  the v3 shortlist outright. Recorded as deferred; revisited only if a
  per-case form is supplied.
- **D7 — Holdout: CONFIRMED UNCHANGED.** One reveal, at the final run, Test
  Engineer custody, receipt/digest only.
- **D8 — Park: YES, all of it, until stage 9.** The 5,000–20,000-profile
  sweep, section G competition dynamics, Sobol beyond the four-pair smoke,
  further error axes, further robustness arms.

**Riders.**

- **R1 — "Keep v2" is a finish.** If no candidate survives Stage C or beats
  v2 on the holdout, the record says so, v2 stays, quiz legs stay shadow, and
  the next tranche's question is which leg is missing. That is a completed
  decision, not a failed one.
- **R2 — Nothing here qualifies anything.** DEVELOPMENT v1 values, a
  diagnostic cohort, a versioned rule. No LIVE, reward, production or
  scientific-qualification claim follows. Battery Phase A's all-burn path is
  unchanged.

## 4. Preregistered selection procedure for rule v3

The reason this can finish despite ~6 recipe clusters among 142 members:
**the decision is made on pick regret, not on τ significance.** The
measurement study showed τ intervals stay ~1.6 wide at any row count because
there are six independent things, not 142. Regret of the score's own top-k
picks, in buyer minutes, is what the buyer experiences and is directly
comparable between candidates on the same panel. τ is reported, not gated.

**Stage A — admissibility (unchanged).** Every candidate keeps the in-force
G-FEAS semantics: a member with a mandatory breach cannot rank. Any candidate
that admits a known-bad probe into the admitted set is eliminated.

**Stage B — real diagnostic cohort (covered region).** For each candidate,
on the same frozen panel and common mask:
- τ(score, value) on P, cluster bootstrap over recipe family, interval reported;
- top-1 and top-k pick regret, Σ mix_b · r_b, in minutes;
- gamer/probe placement: always-decline, random-feasible, known-bad, path
  gamers; count any in the top half;
- wrongful exclusion: admitted-good members demoted below a probe.

**Stage C — shortlist.** Candidate survives iff (i) no gamer in the top half,
(ii) top-k regret ≤ the in-force rule's top-k regret on the same panel,
(iii) wrongful exclusions ≤ the in-force rule's. Among survivors pick minimum
top-k regret; tie → higher τ point estimate; tie → fewer legs.

**Stage D — holdout.** Run the shortlist winner and the in-force rule once on
the Test Engineer's holdout. **Adopt v3** iff winner's top-k regret ≤ in-force
on the holdout. Otherwise **keep v2**, quiz legs stay shadow, record the
numbers and the reason.

**Stage E — adoption.** Rule v3 is a prospective versioned record: gates, legs,
registered weights, panel digest, holdout receipt. Shadow value measurement
continues in every hidden batch. Re-evaluation trigger: the next bank tranche
or 50 newly admitted members, whichever first. No historical rescore.

If **no** candidate survives Stage C, that is a finding, not a failure: record
it, keep v2, and the next tranche's question is "which leg is missing," which
the §0 evidence already suggests is a direct decision-regret leg.

---

## 5. Stop doing

- No new synthetic tranche unless it unblocks a stage in §2. The synthetic
  findings that matter are already in hand: accuracy-only anti-aligns on the
  nominal profile; no fixed scalar aligns across target/shifted/extrapolated;
  gates as score levers hurt (median Δτ −0.133) and exclude good members;
  monotone A+Q blends have a structural ceiling; decision-regret terms matched
  the toy oracle. Cite them; don't re-derive them.
- No new score wrappers or components in the v3 shortlist.
- No large sweep, no section G, no Sobol expansion before stage 9.
- No "trusted local" inputs. Anything the lab reads is committed or
  digest-pinned somewhere a second person can fetch.
- No readout that is primarily a reconciliation of earlier readouts. One
  readout per stage, with numbers.

---

## 6. Schedule

Compute is not the constraint; sequencing is. Dates assume the §3 answers land
on day 1.

| Week | Stages | Gate at end of week |
|---|---|---|
| 1 | D1–D8 answered and recorded; job registration (1); candidate file committed (7); cohort export (3); references launched (2) | Registration digest on main; `ADMISSION.json` regeneration scheduled |
| 2 | References complete (2); score legs incl. Q3/VERIFY-R (4); value traces (5); matched controls (6) | `score_lab replay` runs end-to-end on the real cohort; first real τ / regret table exists |
| 3 | Stage B/C readout; holdout reveal (8); rule v3 or keep-v2 record (9) | Decision record merged |

If week 2's gate slips, the slip is in stages 2 or 4 — both Data Collection —
and the fix is a grant/priority call, not a lab change.

---

## 7. Identities

- Main: `bc465b1d` (#1368, 2026-10-15).
- Verdict: `Business/research/score-lab-campaign-01/SCORE_LAB_VERDICT.md` (INSUFFICIENT_EVIDENCE).
- Readiness: `…/finish-line/READINESS_STATUS.json`, manifest sha256 `ce19b0d5…`.
- Public replay / admission: `Business/research/score-lab-public-v2-01/{READOUT.md,ADMISSION.json}`.
- Plating reference v2: `.agent/decisions/2026-10-13-VALIDATOR-PLATING-REF-V2-02.md` (band 1.0 mV; window (−1.97, 4.5) mV; claim |m20| < 15 mV; rules `-r1`; stop triggers §3).
- Battery v3 law: `docs/development/challenge_pipeline/question-laws/battery-ambient-indexed-v3.{md,json}`, round-two supplement `battery-v3-round2.{md,json}`.
- Score inputs decision: `.agent/decisions/V3-SCORE-INPUTS-01.md`.
- Candidate proxies: sha256 `157b1db5…` (not committed — see D4).
- Lab: `scripts/dev/score_lab/` (`README.md`, `FINISH_LINE.md`, `finish_line.py`, `public_v2_replay`, `campaign_*`).
- Synthetic evidence (done): `error-structure-64/`, `component-goodhart-16/`, `combined-matrix/`, `measurement-study/`, `../score-lab-robustness-01/`.

---

## 8. What this handoff does not do

It selects no threshold, coefficient or band by itself. It does not qualify
the battery exam, the plating reference, or any model. It authorizes no spend
beyond what §3-D3 names inside existing grants. It does not touch the holdout.
It does not relabel the public EV4 CV-onset job as battery-v3 charging-time
value. It creates no LIVE, reward, or production claim. It exists so that the
next three weeks are spent on the three things that are actually blocking a
score decision, and nothing else.
