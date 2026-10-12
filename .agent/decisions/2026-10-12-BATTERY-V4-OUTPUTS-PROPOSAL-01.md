## 2026-10-12 — BATTERY-V4-OUTPUTS-PROPOSAL-01-D1: prospective export and explicit semantics

Ticket PLT-02; working engineering decision, 2026-10-12.

New output modules live beside the pinned training implementation. The
existing reference builds exactly one unchanged DFN simulation; the new
extractor samples its already-stored current, total heat and discharge
capacity. No solver threshold, parameter or numerical model is changed.

Current is positive discharge. The proposed SOC observable is explicitly
soc0 minus change in discharged Ah divided by the solver's nominal capacity.
Its proposed charge identity is therefore minus integral(I dt)/(3600 Q).
This corrects the draft shorthand's missing sign/unit convention without
adopting a physical gate. Nominal coulomb counting is not an independently
qualified or ageing-aware electrochemical SOC measurement.

Signed total heat is not irreversible heat. B14 cannot be claimed checkable
without a separate decomposition; B13 also needs its thermal parameter contract.
Those decisions remain human-owned. A richer solver export can supersede
this proposal prospectively in outputs_v4.py/reference_v4.py and its tests.

The dedicated solve-v4 route requires versioned jobs with the output-contract
digest and a separate append-only records file bound by a sidecar. A v3 file
without that binding is refused before any append; v3 also refuses the v4
binding. Existing bytes and recipe digests remain unchanged. Reusing the
existing filename/default route or changing recipes/training was rejected
because it would reinterpret history. The change is reversible with no
downstream consumers and no Challenge or daemon registration.

Locations: carbon/battery/outputs_v4.py, reference_v4.py and truth_env.py;
tests/cpu/test_battery_outputs_v4.py; the ticket and prospective output-contract
documentation. Carbon Validator reviews the proposal PR. Required human inputs:
SOC interpretation/adoption, thermal/decomposition contract, law tolerances
and v4 Challenge adoption. PLT-01 remains independent and B1–B10 only.
