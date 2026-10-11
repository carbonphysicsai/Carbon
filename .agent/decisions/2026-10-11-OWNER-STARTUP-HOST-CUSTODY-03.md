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

**Not permitted here:**
- anything the earlier records don't permit;
- any bank, validator or mainnet material on a RunPod pod;
- a stopped or kept pod;
- agent access to the pod.
