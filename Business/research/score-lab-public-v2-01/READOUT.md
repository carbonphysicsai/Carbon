# Public EV4 with prospective plating v2: no admitted full-grammar questions

**INSUFFICIENT_EVIDENCE.** This local public-data replay admits **0/12 D and
0/12 V questions** under the existing V2 bank definition and current plating
reference applicability. It therefore computes **no paired learned-versus-cheap
value result and no score–value tau**. No fitting, rule selection, new reference
band or final confirmation was performed. These are new prospective receipts;
the historical EV4 and synthetic campaign files remain unchanged.

| Reference-only question class | Count |
|---|---:|
| SCORED | 0 |
| INCOMPLETE | 22 |
| RESCUE (fallback infeasible) | 1 |
| NONE (no feasible design) | 1 |

All **35 actions** remain in every question. The 137 public raw prediction
bundles matched their manifest; five existing constructed controls complete
the 142-member public physics cohort. The primary learned cohort remains the
original 100 EV4 rebuilds. The comparator is frozen before this replay as the
existing D-only clamped trace-bilinear map; scalar-bilinear and nearest maps
are separate diagnostics. No V response enters any map's calibration, and
no answer-informed comparator envelope is selected.

## The actual reference gap

The registered v2 reader makes no plating claim for `|m20| >= 15 mV`.
Of the 840 offered action-condition cases, **532** lie outside that claim.
Known reach-CV or thermal failures settle **309** of those designs as
INFEASIBLE without claiming a plating verdict. The remaining **223** have
unavailable prospective plating reference support and block full-grammar
admission under the current bank rule. They are an applicability gap, not
223 failed solver executions or a miner penalty.

The public label table separately has 44 decided EV4 near-onset rows,
14 solved in-band UNRESOLVED rows and 19 pending rows. The minimal handoff
retains the unknown outcomes that can affect admission or the pick:

| Blocking category | D | V | Total | Required authority/evidence |
|---|---:|---:|---:|---|
| Outside v2 plating claim, other checks do not settle infeasibility | 135 | 88 | **223** | Validator/owner reference-applicability contract; no new band inferred here |
| Pending mesh160, potentially decision-changing | 6 | 3 | **9** | Data Collection's recorded completion under existing v2 rules |
| Solved in-band, potentially decision-changing | 2 | 2 | **4** | Remain UNRESOLVED; any new reference method/band is reserved |
| Original reference missing/failed | 5 | 0 | **5** | Reference completion evidence; never a candidate failure |

Exact **public** case IDs, classes, common masks and source bindings are in
[ADMISSION.json](ADMISSION.json). Harmless in-band candidates are handled by
the registered decision-determined criterion; known failures on another
mandatory constraint remain INFEASIBLE. Neither mechanism resolves the
223 applicability gaps by assigning an unsupported plating band. Completing
all 103 global pending cases alone is not a substitute for this coverage issue.

## What the legacy score data supports

Exact legacy `member_legs` recomputed `a/r/g/m/n/p` for all **142** members on
**415 OK original public D scoring cases**, using the original EV4 reference
and frozen calibration. **Q3 and VERIFY-R legs remain absent for all 142**;
partial legacy legs are never called a complete v3 result. Across the three
registered legacy registries, 69 rule profiles have incomplete inputs and
79 have score inputs but no common v2 value mask. All ranking correlations
are withheld. The legacy score-reference identity and prospective decision-
reference identity are kept distinct in [PUBLIC_REPLAY.json.gz](PUBLIC_REPLAY.json.gz).

Replay schema v2 separates missing gate measurements from measured failures.
Both SIGN-only profiles have **0 measured gate failures and 100 missing sign
measurements** per split. SIGN+ENV has **55 measured envelope failures**, 45
otherwise-unknown members, and 100 missing sign measurements. The scorer's
100 operational fail-closed verdicts in each profile are retained separately;
they are not evidence of 100 measured scientific failures. Required missing,
null or non-finite gate measures remain UNMEASURED and cannot yield a tau.
`ADMISSION.json`'s `decision_determined` field means decision-determined despite
unresolved candidates, matching the existing bank helper; it is not a flag
that every fully settled question must set.

This is the old EV4 **CV-onset proxy**, not the battery-v3 indexed charging-time
job. The future proof-bank population is unregistered; Q is the fixed public
EV4 grid and w is the uniform diagnostic weight within each split. The cheap
arm's acquisition cost is not matched to model construction, and stronger
GP/RBF/adaptive comparators remain unsupported here. This cannot establish a
VALUE-BAR pass, a proof Challenge, or confirmation power.

## Reproduction and maturity

Use the explicitly public inputs and a fresh output directory:

```sh
python -m scripts.dev.score_lab.public_v2_replay \
  --public-dir <public-EV4-copy> --plt-readings <public-PLT01-readings.json> \
  --cap 3 --kappa 0.1 --unit-seconds 120 \
  --bootstrap 500 --seed 20261013 --ci-level 0.95 --out <new-output-dir>
```

The cap/cost/unit reproduce the prior public research display anchor as
explicit **ASSUMPTION** inputs. They do not affect the reference-only admission
mask and are not adopted rule values. The repaired local run used 51.47 CPU-s,
126.94 wall-s and 208,420 KiB peak RSS under a 1 GiB address-space and 20-minute
wall cap, with no model rebuild, inference or solver. The environment and
artifact hashes are in [RUN_RECEIPT.json](RUN_RECEIPT.json).

The actual run is a **noncanonical local diagnostic**. The initial canonical
wrapper refused the Windows-managed linked-worktree identity. A native Linux
clone subsequently allowed canonical focused validation of the public-shaped
controls and code; full PR CI remains a separate gate. A canonical actual-data
replay is still required before treating these native measurements as canonical
evidence. No protected
bank, holdout, AX42, pod, keys, spend or LIVE path was accessed.

The next evidence decision is a precise full-menu reference-applicability and
case-completion receipt from the Validator/Data Collection. This replay does
not prune the action grammar, relax a limit or choose a favourable subset.
