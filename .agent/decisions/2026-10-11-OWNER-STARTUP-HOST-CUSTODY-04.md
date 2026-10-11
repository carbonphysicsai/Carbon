## 2026-10-11 — OWNER-STARTUP-HOST-CUSTODY-04: RunPod Secure Cloud CPU pods may pre-solve battery's daily championship batches

**Authority.** The owner, 2026-10-11, directly in the Carbon Validator session, as a custody (security) acceptance (AGENTS.md §13).

> 8. Custody: I accept extending OWNER-STARTUP-HOST-CUSTODY-03 to the daily
>    championship batches on RunPod Secure Cloud CPU pods, under the same
>    conditions as today's score-proof run (stock ubuntu base at the truth
>    worker's digest, solver trees exported from the AX42 and hash-verified,
>    pinned SSH host key confirmed per pod, connection logging with
>    invalidation on any foreign peer, shred then Terminate, aggregates only
>    back, AX42 remains producer of record).

**The return path.** The owner was asked:

> Item 8 says "aggregates only back", as in the score-proof run. But a
> championship batch is an answer key: the pod's solved reference records
> (hidden case answers) have to come back to the AX42 so it can sign the
> batch, the same way CUSTODY-01's "records pulled back and merged on the
> AX42" works. Which do you accept for the daily championship pods?

and chose **"Records back to AX42"**, whose description read:

> The pod's solved reference records are pulled back to the AX42 over the
> pinned SSH, journaled, and merged into the sealed batch; nothing goes
> anywhere else. Then the pod is shredded and Terminated. Everything else is
> as you stated.

**Extends** OWNER-STARTUP-HOST-CUSTODY-03 (and through it -01 and -02). Its accepted risks are restated as accepted here:
- the provider's host access to a container;
- no VM boundary and no firewall of ours;
- an unverifiable shred on copy-on-write disk;
- deletion by RunPod's termination.

**Scope.** Battery testnet's daily championship batches (OWNER-BATTERY-CHAMPIONSHIP-01) only: one batch's solve shard per pod.

**Conditions:**
1. **The pod image.** Stock `ubuntu:24.04` at the truth worker's own base digest.
   - `/opt/carbon-worker` and `/opt/uv-python` are exported from the AX42's pinned truth image.
   - They are hash-verified on both sides (file tree; python, numpy and scipy versions).
   - The openssh-server package version is recorded in the run record, as for the score proof.
2. **SSH.** The pod's SSH host-key fingerprint is confirmed by the owner in the Carbon Validator session **for each pod**, before any export.
3. **Connection logging.**
   - `ss -tnp` is logged at solve start, midpoint and end.
   - Any established connection other than our SSH session invalidates the batch. The batch is withdrawn, treated as exposed and never served.
4. **What comes back.** The solved reference records are pulled back to the AX42 over the pinned SSH, journaled, and merged into the sealed batch. Nothing else leaves the pod, and nothing goes anywhere else.
5. **Teardown.** The files are shredded on the pod, then the pod is **Terminated** (never just stopped). No network volume.
6. **The AX42 remains producer of record.**
   - It draws the cases, holds `root.bin` and the journal, and signs the package.
   - None of these, and no validator material, ever go to a pod.

**Not permitted here:**
- bank startups;
- any other Challenge's batches (a new record);
- keeping a pod between batches;
- an agent-run transfer;
- serving anything from a pod;
- any mainnet use.

**Code** (at the VALIDATOR-32 build): `startup_shard.CUSTODY_RECORDS` gains this record. The per-startup root-owned hosts file names it and the pod's key.
