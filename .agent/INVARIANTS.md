# Carbon Build Invariants (Agent Must Enforce)

Aligned with **Build_Out v1.4** §2 for always-on agent context. **Never violate.**

1. **No seed leakage.** Official seeds, derived seeds, draw IDs, or reversible identifiers never appear in EvaluationCard, leaderboard, MCP outputs, or miner-visible logs.
2. **Mock isolation.** Mock / light execution never accesses official packs, official seeds, or hidden exam data.
3. **Pinned evaluation.** Every scored submission is bound to immutable challenge / generator / Score Pack / backend (container digest) versions.
4. **Disclosure allow-list.** InternalResult / Model Card fields are never returned on miner-facing APIs unless explicitly allow-listed for the disclosure tier.
5. **LIVE requires qualification.** LIVE challenges require a complete signed human qualification manifest for that exact challenge version (not merely non-null YAML), with content hashes bound to that version.
6. **Execution isolation.** Miner-supplied strategies run under enforced compute, network, filesystem, and wall-clock limits.
7. **Infra ≠ science.** Infrastructure failures (OOM policy kill, node death, queue loss) are never scored as scientific / physics failures and never grant emissions. Use FAILED_INFRA / refund-retry semantics.
8. **Determinism.** Re-running an identical official evaluation under identical versions, seeds, and limits is deterministic within documented tolerances.
9. **No placeholder LIVE.** Placeholder, fixture, or mock values never enter LIVE configuration or emission weights.
10. **No silent rescore.** Historical evaluation records are never silently reinterpreted under newer packs; new pack ⇒ new scoring_version for future runs only.
11. **Forbidden score inputs.** Prior similarity, `estimate` / `light_*` metrics, exam fee, and mock metrics never enter `S_combined` / Yuma weights.
12. **Free path imperfect.** Free-loop signal may be directionally useful but must remain intentionally incomplete vs the official exam.

## Agent implementation notes

- Prefer tests that fail CI if these break.
- Prefer `HUMAN_INPUT` / `None` over guessed thresholds.
- Label stub backends with `emission_capable=False`.
