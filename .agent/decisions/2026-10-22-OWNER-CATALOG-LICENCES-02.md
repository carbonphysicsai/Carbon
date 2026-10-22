# OWNER-CATALOG-LICENCES-02: BSD-3 cleared; unlicensed code may ship (owner accepts the risk)

Date: 2026-10-22
Status: APPROVED by the owner.
- Said to Graphite Test ("BSD-3 is cleared, go ahead").
- Confirmed directly in the Carbon Validator's session, where the owner chose "BSD-3 yes; ship unlicensed too". The Validator named each licence and the risk in the question.

Amends: OWNER-CATALOG-VENDORED-LICENCES-01 (2026-10-20).

## Decided

1. **BSD-3-Clause is cleared** for the backbone catalog. The named component is **torch-harmonics 0.7.4** (BSD-3-Clause, NVIDIA), shipped inside the SFNO and LocalNO backbones. Its licence text and copyright notice ship with it, as BSD-3 requires.
2. **Code with no licence at all may ship** in Carbon's catalog. The example named was WNO, whose authors grant no rights.
   - **The owner accepts the legal risk:** with no licence, Carbon has no granted right to redistribute such code.
   - Each unlicensed component is listed by name and source in the catalog's licence manifest, as "no licence: shipped under owner risk acceptance OWNER-CATALOG-LICENCES-02".
3. **Unchanged from -01:**
   - permissive licences stay OK;
   - **GPL code (KNO) is still not published.** This decision doesn't address copyleft, and the owner was not asked about it.
   - Nothing reaching `68bfee956` is ever pushed.
