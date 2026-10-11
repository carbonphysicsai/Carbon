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

## Slices

| Slice | Content | State |
|---|---|---|
| 1 | The analysis image carries the tooling closure; the closure test | done (this branch) |
| 2 | The `envelope` subcommand; `graphite_level4_stage`; the Level 4 role variant | in progress |
| 3 | The proposal carries the envelope; staged documents in the record | todo |
| 4 | Pod transport; G6 on the pod; a Level 4 phase-3 dry run that proposes a graph | todo |

## Owner-reserved

- **The isolation review** of lowering untrusted model source in the agent's sandbox, and of the envelope transport.
- **The image release** carrying slice 1 (the next image release; the owner's word).
