## OWNER-VALV3-GPU-VALIDATOR-01: a second testnet validator, valV3, scoring on a rented datacenter A40

**Authority.** The owner, 2026-10-08:
- relayed by the Test Lead: "approve valV3 on A40". valV3 is a second testnet
  validator scoring as `gpu:NVIDIA A40`, beside valV2 (CPU). It runs in test
  windows on a rented A40 in the owner's account, and it is stage 7's second
  validator;
- **confirmed directly in the Carbon Validator session** as a custody
  (security) acceptance (AGENTS.md §13), asked which hosts may hold valV3's
  material. The owner chose **"Datacenter-only"**, whose description read:

  > Accept, but only on a verified-datacenter A40: Vast.ai Secure Cloud
  > (datacenter) offers, or RunPod SECURE as the acceptance used. Community
  > hosts (an individual with root on the box) are refused. Mitigations: leak
  > detection, short windows, VALIDATOR-24 withdrawal, destroy after each
  > window.

### Custody (what may be on the host)

- **Validator-only material:**
  - the current-batch answer keys valV3 imports with its own permit from
    `answers.carbonphysics.ai`;
  - its own deployment state, private root, journal and backups;
  - valV3's **hotkey** file (the coldkey never leaves the owner's PC).
- **Never:** producer roots, seeds, the producer's signing key, tuning sets,
  study sets, the bank, or any other validator's state.

### The host

- **One rented NVIDIA A40 in a verified datacenter only:** Vast.ai Secure
  Cloud (datacenter) or RunPod SECURE.
  - Community hosts are refused.
  - It must be a VM-type instance, because the carrier runs rebuilds in
    Docker.
  - The rental is in the owner's account and is run by the owner. No agent
    has access.
- **Hardening:** the AX42's custody (HIDDEN_HOST_SETUP): key-only SSH, a
  firewall allowing SSH only, fail2ban, and the `carbon-val` account with
  owner-only state.
- **Each window ends with the rental destroyed:** state backed up encrypted
  (Ops 1), copies shredded, then the instance deleted, not stopped. The next
  window is a fresh rental.

### Accepted risk and mitigations

- **Accepted:** a third-party datacenter host holds current-batch answer keys
  during a window. This is the trust model of any mainnet validator.
- **Mitigations:**
  - leak detection (`LEAK_INCIDENT_RUNBOOK.md`);
  - short windows;
  - VALIDATOR-24 withdrawal and VOID;
  - the rental destroyed after each window.

### Gates: valV3 scores nothing before all of these

1. **The A40 acceptance passes** (OWNER-A40-ACCEPTANCE-GRANT-01).
   - GPU determinism is the precondition for trusting GPU scores.
   - The v2 GPU rows stay UNVERIFIED until then
     (OWNER-WORKER-IMAGES-V2-01).
2. **VALIDATOR-27 is merged and released.** The battery validator's GPU
   scoring path: at the time of this record, a battery validator cannot score
   on a GPU.
3. **valV3's permit is live,** its standing authorization is written, and the
   owner's grant for the rental exists.

### Not decided here

- the grant (an hourly cap and a total; proposed separately);
- mainnet hosting;
- any other host type, provider or community host;
- any wider custody.

A change needs a new owner record.
