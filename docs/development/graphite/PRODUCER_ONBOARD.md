# Producer onboard: one resumable command per Challenge (VALIDATOR-20)

`onboard` runs the operator sheet's producer steps for one Challenge, in
order, on the producer host. Each step is the same existing command the
sheet runs by hand. It records what is done, so a rerun picks up where the
last one stopped. It stops by name wherever the owner is needed.

DEVELOPMENT only: no qualification, weight, reward or LIVE authority.

```bash
P carbon.challenge_validator.onboard --challenge battery-fastcharge-ageing-development-v1 \
  --inputs /var/lib/carbon-producer/etc/onboard-battery.json \
  --state /var/lib/carbon-producer/onboard/battery [--study]
```

`P` is the sheets' `sudo -u carbon-producer -H /opt/carbon/.venv/bin/python -m`.

## The inputs file

It is owner-only, `carbon-producer`, mode 0600. It holds paths and public
values only:

```json
{
  "schema": "carbon.challenge-validator.onboard-inputs.v1",
  "challenge_id": "battery-fastcharge-ageing-development-v1",
  "deployment": "/var/lib/carbon-producer/etc/graphite-hidden-battery-v1.json",
  "overlay": "/var/lib/carbon-producer/hidden/truth-overlay",
  "producer_config": "/var/lib/carbon-producer/etc/producer.json",
  "dev_pool": {"producer_public_key": "<hex>", "outbox": "/var/lib/carbon-producer/producer/outbox"},
  "tuning": {
    "role": "graphite-tuning-v2",
    "pool_prior": "graphite-hidden-battery-v1-pool",
    "pool_export": "/var/lib/carbon-producer/etc/hidden-pool.json",
    "priors": {"ev5-confirmation": "/var/lib/carbon-producer/etc/ev5-confirmation.json"},
    "quiz_work": "/var/lib/carbon-producer/tuning/quiz",
    "quiz_panel": "/opt/carbon/docs/development/evidence/battery-quiz-designs/disagreement-panel-v1.json"
  },
  "study": {"spec": "/var/lib/carbon-producer/study/study-spec.json"},
  "units": {"timers": ["carbon-producer.timer"], "push": "carbon-push.service"}
}
```

`dev_pool`, `tuning` and `study` are optional. `study` runs only with
`--study`. The deployment config itself stays operator-written, as in the
sheet's step 5.

## Stages

| Stage | Commands (the sheet's steps) |
|---|---|
| `truth` | `operate truth-verify`; `truth-materialize` first if the verify refuses (step 4) |
| `deployment` | `operate status`; `init` only if the status refuses (step 5) |
| `pool` | `producer tick`, then `answer_key import` (with `dev_pool`), then `producer status`: a batch must be published |
| `tuning` | `export-pool`, `confirmation seal`, then `quiz-jobs`, `solve`, `quiz-refine`, `solve` refine, `quiz-select` (extra rounds and refine retries as it asks), then `quiz-seal` (step 11) |
| `study` | `study_sets init`, `draw`, then `jobs`, `solve`, `ingest` and `manifest` per set (step 14) |
| `verify` | `systemctl is-enabled` and `is-active` for each timer; `systemctl show -p Result` for the push |

## Output

On success, it prints each stage's count of commands run, and `send_back`:
- `deployment/init`: `root_commitment` and `seed_pin`;
- `tuning/seal`: the tuning commitment;
- `tuning/quiz-refine-*`: the refine count;
- `tuning/quiz-seal`: the quiz digest and sequence;
- `study/init` and `study/manifest-*`: the study values.

**Send these back** as the sheet asks. Nothing else from a command's output
is kept.

## Stops

Exit 3 means the owner is needed; exit 2 is a refusal. Each prints
`stopped`, the step, and the next command.

| Code | Do |
|---|---|
| `onboard_needs_input:<name>` | Add the named input or file, then rerun. |
| `onboard_needs_approval` | The producer config's or study spec's approval record is missing or its sha256 is wrong. |
| `onboard_needs_solver_licence:<name>` | Attest the licensed solver, then rerun. |
| `onboard_tell_test_lead:<code>` | An overlap, collision, short Q2 pool or published case. Never work around it. |
| `onboard_no_cadence` | The Challenge's rule has no rotation; the producer schedules nothing. |
| `onboard_pool_not_published` | No batch is published yet. Rerun after the next tick. |
| `onboard_unit_not_running:<unit>` / `onboard_push_failed` | Fix the unit, then rerun. |
| `onboard_code_changed` | The code moved since the last run. Rerun with `--accept-code <commit>` after the sheet's upgrade step. |
| `onboard_state_mismatch` | A recorded check no longer holds. Stop and report it. |
| `onboard_no_adapter` | The Challenge has no onboard adapter yet. |
