## 2026-10-05 — GRAPHITE-RUNNER-USABILITY-01: the Graphite runners tell a person or an agent what was booked, what to do next and where the reports are, and one checked wrapper launches a session

**Authority.** An owner request on 2026-10-05, relayed in the Test Engineer
session: an application friendly to both humans and agents, fixing operator
findings B6, B9, B11, C7, C8 and C9 of the Graphite Launchpad findings.
Engineering decisions within that request, recorded by the executor. No
scientific value, threshold, gate, tolerance, grant amount or economic
parameter changes. No session terminal state, settlement rule or grant check
changes.

### D1 (B6). Booked versus charged or estimated, per pod, with the basis

**Observed.** RunPod reports no pod charge, so every pod settles
`pod_charge_unresolved` and stays booked at its full reservation; the run
report showed only `pods_settled_usd` and `pods_pending_usd`.

**Decision.** `experiment.PodLedger.charges()` and `pod_charge_report()` read
the pod ledger only (no RunPod call, no billing read) and give each pod
`booked_usd` (what the run counts against its cap, unchanged), `charged_usd`
(only a provider-reported charge), `estimated_usd` (the pod's hourly rate
times its created-to-terminated ledger time, for reading, never booked) and
`basis`: `provider_reported`, `reservation` (verified gone, no charge
reported), `unresolved` (not settled, not verified gone) or `released` (no
pod ran). `phase3 run` and `phase3 status` print it as `pod_charges`. The
deterministic `summary()` is unchanged, so recorded sessions replay
byte-identically.

### D2 (B9). A terminal `reconciliation_required` session names its next step

**Observed.** The GRAPHITE-01 ticket said "Running the same command again
resumes a session", but a session ended `failed` with code
`reconciliation_required` is terminal: the same command only prints its end.

**Decision.** The ticket now says what to do: `reconcile`, read `status`, and
make any further attempt a new `--session N` within the grant's permitted
runs. `phase3 run` and `phase3 status` print `next_step`
(`cli_usage.next_step`) for that code. The terminal semantics are unchanged.

### D3 (B11). Phase 4's coverage report and B2 are written once

**Decision.** `phase4.write_reports` writes the coverage report and its
benchmark B2 with `write_once` as canonical JSON at
`<store>/reports/<run_id>/coverage.json` and `benchmark-b2.json` (store
`DIR/attacker` or `DIR/attacker-dry-run`), after `run` and the dry run print
as before. stdout is unchanged; one JSON line on stderr names the files. A
later report with other bytes keeps the first (`kept_first`). phase4.py gets
the new function and two call lines only (open PRs edit it).

### D4 (C7). One credential option: a key file

**Decision.** Phase 3's `--credential-file` is checked with phase 4's
owner-only rule (`phase4.owner_only_file`: regular file, not a link, this
user's, no group or other permission, not empty) before it is used. Phase 3
keeps `--credential-env ENGY_API_KEY` for older launchers, documented as such.
`run-checked` takes key files only. No key is read, printed or logged.

### D5 (C8). `--challenge` errors list the accepted tokens; no default

**Decision.** `cli_usage.ChallengeParser` appends the registered Challenge
tokens (`challenge_scoring.registered()`) and "there is no default" to any
usage error about `--challenge`, and `--challenge` help lists them, in phase
3, phase 4 and `run-checked`. `--challenge` stays required: the neutral
driver never substitutes a Challenge, even on a single-Challenge host (the
finding's suggested default is declined for that reason).

### D6 (C9). `python -m carbon.agent_campaign.graphite run-checked`

**Decision.** A thin composition of existing commands (`run_checked.py`):
gates (phase 3: `load_grant` with provider `graphite`, `check_code_ref`, then
`phase3 run --dry-run`; phase 4: `phase4 prelive`), stopping at the first
refusal; then `phase3 run` or `phase4 run`; then the post-run checks whatever
the launch's exit (phase 3: `reconcile` on the RunPod lane, then `status`;
phase 4: `status`). `--plan` prints the steps and runs nothing. It decides no
gate or result itself. Tests drive it with `--plan` or a scripted step caller
only; nothing is launched.

**Public interfaces.** Additive: `pod_charges` and `next_step` in `phase3
run`/`status` output; the report files and stderr line in phase 4; the
`run-checked` entry point; usage-error text. Changed: phase 3
`--credential-file` now refuses a file that is not owner-only.

**Lesson.** `carbon/challenge_pipeline/lessons/2026-10-05-graphite-runner-usability.json`.
