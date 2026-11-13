# OWNER-CONTAINMENT-ACCEPT-GPUYARD-MAINNET-01: containment and grading class accepted on the GPUYard validator for mainnet 116

Date: 2026-11-12 (owner's local morning, CST)
Status: ACCEPTED by the owner, typed directly in the Deploy-C session at 06:46 CST, after the Lead set out the trade-off in the Lead session.
Owner's words: "I accept containment and the EPYC7402P-VM grading class on the GPUYard validator for mainnet 116."

Scope: **mainnet 116**, on the GPUYard validator (class EPYC7402P-VM-01; see VALIDATOR-HOST-CLASS-EPYC7402P-VM-01, OWNER-GPUYARD-BACKUP-VALIDATOR-01 and OWNER-CONTAINMENT-ACCEPT-GPUYARD-TESTNET-01).

## What is accepted

- This record gives the owner's fresh acceptance that OWNER-GPUYARD-BACKUP-VALIDATOR-01 and OWNER-CONTAINMENT-ACCEPT-GPUYARD-TESTNET-01 require before mainnet use of this host.
- For mainnet 116 it replaces the dedicated-machine host named in OWNER-MAINNET-ONE-VALIDATOR-MACHINE-01. The rest of that record stands: one validator machine, graph inference and the speed gate on its CPU, rebuilds on its GPU.
- The owner accepts the same trade as for testnet. The host's virtual-machine layer could in principle read the sealed exam data in memory. The speed gate is timed on this class's CPU.

## Speed-ceiling basis

The Validator-2C ruling (a), aef9598a (SUMS fe8d5bf1), rules that the registered speed ceilings, which do not depend on the host class, carry over to mainnet 116 unchanged; this class's CPU is where the median of 20 single-design calls is timed. The 1.8 versions keep the same Challenge ids.

## Conditions

- The containment probes on this host must pass the existing pass rule (every part passes, nothing skipped) on the installed mainnet candidate before any counted grade.
- At the door switch, Deploy posts each 116 door's CPU inference image (S-1).
- As evidence only, Deploy posts one testnet 1.8 grade's speed result per Challenge on this class (S-2). If a default fails its own speed gate, that goes to the Lead and the owner before 116.
- This record sets no score, threshold, tolerance or economics. It records no host address and no server id; those are held in custody.
