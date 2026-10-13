# PRD02D-VERIFICATION-CONDITIONS-01 — bind and separate Guard reference conditions

Ticket: Product PRD-02d / GUARD-ACCEPTANCE-CONDITIONS-01.
Base main: `f878ed9529e85cd8d5443266661bc9419b8ee356`.
Authority: Validator follow-up #1235 comment 6136605803 and the Product queue's
2026-10-13 authorization to serialize prerequisites ahead of held draft #1222.
The held Assistant remains unchanged. PRD-02e is a separate future queue item.

KEEP the registered PLT-07 acceptance-link v1 loader, strict native map v2,
immutable Guard configuration, deterministic probes, typed failures and actual
battery-use/applicability holds. REPAIR Guard reference/receipt semantics only.
Plan: baseline; prospective schema/fixture migration; native-link binding and
query distinction; adverse/missing-data regressions; docs, quality and hygiene;
one applicable exact-head CI; named-review request and Ready for PR Head.
Baseline: 126 native Guard/trust-map tests pass (host diagnostic evidence).

Prospectively version Guard reference and receipt as v3. Contract and policy
stay v2. Reject older reference schemas and the ambiguous `conditions` shape;
do not silently classify historical conditions. Require explicit
`verification_conditions` and `application_conditions` in acceptance_scope.
Only application conditions are exact numeric query/probe restrictions; null,
missing or mismatched values remain unresolved. MMS t_end is never inferred
as a physical operating-time limit or a new query input.

Add explicit reference `criteria_digest`, so even a READY route without a map
can load its registered acceptance using contract family/image and criteria.
Require scope family and verification conditions to equal that record, and
code_verification_ref to equal its link digest. A supplied map's independently
validated receipt must agree too. Missing/tampered links or conflicting READY
assertions refuse construction with a fixed code, even without policy or map.
This binds public document identity; it does not authenticate the host's use
acceptance, attest its callable, qualify the reference or remove any owner hold.
owner_acceptance_ref stays a separate host use-acceptance assertion.

Receipts carry the complete registered code-verification record even without
a map and copy both condition blocks. Observables explicitly say
HOST_DECLARED_NOT_VERIFIED_COVERAGE; application restrictions are host-declared;
verification conditions say registered only when READY binding was validated.
Unresolved/failed reference records still REFUSE and preserve failure type.
Any validated map record is independent metadata, never a cure for that hold.

The later acceptance-link v2 verified_scope is deferred to its owner. Do not
invent verified observables or imply full DFN verification from particle/heat
MMS. No scientific thresholds, qualification, solver execution, physical
validation, private/hidden evidence or LIVE behavior is added. Fixture physics,
law adoption, outputs and use acceptance remain explicitly synthetic.

Alternatives rejected: reusing ambiguous v2 semantics would reinterpret
historical data; taking verification only from the optional map would leave
no-map READY routes unbound; treating MMS end time as a query input would keep
the defect; widening PLT-07's verified scope would exceed Product authority.
New reference content pins prospectively change replay vectors. Historical
receipts/timing and public MMS source records remain untouched.

Reversible by prospectively changing Guard configuration/core/demo/README and
Guard tests. The smallest superseding change can alter this v3 projection;
never relax the native loader or reinterpret historical receipts. Reviewer:
Carbon Validator; Data Collection for source joins. Hub retired. Scientific,
reference-use, legal, security and product acceptance remain human-owned.
Reuse-first repository files match the already-read prior delivered tree;
shared physics draft sections 0/5 retain SHA256
`cff7dd9e5b32993ea4dbaa93731fd9e0776b22fd2d5958320a194b9009dc768b`.
