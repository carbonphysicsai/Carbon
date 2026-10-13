## 2026-10-13 — OWNER-PLATING-REFERENCE-01: adopt option A as the next battery reference version (public near-onset only), and annotate EV4, EV5 and the score proofs with the known optimism

**Authority.** The owner, 2026-10-13: "Yes to both", approving D3 and D4 of the
Carbon Validator's `PLATING_REFERENCE_DECISION_2026-10-13.md` (sha 10740f47) as
the Test Lead put them to him. The PR Head then put both to him directly and he
confirmed them in that session before this record was merged — D3 adopts a
reference version and D4 annotates the frozen EV5, so neither is recorded on a
relay alone.

**D3 — the next battery reference version (adopted).** Option A: re-solve the
near-onset cases at the fine mesh, with the window and band set from D2's panel.

- **Scope: the public near-onset set only**, inside the standing weekly test
  grant (`OWNER-TEST-GRANT-01`).
  - **The figure the owner approved was "about USD 3".** The counted set is
    **669 public cases** (611 PDD + 58 EV4) at about 45 CPU-hours: worst case
    **USD 4.3, cap USD 6** (Test Lead, 2026-10-13). Both figures are recorded
    because the second is not the one he was shown. It needs no new approval --
    it is inside the standing grant and below its USD 50 per-run cap -- but the
    record should not restate his approved figure as double it.
  - The count doubled because the window widened from [0, 2.82) to
    (-1.97, +3.5) mV; the extra cases are the in-band UNRESOLVED ones that have
    no usable label today.
  - **Launch on the single 32-vCPU pod only.** The four-pod fallback is USD 10
    for identical compute and is not to be taken; if capacity does not appear,
    stop and return to the Test Lead. Waiting is free and nothing about D3 is
    due tonight.
- **The sealed bank is excluded** and needs the owner's own figure before any
  sealed re-solve.

**D4 — annotation, not re-scoring (adopted).** EV4, EV5 and the score proofs are
annotated with the known optimism, up to about **2.6 mV** (PLATING-CONVERGENCE-01).

- **No re-scoring. Recorded results keep their meaning.** This is an annotation
  of existing evidence, not a reinterpretation of it, and invariant 10 holds:
  no historical result is rescored under a newer contract.
- **How to annotate, and this is binding on the implementation.** Add an
  **additive note file beside each evidence set**, citing PLATING-CONVERGENCE-01
  (#1280). **Never edit the frozen EV5 bytes or their pinned digests**, and the
  same for EV4 and the score proofs. "Annotate EV5" without this mechanism is an
  instruction someone could satisfy by editing EV5, which would break the freeze
  and every digest pinned to it -- the exact outcome D4 exists to avoid.

**What is NOT the owner's, and must not be attributed to him.**

- **D1** is the **Test Lead's** fail-closed DEVELOPMENT interim: safe only above
  about 2.6 mV plus a cushion, otherwise UNRESOLVED. Adoption into frozen rules
  remains the owner's and has not happened.
- **D2** the Test Lead started under the standing test grant.

**Consequences recorded with the decision.**

- `OWNER-SCORE-PROOF-CONFIRM-02-GRANT`'s **USD 37 stays held until D3 lands**.
- **Track A's battery bank waits on D3.**

**Maturity.** DEVELOPMENT and testnet. Adopting a reference version is a
scientific decision the owner has now taken for this scope; it is not a
qualification, a security acceptance, or any authority over the sealed bank.
