## 2026-10-11 — OWNER-SCORE-PROOF-CCX63-GRANT-02: the score-proof CCX63 grant raised to EUR 8, for 150 resolved questions

**Authority.**
- **The cause.** Research (#1055) measured that about 56% of offered
  questions resolve for every member. So the interim look's 150 resolved
  questions need about 267 offered. OWNER-SCORE-PROOF-CCX63-GRANT-01 sized
  150 offered, about 84 resolved, which is underpowered for ±0.15.
- **The owner's approval.** Relayed by the Test Lead for the re-size he
  described as about eight euros: "That increase is fine."
- **Confirmed directly.** In the Test Engineer's session the owner answered
  "Yes, €8 cap" to amending the grant to EUR 8 (about 5.8 server-hours).
- **When it takes effect.** This record adds to OWNER-SCORE-PROOF-CCX63-GRANT-01
  and leaves that record as merged. It binds the spend when merged to main
  through PR Head, after the owner confirms it in PR Head's session.

**Decision.** For the same purpose, platform, custody (OWNER-STARTUP-HOST-CUSTODY-02)
and material rules as OWNER-SCORE-PROOF-CCX63-GRANT-01, these values
replace its caps and estimate:

| Field | Value |
|---|---|
| Purpose | 150 **resolved** sealed confirmation questions for the interim look, about **267 offered** |
| **Monetary cap** | **EUR 8 all-in** (server hours from creation to deletion including setup and idle, primary IP and traffic; no snapshots, volumes or backups). At the quoted EUR 1.37/h this is about **5.8 server-hours** |
| **Node-hours cap** | **5.8** server-hours, created to deleted, whichever cap is reached first |
| Time limit | Delete at the latest **8 hours** after creation |
| Planning estimate | About 174 CPU-hours of standard solves (267 × 35 = 9,345 at about 67 s, measured on EV4's pod CPUs), so about 3.8 h on 46 workers. The refine round is about 20 CPU-hours, about 1 h at 20 workers. Setup is about 0.5 h. About 5.3 h, or about EUR 7.3. The host's own per-solve time replaces this estimate |

Everything else in OWNER-SCORE-PROOF-CCX63-GRANT-01 is unchanged.

**Maturity.** DEVELOPMENT evidence only.
