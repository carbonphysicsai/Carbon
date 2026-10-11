## 2026-10-10 — EVIDENCE-PACK-PROVENANCE-01: a committed evidence pack is checked for provenance, not freshness

**Authority.** The Test Lead's ruling, 2026-10-10 (relayed), unblocking #1009, #1010
and #1017.

**Reason.** Invariant 10: historical evidence is versioned. A pack records what its
tools produced on one day. A later edit to those tools does not make that fact false,
so a CI assertion that the committed pack equals what today's tools generate fails by
construction on any later PR that touches a tool or a recorded input. That failure
carries no information about the pack.

**Decision.**
1. A pack's tests check provenance and internal consistency only:
   - each output's recorded digest matches the committed bytes;
   - each recorded input digest is well formed and, where git history allows, matches
     the file **at the pack's `authority_main`** (never at HEAD); an input inside the
     pack itself is checked against its committed bytes;
   - the run record is complete.
2. Freshness is a **reported status**, not a CI failure: `STALE_TOOLS`, listing the
   changed paths, from `python -m carbon.challenge_pipeline.onboarding pack --run
   <run record>`. Only a provenance problem exits non-zero.
3. A fresh run is a new, versioned pack. A pack's outputs and `authority_main` are not
   regenerated in place.
4. `carbon/challenge_pipeline/onboarding/provenance.py` is the shared check; any pack
   with a HEAD-freshness assertion uses it.

**Applied to.** #1026's `tests/cpu/test_open_benchmark_onboarding.py` (the only pack on
main with such an assertion). Its outputs and `authority_main` are unchanged. No
assertion was deleted without a provenance replacement; tests prove the check still
fails on a tampered output, a missing output, a bad digest, an input that was never the
tool at `authority_main`, a changed pack input and an incomplete run record.

**Not decided here.** Nothing about the science, the stage acceptance or any readiness
status of the pack.
