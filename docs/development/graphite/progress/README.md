# GRAPHITE-PROGRESS-01: does Graphite get better, and at what cost?

**What this is.** One ledger line per level per batch, with efficiency (cost, time, waste) and effectiveness (outcomes,
coverage, real findings, fixes, gate coverage) side by side, plus a small chart and a short trend. The ledger and the chart
live **outside the repository**, on the shared host (`~carbon/shared/graphite/progress/progress.jsonl` and `progress.svg` in
the Ubuntu distro). The repository holds the script, the schema and this page. DEVELOPMENT evidence only: it grades nothing,
accepts nothing and claims no qualification.

**The rules it keeps.**
- **No estimates.** A number with no cited source is the string `UNMEASURED`. Every number carries its sample size `n` and a
  source, so a small sample is visible.
- **No sealed data.** A path that names sealed or private material (`sealed`, `hidden`, `private`, `answer-key`,
  `confirm-sheet`) is refused, never read. Improvement is read from the public categorical outcome of each scored proposal;
  a magnitude is read only from PUBLIC practice scores supplied with the batch, otherwise it is `UNMEASURED` (the Constructor
  is scored on the hidden pool).
- **Dollars** are on the controller-committed basis: pod reservation (pod charges stay unresolved at the provider and stay at
  their reservation) plus the provider-reported model charge; totals only, a lower bound where a model charge was not
  recorded; no account data.
- **Idempotent.** Appending a (batch, level) that is already there with the same content does nothing; with different content
  it is refused. The ledger is append-only.

## What a line holds (`carbon.graphite.progress-line.v1`)

| Block | Field | Meaning |
|---|---|---|
| `constructor` | `improvement.best`, `.median` | PUBLIC practice scores only; `UNMEASURED` otherwise |
| | `improvement.public_dev.{accuracy_error,decision_loss}` | the executor's PUBLIC-development measurement per level: median, best, 95% bootstrap interval, `n`, `small_n` ([spec](PUBLIC_IMPROVEMENT_SPEC.md)); `UNMEASURED` until the executor supplies records. A decision-loss column whose common masks differ between runs, or whose runs disagree in sign, reads `MEASURED_BUT_NOISY` with the per-run values and is not an improvement claim; `small_n` is set under 10 runs |
| | `improvement.proposals_with_outcome_IMPROVEMENT` | scored proposals with the public outcome IMPROVEMENT, of all proposals |
| | `bundled_share` | share of runs BUNDLED |
| | `refusals.rate`, `.by_class`, `.causes` | refused proposals (`REFUSED_*`, `FAILED_INFRA`) by class: `brief_gap`, `envelope_too_tight`, `correct_block`, `infra`, or `UNCLASSIFIED` |
| | `usd_per_bundled` | all booked cost of the batch's runs (waste included) over BUNDLED runs |
| | `wall_hours_per_bundled`, `agent_hours` | session durations from the executor's chain logs, only where one exists |
| | `waste` | refused, FAILED_INFRA, stalled runs, with causes |
| `attacker` | `families` | families listed in the coverage report and how many were attempted |
| | `raw_findings`, `triage`, `real_findings_per_run` | after triage: real escapes only; `UNMEASURED` until every finding is triaged |
| | `usd_per_real_finding`, `usd_per_family_attempted` | reservation plus model-charge basis |
| | `findings_led_to_fix` | triaged real or oracle-gap findings with a recorded fix, over all of them; `UNMEASURED` without a record |
| `gate` | `first`, `last`, `series` | NOT_BUILT and FAIL counts per readiness run from the committed `history.jsonl` |
| `excluded_sources` | | any source left out of the line, with the reason |

A refusal class is looked up as `L<level>:<proposal id>` in the batch manifest (proposal ids repeat across runs). The
classes of the stage A Level 0 refusals come from the committed refused-capability log; anything else stays `UNCLASSIFIED`.

## How to run

    python -m scripts.dev.graphite_progress batch --manifest M.json --root DIR --ledger L.jsonl --chart OUT.svg --history H.jsonl
    python -m scripts.dev.graphite_progress chart --ledger L.jsonl --out OUT.svg
    python -m scripts.dev.graphite_progress trend --ledger L.jsonl

A manifest names, for one batch, the run output files (basenames under `--root`) with their `role` (`constructor` or
`attacker`) and `level`, an optional chain log and label for the session duration, and optional `refusal_classes`, `triage`
(finding id to `REAL_ESCAPE`, `ORACLE_GAP` or `FALSE_POSITIVE`), `finding_fixes` (finding id to the fixing PR) and `excluded`.
The three backfill manifests (stage A, the L1 to L4 ladder sessions, and the L2 to L4 Attacker sessions) are in `backfill/`.

## Reading the first lines

- Stage A to C are one point per level, so no trend exists yet; the ledger shows level against level and, from the next batch,
  batch against batch.
- The L1 to L4 session-1 outputs for L2, L3 and L4 were overwritten by a relaunch that replayed the finished report (lessons
  register B14), so those sessions have no wall-clock; the chain log would show four seconds. They are left without one.
- The L2 to L4 Attacker sessions list ten, nine or fourteen families in the coverage report (the deterministic engine's
  families included) and attempted one each; after #1184 and stop rule v3 the Attacker can reach every adapter family.
