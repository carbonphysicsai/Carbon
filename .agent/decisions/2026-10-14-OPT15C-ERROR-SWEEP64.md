# OPT-15c synthetic error-structure tranche: prospective run contract

Authority: existing owner-directed OPT-15c SCORE-LAB-CAMPAIGN-01 and
SCORE_LAB_EXPERIMENT_PLAN_01 sections 2C, 4 and 6. Root directed continued
authorized synthetic work while host gates wait. DEVELOPMENT only.
Starting main: a3a0b382b62a34c04f0750e89b52b514d668df2f.

Run the existing `physics-error-example.json` and six-axis
`campaign-axes-error-example.json` unchanged, with 64 deterministic LHS profiles,
diagnostic seed 20261014, all ten local Validator proxies (source sha256
157b1db5f091910f5602b15c9f5029f0171e6da7e8b6dbc5ffb5aa5c775bd235) and all seven
existing physics switches. Four interleaved 16-profile shards use one plan.
These count/seed/range values are toy experiment assumptions, not score values.
No component wrapper is added and no candidate is selected after seeing results.

The six axes vary only population member 0: heteroscedasticity, error region,
cross-design correlation, rare-tail rate/size and sigma scale. Other members
and the task remain fixed. This extends the one-proxy eight-profile smoke;
it is not full population realism calibration or a completed campaign.

Before evaluation, rerun the existing controls gate from committed historical
public RES-07/08 aggregates and `campaign-gate-toy.json`, with questions=6 and
cap=3 as in the existing control receipt. A failure stops the tranche.
The public aggregate back-test is distinct from prospective EV4 fitting.

Previous measured ten-proxy profile cost is 24.28 CPU-s: 64 profiles predict
1554 CPU-s (0.43 CPU-h). Each evaluation shard has an 800 CPU-s / 900 wall-s
hard cap and 1 GiB address-space cap; cumulative evaluation allowance is
3200 CPU-s, leaving headroom under the queue's one-CPU-hour ceiling for controls,
plan/atlas generation and export. No rental or solver is authorized.

Record actual commands, source/config/candidate/artifact identities, controls,
measured completion and resource timings separately from this prospective
contract. An incomplete shard cannot yield the complete atlas. Use canonical
execution from a native Linux clone, one thread per numerical library.
Report target/near/extrapolated tau, intervals, gate exclusions and descriptive
axis associations. LHS associations are not Sobol or causal indices. Bootstrap
bands within a toy profile do not establish independent real-world power.

All outputs remain in a new result subdirectory. Existing results, runtime code
and frozen PRs #1344/#1345 retain their bytes. No EV4 fitting/selection, D3
relabel, protected material, holdout read/reveal, AX42, chain, model training,
solver, provider, spend, LIVE, qualification or rule adoption is permitted.
Root/PR Head owns review and merge; owner/domain authorities retain science.
