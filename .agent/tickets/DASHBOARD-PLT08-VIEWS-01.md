# LP-02 — DASHBOARD-PLT08-VIEWS-01

Working contract: implement the Platform queue's transferred LP-02 item in one
PR to main. Reviewers: Launchpad, with Carbon Validator for disclosure.
Starting base: `39300a3b3025f5935224091357cf826b399d476d`.
PLT-08/#1214 is merged; the ticket-start open-PR file scan found no dashboard
overlap. No other session's queue entry or branch belongs to this ticket.

Authority: owner instruction to do the unblocked work, Platform queue LP-02,
CONSTITUTION.md, INVARIANTS.md, current delivery/delegated-decision protocols,
OWNER-DASHBOARD-01, DASHBOARD_PLAN.md and the merged score_feed contract.
Older dashboard-plan text excluding coldkeys is DOCUMENTATION_LAG relative
to PLT-08's expressly authorized public coldkey ladder. This change only
displays that existing bounded exception.

## Scope and working decisions

KEEP the signature/precision/release checks, existing board models and pure
DOM renderer. WRAP the signed `miner_status` field with a count-only reader
and board.v2 projection. REPAIR sealed-ladder presentation and rule prose.

The producer's field is `miner_status`: an optional list of `{hotkey,
received, scored, refused}`, where `refused` maps closed codes to counts.
Absent/null remains unknown, never manufactured zero activity. The optional
key is omitted when unavailable, preserving exact legacy Python/Worker models.
Invalid
shapes, duplicate identities or unsafe integer counts refuse the signed feed
whole. Unknown fields are dropped. Unknown/unclassified refusal codes are
aggregated as `other`; neither their raw names nor payloads reach board JSON
or the DOM. Keep the dashboard independent of validator imports; a parity
test binds its closed refusal list to the producer's list.

Counts may appear before a first released score. A status-only hotkey gets
its own counts without invented rank, role, score, case or window information.
No score is reconstructed from counts. Existing released history is separate.

`leaderboard.ladder` is already projected as `eligible_leaderboard.coldkeys`
and `grain_pct`. A SEALED_UNTIL_GRAIN row never draws a displayed value or
rank. A sealed/empty coldkey ladder cannot fall back to the legacy hotkey
score table. Its message is "Scores sealed until the screening grain is set".
An available grain keeps the existing "Grain x%" note, gated by rulesOk.

## Rule-text inventory

Every rule assertion either requires rulesOk(board), or states a fact from
the following allow-listed board.v2 field. Numeric observations remain visible
without a rules card; rule bars and normative explanations do not.

| Text or family | Binding |
|---|---|
| Rule name / rule-era change | Name: rulesOk; era identity: challenge.rule_digest / history.era |
| Rotation / "Every" / release lag / first-publication duration | rulesOk; existing rotation and timing gates retained |
| Target kind, bars, margins, guard, registered rule and explanation | rulesOk; existing target gates retained |
| "Grain x%" | rulesOk; eligible_leaderboard.grain_pct |
| Failed safety gate cannot be offset | rulesOk |
| Championship entry trigger, round margin, guard bar and gap to win | rulesOk |
| Empty round's "king paid" assertion | rulesOk; without it, only "no contenders" |
| Section labels, sense and units; legacy ranking label | sections / ranking_section / eligible_leaderboard.section |
| Eligible standing, incumbent, challenger role, coldkey membership | eligible_leaderboard / king / handovers; no inferred role for status-only miners |
| King value, measured runner-up gap, crown, reward state and halving | king's explicitly projected fields |
| Rounds' epochs, chunks, solved count, stop, estimates, bounds, safety and outcome | championship.rounds' corresponding explicit fields |
| New king / paid-from epoch | championship.rounds.new_king / paid_from_epoch; no inferred payment |
| Pooled ladder, hotkeys, shown/no-improvement/sealed state | eligible_leaderboard.coldkeys / status; sealed suppresses values |
| Released-only history, era separation and no-first-release observation | history / next_release.released_windows / phase |
| Estimated next block time | next_round / next_release / as_of_block / block_seconds; says "about" |
| Gate results and failed counts | gates.names / king / failing / submissions_with_gates |
| Attempt/refusal status | miner_status; counts and closed plain-language refusal labels only |
| Feed health, labels, device, exclusion and network facts | feed / freshness / labels / device_class / excluded_canaries / network |
| Setup links and undisclosed recipes | Fixed documentation links and the existing disclosure allow-list |

## Validation and delivery

Canonical baseline: 105 dashboard reader/board/web tests passed, including
Node view checks. The local container uses main CI's Node 24.19.0, verified
against its official SHA256, only for validation; no dependency pin changes.

Add Python projection/refusal and Node renderer regressions for absent/count-only
status, unknown codes, pre-release miners, sealed/empty ladders and missing or
mismatched rules cards. Run all dashboard subsystem tests, PLT-08 feed tests,
all invariants, pinned Black 26.5.1/Ruff 0.16.3, diff checks, canonical delivery
hygiene and the exact-head classified CI/Merge gate.

Final local canonical regression command:
`CARBON_UV_GROUPS="science-jax chain archive mcp" ./scripts/dev/canonical.sh bash lp02-canonical-node.sh tests/cpu/test_dashboard_*.py tests/cpu/test_miner_screening_feed.py tests/cpu/test_miner_screening_disclosure.py tests/invariants`
passed 564 tests with no skips. The untracked wrapper installs the SHA-verified
CI-pinned Node in the temporary validation container, then runs pytest. Pinned
Black/Ruff and diff checks passed. The earlier seven legacy Worker parity
failures were repaired by omitting unavailable optional counts, preserving
the older model shape; no Worker source or parity assertion was changed.

No Worker, signing key, deployment, chain, AX42, paid compute, protected
material, scoring rule or grain measurement changes. Scientific adoption and
qualification remain human-owned. Maturity ceiling: implemented/tested display
software for DEVELOPMENT/TESTNET; no new scientific or production authority.
Counts are carried by the Python board builder. The unchanged Worker reader
does not yet carry this optional block; adding it to that separate serving path
is outside the ticket's explicit Worker exclusion and must not be claimed here.

Primary historical map_ref: WAVE-A/A6 (public disclosure). Hub maintenance is
retired by the current delivery protocol; no Hub event or derived file changes.
Completion requires one delivered PR to main, green exact-head required checks
and Merge gate, a Ready for PR Head comment naming both reviewers, a <=15-line
untracked queue report and LP-02 marked DONE. Never merge or approve here.
