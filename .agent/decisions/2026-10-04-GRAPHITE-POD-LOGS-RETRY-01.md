## 2026-10-04 — GRAPHITE-POD-LOGS-RETRY-01: keep a failed pod's logs, retry a failed baseline once

**Authority.** The owner (Ryan) approved two fixes on 2026-10-04 after
Graphite R2 run 4 (REF `05cfb321`), relayed to the executor by the
coordinating session: fix 2, keep the failed pods' logs; fix 3, retry a
failed baseline once. The caps, the retry policy's shape and where each rule
lives are engineering choices within GRAPHITE-01's delegated authority,
recorded here. No scientific value is set: nothing here changes a score, a
gate, a comparison rule or how a pod outcome is attributed
(`pod-attribution-v1`, #573, is unchanged).

Ticket: `.agent/tickets/GRAPHITE-01_in_house_testing_agent.md`.

**Run 4.** 11 pods, all terminated and verified. 4 exited non-zero about
75 s after create, each with `failure.json` `{"stage": "program", "error":
"exit 1"}` after compile and digest verification passed. Their
`program.log` and `phase.log` were exported and digested into the pod ledger
(`pod_exported`) but their bodies were never written, so the cause could not
be read. The baseline was one of the four, which left every later scored
proposal `NO_BASELINE`, never promotable, with no retry.

**Decision 1: keep the logs of a run that did not score** (`pod_logs.py`).
- For a proposal whose outcome is not `SCORED`, Carbon writes each pod
  attempt's `program.log` and `phase.log` under the proposal's record
  directory in the session root, `proposals/<pid>/pod-logs/attempt-<n>/`,
  with an `index.json`. A scored proposal keeps none (unchanged).
- Caps (named constants): the first 16 KiB and last 48 KiB of each file
  (`LOG_HEAD_BYTES`, `LOG_TAIL_BYTES`; a traceback ends a log, so the tail
  gets more); 256 KiB per proposal over all attempts and files
  (`LOG_TOTAL_BYTES`); a log over 16 MiB is not scanned and is withheld
  (`MAX_LOG_SCAN_BYTES`). Each stored file starts with a header line giving
  the full size, sha256 and what was kept; a truncated one has a marker at
  the cut with the bytes left out.
- A log is stored only when its bytes match the sha256 the pod listed for it
  (backends expose an optional `listing(handle)`; `RunPodPods` keeps the
  listing it fetched by, `ScriptedPods` can script a wrong one); otherwise
  `digest_mismatch`. A backend with no listing keeps no log.
- A log whose text names protected material
  (`protected_material.protected`, over the whole log and again over what
  would be stored) is `withheld_protected_material`.
- Every entry keeps the log's size and digest. A kept entry also names the
  class of the last Python traceback's exception, never its message.
- Isolation: operator evidence only. Nothing of a log enters a result record,
  a feedback document, an event, the session summary or a delivery bundle;
  the pod ledger gets a `pod_logs_kept` row with names, statuses, sizes and
  digests only, and delivery leaves even that row out of a bundle's run log.
  Session roots are outside the repository (`phase3._root`), and the tests
  write under `tmp_path`.

**Decision 2: retry a failed baseline once, Carbon-side**
(`baseline_retry.py`, registered policy `baseline-retry-v1`).
- Carbon runs the session's baseline itself (`Experiment.run`, before the
  first admitted proposal), so the retry is Carbon's too: deterministic, not
  something the agent is told to do. Right after the baseline closes without
  a score, before the triggering proposal's own pod, Carbon decides once and
  records the decision write-once (`baseline-retry.json` in the run's
  experiment root), in the pod ledger (`baseline_retry_decided`) and as a
  session event (`kind: baseline_retry`, ingested into the controller ledger
  as data like every other event).
- Retried: `FAILED_INFRA` from a pod that ran and ended in infrastructure:
  `candidate_failure_unattributed`, `compile`, `pod`, `infra`,
  `predictions_missing`.
- Never retried: `CANDIDATE_FAILED`, `CANDIDATE_RESOURCE_EXCEEDED`; a launch
  the launch gate refused (`launch_refused`, nothing was created) or whose
  outcome is unknown (`launch_unresolved`); a process death
  (`interrupted_not_rerun`, never rerun); the attribution policy's own timeout
  outcomes (already retried once); a second retry.
- Limits: the retry's pod and the waiting proposal's pod must both fit the
  session's pod limit, the run's money cap (tokens and pods together) and,
  under the v2 session limits, the remaining elapsed time; the retry's pod
  then passes the usual admission and the pod launch gate. Otherwise no
  retry, with the refusal as its reason code. `Phase3Tools`' time gate counts
  a decided retry that a process death interrupted.
- The retry reruns the same strategy with the failed baseline's seed: a
  rerun, not a new draw.
- A retry that scores is the session's baseline: later proposals are
  compared with it (`record["baseline"]["proposal_id"]` names it), and
  delivery bundles it as the baseline.
- Results scored before the retry are not re-compared: result records are
  write-once and nothing re-compares them. They stay `NO_BASELINE`, and the
  decision lists them with the reason. In this code path a retry is decided
  before any proposal is scored, so this arises only for a session whose
  baseline failed before this rule existed.
- The policy is data, pinned by digest in `baseline_policies/registry.json`;
  the loader refuses (fails closed) a version that retries a
  candidate-attributed outcome or a launch-gate refusal, allows more than one
  retry, names other limits or another seed rule.

**What this does not change, and what it means for run 4.** Under
`pod-attribution-v1` a pod's `program` claim is admissible at Levels 0-3, so
at phase 3's recorded Level 0 the run-4 shape (`stage: program`, `exit 1`) is
`CANDIDATE_FAILED`, and a baseline failing that way is not retried. It is
`FAILED_INFRA` / `candidate_failure_unattributed`, and retried, only at
Levels 4-5 or an unknown level. Whether a crash inside the practice program
is the candidate's or infrastructure is the attribution policy's call
(owner-decided, #573), not this rule's. The kept logs, with the exception
class, are the evidence for that call.

**Dry run.** `phase3 run --dry-run` also runs
`experiment.failure_path_check` and fails unless it is OK: a scripted
baseline pod ending with no claim is retried once and scores, a proposal is
compared with the retry, and a scripted pod exiting 1 with a log larger than
the per-file cap keeps it bounded with its traceback's class.

**Coordination.** `pod_outcome.py` (#573, the Carbon Validator session's) is
unchanged. `phase3.py` changes are four small hunks: the module docstring,
the time gate counting a pending retry, the experiment getting the run's
remaining-time reader, and the dry run running the check.
