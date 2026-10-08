# Startup hosts: hourly CCX63s for a bank startup (PRODUCER-STARTUP-HOST-01)

**What this is:** the owner's checklist for one bank startup on hourly
Hetzner Cloud CCX63 servers. Each server is created for that startup and
**deleted** afterwards.
- The AX42 splits the startup's solves into shards (`startup_shard`).
- Each host solves its shard with the same pinned image, code tag and
  overlay.
- The AX42 merges the records back.
- Setup takes about 30 minutes; most of it is cloud-init.

**Authority:**
- OWNER-STARTUP-HOST-CUSTODY-01, the standing record for this procedure;
- each startup's host keys, written by the owner on the AX42 after
  confirming them in the Carbon Validator session.

No agent has access to any host. DEVELOPMENT only.

**Where:**
- **[Console]** the Hetzner Cloud console;
- **[AX42]** the producer, root session;
- **[HOST]** a startup host, root session.

The shorthands are the operator sheet's: `P` runs Python as
`carbon-producer`. `W` is the work directory being solved, `S` the shard
directory, `C` the Challenge. **Repeat per host** where a step says so.

## Once per producer [AX42]

The producer's startup key, which pushes shards and pulls records:

```bash
sudo -u carbon-producer ssh-keygen -t ed25519 -N "" -C carbon-producer-startup -f /var/lib/carbon-producer/.ssh/startup.key
cat /var/lib/carbon-producer/.ssh/startup.key.pub    # goes into the cloud-init template
install -d -m 0755 /var/lib/carbon-producer/etc/startup-hosts
```

## 1. [Console] Create the hosts (about 2 minutes, then cloud-init)

For each host:
- **Create server:** type **CCX63**, image **Ubuntu 24.04**, your SSH key;
- **Cloud config:** `docs/development/graphite/startup-host.cloud-init.yaml`,
  with its three `<...>` values filled in.

Note each IP. Cloud-init takes about 10–15 minutes: packages, uv, Python
and `uv sync`.

## 2. [AX42] Each host's key, checked, then confirmed in the Carbon Validator session

Per host:

```bash
ssh-keyscan -t ed25519 <IP> > /tmp/startup-<IP>.key && ssh-keygen -lf /tmp/startup-<IP>.key
ssh root@<IP> 'ssh-keygen -lf /etc/ssh/ssh_host_ed25519_key.pub; test -f /var/lib/carbon-startup-ready && echo ready'
```

The two fingerprints must match, and the host must print `ready`.

**Send all the fingerprints to the Carbon Validator session, and confirm
there** that this startup's hosts are these. Then write this startup's hosts
file, owned by root and readable by `carbon-producer`, plus the known-hosts
pin:

```bash
ID=<startup id, for example 2026-10-09-battery-bank>
printf '%s\n' "OWNER-STARTUP-HOST-CUSTODY-01 startup $ID" 'SHA256:<host 1>' 'SHA256:<host 2>' > /var/lib/carbon-producer/etc/startup-hosts/$ID.txt
chmod 0644 /var/lib/carbon-producer/etc/startup-hosts/$ID.txt
cat /tmp/startup-*.key | sudo -u carbon-producer tee /var/lib/carbon-producer/.ssh/startup-known-hosts >/dev/null
```

## 3. [AX42] Split

One shard per host, or more for balance; shards go to the hosts
round-robin:

```bash
P carbon.challenge_validator.startup_shard split --work $W --shards <N> --out $S --challenge $C \
  --custody /var/lib/carbon-producer/etc/startup-hosts/$ID.txt \
  --host-key 'SHA256:<host 1>' --host-key 'SHA256:<host 2>' --overlay /var/lib/carbon-producer/hidden/truth-overlay
```

It prints each shard's `host_key` and `manifest_digest`.
`startup_custody_unrecorded` means a key or the record id is missing from
the file.

## 4. [AX42] Push the shards, and the overlay for battery (repeat per shard)

```bash
SSHO="ssh -i /var/lib/carbon-producer/.ssh/startup.key -o IdentitiesOnly=yes -o UserKnownHostsFile=/var/lib/carbon-producer/.ssh/startup-known-hosts -o StrictHostKeyChecking=yes"
sudo -u carbon-producer rsync -a --chmod=D700,F600 -e "$SSHO" $S/shard-<k>/ carbon-producer@<IP>:shard-<k>/
sudo -u carbon-producer rsync -a --chmod=D700,F600 -e "$SSHO" /var/lib/carbon-producer/hidden/truth-overlay/ carbon-producer@<IP>:overlay/
P carbon.challenge_validator.startup_shard note --work $W --event pushed --host-key 'SHA256:<host>' --manifest-digest <digest> --bytes $(du -sb $S/shard-<k> | cut -f1)
```

## 5. [HOST] Solve (per host), with workers = threads − 2

```bash
sudo -u carbon-producer -H sh -c 'cd /opt/carbon && .venv/bin/python -m carbon.challenge_validator.tuning solve \
  --work /var/lib/carbon-producer/startup/shard-<k> --overlay /var/lib/carbon-producer/startup/overlay --workers $(( $(nproc) - 2 ))'
```

That is battery. Motor is its source's `run_batch` over the shard's
`jobs.json`. The truth image is pulled by digest on first use. The solve is
resumable: rerun it after any interruption.

## 6. [AX42] Pull the records and merge (per shard)

```bash
sudo -u carbon-producer rsync -a -e "$SSHO" carbon-producer@<IP>:shard-<k>/records.jsonl $S/shard-<k>/records.jsonl
P carbon.challenge_validator.startup_shard note --work $W --event pulled --host-key 'SHA256:<host>' --manifest-digest <digest>
P carbon.challenge_validator.startup_shard merge --work $W --shard $S/shard-<k> --challenge $C --overlay /var/lib/carbon-producer/hidden/truth-overlay
```

- **Merge** is all-or-nothing:
  - `startup_record_mismatch` and the `startup_shard_*` codes refuse the
    shard, with nothing appended: stop and report the code;
  - `FAILED_INFRA` records are left for a re-split (steps 3–6 again on what
    remains).
- **Then** the work directory's normal seal or ingest runs, unchanged.

## 7. [HOST] Wipe, then [Console] DELETE (not stop) each host

```bash
find /var/lib/carbon-producer/startup -type f -exec shred -u {} + && rm -rf /var/lib/carbon-producer/startup/*
```

```bash
P carbon.challenge_validator.startup_shard note --work $W --event wiped --host-key 'SHA256:<host>'
```

**[Console] Delete the server.** Not "Power off" or "Stop": a stopped
server keeps its disk and is still billed. Then journal it:

```bash
P carbon.challenge_validator.startup_shard note --work $W --event deleted --host-key 'SHA256:<host>'
```

## 8. Send back (public values only)

- `P carbon.challenge_validator.startup_shard status --work $W`: per shard,
  jobs, merged, and the per-solve wall-time p50 from the records' `wall_s`.
  This is the first measurement on a CCX63, and it replaces the capacity
  model's estimate.
- The startup id and the host count.
