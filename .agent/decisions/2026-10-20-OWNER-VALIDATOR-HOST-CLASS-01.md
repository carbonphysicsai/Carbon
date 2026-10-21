# OWNER-VALIDATOR-HOST-CLASS-01: every validator runs one host class

Date: 2026-10-20
Status: APPROVED by the owner. Confirmed in the Test Lead's session and relayed to the Carbon Validator, who records it.
Implementation: **not yet implemented.** There's no machine check in the validator install yet.

## Owner, verbatim

> all validators will be running the same hardware.

## Decided

- **One registered validator host class** is a validator requirement for the testnet and mainnet alike.
- **The class** is `(lscpu model name, the ISA flags among avx2/fma/avx512f/avx512_bf16/amx_*, vCPU count, minimum memory)`, measured once on the calibration host. It's registered as `validator-host-class.json`, which the Validator reviews.
- **The validator install's machine check refuses any other class,** with a typed code, before anything is installed or graded.

## What it settles

- **Rebuild noise and leg minimums are measured on, and valid for, that one class** (KOTH-TAKEOVER-RULE-01 §2a). With no other class there's no cross-class comparison.
- **Wall-time headroom stops varying between validators:** every validator runs the same speed class (OWNER-REBUILD-TIME-LIMIT-01).

## Not decided here

The class's actual values. They're measured from the calibration host, not chosen.

## The registered DEVELOPMENT class (measured by the Test Lead, 2026-10-20)

- **Source:** measured on the calibration VM, carbon-motorcal3-step1-20261020 (a Targon cpu-small-amd host).
- **Processor:** `AMD EPYC-v4 Processor`, with avx2 and fma; no avx512f, avx512_bf16 or amx.
- **vCPU:** 4.
- **Memory:** at least 50 GiB, the measured MemTotal of 52,858,868 KiB rounded down to whole GiB.
- **Scope:** testnet and rehearsal only. **The mainnet class comes from the owner's choice of validator hardware before launch.** That's a new registration, with re-measured rebuild noise and leg minimums.
- **Consequence for cadence:** R in `exam_cadence.json` (270 CPU-h a day) assumed a 16-vCPU host. On this 4-vCPU class the measured capacity is about a quarter of that, so R must be re-registered from the class. That's a measured value, not a choice.
- **What a miner experiences:** on this class, the daily graded-submission allowance per Challenge (OWNER-CADENCE-AND-ROTATION-02) is about 7 at 2 active miners, 2 at 5 miners, and 1 (the floor) at 25 or more. That replaces the 11 at 5 miners and 2 at 25 the 16-vCPU assumption gave.

## Mainnet hardware (owner, 2026-10-20, directly in the Carbon Validator's session)

> They will run GPUs so we limit no rebuild options. Likely 4090s

- **Mainnet validators run GPUs: the RTX 4090.** Owner, verbatim, later the same day: "RTX 4090 confirmed for now." It's revisable ("for now"); a change of card is a new class registration with re-measurement.
- **The mainnet host class** adds the GPU: model, VRAM, driver and CUDA version, and compute capability, alongside the CPU fields. It's measured once on the chosen hardware and registered the same way. The DEVELOPMENT 4-vCPU class above stays for testnet and rehearsal until then.
- **Required before the GPU class is registered (Validator):**
  - **A rebuild on one GPU of the class is bit-identical when repeated.** Deterministic GPU kernels are enforced in the judge: XLA deterministic ops, torch deterministic algorithms, and a fixed cuBLAS workspace. If a recipe can't rebuild deterministically on that GPU, that's a typed refusal, not a silent pass.
  - **JAX and PyTorch match on that GPU** (backend parity).
  - **Everything is re-measured on the GPU class:** the paired-repeat floors, rebuild noise, leg minimums, rebuild wall time, and the cadence capacity R. That's the mainnet recalibration.

## Revision: the mainnet validator machine is TBD (owner, 2026-10-20, directly in the Carbon Validator's session)

> Just go TBD on the validator machine it's not a needed decision until launch time.

- **The mainnet validator hardware is TBD until launch.** The earlier "GPUs, RTX 4090 confirmed for now" is a working assumption only, not a registered requirement.
- **Nothing is built for a GPU class yet:** no GPU fields in the install check, and no GPU determinism probe as a gate. These wait for the launch-time hardware decision.
- **The 4-vCPU DEVELOPMENT class stays the only registered class,** for testnet and rehearsal.
- **The one-host-class rule itself stands.**

## Why the ISA match is an exact set (Validator, 2026-10-21, from measurement)

- **The evidence:** the rebuilt KRR baseline legs reproduce the recorded values exactly on Intel (Hetzner cx43) and on AMD EPYC-Rome (cx43 hel1). They differ only on AMD EPYC-Genoa (cpx42): Cooling A differs by about 2.4e-10 and Motor A by about 9e-14.
  - Genoa adds `avx512f`, so the maths library takes a different kernel path.
  - The source is the Test Lead's gate results of 2026-10-20 and 2026-10-21, at bases 2a0f504a6, 283ee48da and 264a51220.
- **Why that makes the rule exact:** a floor rule ("at least avx2+fma") would admit Genoa and its drifting legs. That's why the install check compares the ISA flags as an exact set, and why a host with extra instructions counts as another class.
- **For any future class (mainnet included):** leg minimums and rebuild noise are re-measured on that class's own CPU. They're never carried over from another class.
