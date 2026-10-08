## 2026-10-07 — OWNER-REHEARSAL-CPU-CLASS-01: battery rehearsal 3a runs on device class CPU, beside the producer

**Authority.** The owner, 2026-10-07: "approve A + CPU rehearsal record".
The Test Lead relayed it to the Carbon Validator session the same day.

"A" is the custody option the Carbon Validator laid out. Testnet's
validator holds the imported answer key **on the AX42, beside the producer**:
the same custody domain, so no hidden material on an agent-reachable host
and none on rented compute.

It supplements:
- OWNER-SHARED-ANSWER-KEY-01 ("a rebuild on any other class, or on CPU, is
  not a scored result");
- OWNER-REHEARSAL-AND-RELEASE-01;
- OWNER-TESTNET-V2-SWITCH-01;
- OWNER-TESTNET-WEIGHTS-01.

**The rehearsal:**
1. **3a runs on device class CPU.** Rebuilds run on the AX42's CPU, in the
   pinned released worker images.
2. **Labelled, development-only.** Its scores and weights are labelled
   device class CPU and are development-only. They are never evidence of GPU
   determinism, and never a scored result in OWNER-SHARED-ANSWER-KEY-01's
   sense. The hidden-score ranking already partitions by device class
   (#721), so CPU results never mix with GPU results.
3. **Pipeline evidence only.** It proves the pipeline end to end:
   - the producer draws, solves and publishes;
   - the distribution host serves permit holders;
   - the validator imports and verifies;
   - miners commit on chain and submit through the real door;
   - the validator scores;
   - weights are set on testnet 567.
4. **Where:**
   - the validator runs under its own OS account on the AX42 (`carbon-val`);
   - its door binds loopback only, so the producer host stays
     non-internet-facing, and rehearsal miners reach it by SSH local
     forward;
   - valV2 sets the weights;
   - only valV2's hotkey file is on the AX42, with its signer started by the
     owner;
   - coldkeys, registration and stake stay on the owner's PC;
   - UID 0 is not used and stays untouched.
5. **The PC's testnet deployments** (v1, EV5's frozen archive, and v2) stay
   only as a backed-up archive. They no longer serve testnet.

**Deferred:** a GPU-parity rehearsal on the pinned A40 class, until A40
hardware is available. That needs its own record.

**Not granted here:**
- qualification, LIVE, reward or production claims;
- any mainnet weight;
- any change to OWNER-SHARED-ANSWER-KEY-01's scored-result rule for
  mainnet.
