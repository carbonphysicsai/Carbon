# C-W1-D2 — observed non-paying DEVELOPMENT comparison

One real agent produced an FNO-48 challenger after reading its own permitted
historical FNO-40 feedback. Three isolated reconstructions completed. Field and
weak-PDE errors decreased on this development cohort; conserved-mean defects and
the STRESS maximum-principle defect increased. The result is mixed.

**Disposition: INDETERMINATE_NO_ACCEPTANCE_RULE.** There is no applicable
authorized scalar, improvement or equivalence rule. No winner, tie, better
physics-model claim, qualification or payment follows. These are descriptive
observations on a seen 12 TRAIN / 12 EVAL / 12 STRESS development subset, not a
prospective confirmatory experiment or full Burgers V1 coverage.

## Frozen contract and authentic sources

- Profile: `carbon.burgers-supervised-development.v2`, Burgers Dynamics V1 1.0.
- Contract: `sha256:846de1bf4f02608d8c7349fafaedd62a90799a906642f2faa3c10892e441cc13`.
- Historical source: `sha256:7000fbdb0e1204b0adc129fe3a74203732707fa29bf230430e34539b3ea5ad68`.
- Challenger source: `sha256:db00dd4171167c765eac56a689471a1a242f2666eb4815745834611fc8f720b1`.
- Challenger receipt: `sha256:55ebe2dc51b12921e10949650b53a3eb7a5e1085726655427224668e391d69f6`.
- Comparison: `sha256:2ff6e56ab7a5b89a9e4647691478fc091823c11c01af3cde67aea5e9c9bf659b`.

Existing C-06 signatures, ACTIVE lifecycle, C-07 source/dossier association,
C-08 authentication, original construction/resources and complete C-05 cohorts
were verified. No C-10 reexecution is recorded for either source; this is not
independent validation. Downstream projections recheck the configured quarantine
journal and source lifecycle. The earlier engineering fixture is not a baseline.
The authentic baseline was not rerun, rescored or silently normalized.

The [working contract](CW1_DEVELOPMENT_COMPARISON.md) records aggregation,
failure/censoring, identities, feedback and rejection rules. Exact private case,
seed, evaluator and credential material stays outside the repository and miner.

## Permitted aggregate measurements

For each role, average 12 cases within each replica, then average three replicas.
All values below are C-05 normalized errors/defects; lower means lower observed
error/defect. Difference is challenger minus baseline. Arithmetic equality does
not establish a tie. EVAL and STRESS are separate; no metric is omitted or pooled
into a scalar. Energy half-time is horizon-clipped, not uncensored timing.

### EVAL

| Metric | FNO-40 baseline | FNO-48 challenger | Difference |
|---|---:|---:|---:|
| conserved_mean | 0.007338127466 | 0.01052201376 | +0.003183886297 |
| energy_dissipation_balance | 0 | 0 | +0 |
| energy_half_time | 2.766480494 | 2.766480494 | +0 |
| field_phase_rms | 0.5617884432 | 0.5577363118 | -0.00405213138 |
| initial_condition | 9.619945448e-08 | 9.619945448e-08 | +0 |
| maximum_compression | 0.2313302377 | 0.2313302377 | +0 |
| maximum_principle | 4.585478053e-08 | 4.585478053e-08 | +0 |
| peak_dissipation | 0.000133442342 | 0.000133442342 | +0 |
| periodicity | 8.256693082e-16 | 8.17652792e-16 | -8.01651625e-18 |
| weak_local_pde | 1.469732576 | 1.462115548 | -0.007617027566 |

### STRESS

| Metric | FNO-40 baseline | FNO-48 challenger | Difference |
|---|---:|---:|---:|
| conserved_mean | 0.01117046542 | 0.01180154515 | +0.0006310797264 |
| energy_dissipation_balance | 0 | 0 | +0 |
| energy_half_time | 2.926730091 | 2.926730091 | +0 |
| field_phase_rms | 0.5847758238 | 0.5802561606 | -0.004519663193 |
| initial_condition | 1.00118658e-07 | 1.00118658e-07 | +0 |
| maximum_compression | 0.2822346661 | 0.2822346661 | +0 |
| maximum_principle | 4.074133334e-08 | 0.0009731619153 | +0.000973121174 |
| peak_dissipation | 0.0315835958 | 0.0315835958 | +0 |
| periodicity | 6.965853726e-16 | 7.011630234e-16 | +4.577650871e-18 |
| weak_local_pde | 1.662115185 | 1.6539162 | -0.008198984402 |

Case and replica variability are separate dependence dimensions. The private
owner report retains all three replica means, their sample spread and paired
case-mean differences. It does not treat 36 case-by-replica cells as independent
cases. Three reconstructions provide limited descriptive spread, with no
qualified confidence interval or p-value. Detailed owner-only diagnostics do not
expand the existing miner feedback projection.

## Agent behavior and bounded accounting

Actual provider/runtime: OpenAI Responses API, `gpt-5-mini-2025-08-07`.
The frozen prompt and 7 miner tool definitions are retained in the private
model-run plan. The agent discovered the challenge/scaffold, read its own prior
aggregate feedback, validated and estimated FNO-48, submitted it, read the result
and stopped. It adapted from the historical construction, but did not revise
after the new feedback. No second proposal was forced or replacement run made.

| Item | Authorized/frozen maximum | Actual new work |
|---|---:|---:|
| Model-provider exposure | USD 1 | USD 0.00348135 priced usage |
| Conservative provider accounting | USD 1 | USD 0.00745575 |
| Provider calls, including failures/retries | 24 | 8 |
| New distinct proposals / evaluations | 2 / 2 | 1 / 1 |
| Reconstruction replicas | 6 | 3 |
| Training updates | 384 | 144 |
| Prediction operations | 6 | 3 |
| C-05 measurement reports | 144 | 72 |
| Total worker operations | 156 | 78 |
| Worker wall seconds | 7200 cumulative | 271.791944896 |
| Session wall seconds | 10800 | 319.958922552 |
| Observed worker CPU seconds | bounded by worker envelope | 162.448064 |
| Per-worker memory | 4 GiB, no swap | peak 806612992 bytes |
| Session storage bytes | 172662718464 | 5687500 at owner-report seal |
| Public-network transactions / test TAO | 0 / 0 | 0 / 0 |

Token usage: 22,255 input, including 17,664 cached input, and 946 output tokens.
Priced usage uses retained provider usage and published rates; no invoice was
retrieved. Conservative accounting prices all input uncached. No failed or
ambiguous billable request, pending worker, OOM or quarantined attempt remains.
All requests, responses, proposals and tool outcomes are retained. The accepted
C-03 two-CPU, 4-GiB/no-swap, single-worker/no-network controls were unchanged.
All 36 historical references were reused; zero new reference runs occurred.
This accounting is separate from Ask Carbon's website budget.

## Retained owner report and replay recovery

Private session directory:
`/home/carbon/.local/share/carbon-testnet/burgers-comparison-20260916`.
It contains `agent-report.json`, `owner-report.md`, `owner-report.json`,
`comparison-contract.json`, `budget.sqlite3`, the signed source and immutable
`comparison-a487e6f4-36a9-4d26-9b02-0db7e50f5992.json` / `.md`.
The source export retains the numerical reports and signed evidence.

```bash
cd /home/carbon/Carbon
.venv/bin/python -m carbon.development_comparison status --root /home/carbon/.local/share/carbon-testnet/burgers-comparison-20260916
.venv/bin/python -m carbon.development_comparison report --root /home/carbon/.local/share/carbon-testnet/burgers-comparison-20260916
```

Both commands read retained evidence; do not repeat `run`. On Ryan's machine,
the combined readable view is
`C:/Users/Ryan_/source/Carbon/.worktrees/Carbon-Development-Comparison-Results.md`.
These local paths are owner locations, not publicly downloadable evidence.

Runtime commit `37b23bec` produced the completed model/evaluation and comparison.
Final owner-summary readback initially rejected tuple/list representations of
the same canonical signed binding. Repair `1e682e8a` compares canonical JSON
bytes and verifies actual feedback-read ordering. The immutable comparison and
signed sources stayed unchanged; only the owner summary was regenerated. The
failure/recovery is retained in `report-readback-recovery.json`. No model call,
reconstruction, evaluation or transaction was repeated after that report error.

## Delivery and next non-burn prerequisite

PR #196 delivered the historical checked recovery: accepted head
`594b8cb668e9b133cb071b32f0ca3e7785d5c3f9`, run `35143278595`, normal merge
`15ecbe923c8710313cbeadadc8dd5c7d5ec2ae9e`. The exact approved second parent
and all PR #196 files were preserved alongside disjoint PR #200 Workbench work.
The earlier subnet-567 journal remains ROW_VERIFIED with row `[[0, 65535]]`;
its numerical source remains COMPLETE_UNRESOLVED. Burn amounts, epoch effects,
miner payment and settlement remain unproven. That demonstration was not repeated.

C-W1-D2 implementation is submitted in PR #201. Its engineering closeout is
conditional on required CI and normal expected-head merge, recorded in the PR
completion comment. This condition does not change the observed experiment.

The next concrete milestone is a prospectively authorized DEVELOPMENT
acceptance rule and non-paying reward simulation consuming eligible signed
comparisons. The rule must own metric admissibility, comparison/equivalence,
uncertainty assumptions and any scalar mapping; do not fit it to these outcomes.
Existing C-REWARD takeover, self-improvement and decay are tested with synthetic
accepted fixtures only. Later non-burn publication additionally needs eligible
real evidence under that rule, reward/allocation/decay policy, finalized
miner-to-UID mapping, a winner-capable publication profile and separate exact
transaction authority. Multiple challenge allocations remain separately enabled.
No real winner, reward payment or all-burn profile modification occurs here.
