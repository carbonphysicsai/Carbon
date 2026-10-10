## 2026-10-10 — OWNER-MOTOR-TRAIN-GRANT-01: public 10p/12s motor TRAIN, stage 1, on the battery CCX63

**Authority.** The owner's team cost-benefit bank budget (EUR 500 maximum, approved 2026-10-10), staged by the Test Lead the same day. Binding when merged through the PR Head, which confirms with the owner.

**Why.** The motor panel is the MOTOR-FEASIBILITY-02 10p/12s double-layer family. Carbon's current motor kit is the GRUCAD 8p/24s machine and cannot serve it.

**Decision (stage 1 only).**

| Field | Value |
|---|---|
| Set | 128 public TRAIN geometries: seeded Latin hypercube over the registered six-coordinate grammar, geometric validity enforced, rejecting any point within normalised distance 0.10 of the 43 panel/study designs (24 public panel + 19 study; closest existing pair 0.200) |
| Solves per geometry | the panel's bundle: J 0; J 10 and J 15 at gamma -10/-5/0/+5/+10 (three-slice step skew 0/2/4 deg reconstructed as the panel) = 11 |
| Total | 1,408 standard-resolution solves, pinned motor reference image (sha256:599521e7...), flux observers on |
| Cost basis | standard solve p50 1.16 / p95 1.85 allocated CPU-h (loaded operator host; an upper bound) |
| Platform | the same Hetzner CCX63 as OWNER-CCX63-EVIDENCE-GRANT-01, immediately after the battery run: one server lifetime and one setup; the owner creates and deletes it |
| **Monetary cap** | **EUR 75 all-in** for the motor stage, in addition to the battery grant's EUR 10 |
| Node-hours cap | 55 server-hours for the motor stage |
| Stage 2 (to 256) | a separate decision, only if the stage-1 learning curve shows ripple and cogging still improving |
| Value claims | GetDP code verification (MMS) must pass before any value claim from this set; not required before TRAIN |

**Material.** Public development geometry only; no hidden, AX42 or held-out panel material. DEVELOPMENT; no qualification or LIVE authority.
