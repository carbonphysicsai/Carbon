## 2026-10-08 — OWNER-REFERENCE-ROUTE-TRIAGE-GRANT-01: a capped hourly cloud host for #787's reference-route cost triage

**Authority.** The owner, 2026-10-08, answering "yes" to the Test Lead's
proposal, as relayed by the Test Lead to the Data Collection session. This
record takes effect only when it is merged to main. Merging is the owner's
confirmation through the PR Head.

**Context.** CHALLENGE-REFERENCE-ROUTES-01 (#787, merged at
`58a429a8272cc3a1a05bbeb49bad961507375564`) proposes a cost triage of five
families' reference routes (f02, f06, f08, f13, f17) on public recipe panels
(`docs/development/challenge_pipeline/round1/reference-route-panels.json`).
Its grant proposal recommended spare AX42 CPU or the laptop at a $0 cash cap.
The owner chose a separate host instead. The AX42 holds hidden data, and the
laptop's timing profile is not comparable.

**Decision.**

| Field | Value |
|---|---|
| Purpose | #787's reference-route cost triage on its public recipe panels only |
| Platform | Hetzner Cloud, one hourly-billed server with 8 dedicated vCPU (a CCX-class type with at least 24 GiB RAM), x86-64, created by the owner in the Hetzner console |
| Not this platform | The AX42 (hidden-data host), the laptop, RunPod, any GPU |
| **Monetary cap** | **EUR 5 all-in** (server hours including setup and idle, primary IP, traffic; no snapshots, volumes or backups) |
| **Node-hours cap** | **20** server-hours, created to deleted, whichever cap is reached first |
| Allocated CPU | at most 8 logical CPUs; at most 160 allocated logical-CPU-hours |
| Memory | at most 24 GiB aggregate total cgroup memory |
| Concurrency | one case worker or coordinated solver group at a time; at most 16 live OS processes in a case group |
| Per-case wall timeout | 7,200 s; automatic retries 0 |
| Solver launches | at most 442 in total (one external solver invocation or coordinated MPI group = one launch) |
| Transferable | no: caps are sequential and per family, as below |
| Paid fallback | none |

**Per-family ceilings (#787 §Grant proposal), sequential and non-transferable.**

| Family | Node-hours | Allocated logical-CPU-hours | Solver launches | Separate work ceiling |
|---|---|---|---|---|
| f02 | 2 | 16 | 32 | ≤ 4,800 internal steps per transient attempt |
| f06 | 8 | 64 | 200 | 144 primary, 36 witness, 16 2D screen, 4 controls; no 10-nm run |
| f08 | 2 | 16 | 58 | ≤ 40,000 harmonic frequency evaluations |
| f13 | 4 | 32 | 20 | ≤ 7,000 frequency systems; ≤ 601 points per curve |
| f17 | 4 | 32 | 132 | 96 primary, 24 refined, 12 controls/parity |
| **Total** | **20** | **160** | **442** | not a budget for filling #776's banks |

#787's conditional f06 high-memory proposal (16 CPUs, 256 GiB) is **not**
granted here.

**Delete-after rule.**
- The server is **deleted**, not powered off (a stopped server still bills). Deletion happens when the triage ends, when either cap is reached, or after 48 hours, whichever comes first.
- Its primary IP is released with it. No snapshot, image, volume or backup is kept.
- Before deletion, only the public measurement ledger and public artifacts named by #787 are copied off.
- The deletion and the final node-hours are recorded in the private spend ledger.

**Access and material.**
- Agents get SSH access to this one server only, with the agent key the owner adds at creation. No other credential, token or host is exposed.
- Only #787's public recipe panels, pinned solver packages and public decks run there. Never hidden EVAL, STRESS, quiz or tuning material, seeds, labels or their derivatives. Never validator state, private roots or journals.

**Entry conditions.** A family's cases launch only when all of these hold:
- this record is on main;
- that family's solver package is pinned: source, build and image digests, plus deck, mesh and observer pins recorded per #787 "Acquisition packages and immutable pins";
- that family's feature/control proof required by #787 passes;
- the enforced runner applies the wall, CPU, memory, launch and process caps above, with no retries;
- a private ledger records node-hours, CPU-hours, memory peaks, launches, failures and censored cases from the first minute.

**Not decided here.**
- Any reference adoption, decision-agreement threshold or adequacy claim. #787's checks remain HUMAN_INPUT.
- Expansion to the Foundation Plan 30-case study.
- Any purchase beyond this server.
- Protocol-stage timing fields: these measurements stay in the measurement ledger, per #787.

**No execution** happens through this record. Spend is booked privately, never
in the repository.
