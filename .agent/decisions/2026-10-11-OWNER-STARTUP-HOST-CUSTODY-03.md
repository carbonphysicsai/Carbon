## 2026-10-11 — OWNER-STARTUP-HOST-CUSTODY-03: a RunPod Secure Cloud CPU pod may hold the score proof's solve shard

**Authority.** The owner, 2026-10-11.
- **Relayed by the Test Lead:** the owner chose RunPod's largest Secure
  Cloud CPU pod for today's score proof (sealed tuning questions, testnet
  only) after Hetzner refused the CCX63.
- **Confirmed directly in the Carbon Validator session, as a custody
  (security) acceptance.** Asked:
  > Do you accept this custody for today's score proof on a RunPod Secure
  > Cloud CPU pod? Sealed tuning questions are drawn on the AX42; only the
  > solve shard goes to the pod. The pod is a container on RunPod's host
  > (RunPod's host operators can reach its disk and memory; there is no VM
  > boundary or our own firewall). No network volume; SSH over exposed TCP
  > with the pod's host-key fingerprint confirmed in this session before any
  > export; records pulled back and merged on the AX42; files shredded on
  > the pod, then the pod TERMINATED (not stopped). A shred on the
  > container's copy-on-write disk cannot be verified; deletion relies on
  > RunPod terminating the pod.

  the owner chose **"Accept as described"**, whose description read:
  > Record OWNER-STARTUP-HOST-CUSTODY-03: RunPod Secure Cloud CPU pods may
  > hold one SCORE-PROOF-01 shard under this procedure, with the
  > provider-host access and unverifiable shred stated. Testnet tuning
  > questions only; no bank or validator material.

**Extends** OWNER-STARTUP-HOST-CUSTODY-01 and -02. The host may be a RunPod
Secure Cloud CPU pod, but only for SCORE-PROOF-01's sealed testnet tuning
questions. Bank startups and validator material stay on Hetzner startup
hosts or the AX42.

**Accepted as stated:**
- the provider's host access to a container;
- no VM boundary and no firewall of ours;
- no cloud-init;
- an unverifiable shred on the container's copy-on-write disk;
- deletion by RunPod's termination.

**The procedure:** `docs/development/graphite/STARTUP_HOST_RUNBOOK.md`, with
the differences in the shared operator block `RUNPOD_CUSTODY_BLOCK.md`:
- no network volume;
- SSH over exposed TCP with the pod's host-key fingerprint confirmed in the
  Carbon Validator session before any export;
- a root-owned custody file naming this record;
- only the shard leaves the AX42;
- journaled, host-key-pinned transfers;
- an all-or-nothing merge on the AX42;
- shred, then **terminate** (never stop);
- the exit check.

**The solve runs without network isolation (accepted the same day,
directly in the Carbon Validator session).** A pod cannot run Docker, so
the shard is solved natively inside the pod, which is launched from the
truth image by its pinned digest. On a Hetzner host or the AX42, the solver
runs in a container with `--network none`; on the pod it holds the sealed
questions while the pod has network access, which SSH needs. Asked:
> On the RunPod pod, Docker isn't available, so the score proof's shard
> would be solved natively inside the pod (launched from the truth image by
> digest) instead of in a container with `--network none`. The solver would
> hold the sealed questions while the pod has network access (it needs SSH).
> Accept that deviation for today's score proof?

the owner chose **"Accept, pinned image only"**, whose description read:
> Solve natively in the pod launched from the truth image by its pinned
> digest, nothing else installed beyond the r7 code. Recorded as an
> amendment to CUSTODY-03: no network isolation during the solve; the image
> pin and termination are the controls.

So the pod runs the truth image by its pinned digest with nothing installed
beyond the r7 code. The image pin and the pod's termination are the
controls.

**SSH transport on the pod (the owner's own wording, same day, directly in
the Carbon Validator session).** The truth image has no `sshd` or `rsync`,
so a pod from it cannot receive the shard over the host-key-pinned SSH the
procedure relies on. Asked to accept installing `openssh-server` and `rsync`
from the pod's distribution for transport only, the owner answered:
> Allow installing openssh-server from Ubuntu's signed apt repository at pod
> start for the RunPod score-proof run only (SSH transport, not scoring);
> record the package version in the run record.

Therefore:
- **`openssh-server` only**, from Ubuntu's signed apt repository, at pod
  start. Its version (`dpkg-query -W openssh-server`) goes into the run
  record.
- **No `rsync`.** Transfers use SSH alone: `scp` over the SFTP server
  `openssh-server` ships, or `tar` through `ssh`, still pinned by the host
  key.
- **Not an Ubuntu image** (no signed Ubuntu repository): stop.

**Not permitted here:**
- anything the earlier records don't permit;
- any bank, validator or mainnet material on a RunPod pod;
- a stopped or kept pod;
- agent access to the pod.
