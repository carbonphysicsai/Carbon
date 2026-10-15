# Development claim citation checks

PRD-05 adds artifact traceability checks to the existing development renderer.
It does not decide whether a physical reference is adequate or accept a product.
The common dossier schema and four output filenames remain unchanged.

`claim-inventory.json` covers the package specification and renderer guide,
Guard presentation, model-card design (within the package specification),
trust-map guide, standards crosswalk and dated reference-honesty note. Every
section is bound to its exact presentation bytes and registered supporting
artifact digests/locators. Whole-file locks also reject new uncited text.
The artifact list is explicit; no filesystem discovery or protected input is
used. Normative designs are SPECIFICATION, not implementation evidence.
Crosswalk records are SOURCE_OBSERVATION, not standards compliance.

The native disclosed-panel example is compared with the actual runtime
PANEL_SCHEMA literal. The dated battery note's route version is compared with
the public worker's VERSION literal. Both comparisons parse code without
executing it. A route/version name does not establish registration, resolved
mesh evidence, code verification, current-use acceptance or qualification.
All original near-onset and Undeclared physical-validity holds remain.

Generated manifests carry `claim_inventory` and a fresh `claim_check`. Sourced
facts, component rows, card/map measurements, crosswalk mappings and host risk
declarations are indexed. GAP is not an affirmative observation. Source-only
historical results retain their identities/outcomes; they do not demonstrate
current reference adequacy. Host declarations retain HOST_DECLARED_NOT_COMPARED
and never satisfy VERIFIED. The generic checker has no positive VERIFIED path:
a citation does not confer domain-owned verification/acceptance authority.

The renderer re-reads registered current public artifacts and compares actual
values, scopes, locators and identities before returning output. Prior output
verification additionally checks original Git citation membership when direct
Git is available, and reproduces the three customer files with already-checked
original citation URLs. An edited Markdown number cannot hide behind a valid
manifest. A claimed PASS, rebound digest, missing inventory, unknown value or
unsupported authority flag is not accepted as evidence.

```text
python -m scripts.dev.customer_deliverable.check_claims --ref HEAD
python -m scripts.dev.customer_deliverable.check_claims --ref HEAD --manifest <public-output-directory>/generation-manifest.json
```

The selected ref is the verifier's current commit, not a revision chosen by
old output. For the generator CLI, current presentation checks run against the
tool checkout's HEAD even when rendering an explicitly historical public
evidence snapshot. Missing or changed citations fail before files are written.
Failures name the claim and artifact. Unsupported claims go to Carbon Validator
for removal; the checker does not turn them into low-confidence positives.

Do not automatically refresh the inventory to make a failing check pass.
Inspect changed presentation/evidence and the reference decision, resolve the
finding with the named reviewer, then prospectively update the specific
approved binding. This preserves historical records and avoids silent rescore.

PASS means ARTIFACT_TRACEABILITY_ONLY_NOT_SCIENTIFIC_ACCEPTANCE. It establishes
that registered bytes/locators and artifact-derived claims match, not the truth
of a source, completeness of physical evidence, authentic host authority or
standards applicability. Offline public exports retain their trusted-exporter
membership assertion; byte equality does not authenticate that exporter.
Fixtures test the mechanism only. No solves, new tolerances, thresholds,
qualification, accreditation, security acceptance, protected reads or LIVE.
