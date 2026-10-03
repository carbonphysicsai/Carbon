## 2026-10-03 — OWNER-EXEC-APPROVALS-01: the four open decisions from the executive update

**Authority.** The owner, in chat on 2026-10-03, answering the four decisions
listed in the session's executive update: "I approve all. Including security
review and GPu Julia".

1. **The near-limit optimism gate's cutoff.** The owner approved the lead
   session's recommended cutoff (OWNER-EV5-CAP-01 item 3).
   - **Not applied.** This session's automated permission check refused the
     change to `admissibility.THRESHOLD_BANDS` again.
   - **Effect.** The value stays None and the gate stays INACTIVE. EV5's
     freeze still waits on it (EV5 §8 item 1) until the owner applies the
     change.
2. **A measurement for the localized sign-error failure: commissioned.**
   - **What is built.** Near-limit false acceptance
     (`carbon/battery/value/false_acceptance.py`): the worst constraint's
     share of the reference-resolved FAILs in the important region that a
     model calls PASS. The contract's verdicts and bands are used, and
     nothing new is chosen.
   - **Controls.** The sign-error control scores 0.95 and the boundary
     optimist 1.00; oracle, conservative and rank-preserving delay score 0
     (`docs/development/evidence/near-false-acceptance-2026-10-03/`).
   - **Real members are not measured.** Their predictions are not retained.
     The measurement is proposed as EV5's H3 quantity, reported for every
     member, and the SciML lead may amend it before the freeze.
   - **Not a gate.** No cutoff exists (HUMAN_INPUT), and no score changes.
3. **Security review of the C-MLP-05 GPU code cell
   (https://github.com/carbonphysicsai/Carbon/pull/523): approved and run.**
   An agent review of the PR head `9efe083d`, read-only. It is not
   SECURITY_QUALIFIED; human security acceptance stays reserved (AGENTS.md
   §13).
   - **Sound.**
     - No path sends validator-private roots, seeds, hidden batches or
       reference labels to either GPU lane.
     - The local GPU lane keeps the CPU lane's isolation and adds exactly one
       GPU, by UUID from the host record, checked after create.
   - **Medium, to fix before C-MLP-05 merges.**
     - The remote lane does not give agent-written code the isolation its
       tool text promises. The ssh-docker container has network access and
       every GPU; the ssh-container route has no sandbox. The miner's own
       credentials and machine are what is at risk.
     - Remote output is decompressed in full before its size is checked. The
       same library code is on `main` from
       https://github.com/carbonphysicsai/Carbon/pull/511, but no setup path
       reaches it there yet.
     - A correctness bug: a successful remote run is reported as failed.
   - **Low.**
     - Malformed remote output leaves the ledger RESERVED.
     - The miner and validator GPU locks are separate.
     - The local tunnel port can be claimed by another local user.
     - ssh-container cleanup can report confirmed while a child survives.
     - MIG UUIDs are refused on the local lane.
   - **Needs a GPU host:**
     - whether the toolkit exposes only the selected UUID;
     - the shared driver device surface;
     - GPU memory scrubbing between runs.
   - **Next.** The findings went to the owner with file and line detail, for
     the C-MLP-05 lane to fix.
4. **CUDA in the pinned Julia depot, so `run_julia` can use the GPU:
   approved.**
   - **Scope.** `.agent/tickets/JULIA-GPU-01_cuda_julia_depot.md`.
   - **Slice 1, the depot.** It can land on `main` first. It needs a Docker
     host and GHCR write access to publish the depot, which a cloud session
     does not have.
   - **Slice 2, the code cell.** It follows C-MLP-05.
   - **Unchanged.** The validator stays on jax-cpu, and Julia analysis stays
     non-evaluator (`official_eligible: False`).

**Unchanged.** DEVELOPMENT only:
- the testnet rule stays deciding;
- no chain action, reward or weight change;
- nothing is qualified.
