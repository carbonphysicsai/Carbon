# PKT18-MODEL-PROBES-01

Ticket: PKT-18-MODEL-ROBUSTNESS-ATTACK-FAMILY-01.
Working engineering decision: separate model-boundary probes from construction
adapters, with a trusted host callback and structurally fixture-only demo.

Problem: construction families cannot evidence robustness of a trained operator.
Shared campaign adapters are currently owned by Packets2 #1317. Importing a miner
model directly would also bypass the existing hostile-execution security domain.

Chosen implementation: carbon/agent_campaign/attack/model_robustness.py and
model_robustness_demo.py; new tests and MODEL_ROBUSTNESS.md. Reuse engine hashing
and failure vocabulary. Predict/refuse/abstain statuses are explicit. Missing
reference or policy is NOT_RUN, never NOT_APPLICABLE or HELD. A declared absence
of the relevant input capability is NOT_APPLICABLE and contributes zero coverage.

Rejected: new unsafe in-process model loader; copying submission schema checks
and claiming model robustness; folding conservation into a score; adopting
paper perturbation budgets as Carbon physical limits; editing #1317's files.

Reversible: remove the standalone modules/registrations when the host route is
superseded. No historical score, interface, registry or result is rewritten.
Notify Test Lead; Validator owns thresholds and campaign integration; Launchpad
owns miner projection. Current output is internal DEVELOPMENT only.

Human inputs: scientific policy and real-host acceptance remain unavailable.
Content pins bind supplied data, not authenticated host/model provenance.
