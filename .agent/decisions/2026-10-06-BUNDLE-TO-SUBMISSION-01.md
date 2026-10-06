## 2026-10-06 — BUNDLE-TO-SUBMISSION-01: a Graphite phase-3 bundle becomes the Launchpad's submission

**Authority:** the owner's approval of rehearsal-first testing (#707) and the
executor's mainnet launch blocker relayed by the Test Engineer: there was no
way to turn a Graphite phase-3 winning bundle into a miner submission.
Engineering choices only. No scientific, economic or security value is chosen
here, and nothing is submitted, signed or sent.

**Base:** `origin/main` 30876180e, branch `claude/bundle-to-submission`.

### BTS-D1 — One command, the Launchpad's own path

`python -m carbon.agent_campaign.graphite.bundle_submission --bundle DIR --out FILE`
reads a phase-3 bundle alone and writes the frozen-candidate record the
Launchpad's freeze writes (`selected-recipe.json`), byte for byte. No
parallel compiler: the recipe passes the Launchpad's check-design verdict
(`design_check.check_design`), the per-Challenge admission
(`challenge_contracts.compile_submission`) under the digest the Challenge's
miner-facing description publishes (`challenge_registry.registry.describe`),
and the freeze's one record builder (`research_loop.candidate_record`). The
bundle's integrity check is `delivery.verified_files`, factored out of
`clean_rebuild` unchanged so both share it; `clean_rebuild` then confirms
Carbon rebuilds the bundle from its files.

### BTS-D2 — Typed refusals; a refused bundle produces nothing

In order, before anything is written: `bundle_tampered`,
`score_variant_labelled`, `development_level_bundle` (a `development`
binding, Level 1 or above), `development_variant_digest` (any registered
contract or score variant name or digest anywhere in the bundle: the names
`capability_registry.is_development_variant` refuses, read once),
`challenge_not_published`, `contract_digest_not_published`,
`recipe_not_admitted`, `bundle_not_rebuilt`, `submission_digest_mismatch`
(the frozen record's strategy hash, plan, recipe and contract digests must be
the bundle's) and `output_exists`. A Level-1 bundle names the base contract
digest, so the level check reads the recipe's development binding rather
than relying on the digest alone.

### BTS-D3 — The record's fields

`reason` names the bundle by its manifest digest and, for a v3 bundle, its
rebuilt artifact. `used_feedback` is false: a phase-3 session sees practice
feedback only. The miner passes the same strategy, reason and used_feedback
to the Launchpad's `freeze_candidate`, which writes the same bytes.

### BTS-D4 — Submitting stays the miner's

The command opens no connection, holds no key and never signs. It prints the
next Launchpad step: in an agent-none campaign for the Challenge, practice the
strategy (the freeze requires a practice result), freeze it with the record's
fields, then submit. Parity is pinned in
`tests/cpu/test_graphite_bundle_submission.py`: the Launchpad's freeze writes
the converter's bytes, and the Launchpad's submit
(`battery.campaign._evaluate_through_intake`, its intake replaced by a
capture) sends the converter's strategy and contract digest.

**Maturity:** IMPLEMENTED and TESTED on fixture bundles. Not exercised on the
run-5 bundle itself, not scientifically, security or network qualified.
