# VALIDATOR-06 — Graphite's CPU carrier lane

**Status:** implemented in bounded DEVELOPMENT scope, awaiting review.
**Flagged for the dedicated security review (AGENTS.md §13):** this lane runs
programs in the C-03 carrier on the operator host.

**Authority:**
- OWNER-GRAPHITE-TEST-WAVE-06 (#595): cooling's Graphite runs test both a
  CPU carrier lane and a GPU pod lane, and no route is hard-wired
  (matrix §3a);
- the Test Lead's design approval, 2026-10-05:
  - a second experiment backend beside RunPod, chosen by flag;
  - host timing authoritative, compared with the lane's effective program
    deadline;
  - a pod money cap of 0;
  - Levels 4-5 refused;
  - operator host only;
  - the tokens-only grant id `GRAPHITE-GRANT-PHASE3-COOLING-CPU`.

**Executor:** the Carbon Validator session. Branch
`claude/graphite-carrier-lane`, from main `8ab444d0f`.

## Outcome

A phase-3 run can execute its proposals on this host's CPU in the isolated
C-03 carrier instead of on RunPod, with the same scoring, attribution and
budget rules. The program comes from the Challenge's scoring adapter. The
lane runs Graphite's internal runs on the operator host, never on a miner
host. DEVELOPMENT only.

## Working decisions (delegated engineering scope)

- **VAL6-D1 — one backend protocol.** `carrier_pods.CarrierPods` implements
  `pods.PodBackend`. `launch` records the job, and `wait` runs it
  synchronously:
  1. compile on this host exactly as `pod_phase.run` does on a pod (the
     Challenge's `built_record`, or the registered development variant's);
  2. check the pinned staged files and program;
  3. run the program in the carrier's trusted lane
     (`research_carrier._run`, provenance `GRAPHITE_CARRIER_PRACTICE`), with
     one carrier ledger per job;
  4. return the snapshot's `predictions.json`, `fit.json` and
     `runtime.json`, with `built.json`, `DONE.json` and a bounded
     `program.log`.

  `fetch` applies the pods' fetch limits. `listing` gives digests.
  `terminate` is True, `charge` is 0, and `recover` is None (nothing outlives
  the call).
- **VAL6-D2 — claims and failures.**

  | What happened | Result |
  |---|---|
  | Compile failure | `compile` claim |
  | Pin mismatch | `verification` claim |
  | Carrier `RUNTIME` failure (non-zero exit) | `program` claim |
  | Carrier `DEADLINE` | `timeout` claim |
  | Any other carrier failure | infrastructure, no claim (FAILED_INFRA) |

  Claims are typed by the registered attribution policy, exactly as on pods.
- **VAL6-D3 — timing (the Test Lead's change).**
  - Host-observed time is authoritative: `timing` is the clock around the
    whole carrier call.
  - The lane declares its effective program deadline,
    `effective_work_seconds(contract) = contract - SETUP_MARGIN_S` (45). The
    trusted lane's program exec times out at `seconds - 45` from the run's
    start.
  - The experiment compares host timing with the backend's declared
    deadline (`Experiment._program_deadline`) and records it on the outcome
    (`program_deadline_seconds`).
  - A carrier stop at its own deadline is therefore confirmed, not
    contradicted: one retry, then CANDIDATE_RESOURCE_EXCEEDED on a second
    confirmed timeout, the same rule as pods.
  - A deadline claim the host contradicts still raises the signal.
  - The margin is a declared lane property in `describe()`, and a test pins
    it to the carrier's own source.
- **VAL6-D4 — money.**
  - The lane's `hourly_usd` is 0.
  - `phase3_budget` takes the backend's rate, so pod allowance is 0 and the
    whole run cap goes to tokens. `max_pods` keeps the session shape.
  - `TOKENS_ONLY_GRANTS = {"GRAPHITE-GRANT-PHASE3-COOLING-CPU"}`: a RunPod
    run under that grant is refused
    (`grant_is_tokens_only_use_the_carrier_lane`). The grant file ships in
    its own PR, and the two may merge in either order.
- **VAL6-D5 — the flag and refusals.**
  - `phase3 run --compute {runpod,carrier}`, defaulting to `runpod` so
    every existing command is unchanged.
  - `carrier` requires `--image-manifest` (the pinned C-03 worker image),
    needs no RunPod key, and refuses unless the host doctor finds the host
    eligible.
  - Levels 4-5 are refused at the CLI (`carrier_lane_refuses_levels_4_5`)
    and again at `launch` (`carrier_level_refused`, nothing created).
- **VAL6-D6 — where it runs.** The operator host, for Graphite's internal
  runs only. The carrier's controls are its own:
  - no network;
  - a read-only root;
  - uid 65532 with every capability dropped;
  - cgroup CPU, memory and pid limits and a watchdog, with the effective
    controls verified after start.

  They are engineering controls, not a security qualification.

## Validation

- `tests/cpu/test_graphite_carrier_lane.py` uses a stand-in with the
  carrier's contract that runs the program in a local subprocess. It
  covers:
  - a cooling job runs its own program and scores;
  - a cooling proposal and its baseline score end to end through
    `Experiment`, with zero pod money;
  - failure mapping (five cases);
  - a carrier deadline stop is confirmed against the declared deadline and
    raises no forgery signal, with one retry and then
    CANDIDATE_RESOURCE_EXCEEDED;
  - a contradicted deadline still signals;
  - the margin matches the carrier's source;
  - a cancelled run never starts the carrier;
  - Levels 4-5 are refused before anything is created;
  - the budget gives the whole cap to tokens;
  - the `--compute` flag, image-manifest, Level and tokens-only-grant
    refusals;
  - the carrier ledger's dispatch-once semantics and owner-only root.
- **Native:** the carrier, pod-timeout, pod-logs-retry, pod-store-threads,
  phase 3 and cooling scoring suites (results in the PR).
- **Canonical:** recorded in the PR.
- **Not run:** a real C-03 run. It needs this host's pinned worker image.
  The carrier's own suites cover its isolation.

## Maturity

SPECIFIED, IMPLEMENTED, TESTED (DEVELOPMENT, with a carrier stand-in). Not
SECURITY_QUALIFIED. No live carrier session has run.

## Human input required

- **Security review:** the dedicated review of running Graphite programs in
  the C-03 carrier on the operator host.
- **The grant:** `GRAPHITE-GRANT-PHASE3-COOLING-CPU` is owner-approved and
  the Test Engineer is writing its file.
