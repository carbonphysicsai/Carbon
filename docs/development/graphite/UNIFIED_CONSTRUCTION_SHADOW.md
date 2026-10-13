# Unified construction Phase 1 (PLT-16)

This is an additive DEVELOPMENT library and operator shadow hook. The public
intake, commitments accepted by the daemon, Launchpad wire format, ladder
compiler and evaluation policy still use their existing contracts. PLT-16b
owns intake wiring after the intake-security prerequisite merges. Phase 2 owns
registered combinations. No external opening or deployment is performed here.

`carbon.construction.unified.classify(strategy, contract)` is pure and can run
before signing. It strictly parses the existing TrainingStrategy schema, checks
registered field types, ranges and applicability, selects arms by content, and
returns `change_set`, informational `label`, required `checks`, pinned `binding`,
`refusal` and a plain reason. `derive` is its observational core; it grants no
admission. The generic library accepts other Challenge contracts; the shipped
battery factory assembles one from the base registry and pinned current variants.
That factory reads public policy/count manifests, never data samples.

An absent field is its Level 0 default. Explicit registered bool/menu defaults
remain Level 0. A non-default pool selection is L2; a non-default line search is
L3. L1 uses the first matching arm in canonical registry order; only signed
expressions require the signed attack arm. Supplied null/unknown/malformed values
and missing prerequisites refuse. Full budget, material, graph-envelope and
compiler checks still belong to the existing isolated development path. Public
preview success alone never certifies those checks or qualification.

The contract is closed immutable canonical JSON. Its digest pins the base,
registry version/order, type/arm bounds, opening, ceiling and check health. The
binding records that digest, registry version, derived change set/label and arms;
`verify_binding` re-derives it with canonical, type-sensitive equality. The
level-free library commitment hashes canonical JSON containing only Challenge,
unified digest and canonical strategy digest. Producing that digest never signs
or authorizes submission; the current network still uses its old commitment.

The shipped battery profile has all widened types INTERNAL, no owner acceptance,
an unset ceiling and unavailable check-health facts. `classify` thus refuses
widenings with `construction_beyond_ceiling`. Configured profiles can report
`construction_type_not_open:<type>` or `construction_type_closed:<type>`;
unregistered types/combinations and unclassified input also fail closed. Creating
an EXTERNAL profile requires a recorded owner acceptance reference; this library
does not authenticate such records and is not an authority issuer.

Operators can explicitly install an observer alongside the current ladder:

```python
from carbon.battery.unified_contract import contract
from carbon.development_ladder.operate import setup
from carbon.development_ladder.unified_shadow import Observer

profile = contract()
setup(target, config, shadow=Observer(profile, operator_diagnostic_sink))
```

No observer is installed by default. The hook runs only after successful legacy
compilation, receives a copy of the strategy and no compiled mutable object,
and emits only contract/equality/refusal metadata. Callback failure increments
an operator-local counter and cannot veto legacy compilation. Retention and
access to the sink remain the operator's responsibility.

`compare` accepts the same strategy, legacy variant digest, and optional separate
`legacy_artifact`/`unified_artifact` rebuilt-artifact digest receipts. It reports
derivation, compiler-route and artifact equality separately. Without both valid
artifact receipts, agreement is INCOMPLETE; unequal routing/artifacts is
MISMATCH. Matching receipts are diagnostics, never scoring/deduplication inputs.
Never substitute a recipe, expression or construction-plan hash for an artifact.
This phase does not produce a second rebuild or attest receipt provenance.

Validation covers content/default/arm derivation, public health/opening guards,
strict input, type-sensitive binding/commitment pins, a second-Challenge fixture,
shadow mismatch/incomplete receipts, callback isolation, fresh child-compilation
agreement for L1–L3, and import closure excluding the development compiler.
Artifact receipt comparison fixtures are synthetic; no physical validity,
security qualification, live equality experiment, LIVE or production authority
is earned by them. G-FEAS, B15, scoring, window, budget and weight behavior are
unchanged. External security acceptances and ceiling policy remain human-owned.
