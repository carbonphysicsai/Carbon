# Reference-solvers operator environment

For the operator who runs the reference-solver pods on RunPod. Status, findings and
what is left: [REPORT-2026-10-15.md](REPORT-2026-10-15.md). Authority and caps:
`.agent/decisions/2026-10-15-OWNER-RUNPOD-SOLVER-READINESS-01.md` (USD 25 phase cap,
USD 15 balance floor, CPU pods only, ≤4 live, public material only).

## 1. Machine
Any Linux box (Ubuntu 22.04/24.04 tested) with git, python3 ≥3.11 and curl. It does
not run solvers: pods build and run them natively. Docker is only for local checks.
Keep it powered while a pod runs: the collector must fetch results before the pod's
deadline, or they are lost when the pod deletes itself.

## 2. Set up (once)
```bash
git clone https://github.com/carbonphysicsai/Carbon && cd Carbon
git checkout claude/compassionate-curie-yt9dxx
export RUNPOD_API_KEY=...        # your key; never commit, paste or print it
bash scripts/dev/reference_packages/operator_setup.sh     # --cap-usd/--floor-usd/--no-docker
```
For a separately owner-funded operator phase whose historical private billing
ledger is on another machine, use `--operator-phase resume-2026-10-15` with setup
and every `pod_control` command. This preserves the historical campaign and
uses separate public/private ledgers and active-pod state. The phase identifier
does not grant money or renew a budget. Reuse the same identifier on restart;
never create another phase to evade a consumed cap. See
`SOLVER-READINESS-RESUME-PHASE-01` for this phase's USD25 authorization.
It installs the Python env, writes `~/.runpod/api_key` and `~/.runpod/campaigns.json`
(mode 600), starts the `reference-solvers` campaign, builds a clean Python for ship
checks, and prints the RunPod balance. Existing campaign entries and any higher
account balance floor are preserved. Rates, billing figures and host machine
identities stay in `~/.runpod`; only
public events go to `docs/development/evidence/reference-solvers-2026-10-15/accounting/ledger.jsonl`.

## 3. Before every launch: ship check
Pods receive only files the plan names. Check the plan's pod scripts import cleanly:
```bash
.venv/bin/python scripts/dev/reference_packages/ship_check.py \
  docs/development/evidence/reference-solvers-2026-10-15/plans/PLAN.json MODULE[,MODULE] --write
git commit -am "PLAN: ship list" && git push      # the pod fetches code at a pushed commit
# Then repeat without --write, pinned to the committed payload:
.venv/bin/python scripts/dev/reference_packages/ship_check.py \
  docs/development/evidence/reference-solvers-2026-10-15/plans/PLAN.json MODULE[,MODULE] \
  --ref "$(git rev-parse HEAD)"
```
The read-only check copies committed file bytes, reports the modules examined,
and fails when imports need missing shipment files. `--write` produces a plan
proposal that must be committed and checked again. This is a top-level import
smoke check: inspect lazy imports and runtime files separately, especially paths
embedded inside shell command strings.
Modules per plan: f02 `scripts.dev.reference_packages.elmer.f02_bank` (check the plan's
steps for others); f08 `scripts.dev.reference_packages.calculix.f08_bank`; f13
`scripts.dev.reference_packages.elmer.f13_pod_checks,scripts.dev.reference_packages.elmer.f13_triage_freeze`;
f17 `scripts.dev.reference_packages.openfoam.f17_pod_judge` (if the plan names it).

## 4. Launch, collect, stop
```bash
REF=$(git rev-parse --short HEAD)
.venv/bin/python -m scripts.dev.exam_design.runpod.pod_control --campaign reference-solvers \
  dispatch-solver KIND --pod-plan docs/development/evidence/reference-solvers-2026-10-15/plans/PLAN.json \
  --vcpu 16 --minutes 120 --memory-gib 32 --flavors cpu5c,cpu3c,cpu3g,cpu5g --ref $REF --max-pods 4
# "not in stock": retry each minute.  On success note pod_id, then (keep running):
.venv/bin/python -m scripts.dev.exam_design.runpod.pod_control --campaign reference-solvers \
  collect docs/development/evidence/reference-solvers-2026-10-15/DEST --pod POD_ID --wait --poll-s 120
# stop a pod now:
.venv/bin/python -m scripts.dev.exam_design.runpod.pod_control --campaign reference-solvers terminate --pod POD_ID
```

| Plan | KIND | vCPU | Minutes | Worst case |
|---|---|---|---|---|
| f02-verification.json | elmer | 8 | 150 maximum | $0.60 estimate |
| f08-triage-bank.json | calculix | 16 | 120 | $1.12 |
| f13-verification.json | elmer | 16 | 450 | $4.20 |
| f17-witness-triage.json | openfoam2506 | 8 | 90 | $0.60 |

`collect` deletes the pod after fetching. Then commit `DEST/` and the public ledger.

## 5. Read results
`DEST/out/<step>/step.json` (`status`, `why`) · `deck-verification.json` (digests;
`host_regenerated` for meshes regenerated on the AMD pod) · `ledger.jsonl` (per case:
outcome, CPU-s, peak memory) · family verdict files · `setup.log` (`SETUP FAILED` = build broke).

## 6. Known failure modes
| Symptom | Cause | Fix |
|---|---|---|
| `No module named 'carbon'` | plan's ship list incomplete | §3 ship check |
| `N selected case(s) differ from the manifest`, `command_matches_freeze: false` | family changed its case command | re-freeze (e.g. `f08_freeze.py --out DIR`), pin the new manifest, point the plan at it |
| same, only mesh files differ | Gmsh output differs on AMD | add them to the step's `host_regenerated_files` |
| `fetch failed ... pod-phase.json` | phase still writing | rerun `collect --wait` |
| no stock | RunPod Secure CPU stock is intermittent | retry each minute |
| Docker Hub 429 (local only) | anonymous rate limit | `registry-mirrors: mirror.gcr.io` (setup does this) |

Never run hidden/sealed material (EVAL, STRESS, quiz, tuning, seeds) on RunPod; those
roles are generated on the custody host.
