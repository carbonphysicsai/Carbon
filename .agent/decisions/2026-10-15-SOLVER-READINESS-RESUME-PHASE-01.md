# SOLVER-READINESS-RESUME-PHASE-01

The owner resumed execution on 2026-10-15: "Why is execution stopped?
Execute", followed by "You have my approval to use runpod budget" and the
new-operator setup specifying USD25 per phase and a USD15 balance floor.

This authorizes one resume phase, `resume-2026-10-15`, capped at USD25,
retaining the USD15 floor, CPU-only public workloads and at most four live
pods. It does not authorize the approximately USD95 bulk campaign, automatic
budget renewal, sealed material, qualification, LIVE or rewards.

The new operator has the account key but not the original operator's private
reference-solvers billing ledger. Keep both original ledgers and their
interpretation unchanged. Add an explicit operator-phase namespace for new
public/private accounting and active-pod state. Every existing stock, live-pod,
balance, full-deadline reservation, cleanup and termination guard still runs.
The original unphased campaign continues refusing incomplete billing history.
An operator-phase identifier grants no spend by itself.

The setup was exercised on the operator's Ubuntu environment, which has no
system pip. Use the pinned uv installer in that case, preserve other campaign
entries and any higher existing balance floor, and explicitly chmod existing
key/config files to 0600. Read-only ship validation inventories and copies the
same committed revision; --write is a proposal, not proof of a committed
payload. Its evidence covers named top-level imports, not lazy imports or
runtime inputs. f17's periodic-control JSON is explicitly shipped because its
path is embedded in a shell string and is not found by exact-path discovery.

KEEP the existing accounting implementation. WRAP its paths with the new
phase namespace. REPAIR setup to preserve other campaign configuration and
resume an already-started phase only through a successful status check.
The alternative of fabricating original rates or resetting the historical
ledger was rejected. Reversal: remove the optional namespace and restore the
original operator's complete private ledger; existing phase evidence stays
historical evidence and is never folded into the old campaign by inference.

The existing f02 verification and f08/f17 verification/pilot plans are the
first dispatch candidates after clean shipping checks. f13 retains its
scientific findings and must satisfy its registered bands before bank work;
f06 receives no 3D spend while the slab control fails.
