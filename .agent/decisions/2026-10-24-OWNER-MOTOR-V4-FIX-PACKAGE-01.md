# OWNER-MOTOR-V4-FIX-PACKAGE-01: approve Data Collection's Motor v4 fix package (no loosening), then retry

Date: 2026-10-24 (UTC)
Status: APPROVED by the owner, directly in the Lead session (local_b7032708-92d1-4a7c-a1d3-9ad008ba9cae): "yes, approve the Motor fix package".
Context: the Motor v4 sealed family stopped after its third unusable batch. The spot check (finer mesh) disagreed with the primary solve on mean torque beyond the recorded tolerance (0.0052 N·m) on one case, an accuracy problem in the simulation. Earlier batches lacked a straddle or a feasible-everywhere design. Data Collection's stop report proposed a three-option package: no gate or tolerance loosened, about $0 in rentals (custody-host time only, about 5 host-hours of new solves plus dev time), then a retry.

## Decided

- Data Collection's three-option Motor fix package is approved as proposed. It is a no-loosening package: U, the QA bands, the spot-check tolerance and the straddle and decision rules stay unchanged.
- Data Collection implements it. The Validator receipts it and signs a new Motor readiness gate before any run. Test Lead runs the retry on a custody host.
- If the retry also fails QA, it stops, and the Motor exam design comes back to the owner with options.
