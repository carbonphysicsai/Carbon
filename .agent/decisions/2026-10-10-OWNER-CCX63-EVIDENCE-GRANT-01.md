## 2026-10-10 — OWNER-CCX63-EVIDENCE-GRANT-01: one hourly CCX63 for development evidence panels

**Authority.** The owner, 2026-10-10. His whole reply was "Approve", answering
the Test Lead's exact line "approve €10 CCX63 evidence runs". The Test Lead
relayed it to the Data Collection session. The owner creates the server
himself in the Hetzner console; that act confirms the spend. This record binds
the spend and takes effect when merged to main through the PR Head.

**Decision.**

| Field | Value |
|---|---|
| Purpose | Development evidence panels on public material, in priority order: (1) the battery v3 middle-band panel (#965, after its reuse check against the 93 registered middle-band refinements), (2) the f02 v2 full schedule menu (384 frozen decks), (3) motor's remaining heavy solves (rung-2 and frontier skew panels) if the cap allows |
| Platform | Hetzner Cloud, one hourly-billed **CCX63** (48 dedicated vCPU, 192 GB RAM, x86-64), Ubuntu 24.04, created by the owner |
| Not this platform | The AX42 (hidden-data host), the laptop, RunPod, any GPU |
| **Monetary cap** | **EUR 10 all-in** (server hours from creation to deletion including setup and idle, primary IP, traffic; no snapshots, volumes or backups). At the quoted EUR 1.37/h this is about 7 server-hours |
| **Node-hours cap** | **7** server-hours, created to deleted, whichever cap is reached first |
| Paid fallback | none |

**Delete-after rule.** The server is deleted (not powered off) when the panels
finish, when either cap is reached, or 24 hours after creation, whichever comes
first. No snapshot, image, volume or backup is kept. Before deletion only the
panels' public records, ledgers and evidence are copied off. The final
node-hours are recorded in the private spend ledger, not in this repository.

**Access and material.**
- Agents get SSH access to this one server only, through the agent key the owner attaches at creation (`carbon-reference-triage-agent`, ed25519). No other credential, token or host is exposed, and no server address is committed.
- Only development panels on public, frozen decks run there: the pinned battery truth overlay, the pinned Elmer and motor reference images, and public plans with registered identities. Never hidden EVAL, STRESS, quiz or tuning material, seeds, labels or derivatives; never validator state, private roots, journals or AX42 material.

**Maturity.** DEVELOPMENT evidence only. Results confer no qualification,
reference adequacy, LIVE authority or production claim.
