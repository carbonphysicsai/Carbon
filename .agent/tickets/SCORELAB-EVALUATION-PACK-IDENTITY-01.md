# Private evaluation-pack identity

Root's current shared-pack integration assignment closes the selected-manifest
identity seam between trusted retention, ScoreLab evidence and cached comparisons.
This is development identity plumbing, not a score rule or reference change.

Use the existing private source receipt and key. A prospective v2 source and
sidecar carry `evaluation_pack_digest`, matched against the trusted receiver's
retained snapshot pin. A v1 source cannot satisfy a selected-pack evaluation.
Legacy no-pack source/sidecar bytes and key semantics remain unchanged. The pin
stays private; this work adds no public projection, loader or comparison rule.

Owned paths: `carbon/scoring/private_evaluation_evidence.py`,
`carbon/challenge_validator/bank_promotion.py`, and focused synthetic tests.
Platform owns the trusted task binding/retention caller; NewChallenge owns the
loader/source producer. Packets3 tests the actual join and historical cache.

Product runs the new synthetic tests and existing private-evidence/cache tests
in the canonical environment. Source authors perform static checks only.
Completion requires those checks and Lead's normal coherent integration.
Development Hub is frozen; this changes no scientific or production maturity.
