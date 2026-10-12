# PUBLIC-DEV-DECISIONS-01: run sheet

**What.** Solve and refine the references for up to 110 new public battery
development decision questions, to lift the public τ ceiling (SCORE-CEILING-01).
The target is >= 64 questions resolved for every member, which gives a ceiling
near 0.8.

**Authority.**
- The Test Lead, 2026-10-11.
- Spend only under OWNER-PUBLIC-DEV-DECISIONS-GRANT-01, once the owner has
  confirmed it in PR Head's session and it is merged.

**Custody.** None is needed. Everything is public: the code, the seed, the
questions, the references and the results. No sealed, hidden, tuning, bank or
validator material is drawn, read, transferred or held.

## The questions (registered here, before any solve)

| Item | Value |
|---|---|
| Generator | `python -m scripts.dev.battery.public_dev_questions draw --work W --questions 110` |
| Seed | public: sha256(`PUBLIC-DEV-DECISIONS-01`) |
| Conditions | 110 on the 0.25 degC-offset 0.5 degC x 0.01 grid inside EV4's envelope (5–40 C, SOC0 0.05–0.50). By construction none is a 0.5 degC grid point, so none equals a sealed SCORE-PROOF condition or one of EV4's 24 public conditions |
| Contract | EV4's decision contract (`ev4-dev-proof-v1`) with these as development scenarios; `public-dev-decisions-v1`, digest `sha256:875b5c40…610444a` |
| Jobs | 3,850 standard (35 per question, in question order), `jobs.json` sha256 `803b3c40…3b92ff`. A test pins this |
| Refine | REF-RESOLVE-01's policy: every standard reference the bands leave UNRESOLVED, or that failed, gets one refined solve. No automatic retries |
| Solver | The pinned truth image `ghcr.io/carbonphysicsai/carbon-determinism-study@sha256:2d19b261…bd940` plus the locked PyBaMM overlay, through `carbon.battery.truth_env solve`. It runs natively in the pod, since a pod has no Docker |

## How the pod runs (unattended, with its own hard stop)

The pod's start command is the existing public-research bootstrap
(`scripts/dev/exam_design/runpod/bootstrap.py`, used for the exam-design and
challenge-pool pods):
- it fetches every code file from GitHub at CODE_REF and checks its sha256;
- it installs the overlay from `battery-overlay.lock.json`, checking each
  wheel's sha256;
- it runs `python -m scripts.dev.battery.public_dev_pod_phase solve`;
- it serves the results on port 8000 to the holder of PROBE_TOKEN;
- **at PROBE_DEADLINE it terminates the pod itself** with RunPod's pod-scoped
  key. That is the hard stop the overrun lesson asked for.

The truth image has no git, curl or sshd, which is why the run uses this path
rather than SSH.

The phase (`public_dev_pod_phase.py`):
1. draws the questions and refuses unless the jobs match the registered
   sha256;
2. solves a dry pass of 30 jobs and measures the mean wall time;
3. keeps the first N whole questions whose projected standard and refine time
   fits PDD_SOLVE_BUDGET_S (x1.15 tail, +15 % refine), up to 110;
4. solves them, then their refine jobs until the budget ends;
5. writes the contract, jobs, records and a summary to the served
   directory.

**A slower pod solves fewer questions; it never runs over.**

## Cost (measured inputs, projected wall)

| | Value |
|---|---|
| Per standard solve | 76.8 CPU-s pinned (SOLVE_COSTS.md, 75–81 over 3). GRANT-03's planning figure was 67 s |
| Per question on 30 workers | 35 x 77 / 30 = 90 s; with the phase's tail and refine margins, 119 s |
| 110 questions | 2.7 h standard + about 0.3 h refine; the phase reserves 3.6 h |
| Setup and fetch | about 0.25 h |
| Memory | 0.6–2.0 GB per solve, so at most 60 GB of 256 GB |

| Cap (USD 1.76/h) | Pod-hours | Solve budget | Questions fitted (projection) | Expected resolved (58 % mask rate) |
|---|---|---|---|---|
| USD 6 (the Test Lead's proposal) | 3.4 | 10,800 s | about 90 | about 52, short of 64 unless refinement resolves more |
| **USD 8 (recommended)** | **4.5** | **14,400 s** | **110** | about 64 |

The mask rate comes from EV4's 7 of 12. Refinement should raise it, but that
is not yet measured.

## Steps (the owner acts; no agent holds a RunPod key or touches the pod)

1. **Data Collection** prepares the pod spec right before launch, after this
   PR merges.
   - It sets the CODE_REF commit, the code manifest, PROBE_TOKEN, and
     PROBE_DEADLINE (creation + the grant's pod-hours − 0.1 h), plus
     PDD_SOLVE_BUDGET_S.
   - The spec goes in a private file on the operator host, never the
     repository. The token is not secret material, but it stays out of
     public text.
2. **The owner creates** one RunPod Secure Cloud CPU pod, 32 vCPU / 256 GB at
   USD 1.76/h.
   - Image: the truth image by digest.
   - Container disk 40 GB, no network volume, HTTP port 8000.
   - Environment and start command from the spec. The start command is
     `exec python3 -I -c "$CARBON_BOOT"`.
3. **Wait.** The pod sets itself up, solves, and serves
   `GET /status` (stage, phase exit).
4. **Fetch.** The owner runs one command from the operator WSL:
   ```bash
   curl -fsS -H "X-Probe-Token: $TOKEN" https://<pod id>-8000.proxy.runpod.net/out.tar.gz -o ~carbon/runs/pdd/out.tar.gz
   ```
5. **Terminate** in the console (never stop). If nobody does, the pod
   terminates itself at PROBE_DEADLINE.

**Afterwards** (Data Collection, local free CPU, no spend):
- `public_dev_questions evaluate --work ~carbon/runs/pdd --workers 8`;
- a resolved-question count against the >= 64 target;
- a hand-off of the decision values for the τ ceiling.

Spend totals go to the operator's private ledger, never this repository.

## Smoke (local, no spend)

The phase ran end to end inside the truth image locally, with 3 workers and
PDD_SOLVE_BUDGET_S 2,000 on the shared operator host:
- the draw matched the registered jobs sha256;
- the dry pass had a mean of 88 s per solve, so the run was sized to 1
  question;
- 35 standard and 4 refine solves (11 %), all OK;
- 1,598 s elapsed, inside the budget, with no partial lines.

## Grant line for PR Head (the owner's figure to confirm)

> OWNER-PUBLIC-DEV-DECISIONS-GRANT-01: PUBLIC-DEV-DECISIONS-01 on one RunPod
> Secure Cloud CPU pod, 32 vCPU / 256 GB at USD 1.76/h, truth image by
> digest. **USD 8 all-in cap (4.5 pod-hours)**, or USD 6 (3.4 pod-hours, about
> 90 questions). The bootstrap self-terminates at PROBE_DEADLINE, the cap's
> pod-hours from creation. Public material only, no custody. The owner
> creates, fetches and terminates; no agent holds a key or touches the pod.
