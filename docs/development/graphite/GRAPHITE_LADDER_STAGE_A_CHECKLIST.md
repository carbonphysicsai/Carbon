# Graphite ladder wave, stage A launch checklist (L0 and L1)

**Status:** READY CHECKLIST for the Graphite Test executor. **Author:** Graphite Testing
Manager. **Authority:** the owner approved stage A (USD 128.44) on 2026-10-09 (relayed by
the Test Lead); plan: `GRAPHITE_LADDER_WAVE_PLAN.md` (in #889). The executor runs live; the
Testing Manager does not. This file starts nothing and spends nothing. A box is checked
only with evidence (a command output digest, a PR number on main, a decision id), never by
assertion.

Stage A is 9 runs: Constructor L0 x2, Constructor L1 x3 (R4), Attacker L0 x2, Attacker L1
x2, kimi-k3 throughout. Concurrency 2 (raised to 4 only after a recorded host-load check).
L0 confirms through the Launchpad on the main deployment. L1 explores on the development
door; **L1 confirmation waits for VALIDATOR-25** (dev-ladder), and no L1 run counts as
"passed through the Launchpad" before it.

## 1. Preconditions (all must hold; none is assumed)

| # | Precondition | Owner | Evidence to attach |
|---|---|---|---|
| 1 | The WSL host is healthy (Data Collection or the Test Lead says so) | Data Collection | their word, recorded in the run brief |
| 2 | **Readiness baseline 2** has run on the host, with the L0 and L1 items in section 2, and its history and reports are committed through a PR | Graphite Testing Manager | the PR number on main and the report digests |
| 3 | The stage A grant is bound on main: the Constructor L0 kimi-k3 binding, the kimi-k3 Attacker token share, R4 for L1, and `max_concurrency` 2 | Test Engineer (binding), owner (grant) | `grant_binding` entries and the committed grant blobs on main; the runner refuses a run otherwise |
| 4 | A host-load check with Data Collection, recorded: free memory and CPU headroom for 2 concurrent runs (4 only after a second check) | Data Collection and executor | the check's output in the run brief |
| 5 | The minerD-G lane is checked on chain with Carbon's reader after the WSL restart: UIDs 8 to 11 registered and the signer opt-in set | executor with the Test Lead | the reader's output (no account detail committed) |
| 6 | The REF: a merge commit on `origin/main`, containing every PR this checklist names, the installed checkout clean at it, setup redone after any reinstall (OWNER-GRAPHITE-TEST-WAVE-05 section 3) | executor | the SHA and the clean-tree output |
| 7 | `phase4 prelive` and `pods.real_path_check` pass at that exact SHA for each challenge and level the run uses. **R1's containment check needs the analysis image manifest**, a host-side file: the closed four-key document (`schema`, `image_id`, `parent_image`, `runtime_digest`) that `research_image.load_analysis_image` reads. It is **not a release artefact**: `research_image.build_analysis_image(parent_manifest, root)` writes it on the host from the local parent image, which is how phases 3 and 4 got theirs. After the WSL restart the executor reuses the existing phase-4 manifest or rebuilds it, and sends the Testing Manager the host path; the readiness runner reads it from `CARBON_READINESS_ANALYSIS_IMAGE_MANIFEST` (PR #892) and passes it to `phase4 prelive --analysis-image-manifest`. The worker-images-v3 image `ghcr.io/carbonphysicsai/carbon-miner-analysis@sha256:5cce1c2d44d87a35dd1f7273f4b8dd75da9bb19a2c40ebae9e0da0d2556d075e` (release `c80a18f21`, CPU-verified) is at most the parent-image reference if the executor builds the manifest from it; it is not the manifest and nothing here writes a manifest by hand | executor | the prelive reports and the manifest file's digest |
| 8 | The host window is agreed in writing between the executor and Data Collection, and no sealed or EV5 host work runs in it | executor and Data Collection | the written agreement |
| 3a | **A4 designations (Test Lead ruling, 2026-10-09):** battery L1 to L4 get dedicated zero-spend controllers; the executor creates the L0 to L4 controller roots and identities first thing after the WSL restart, and the designation entries are recorded in `admission_controllers.json` (a PR through PR Head). **A4 stays NOT passed until those entries exist on main**; it is a precondition owned by the executor, no longer an unresolved blocker | executor (roots and identities), Test Engineer (the designation records) | the five entries on main, `status: DESIGNATED` with an identity, and A4 PASS at levels 0 and 1 in the readiness report |
| 9 | Each run has its own fresh controller root; the W2 rule applies (an open finding blocks LOCK, not exploration) | executor | the root path per run (no secret in the brief) |
| 10 | R4's recorded entry conditions for L1 hold: the owner has picked the score variant; the `hidden_score` variant fix is merged; Level 0 run 3 has completed on the same variant; the Test Engineer's Level 1 hidden-path check says yes | Test Lead | the decision or PR for each (these are not wired into code) |

## 2. Readiness items that must PASS before the live run

Run `python -m carbon.challenge_pipeline readiness --challenge battery-fastcharge-ageing-development-v1
--level 0` and `--level 1` on the healthy host. Last known statuses are the first baseline
plus #698; baseline 2 refreshes them.

| Group | Items | Last known | Needed state |
|---|---|---|---|
| Ownership and decisions | O1, O2, O3 | O2, O3 PASS; O1 REVIEW_REQUIRED | O1 needs the Test Lead's committed review |
| Plumbing | P1, P2, P4, P5, P6, P7 | PASS | PASS |
| Plumbing | P3 | NOT_BUILT (battery) | Test Lead decides: build, or waive by a recorded decision |
| Runtime | R1 | FAIL (containment image manifest) | PASS: the host-built analysis image manifest (precondition 7), named by `CARBON_READINESS_ANALYSIS_IMAGE_MANIFEST` and given to prelive. Unset or malformed fails closed with the reason (PR #892) |
| Runtime | R3, R6 | R3 PASS; R6 REVIEW_REQUIRED | R6's host-window review recorded |
| Runtime | R2, R4, R5, R7 | NOT_BUILT | Test Lead decides each: build, or waive by a recorded decision |
| Attack instrument | A1, A3, A5 | A1 PASS; A3 NOT_BUILT; A5 REVIEW_REQUIRED | A5 review recorded; A3 per the same rule |
| Attack instrument | A2 at level 0 and level 1 | NOT_BUILT (route-to-family check) | adapters exist at both levels; the missing check is the Test Engineer's |
| Attack instrument | **A4 at level 0 and level 1** | FAIL: level 0 identity PENDING; **no level 1 entry** | PASS once precondition 3a's entries exist on main (zero-spend controllers, executor-created) |
| Scoring | S1 to S5 | S5 PASS; S1 to S3 NOT_BUILT; S4 REVIEW_REQUIRED | each decided as above |
| Hidden path | H1, H3 | PASS | PASS |

NOT_BUILT items are never treated as PASS. Gate items only get stricter: a waiver is a
recorded Test Lead decision naming what replaces the check. This checklist proposes none.

## 3. Run order inside stage A

1. Constructor L0 (x2), concurrency up to 2, each in its own controller root.
2. Attacker L0 (x2), after a Constructor L0 run exists to attack (the Attacker reads the
   registered adapter at (battery, 0)).
3. Constructor L1 (x3, R4) and Attacker L1 (x2), exploring on the development door.
4. L0 confirmations through the Launchpad on the main deployment with the auto-confirm
   signer, one commit per hotkey per tempo.
5. L1 confirmations only after VALIDATOR-25 is up (stage B plan, section 1).

## 4. Stop conditions (the executor stops and reports; no retry in place)

- A readiness item that was PASS turns FAIL, or any precondition above stops holding.
- Host memory pressure or the Data Collection host window ending.
- A finding that would leak hidden material into any agent-visible output.
- A grant refusal (`run_cap_reached`, `grant_requires_*`, `start_model_below_the_grants_start_rung`).
- Infrastructure failure is never a scientific result: it is typed `FAILED_INFRA`, retried or
  refunded by the registered policy, and reported.

## 5. After each run

A lessons entry (`carbon/challenge_pipeline/lessons/`), the run's evidence digest, spend as a
count against the grant (caps only, no balance in the repo), and the executor's report to the
Test Lead. The Testing Manager then updates the register.
