# GRAPHITE-L4-STAGING-01, route R1: the working contract

**Ticket.** `.agent/tickets/GRAPHITE-L4-STAGING-01.md` (#1081).

**Authority:**
- **The owner:** "I approve graphites level 4 packaging tool". This covers building it. The isolation acceptance stays the owner's review of the finished PR.
- **R1** (the Test Lead, 2026-10-11): agent code stays in the agent's own sandbox, and Carbon processes the envelope as data, never executing it.

**Maturity:** DEVELOPMENT; the tool runs only in development-level phase-3 sessions.

## The flow

1. **The agent lowers its own model in its sandbox.**
   - `run_python` runs `python -m carbon.level4.tooling lower SPEC OUT --challenge … --interface … --batch …`, then `python -m carbon.level4.tooling envelope OUT /scratch/output/level4-envelope.json.gz`.
   - The analysis image carries the tooling's exact import closure (slice 1, `research_image.LEVEL4_TOOLING`).
   - Carbon never runs the spec.
2. **`graphite_level4_stage {strategy_json, task_id}`,** a Graphite tool offered only in Level 4 sessions (a role variant, as `study_role` adds the study probe, so every other manifest digest is unchanged).
   - **`task_id` empty:** the reply is the base recipe's interface digest, inputs and batch (`level4_admission.interface_and_batch`), and the exact two commands. Nothing is staged.
   - **`task_id` given:** Carbon reads that finished workspace run's export `<tail>-level4-envelope.json.gz` through the miner's own door: `read_file` research tasks, polled, the same calls an MCP client makes. Then:
     - it gunzips under the transport bound (G0's `submission_bytes` plus envelope overhead);
     - it parses strictly as data (`staging.from_envelope`);
     - it requires the strategy's `parameters.composition_graphs` to equal the submission digest;
     - it runs G0, G3 and G4 (`level4_admission.admit_envelope`);
     - it keeps the envelope in the experiment root by submission digest.

     The reply is `{submission, admitted | the typed refusal}`.
3. **The proposal** (`graphite_run_proposal`) names that digest in `composition_graphs`.
   - Carbon writes the kept envelope beside the proposal (`construction_level.write_envelope`).
   - It stages the documents (`staging.workspace`) into the rebuilt record's files, so `expected.staged` pins them.
   - A digest with no kept envelope is refused, typed (`level4_submission_not_staged`).
4. **The pod** gets the documents in `PHASE_CONFIG` as gzip+base64. A refusal above a cap is typed, never truncated. The baseline MLP and DeepONet measured 6–10 KB.
   - `pod_phase` writes them into `work/`.
   - G6 trains (`level4_model.build_from_work`).
   - G7 is the host's frozen-rule scoring of the predictions.
5. **G5** (compile in isolation) stays as accepted for development and testnet (OWNER-L4-G5-COMPILE-ISOLATION-01). This ticket does not wire it into the pod path.

## Invariants

- **No agent code runs on a Carbon host.** Lowering runs only in the agent's sandbox. Carbon reads bytes the agent named, by task id, through the miner door.
- **Envelope bytes are data.** They are size-bounded before parsing, and digests are checked against the manifest.
- **A refusal is typed** and never scored. Infrastructure failure stays `FAILED_INFRA`.
- **Nothing reaches a frozen or LIVE rule.**

## Host bounds (LANE-RESOURCE-BOUND-01, 2026-10-12)

The lowering runs in the miner research lane (`carbon.miner-research.unlimited.v1`). On Carbon's own operator host that lane is bounded; on a miner's machine it is not.

- **A live Level 4-5 session refuses to start unbounded.** `phase3 run` and `phase4 run` at `--level 4` or above refuse, typed, before anything is read or spent:
  - `resource_profile_required`: no host resource profile is in force;
  - `resource_profile_invalid`: the installed profile is unreadable or malformed.
  Dry runs and Levels 0-3 are unchanged (`phase3.hostile_lane_bounds`, `miner_container.require_host_profile`).
- **How the profile reaches every process.** It is read from the owner-only file named in `CARBON_RESEARCH_RESOURCE_PROFILE`, or, when that is unset, from `~/.config/carbon/research-resource-profile.json` if it exists. The fallback reaches MCP door processes started without the variable, and the supervisors they spawn. Both locations fail closed under the same rules. The variable takes precedence.
- **Operator profile for `carbon-fresh`** (installed by the operator after merge, mode `0600`, owned by the lane's user):

  ```json
  {"schema": "carbon.miner-research.resource-profile.v1", "cpus": 4, "memory_bytes": 8589934592, "pids_limit": 512, "nofile": 8192}
  ```

  - 8 GiB memory, swap included, leaves about half of the 15.9 GB WSL VM to the other sessions.
  - 512 tasks stop a fork bomb but leave room for the thread pools of JAX and BLAS.
  - 4 CPUs keep the host responsive.
  - 8,192 open files are generous for research. Kernel memory for descriptors is charged to the memory bound.
- **Scratch is capped by a watchdog** (the Test Lead's choice (c)). Scratch stays a host bind mount (`<operation>/scratch`), and the carrier still reads `scratch/output` from the host disk.
  - The cap is 2 GiB per run (`miner_container.SCRATCH_CAP_BYTES`), a named constant, so profile v1 is unchanged.
  - Where a host profile is in force, the carrier measures scratch every second, inside the container as the worker that owns it. When a run passes the cap, the carrier kills its container. The run settles typed: `FAILED_MINER`, worker code `POLICY`, observation `scratch_cap_exceeded`. The detail goes in `scratch-watch.json`. It is never a score or a scientific outcome.
  - A run that hides part of its scratch from its own user, or whose scratch stays unmeasurable for 15 polls, is stopped the same way.
  - A miner's machine has no profile, and so no watchdog.
  - A run can overshoot the cap by about one poll's worth of writes before it is killed.
- **The host floor.** A live Level 4-5 session refuses to start, typed `scratch_host_low_space`, when the filesystem holding its campaign's scratch has less than 15 GB free (`shutil.disk_usage`).
- **The bound is per container.** Concurrent runs from several sessions each get their own bound.

## Slices

| Slice | Content | State |
|---|---|---|
| 1 | The analysis image carries the tooling closure (`research_image.LEVEL4_TOOLING`, staging included); the closure test | done |
| 2 | The tooling's `envelope` subcommand; `graphite_level4_stage`; the Level 4 role variant (the brief's `level4_stage`) | done |
| 3 | The proposal carries the envelope (`expected.staged` pins the documents); a never-staged digest is unrebuildable | done |
| 4 | The pod job carries the envelope; the pod builds with it; the practice program takes the Level 4 build; the bundle carries it, so the clean rebuild is REBUILT | done |

**Tested on the CPU:** a scripted Level 4 Constructor stages a lowered graph through a stand-in miner door, proposes it, is scored on scripted pods and bundled (`test_graphite_level4_session.py`).

**Not yet exercised:**
- **A live lowering in the miner lane.** It needs the analysis image release carrying slice 1.
- **G6 training of a graph on a real pod.** The first live Level 4 run exercises it.
- **G5 (compile in isolation)** stays unwired here, as stated above.

## Owner-reserved

- **The isolation review** of lowering untrusted model source in the agent's sandbox, and of the envelope transport.
- **The image release** carrying slice 1 (the next image release; the owner's word).
