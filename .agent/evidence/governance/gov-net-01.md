# GOV-NET-01 stable evidence — post-Wave-B Bittensor roadmap

**Evidence class:** stable tracked planning/governance evidence
**Exact base commit:** `7161fe3c4a04821b7f676ab006bd5d313d0442d2`
**Exact base tree:** `619e366dead2288ccfd312f54ad09f17f86a1c62`
**Branch:** `agent/post-wave-b-bittensor-roadmap`
**Primary Hub map_ref:** `SYSTEM/DEVELOPMENT-SEQUENCING`

## Recorded scope

The candidate ratifies planning authority only: Wave B stays unchanged;
post-Wave-B network work is decomposed into C0/C1/C2; G3 is a temporary,
winner-triggered, no-winner-safe testnet proof; Wave D remains the first
scientific qualification gate; Wave H alone creates frontier events; Wave I
is mainnet-critical and settles through treasury routing. Exact operational,
security, scientific, and economic values remain unprovided.

## Stable acceptance evidence to record in-tree

- exact base and owner direction;
- durable decision and supersession ledger;
- authority-document and Hub-source manifest;
- local validation commands/results that do not depend on the final PR head;
- exact maturity ceiling and next-state statement.

Exact candidate head/tree, exact-head CI and Greptile, review threads, merge
identity/topology, exact-main checks, notification URL, and external receipt
are dynamic completion facts and are not copied into this tracked file solely
to retrigger validation.

## Baseline observations

- Current main selects B-04 `in_progress`; its runtime remains governed by the
  existing B-01F conditional predicate. This ticket does not change either.
- No current executable Bittensor integration exists in the active authority
  tree. `carbon.chain` is a reserved adapter seam; archived network code has
  no current implementation authority.
- Older documents contained direct score-to-weight and optional direct-weight
  mainnet-beta shorthand. The candidate records those statements as
  prospectively superseded rather than deleting their history.
- The Hub's old linear predecessor model incorrectly made H depend on G. The
  bounded Hub update represents D→H→I as the launch-critical branch while
  E/F/G remain parallel planning lanes after D.

## Authority snapshot manifest (commit A)

```text
.agent/DECISIONS.md
.agent/INVARIANTS.md
.agent/WAVE.md
.agent/WAVE_B.md
.agent/WAVE_B_CODEX_HANDOFF.md
.agent/evidence/governance/gov-net-01.md
.agent/plans/GOV-NET-01_post_wave_b_bittensor_roadmap.md
.agent/tickets/GOV-NET-01_post_wave_b_bittensor_roadmap.md
Design_Specs/Agentic_Development_Master_Plan.md
Design_Specs/Build_Out.md
Design_Specs/Build_Out_Constitutional_Overlay.md
Design_Specs/Build_Out_Protocol_Extension.md
Design_Specs/Compute_Optimization.md
Design_Specs/Evaluation_Evidence_and_Validator_Audit.md
Design_Specs/JAX_Optimization.md
Design_Specs/Operations.md
Design_Specs/Scoring.md
Design_Specs/Specialist_Bank.md
SPEC.md
docs/context/Architecture_Rationale.md
docs/context/Carbon_Context.md
docs/context/DEFENSIBILITY_REGISTER.md
docs/context/Decisions.md
docs/context/IMPLEMENTED_VS_SPECIFIED_CURRENT.md
docs/context/MASTER_OPEN_DESIGN_QUESTIONS.md
launch/Carbon_Testnet_to_Mainnet_Launch_Path_v1.0.2.md
launch/Carbon_Testnet_to_Mainnet_Launch_Path_v1.0.3.md
launch/Carbon_Testnet_to_Mainnet_Launch_Path_v1.0.4.md
```

No `carbon/`, test, dependency, image, workflow, or Bittensor runtime path is
in A. Commit H is limited to the Hub source/validator/playbook and the exact
deterministic outputs produced from those sources; its final exact manifest is
recorded in the PR and normalized external completion receipt.

## Validation contract

Run and record at the final candidate:

```text
git diff --check <exact-base>...HEAD
scripts/dev/canonical.sh ci
python docs/development/carbon_hub/tools/render_hub.py --check
python docs/development/carbon_hub/tools/test_decisions.py
python docs/development/carbon_hub/tools/validate_hub.py --repo-root .
python docs/development/carbon_hub/tools/test_validator.py
node docs/development/carbon_hub/tools/test_routes.js
python docs/development/carbon_hub/tools/browser_smoke_test.py --timeout 30
python scripts/dev/classify_changes.py --base-ref <exact-base> --head-ref HEAD
```

The current classifier intentionally fails unknown `launch/` paths and Hub
validator-tool changes to `RUNTIME_FULL`; it is not loosened by this ticket.
Exact-head required CI, Greptile, thread, merge, exact-main, and receipt
results remain dynamic external completion evidence.

## Local pre-snapshot results

- `git diff --check`: **PASS**.
- `python docs/development/carbon_hub/tools/test_decisions.py`: **PASS**,
  `Decision Console: 19 decisions, 19 unique IDs, focused checks passed.`
- Native invariant/focused pytest: **NOT RUN in the bundled host runtime**;
  that interpreter reports `No module named pytest`. This is an environment
  limitation, not a claimed pass.
- Local canonical Docker validation: **UNAVAILABLE** because the host Docker
  daemon/named pipe is not reachable. Exact-head required GitHub CI remains
  controlling.
- Baseline Hub render check: **EXPECTED PRE-HUB DRIFT**. Commit H will pin the
  source snapshot to commit A, regenerate deterministic outputs, and rerun the
  full Hub contract before the candidate is offered for merge.

## Maturity ceiling

```text
SPECIFIED: YES
OWNER_DIRECTION / RATIFIED_ROADMAP: YES after merge under current governance
BITTENSOR_IMPLEMENTED: NO
TESTNET_WEIGHTS_IMPLEMENTED: NO
NETWORK_QUALIFIED: NO
SCIENTIFICALLY_QUALIFIED: NO
TREASURY_IMPLEMENTED: NO
ECONOMICALLY_QUALIFIED: NO
LIVE: NO
MAINNET: NO
PRODUCTION_QUALIFIED: NO
```
