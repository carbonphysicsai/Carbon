## 2026-10-04 — GRAPHITE-POD-LOGS-RETRY-01: keep a failed pod's logs, retry a failed baseline once

**Authority.** The owner (Ryan) approved two fixes on 2026-10-04 after
Graphite R2 run 4 (REF `05cfb321`), relayed to the executor by the
coordinating session: fix 2, keep the failed pods' logs; fix 3, retry a
failed baseline once. Then, after the coordinating session explained that
`pod-attribution-v1` types a Level 0-3 `program` crash as `CANDIDATE_FAILED`,
the owner directed, verbatim:

> "Yes, retry baseline crashes"

That direction extends the retry to the session baseline's program crash
(decision 2), and only to the baseline: the coordinator made it conditional
on the baseline being Carbon's own recipe, which the premise check below
verifies. The caps, the retry policy's shape and where each rule lives are
engineering choices within GRAPHITE-01's delegated authority, recorded here.
No scientific value is set: nothing here changes a score, a gate, a
comparison rule or how a pod outcome is attributed (`pod-attribution-v1`,
#573, is unchanged; the crashed baseline's own record stays
`CANDIDATE_FAILED`).

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
- It applies to the session's baseline only (`applies_to:
  session_baseline`; `baseline_retry.is_session_baseline` checks proposal id
  `baseline` and kind `baseline`). An agent proposal, an ablation or the
  retry itself is never retried by it; an agent proposal keeps #573's
  attribution unchanged.
- Retried: `FAILED_INFRA` from a pod that ran and ended in infrastructure
  (`candidate_failure_unattributed`, `compile`, `pod`, `infra`,
  `predictions_missing`), and, at the owner's direction, the baseline's
  program crash (`CANDIDATE_FAILED`, reason `program`).
- Never retried: `CANDIDATE_RESOURCE_EXCEEDED`; any other `CANDIDATE_FAILED`
  reason; a launch the launch gate refused (`launch_refused`, nothing was
  created) or whose outcome is unknown (`launch_unresolved`); a process death
  (`interrupted_not_rerun`, never rerun); the attribution policy's own timeout
  outcomes (already retried once); a second retry, whatever the first retry's
  outcome.
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
- The policy is data, pinned by digest in `baseline_policies/registry.json`
  (repinned for the owner's direction; v1 had not merged). The loader
  refuses (fails closed) a version that:
  - applies to anything but the session's baseline;
  - retries a candidate outcome other than the baseline's program crash
    (`ALLOWED_CANDIDATE_RETRIES` is exactly `(CANDIDATE_FAILED, program)`);
  - does not list `CANDIDATE_RESOURCE_EXCEEDED` as never retried, or lists a
    retried status as never retried;
  - retries a launch-gate refusal, an unknown launch or a process death;
  - allows more than one retry, or names other limits or another seed rule.

**Premise check for the owner's direction** (line numbers on this branch,
based on main `feb40756`). The direction rests on the agent being unable to author,
choose or seed the baseline, so a crash retry cannot be gamed. It holds:
- The recipe is Carbon's: `BatteryScoring.baseline_strategy` returns the
  module constant `SCAFFOLD` (`carbon/challenge_validator/battery_scoring.py:154-157`,
  `carbon/battery/research.py:83`). `phase3.session_brief` uses it when no
  baseline is passed (`carbon/agent_campaign/graphite/phase3.py:729`) and puts it in
  the brief (`:737`). The live runner passes none (`phase3.py:1120-1122`), and
  neither does the dry run.
- The brief is Carbon's, written before the agent runs: `run_session`
  registers it (`phase3.py:860`, `provider.register_brief`,
  `carbon/agent_campaign/graphite/provider.py:519-524`), and every read is checked against
  its digest (`provider._brief`, `provider.py:526-533`, `brief_changed`).
  `Phase3Provider.start` refuses a brief whose baseline Carbon cannot rebuild
  (`check_observation`, `phase3.py:661`). The experiment takes the baseline
  from that registered brief (`phase3.py:451`) into `Experiment.baseline`
  (`experiment.py:353`).
- Only Carbon runs it: the one call with kind `baseline` and id `baseline`
  is Carbon's own, before the first admitted proposal
  (`experiment.py:855`). The agent's tool always runs kind `proposal` under an
  id `p-` plus a digest of its call identity (`experiment.py:618`), and
  delivery's ablations are `a-...` (`delivery.py:127`), so neither can be, or
  overwrite, `baseline`.
- The seed is Carbon's: `Experiment._seed` draws 4 bytes from Carbon's
  `randomness` (`os.urandom` by default, `phase3.py:330`) write-once into the
  proposal's `seed.bin`; the retry copies the baseline's own `seed.bin`
  (`_run_retry`, `experiment.py:756`).
- The baseline's pod runs before any agent pod (the first proposal's pod
  starts only after the baseline and its retry close), on a fresh pod.
The agent influences only when the baseline runs (by making its first
proposal), never its recipe, seed or pod.

**What this means for run 4.** Under `pod-attribution-v1` a pod's `program`
claim is admissible at Levels 0-3, so at phase 3's recorded Level 0 the run-4
shape (`stage: program`, `exit 1`) is `CANDIDATE_FAILED`. On the session's
baseline it is now retried once; on an agent proposal it is not. At Levels 4-5
or an unknown level it is `FAILED_INFRA` / `candidate_failure_unattributed`,
retried on the baseline as before. Whether a crash inside the practice program
is the candidate's or infrastructure stays the attribution policy's call
(owner-decided, #573). The kept logs, with the exception class, are the
evidence for that call.

**Dry run.** `phase3 run --dry-run` also runs
`experiment.failure_path_check` and fails unless it is OK:
- a scripted baseline pod ending with no claim is retried once and scores,
  and a proposal is compared with the retry;
- a scripted agent proposal's pod exiting 1 with a log larger than the
  per-file cap keeps it bounded with its traceback's class, and is not
  retried;
- in a second run, a baseline exiting 1 at stage `program` (`CANDIDATE_FAILED`
  at Level 0) is retried once, scores and is compared against.

**Coordination.** `pod_outcome.py` (#573, the Carbon Validator session's) is
unchanged. `phase3.py` changes are four small hunks: the module docstring,
the time gate counting a pending retry, the experiment getting the run's
remaining-time reader, and the dry run running the check.
