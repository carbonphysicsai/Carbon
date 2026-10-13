# Carbon Model Package evidence-honesty audit — 2026-10-13

DELIVERABLE-EVIDENCE-HONESTY-PASS-01. DEVELOPMENT documentation audit only.
Audit baseline: main `e9a28008b3975c3aaa93b710b6f623221241c2eb`.
No model, reference, measurement, gate, score or qualification is added.

## Reference transition and the current hold

The Test Lead's Product queue reports near-onset plating-margin optimism of
1.3-2.46 mV, comparable to the historical uncertainty band. The public
[PLATING-CONVERGENCE-01 finding](https://github.com/carbonphysicsai/Carbon/pull/1280)
at `09306301176be32c21769d9935d17faa1ef74b16` reports approximately 1.3-2.6 mV
for its public near-onset panel, with extrapolation uncertainty and a failed
mesh-320 rung retained. These are bounded source observations, not a universal
error bound, new tolerance or physical-validation result.

[OWNER-PLATING-REFERENCE-01](../../../.agent/decisions/2026-10-13-OWNER-PLATING-REFERENCE-01.md)
adopts the next reference route for the **public near-onset set only** and
requires additive annotations of EV4, EV5 and score proofs. The pending
[D3 worker](https://github.com/carbonphysicsai/Carbon/blob/b29f6191627a6f373456dbb04fd774367deac914/scripts/dev/battery/plating_rereference.py)
names `battery-plating-ref-v2`; [PR #1288](https://github.com/carbonphysicsai/Carbon/pull/1288)
explicitly says no reference version is sealed or registered there. This audit
does not declare that work complete or adopt its numerical rules in Product.

**No usable near-onset label is established for the v2 route before the required
resolved mesh-160 solve and version-bound reference acceptance exist.** Missing,
failed or unresolved reference evidence prevents a feasible/accepted decision;
it cannot become a low-confidence positive or a model failure. A name, image
digest, host READY flag, map cell or MMS link cannot close this hold.
The Product battery/plating comparison remains **SOLVER_NOT_ACCEPTED / GAP**.
Physical validity remains Undeclared. No physical/qualified claim is supported.

Reference refinement consumes compute. Near-limit speed, cost and equal-budget
claims require measured refinement, failed/retry and fallback costs on the same
supported job and reference version. Historical wall_s aggregates neither
provide complete v2 costs nor CPU core-seconds. No saving or speed-up is claimed.

## Five-surface audit and prospective repairs

| Surface | Finding / retained boundary | Repair / evidence needed |
| --- | --- | --- |
| Package / CMP-02 | A blanket "verified solver" yardstick can imply accepted application/plating truth. | Require observable/use/version-specific resolved reference evidence. Cite this v2 transition; do not transfer particle/heat MMS acceptance to plating. |
| Envelope Guard / CMP-08 | Constructor checks registered MMS conditions, but use acceptance, application conditions and observables remain host assertions. | Document that structural checks do not authenticate authority or resolve v2 labels. Keep REFUSE/current-use holds. PRD-02f's HOST_DECLARED_NOT_COMPARED remains explicit for non-READY conditions. |
| Model card / CMP-03 | Historical near-limit accuracy, uncertainty and timing could be read as current v2 adequacy. | Identify source reference/measurement version and resolved mask. Preserve old observations; remove any current adequacy/speed inference without matched refined evidence. Floors/acceptance remain HUMAN_INPUT. |
| Trust map / CMP-04 | Code-verification identity and pooled errors do not qualify plating labels or selected designs. | Retain source-scoped cells/counts; no v2 TRUST permission from an old cell or image match. Require current supported reference evidence before a current-use claim. |
| Credibility crosswalk / CMP-06 | "Owner acceptance conditions" could read as application acceptance; digest-bearing risk/use declarations could read as authenticated decisions. | Label MMS conditions as test-design metadata and declarations as host assertions. Source outcomes remain separate from NOT_ASSESSED requirement acceptance; no standards compliance/accreditation. |

The generator's revised text is prospective. Existing v2/v3 examples remain
historical snapshots with their original bytes and source revisions. EV4, EV5,
score-proof values, verdicts, hashes and rankings are not edited or re-scored.
This Product note does not substitute for the owner-required additive notes
beside those evidence sets; their evidence owners retain that work.

The optional public projection can establish document identity and copy source
facts. It has no v2 plating-acceptance/refinement receipt contract, and no new
join is implemented here. It cannot establish current v2 applicability from
an image-only identity. Unsupported affirmative claims are absent; gaps remain.
Carbon Validator and Data Collection assess the reference/evidence joins.
Scientific acceptance, qualification, disclosure/rights and LIVE remain owned
by their responsible authorities. Hub retired; PR Head owns merge.
