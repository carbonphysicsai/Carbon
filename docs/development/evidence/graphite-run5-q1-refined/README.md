# Graphite run-5 Q1, rerun with refined references (policy ev4-dev-refined-v1)

This is the same panel, rebuilds and analysis as #609, with REF-RESOLVE-01's settled references overlaid.

**Coverage** grows from 6 to **7 of 12** development scenarios (D-T34-S0.33 recovers). Five scenarios stay excluded on references that remain UNRESOLVED or failed.

**Conclusions are unchanged:**
- one-seed τ-b is −0.47 (ρ −0.54);
- all-seed τ is −0.08 (band [−0.87, 0.25]);
- top-1 by score is the bundled winner, `p-1d4aaff5d292`;
- top-1 by decision value is the baseline MLP.

Full coverage is not reachable under the conservative band. Whether a tighter band for refined solves is worth proposing is the science owner's decision (`../ev4-dev-refined-v1/settling.json` lists the 16 margins).
