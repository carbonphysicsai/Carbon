# OWNER-D-IS-OPTIMIZATION-01: design value is tested by optimizing with the model's own outputs

- **Received by:** the Lead session (local_b7032708-92d1-4a7c-a1d3-9ad008ba9cae), directly from the owner in chat, 2026-10-24.
- **Owner's words:** "I love this. I think it should be the true test of design value is the model doing it's best to optimize a design using its own outputs. Is what we are currently doing even worth it compared to a good version of that?"
- **Direction:** the core of design value (D) becomes an optimization test. For each hidden design target (requirements plus an objective), Carbon's FIXED optimizer, run inside the validator sandbox, uses the submitted model's predictions to search for the best design under a fixed query budget. Carbon's solver then verifies the final design. D scores whether it truly meets every requirement and how close it gets to the best known design (a reference optimum Carbon precomputes per exam version with the solver). Targets include the "remotely similar" variants (OWNER-GEN-SCOPE-AND-HARD-D-01).
- **Today's pick/ranking/regret checks:** they become secondary or diagnostic, kept only where they add cheap signal. The Validator recommends the split.
- **Authority boundary:** the optimizer, targets and verification are Carbon's. The miner's model is only queried, so the grade stays Carbon's (constitution 7.9).
- **Bounds:** the owner sets the values and the target counts from the curves; changes ship as new exam versions; the Validator prices it in solver cost per exam version and per submission.
