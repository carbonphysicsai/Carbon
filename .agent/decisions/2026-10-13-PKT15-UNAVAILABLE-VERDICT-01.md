## 2026-10-13 - PKT15-UNAVAILABLE-VERDICT-01: distinguish unavailable oracle evidence from genuine NA

Amends PKT15-BOUNDED-ORACLES-01 for PKT-15. The verifier currently translates
ordinary NOT_RUN into NOT_APPLICABLE. That would give a wrong interpretation
to missing runtime evidence and unresolved D4 inputs in this ticket.

Add private reading NO_ORACLE_EVIDENCE to the adapter contract and map it to
UNDETERMINED with a distinct reason. All six L4 unavailable families use
that reading; no specimen is fabricated. The distinct reason must not be
eligible for agreed-admissible closure. Preserve existing INCONCLUSIVE,
NO_REBUILT_CONSTRUCTION and genuine out-of-scope mappings.

Add only adapter.py and verify.py to the working manifest, plus this record;
the fresh overlap check found no owning open PR. Integration controls must
exercise the actual verifier and retain the old branches. Reversal removes
the new reading/routing and its L4 uses. No schema status enum changes,
scientific decision, hidden data access or historical rescore is authorized.
