# F13-LOCAL-THREAD-BOUNDARY-01

Owner-directed solver-readiness execution resumed on 2026-10-15. Starting
revision: a8ebab8d480bf21fe482d9c5f4f65baf4d59aa54.

KEEP the pinned solver/mesher images, scientific bands, decks and observers.
REPAIR the f13 container launch: explicitly constrain BLAS/OpenMP threads so
the one-CPU mesher does not exhaust its existing 16-process limit on a host
with more cores. Keep network, memory, process and wall limits intact.

Evidence before repair: the pinned motor/Gmsh image fails importing gmsh
under the f13 16-process limit on a 20-logical-CPU host; stderr reports
OpenBLAS pthread_create failures. Adding OPENBLAS_NUM_THREADS=1 and
OMP_NUM_THREADS=1 allows the same 4 mm small-coaxial meshing operation to
complete. The initial attempt is infrastructure failure, not scientific
failure. No paid resource has been created.

Definition of done: implement the explicit thread environment, retain a
regression for the bounded container command, run the affected canonical
tests, and retain the local diagnostic outcome and its image identity.
The sparse 21-frequency diagnostic does not satisfy full B3 acceptance.

Primary historical map_ref: C19 (reference solvers). Hub source remains
frozen under OWNER-WORKFLOW-SPEED-01. No qualification or LIVE status changes.
The original RunPod campaign remains fail closed without its private billing
ledger. The owner's subsequent explicit resume-budget direction is recorded
in SOLVER-READINESS-RESUME-PHASE-01: a separate USD25 resume phase preserves
that old history and the USD15-or-higher shared balance floor. Local container
profiling is diagnostic only, not a complete acquisition-cost receipt; the
two standalone mesher/import troubleshooting commands were not metered.
