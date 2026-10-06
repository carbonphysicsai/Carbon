# EV4 development references, refined (REF-RESOLVE-01 policy v1)

This is DEVELOPMENT evidence. The policy is in `.agent/tickets/REF-RESOLVE-01_refined_reference_policy.md` (Test Lead rulings (a) and (b), 2026-10-05).

**Scope.** 27 EV4 development reference cases blocked run 5's 6 excluded scenarios: 22 were UNRESOLVED (plating, within the band) and 5 were REFERENCE_SOLVER_FAILED. Each was solved once with `refined=True` in the pinned truth image (PyBaMM 26.8.0.0) on the operator host's CPU.

**Outcome** (`settling.json`, with the same contract band):
- **6 resolve.**
- **16 stay UNRESOLVED.** Their refined plating margins lie within ±1 band (0.00197 V), between −0.97 and +0.64 bands.
- **5 fail again.**
- Every refined plating margin moved *down*, by 0.0002 to 0.0011 V, relative to the standard solve.

**Use.** A study opts in with `carbon.battery.value.reference_policy` (`settled-references.jsonl` in its output). EV4's committed results and every earlier study are unchanged.
