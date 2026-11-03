# OWNER-TRAIN-DATA-ADEQUACY-CHECK-01: training-data adequacy is an exam quality check

Date: 2026-11-02 (CST), ~13:55
Status: DIRECTION from the owner, typed in the Lead session (local_87151681-c66e-4949-a26c-23c4641b5722).
Owner's words, in order: "Could part of the problem with operator performance be our train data set they're built with?"; "Yeah dig into this one deep for every exam"; "Good. Just add it to exam quality checks".

## Decided
- Every exam version carries a TRAIN DATA ADEQUACY CARD. Exam Quality writes it and the Validator receipts it, alongside the physics hardness card (OWNER-HARD-REAL-PHYSICS-DIRECTION-01). It covers:
  1. **Size:** the number of TRAIN cases against the input dimension and the physics complexity.
  2. **Richness:** what each TRAIN case publishes (scalars vs fields, time traces or intermediate quantities), and what the reference solver already computes but does not publish.
  3. **Regime coverage:** every mechanism or regime the OOD classes need appears in TRAIN, with counts (the G4 coverage table).
  4. **Learning-curve evidence (G6):** whether learners improve with more TRAIN data while fits plateau.
  5. **Usability:** whether the training interface lets a model use auxiliary or field supervision beyond the graded outputs.
- **Binding reading:** where a version's TRAIN starves learners (too small, or scalars only while the solver has fields), the card says so. The fix is weighed before freeze: publish already-computed fields at ~$0, add cases, or widen the interface.
  - Publishing fields of public TRAIN cases is allowed only after the Validator's leakage ruling; exam cases stay sealed.
  - Any new spend, and any change to what is published, comes to the owner as one choice with a figure.
- It applies to the 4 new versions (RB 2.0, BT 3.0, Motor 1.7, Cooling 1.8) before their S4 freeze, and to every later version.
