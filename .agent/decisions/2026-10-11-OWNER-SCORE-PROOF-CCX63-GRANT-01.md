## 2026-10-11 — OWNER-SCORE-PROOF-CCX63-GRANT-01: one hourly CCX63 to solve the score proof's first 150 resolved sealed questions

**Authority.**
- **The owner's choice.** The Test Lead relayed the owner's option B on
  2026-10-11: "run the score proof's first 150 questions on an hourly CCX63
  … He approved about €5; the grant cap is five euros."
- **Confirmed directly.** In the Test Engineer's session the owner answered
  "Yes, €5 cap" to: record a grant file with a €5 cap and write the run
  sheet for that host.
- **Custody.** OWNER-STARTUP-HOST-CUSTODY-02 (#1052) covers it. The owner
  confirmed the custody directly in the Carbon Validator's session.
- **When it takes effect.** The owner creates the server himself, and that
  act confirms the spend. This record binds the spend and takes effect when
  merged to main through PR Head.

**Decision.**

| Field | Value |
|---|---|
| Purpose | Solve the reference shards for SCORE-PROOF-01's interim look: 150 **resolved** sealed confirmation questions, about **267 offered** at the measured resolution rate of about 56% (#1055). This is the pre-registered group-sequential design (`proof-sequential-v1.json`). The standard solves come first, then the refine round if the caps allow |
| Platform | Hetzner Cloud, one hourly-billed **CCX63** (48 dedicated vCPU, 192 GB RAM), Ubuntu 24.04, created by the owner from `startup-host.cloud-init.yaml` |
| Not this platform | The laptop, RunPod and any GPU. The AX42 keeps the sealed questions, the merge, the rebuilds and the proof |
| **Monetary cap** | **EUR 8 all-in** (amended from EUR 5; see the amendment below): server hours from creation to deletion, including setup and idle, plus the primary IP and traffic. No snapshots, volumes or backups. At the quoted EUR 1.37/h this is about **5.8 server-hours** |
| **Node-hours cap** | **5.8** server-hours, created to deleted, whichever cap is reached first |
| Planning estimate | About 174 CPU-hours of standard solves (267 × 35 = 9,345 at about 67 s each, measured on EV4's pod CPUs), so about 3.8 h on 46 workers. The refine round is about 20 CPU-hours (about 3% of solves at about 245 s), about 1 h at 20 workers for memory. Setup is about 0.5 h. About 5.3 h, or about EUR 7.3. This is an estimate: the host's own per-solve time replaces it |
| Paid fallback | None. Anything unsolved at the cap stays for the AX42. The interim look then uses the questions that resolved, at their actual information fraction |

**Delete-after rule.** The server is deleted, not powered off, when the
shards are merged, when either cap is reached, or 8 hours after creation,
whichever comes first. Before deletion, every file under the host's
startup directory is shredded (runbook §7). No snapshot, image, volume or backup is
kept. Only public counts and the per-solve wall-time p50 leave the
procedure. The final node-hours go in the private spend ledger, not in this
repository.

**Material.**
- **On the host:** the solve shards (case ids and inputs) and the pinned
  truth overlay.
- **On the AX42 only:** the sealed contract, its seed and the merged
  records. Nothing sealed reaches the PC.

**Maturity.** DEVELOPMENT evidence only. Results confer no qualification,
adoption, LIVE authority or production claim.

**Amendment (2026-10-11): EUR 8, for 150 resolved questions.**
- **The cause.** Research (#1055) measured that about 56% of offered
  questions resolve for every member. So 150 resolved questions need about
  267 offered. The original EUR 5 sized 150 offered, about 84 resolved,
  which is underpowered for ±0.15.
- **The owner's approval.** Relayed by the Test Lead for the re-size he
  described as about eight euros: "That increase is fine."
- **Confirmed directly.** In the Test Engineer's session the owner answered
  "Yes, €8 cap" to amending this grant to EUR 8 (about 5.8 server-hours).
- **What changes.** The cap is EUR 8 all-in, 5.8 server-hours. The time
  limit is 8 hours after creation. Everything else is unchanged.
