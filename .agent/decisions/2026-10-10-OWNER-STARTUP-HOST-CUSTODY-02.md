## 2026-10-10 — OWNER-STARTUP-HOST-CUSTODY-02: the startup-host custody also covers SCORE-PROOF-01's sealed questions

**Authority.** The owner, 2026-10-10.
- **Relayed by the Test Lead:** the owner approved a single hourly CCX63,
  about €5, for the score proof's first 150 sealed questions, "under the
  same custody procedure as bank startups".
- **Confirmed directly in the Carbon Validator session, as a custody
  (security) acceptance.** Asked:
  > Do you accept that same custody (key-only host, host-key fingerprints
  > confirmed here, shards solved on the host, then shredded and the server
  > deleted) for the score proof's sealed questions too?

  the owner chose **"Yes, same custody"**, whose description read:
  > Extend OWNER-STARTUP-HOST-CUSTODY-01 to SCORE-PROOF-01's sealed
  > questions, with the identical runbook. I record it as a short amendment,
  > and the host-key fingerprints are still confirmed in this session before
  > any export.

**Amends** the scope of OWNER-STARTUP-HOST-CUSTODY-01, item 1 ("each is
created for one bank startup"). An hourly startup host may also be created
for one SCORE-PROOF-01 sealed-question solve, and deleted afterwards. All
else in that record is unchanged:
- the cloud-init custody;
- the host-key fingerprints, confirmed in the Carbon Validator session
  before any export, and the root-owned hosts file;
- material held only for the solve, then shredded and the server deleted;
- the journaled transfers;
- the all-or-nothing merge;
- no agent access.

`docs/development/graphite/STARTUP_HOST_RUNBOOK.md` is the procedure, with
the score proof's work directory in place of a bank tranche's. The spend is
the owner's, about €5 for one CCX63.

**Not permitted here:** anything OWNER-STARTUP-HOST-CUSTODY-01 does not
permit. Hosts are never stopped and kept, never reached by an agent, and
material never leaves for anywhere else.
