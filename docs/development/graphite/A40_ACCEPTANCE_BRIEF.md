# A40 acceptance run for the released validator image: run brief and grant

*From the Graphite Test executor for Test Lead and the owner, 2026-10-06. Pattern: `docs/development/GPU_DETERMINISM_STAGE_B_RESULT.md` (two single-GPU A40 pods, same class, separate hosts) and `VALIDATOR_GPU_DETERMINISM_POLICY.md` (the pinned configuration). Rates and caps are engineering arithmetic from recorded prices, not a new price. Blocked until the hidden-data VM (VALIDATOR-19 S0) and the released validator image exist.*

## 1. Question

Does the released validator image, under the pinned determinism configuration, rebuild the same battery recipes to the **same digest within a host and across two separate A40 hosts**, for JAX GPU and for PyTorch GPU? And, as a record only, how does the GPU digest differ from CPU?

## 2. Design

| Item | Value |
|---|---|
| Hosts | 2 separate single-GPU A40 SECURE pods, created together in one datacenter (Stage B created two 11 s apart in CA-MTL-1) |
| Backends | JAX GPU and PyTorch GPU, each pinned (XLA: `--xla_gpu_deterministic_ops=true`, `--xla_gpu_exclude_nondeterministic_ops=true`, `--xla_gpu_autotune_level=0`; `JAX_DEFAULT_MATMUL_PRECISION=highest`, `NVIDIA_TF32_OVERRIDE=0`, `CUBLAS_WORKSPACE_CONFIG=:4096:8`; the PyTorch equivalents, see gap G1) |
| Recipes | 3 neural recipes from EV4's public set by the rule in §2b (smallest, median, largest `n_params`) plus one PyTorch-only `fno`; no sealed or confirmation material |
| Repeats | each recipe rebuilt **twice per host per backend**, each rebuild in a fresh interpreter (a fresh session) |
| Rebuilds | 14 per host, 28 in total (§2b item 6) |
| Acceptance (descriptive, no tolerance invented) | for each (backend, recipe): identical weights/predictions digest across the 2 repeats on a host (`within_host`) and across the 2 hosts (`across_hosts`) |
| CPU vs GPU | each recipe is also rebuilt once on CPU through the same image on the Carbon host or the pods' CPU, **expected to differ**, recorded as a digest comparison only |
| Image | the **released validator image** (pinned by sha256), not the study image; direct execution inside it (Stage B ran pod-native), so this says nothing about `validator_launch` unless Test Lead widens it |

## 2b. Recipe selection rule (written before any result is looked at; Test Lead 2026-10-06)

1. **Pool:** EV4's public panel members that are trained on a GPU, i.e. neural backbones (the panel's families are `deeponet`, `knn` and `mlp`; `knn` has no training and is excluded by this rule).
2. **Measure:** each member's parameter count (`n_params`) from its recorded fit in the public EV4 evidence, read once and written to the run's record **before any rebuild or digest exists**.
3. **Pick three:** the member with the **smallest** `n_params`, the **lower median** (the member at position ⌊(n+1)/2⌋ when sorted ascending), and the **largest**. Ties are broken by the lexicographically smallest member id. A member whose backbone cannot be rebuilt on both JAX and PyTorch is skipped and the next one in the same direction is used.
4. **Plus one PyTorch-only `fno` recipe** for the PyTorch leg: the registered `fno` public recipe with the smallest `n_params` (ties by member id). It runs on PyTorch only; the JAX leg records it as not applicable.
5. The chosen ids and the pool's `n_params` list are written to the run record first, and then the run starts. No re-picking after results.
6. **Rebuild count with the fno:** 3 recipes × 2 repeats × 2 backends (12 per host) plus 1 recipe × 2 repeats × PyTorch (2 per host) = **14 per host, 28 in total**. The grant arithmetic in §5 holds: the fno adds two short rebuilds per host inside the same 2 h deadline.

## 3. Pre-run checks (all must pass before any rebuild; the Stage B gap was closed in Amendment 9)

1. **Driver builds match across the two pods**: `run_on_pod.sh` writes the NVML driver build into every session record and refuses when unreadable; `compare_units.py --preflight` refuses differing builds across pods, and a comparison returns `REFUSED_DRIVER_MISMATCH` unless a recorded deviation names exactly the builds. A mismatch is recorded as a deviation, not hidden.
2. **GPU probe:** pod-attribution-v2's Carbon-owned probe runs before any candidate code. A GPU-less host is a FAILED_INFRA environment failure with one relaunch.
3. **Pins:** the pod env carries the configuration of §2, `allowedCudaVersions ["13.0"]`, and the image digest; I record `observed_environment` and device identity per session.
4. **Cost gate:** the pod reservation and the balance floor (`~/.runpod/campaigns.json`) hold, as in phase 3.

## 4. Procedure (once cleared)

1. REF and image: a merge commit on main that contains the released image's pin and the comparison tooling; WAVE-05 §3 six-item record to Test Lead, including a host window agreed with Data Collection.
2. Create the 2 pods concurrently through the operator layer (`operator_compute`), not through Graphite; one intent each, deadline per §5.
3. On each pod, per backend: for each recipe, run 2 fresh-interpreter rebuilds; write session records; fetch them; terminate the pod with verified termination.
4. Run `compare_units.py` offline on the operator side: within host, across hosts, CPU vs GPU.
5. Step 9: both reconcilers (operator layer and independent) clean; no `carbon-…` pod left; report to Test Lead.

## 5. Grant (approved by the owner 2026-10-06, OWNER-A40-ACCEPTANCE-GRANT-01)

Prices from the EV4 pod tooling: `MAX_RATE` USD 0.49 an hour for one A40 SECURE pod, plus container disk 20 GB at USD 0.10 a GB-month over 730 hours: 0.002739726 an hour, so **USD 0.492739726 an hour** per pod. The rate is a ceiling: the runner refuses a pod RunPod offers above it. RunPod reports no pod charge, so each pod is booked at its full reservation.

| Item | Value | Basis |
|---|---|---|
| Platform | RunPod, A40 SECURE, 1 GPU per pod | Stage B |
| Pods | 2 simultaneous, plus up to **2 replacements** (one relaunch each, for a GPU-less host or a mismatched driver) | pod-attribution-v2; Stage B's mismatch |
| Hours per pod | **2.0 h deadline** (15 min start-up, 12 rebuilds with fresh interpreters and compile at about +1 s each plus the image's own start, export, margin) | to be replaced by a measured figure after a 1-rebuild smoke on the first pod |
| Worst case | 4 pods × 2.0 h × 0.492739726 = **USD 3.94** | arithmetic |
| Expected | 2 pods × about 1 h × 0.4927 = **USD 0.99** | arithmetic |
| Cleanup allowance | USD 0.25 (`CLEANUP_RESERVE_USD`) | as in phase 3 |
| **Proposed cap** | **USD 4.25** (3.94 + 0.25 rounded up to the cent: 4.19; rounded to 4.25) | |
| Runs | 1 | |
| Concurrency | 2 pods | |
| Model spend | none (no model calls) | |

Notes on the arithmetic:
- The cap is a ceiling for a worst case of two replacements; a clean run is about USD 1.
- If the owner prefers a tighter cap: 2 pods × 2 h with no replacement is USD 1.97 + 0.25 cleanup = **USD 2.22**, and a failure then stops the run and asks.
- A new grant file would follow the committed shape (`carbon.agent-campaign.spending-grant.v1`) with provider `graphite`-style fields adapted by Test Lead, or a decision record if the operator layer takes a plain cap. I don't author grants; this is the proposal.

## 6. Gaps and risks, for Test Lead

- **G1 (Test Lead: the Test Engineer adds a pinned PyTorch GPU configuration to the image release): PyTorch GPU pinning was not established in what I read.** `carbon/battery/torch_determinism.py` is a repeat-and-compare harness that records host facts (CPU model, thread count) and was written for the CPU backend; I didn't find a GPU pinning policy for PyTorch equal to the XLA policy. The deterministic-algorithms switch, `CUBLAS_WORKSPACE_CONFIG`, the TF32 settings and the cuDNN flags would have to be named and pinned for the PyTorch rebuild. Without that, a PyTorch GPU mismatch would say nothing. Owner/Validator decision.
- **G2: the released image does not exist yet; the run waits for its release digest.** The brief assumes a sha256-pinned image carrying both backends and the comparison tooling. The owner approves the USD 4.25 cap first (Test Lead is putting it to them).
- **G3: class coverage.** Stage B showed A40 agreement only; H100 and Blackwell were each measured on one host and are out of scope here.
- **G4: tolerance.** None is set; the acceptance is digest equality only. A mismatch is a finding, not a failure to tune away (MQ-008).
- **G5: orchestration vs numerics.** As in Stage B, two hosts agreeing on numerics is not two validators agreeing on a score; this run doesn't exercise `validator_launch`.
- **Host load:** CPU-vs-GPU's CPU leg and the offline comparison run on this host; the pods run on RunPod, so the host window with Data Collection is light.

## 7. What I will report (one message plus a file under the run root)

Per (backend, recipe): within-host and across-host digest equality, the driver builds and device ids recorded, CPU-vs-GPU digests, any refused cell or REFUSED_DRIVER_MISMATCH, pod ids and datacenter, total pod time against the reservation, step-9 results, and booked spend (privately, not in the repo).
