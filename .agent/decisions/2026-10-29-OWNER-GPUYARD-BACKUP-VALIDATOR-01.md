# OWNER-GPUYARD-BACKUP-VALIDATOR-01: the testnet validator moves to the GPUYard 4090 while HOSTKEY repairs [server id held in custody]

- **Received by:**
  - the Test Lead session (local_0f493eac-c584-4099-9783-916a453a7967), typed by the owner directly in that session, 2026-10-29;
  - and, to the Lead, "B lets press with the back up".
- **Owner's words (Test Lead session):** "Yes: switch the testnet validator to the GPUYard 4090 ([address and host key held in custody]), redacted for the public record, as the backup while HOSTKEY repairs [server id held in custody]. Run the full kit: hardening, driver/Docker, a 60-minute load test, then the M9' install, measurements, containment probes, its own class registration and calibration. For testnet I accept (1) the switch, (2) that GPUYard's virtual-machine layer could in principle read the sealed exam data in memory, and (3) smaller miner limits from its 8 cores. Mainnet still needs a dedicated machine and my fresh acceptance."
- **Context:**
  - HOSTKEY server [id held in custody]'s RTX 4090 fell off the PCIe bus twice, Xid 79: at 21:32:37Z at idle, and at 23:39:13Z under light load (55°C, 64 W).
  - It's a hardware fault and a provider ticket is open. Maintenance is offered for 30 Oct.
- **Decided (testnet):**
  - The validator runs on the GPUYard VM: oVirt, 8 vCPU of an EPYC 7402P (Zen 2, no AVX-512), 62 GB, 4090 passthrough.
  - It gets its own host-class registration (draft: GPUYARD_SPARE_CLASS_PREP_20261029.md) and its own registered calibration on the gated M9' tree.
  - The miner limits are measured from its 8 cores.
- **Security acceptance (testnet only, the owner's words above):** the hypervisor-custody exposure of sealed exam data.
- **Bounds:**
  - Mainnet needs a dedicated machine and the owner's fresh acceptance.
  - The move back to the repaired HOSTKEY box goes through its own calibration, with crowns and weights paused across the move.
  - The VM-only checks in the class prep still apply: pinned vCPU, no ballooning, no live migration. Where the provider can't confirm them in writing, that's recorded.
  - The open dispute with GPUYard over the order (dedicated vs VM) is unaffected.
