# RES-02 — registry-v9 attack audit: owner summary

**Research only; no scoring change or qualification.** Recommendation: keep
known-bad placement mandatory; pre-register a fixed-list/value-invariance
attack, a pessimism/abstention control and full shortlist budget checks.
Neither A/R nor one-sided P/ENV is sufficient evidence of useful decisions.
V3 should be tested on its disjoint LEG questions against independent VALUE
questions. Its exact public performance remains a gap.

The [pinned registry](https://github.com/carbonphysicsai/Carbon/blob/e99881523712d2a8969a003a7ffcdd99641f1d01/docs/development/evidence/battery-score-tuning/registry-v9.json)
contains the queue's ten entries; #1161's description names additions absent
from that head. This audit uses the file, not those uncommitted descriptions.
Only A and R can be measured exactly from the supplied public EV aggregates;
P, ENV, joint G-FEAS, Q3 q and real top-three orders are missing. Synthetic
counterexamples cover all ten definitions without inventing those fields.

**Observed finite-panel results** ([measurements](results.json)): each control
is ranked against the **99** eligible real members plus that control; other
controls/attacks are excluded from its rank pool. Counts are fixed source
measurements, not independent trials or forecast confidence intervals.

| Public verification control | A rank | R rank | Unsafe single picks / offered questions |
| --- | --- | --- | --- |
| Boundary optimist, EV4 and EV5 | 1 | 74 | 8 / 12 |
| Localized sign error, EV4 and EV5 | 1 | 1 | 4 / 12 |

R demotes the broad boundary optimist but misses the localized failure. In
EV5, the sign control outranks **89** real members with better bounded
verified-service value. R also leaves steps-b at **5–6**, despite an unsafe
pick and **43** value inversions. These are observations, not causal attack
effect estimates or results from the owner's sealed confirmation.

**Structural tests, explicitly ASSUMPTION toys:** P scores perfectly and
ENV sees zero optimism when predictions are excessively pessimistic and no
design is returned. Concentrating five sign flips among 100 failed toy
scoring cases passes the registered strict 5% allowance, yet all three
proposed designs can fail verification. ARP/ENV-ARP score can rise in this
toy while service value falls; V3 falls. Separately, improving A with the
exact list and verifier results frozen raises ARP-V3 and A-Q but leaves pure
V3 unchanged. No physical trajectory or trained attack is claimed.

Exact duplicates, overlength and out-of-family lists are already refused
by the public verifier; attempted failures consume its budget. Preserve
those guards in the proof. Current quiz replay does not charge inference
overhead, so actual delivery latency/cost remains an evidence gap.

Copying prevalence is unmeasured. An assumed row-cloning stress changes
pooled rank agreement without changing any original member's value. Actual
artifact uniqueness is unmeasured. Freeze
the comparison pool, show recipe/artifact views and keep attribution/IP
separate from scientific score.

[Attack matrix/protocol](ATTACKS.md), [sources](SOURCES.md),
[Test Engineer handoff](handoff.json) and [working contract](WORKING_CONTRACT.md)
retain missing measurements and adverse results. Detector tolerances,
equivalence tests and adoption remain **HUMAN_INPUT**. No hidden/sealed
material, AX42, solver, training, spend, network or runtime change.
