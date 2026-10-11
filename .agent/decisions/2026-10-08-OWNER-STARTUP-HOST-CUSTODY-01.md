## OWNER-STARTUP-HOST-CUSTODY-01: hidden cases may go to hourly startup hosts, created per startup and deleted afterwards

**Authority.** The owner, 2026-10-08:
- relayed by the Test Lead: "I want a dedicated server for bank start up on
  all 8 challenges and all future challenges … I can't be waiting 6 days",
  then "hourly CCX63s" (the dedicated AX162 was declined on cost);
- confirmed directly in the Carbon Validator session, as a custody (security)
  acceptance: "Approve as described".

This is the owner's security call (AGENTS.md §13). It extends the AX42's
custody of hidden cases to temporary startup hosts, under exactly this
procedure (`docs/development/graphite/STARTUP_HOST_RUNBOOK.md`,
PRODUCER-STARTUP-HOST-01).

**Scope:**
1. **Hosts.** Hetzner Cloud CCX63 servers, hourly, the owner's spend. Each
   is created for one bank startup and **deleted** afterwards; never
   stopped and kept.
2. **Setup:** the AX42's custody, applied by the cloud-init template
   (`startup-host.cloud-init.yaml`):
   - key-only SSH;
   - ufw allowing SSH only, and fail2ban;
   - the `carbon-producer` account, with an owner-only state directory;
   - the released code tag and pinned images.

   No agent has access.
3. **Per startup:** before any export, the owner checks each host's SSH
   host-key fingerprint and **confirms them in the Carbon Validator
   session**. Then the owner writes that startup's hosts file on the AX42:
   - it names this record and every key;
   - it is owned by root, and only root can write it.

   `startup_shard split` refuses without both this record and that file.
4. **Material:**
   - the startup's shards (hidden cases);
   - the truth overlay (solver wheels);
   - the solved records.

   They are held only for the startup. Afterwards they are shredded on the
   host, and the server is deleted.
5. **Transfers:** owner-run rsync over SSH between the `carbon-producer`
   accounts, pinned by host key. Each is journaled on the AX42 (`pushed`,
   `pulled`, `wiped`, `deleted`).
6. **Merge:** all-or-nothing, against each shard's pinned code, image and
   overlay. No record changes the producer's custody or seal rules.

**Not permitted here:**
- any other host type or provider;
- keeping a host between startups;
- an agent-run transfer;
- serving anything from a startup host.

A change needs a new owner record.
