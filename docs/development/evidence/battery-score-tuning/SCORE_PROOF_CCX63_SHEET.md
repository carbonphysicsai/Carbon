# Score proof, interim look: the CCX63 run (SCORE-PROOF-01)

This sheet solves the first 150 sealed confirmation questions on one hourly
Hetzner CCX63, under the startup-host custody procedure. The rest happens
on the AX42.

- **Grant:** OWNER-SCORE-PROOF-CCX63-GRANT-01, a cap of **EUR 5 and 3.6
  server-hours**, whichever comes first.
- **Custody:** OWNER-STARTUP-HOST-CUSTODY-02, following
  [STARTUP_HOST_RUNBOOK.md](../../graphite/STARTUP_HOST_RUNBOOK.md).
- **The design:** registered in `proof-sequential-v1.json` (target ±0.15,
  interim look at 150).

**What happens where:**
- **The AX42 keeps everything sealed:** it draws the questions and holds the
  sealed contract and seed, the merge, the member rebuilds and the proof.
- **The CCX63 only solves** its shard of reference jobs. Nothing sealed
  reaches the PC.

`P` runs Python as `carbon-producer` (the operator sheet's shorthand). `W`
is the proof-question work directory, for example
`/var/lib/carbon-producer/private/score-proof-1`. `T` is the tuning work
directory and `Q` its quiz.

## 0. Before

- The release containing #1044 is installed on the AX42. The cloud-init
  for the host names the same release tag.
- **Run 1 of [SCORE_PROOF_OWNER_SHEET.md](SCORE_PROOF_OWNER_SHEET.md) is
  done**, and you have picked a rule from `selection.md`. Call it `<PICK>`.

## 1. [AX42] Draw the sealed questions

```bash
P scripts.dev.battery.score_proof_questions draw --work $W --questions 150 --quiz $Q
```

- **The seed.** The AX42 makes its own seed in `$W/seed`.
- **What it prints:** the question count, the job count (5,250) and the
  sealed contract's digest. Only the digest is public: send it to the Test
  Lead before any solve.

## 2. [Console] Create the CCX63 (runbook §1)

**CCX63**, Ubuntu 24.04, cloud config `startup-host.cloud-init.yaml` with its
three values filled in, including the release tag. Note the IP.
Cloud-init takes about 10–15 minutes. **The caps start now.**

## 3. [AX42] Confirm custody by host key (runbook §2)

```bash
ID=2026-10-11-score-proof
ssh-keyscan -t ed25519 <IP> > /tmp/startup-<IP>.key && ssh-keygen -lf /tmp/startup-<IP>.key
ssh root@<IP> 'ssh-keygen -lf /etc/ssh/ssh_host_ed25519_key.pub; test -f /var/lib/carbon-startup-ready && echo ready'
```

1. **Check.** The two fingerprints must match, and the host must print
   `ready`.
2. **Confirm.** Send the fingerprint to the Carbon Validator session and
   confirm it there, before any export.
3. **Pin.** Then write the hosts file and the known-hosts pin:

```bash
printf '%s\n' "OWNER-STARTUP-HOST-CUSTODY-02 startup $ID" 'SHA256:<host>' > /var/lib/carbon-producer/etc/startup-hosts/$ID.txt
chmod 0644 /var/lib/carbon-producer/etc/startup-hosts/$ID.txt
cat /tmp/startup-<IP>.key | sudo -u carbon-producer tee /var/lib/carbon-producer/.ssh/startup-known-hosts >/dev/null
```

## 4. [AX42] Split, push and journal (runbook §3–4)

```bash
P carbon.challenge_validator.startup_shard split --work $W --shards 1 --out $W/shards --challenge battery-fastcharge-ageing-development-v1 \
  --custody /var/lib/carbon-producer/etc/startup-hosts/$ID.txt --host-key 'SHA256:<host>' --overlay /var/lib/carbon-producer/hidden/truth-overlay
```

Then push `shard-0` and the overlay, and journal `pushed`, exactly as the
runbook's §4.

## 5. [HOST] Solve (runbook §5)

```bash
sudo -u carbon-producer -H sh -c 'cd /opt/carbon && .venv/bin/python -m carbon.challenge_validator.tuning solve \
  --work /var/lib/carbon-producer/startup/shard-0 --overlay /var/lib/carbon-producer/startup/overlay --workers $(( $(nproc) - 2 ))'
```

This is about 2.1 hours on 46 workers, by estimate. If the server is near
**3.2 server-hours** and the solve is still running, stop it and go to
step 6: whatever merged is kept, and the rest stays for the AX42.

## 6. [AX42] Pull, journal and merge (runbook §6)

Pull `records.jsonl`, journal `pulled`, and run `startup_shard merge
--work $W --shard $W/shards/shard-0 ...` as in the runbook. **The merge is
all-or-nothing.** On a `startup_*` refusal, stop and report the code.

## 7. [AX42] The refine round, only if time remains

```bash
P scripts.dev.battery.score_proof_questions refine --work $W
```

**If it prints refine jobs and the server has more than 40 minutes left
before 3.6 hours**, repeat steps 4–6 for them:
- split into `$W/shards-refine`;
- on the host, solve with `--workers 20`, because refined solves need much
  more memory.

Otherwise skip it. Those references stay UNRESOLVED, and the AX42 can
refine them later.

## 8. [HOST] Wipe, then [Console] DELETE (runbook §7)

```bash
find /var/lib/carbon-producer/startup -type f -exec shred -u {} + && rm -rf /var/lib/carbon-producer/startup/*
```

1. Journal `wiped`.
2. **DELETE** the server in the console. Power off is not enough: a stopped
   server is still billed.
3. Journal `deleted`.
4. Check that `P carbon.challenge_validator.startup_shard status --work $W`
   shows the shard merged, and pushed, pulled, wiped and deleted for that
   host key.

## 9. [AX42] Rebuild the members and evaluate

```bash
P scripts.dev.battery.score_proof_questions evaluate --work $W --workers 6
```

It rebuilds every panel member on host CPU, about 1.5 CPU-hours, and writes
the sealed decision results to `$W/experiment/results/results.json`, where
they stay.

## 10. [AX42] The interim look

```bash
P scripts.dev.battery.score_proof --phase confirmation --look interim --rule <PICK> --work $T \
  --dev-results $W/experiment/results/results.json --q3-regret $T/q3-regret.json --out $W/proof
```

`$W/proof/confirmation.md` opens with the verdict at the pre-registered
O'Brien–Fleming level for the resolved question count (99.26 % at 150
questions):
- **PROVEN or FAIL:** stop.
- **FUTILE:** stopping is offered, and is your call.
- **CONTINUE:** the next tranche draws more questions towards about 280,
  under a new grant.

Per-level screens are FAIL-able, and per-level τ is descriptive.

## Return (public values only)

- `$W/proof/confirmation.md`, plus `confirmation.json` for the detail;
- the `startup_shard status --work $W` output: counts and the per-solve
  wall-time p50;
- the sealed contract's digest from step 1.

Nothing else leaves the AX42. Shred `$W/seed` once the final look is done
or abandoned.
