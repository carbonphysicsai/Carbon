# OPT-15c control gate, development only

`CONTROL_GATE.json` was recomputed from the committed RES-07 and RES-08
development aggregates plus an analytic finite-grid toy. The source hashes
are in that JSON. The historical EV5 verification common mask places the
always-abstain control **2nd of 100**, and the RES-08 nominal bilinear map
captures the offered-grid ceiling with three verifications. The toy control
places abstention 1st of 14 and captures the offered-grid optimum. The gate
therefore reports `CONTROL_PASS` for these stated inputs.

The experiment plan's older **1st of 75** P observation is a different cohort
and is not reconstructed by this aggregate replay. This gate is a known-flaw
and arithmetic control, not proof that every historical score or real buyer
decision was replayed. No score rule or threshold is selected from it.

The synthetic lever campaign may proceed. Public EV4 fitting, realism
calibration and tier-2 selection remain held for the D3 v2 reference labels;
the independent Test Engineer holdout remains unopened.
