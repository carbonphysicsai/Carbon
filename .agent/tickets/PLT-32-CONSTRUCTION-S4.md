# PLT-32 / S4 - construction capability promotion, empty

Status: IN_PROGRESS; Platform3 owns this slice end to end. One PR to main,
reviewer Carbon Validator for the promotion boundary. Exact start is S3's
normal merge b0c9c65879b729e17a1f9afbf79e9e3ae5980698, second parent
9e65c610da031512733b3781471704ce05eb49b5; all40 S3-owned blobs preserved.

Authority: canonical queue PLT-32; OWNER-CONSTRUCTION-ANYTHING-01 section6;
CONSTRUCTION_CONTRACT_PLAN_01 section3/S4; current constitution, invariants,
delivery/delegated protocols and owner finish-line sequencing. L5 candidate
measurement brief and candidates page are hypotheses/dependency context.
This is construction capability adoption, never frontier promotion/payment.

## Working contract and decisions

KEEP current base contracts, composition/variant pins, expansion history and
all compiler/budget/containment behavior. Add a separate promotion-record
schema and registered EMPTY set. A record binds one capability, its exact
source base/composition, content-addressed evidence pointers and a decision
record pointer; a pointer or claimed outcome is not measured acceptance.
Promoted fields belong to the next combined contract's base for everyone,
never a private arm or a level above4. Do not publish a next version or pin
because this slice promotes no capability.

The promotion bar (which evidence and whose sign-off) is HUMAN_INPUT, stored
as null. No public caller supplies a passing bar or acceptance Boolean.
Promotion attempts and nonempty registry application fail closed while that
bar is undefined; a forged non-null bar is not registration. A future owner
bar requires its own registered policy/version and actual evidence review.
The three recovered candidates remain unmeasured and absent from the set.

WRAP existing registry/compiler entry points in a promotion-aware DEVELOPMENT
helper: with an authenticated empty set it returns the exact existing base
and composition and delegates to the unchanged composition compiler. This
is an operator/library mechanism, not a newly served miner/validator route.
No S3 source edit or activation is needed while the set is empty. A proposal
record can be structurally validated/serialized, but cannot mint promotion.

Plan: authority/orientation and overlap scan; canonical baseline; contract
commit; one coherent data/record/empty-application slice; focused canonical
tests and style/hygiene; one final candidate review/check handoff. Root owns
engineering merge. No intermediate review or repeated clean-pass quota.

Expected manifest: this ticket; .agent/decisions/2026-10-14-PLT32-S4-EMPTY-PROMOTIONS.md;
carbon/reconstruction/construction_promotions.py and construction_promotions.json;
tests/cpu/test_construction_promotions.py;
docs/development/graphite/level5/PROMOTION_PATH.md. No open PR overlaps these
new paths at start. Hub retired; historical map_ref SYSTEM/DEVELOPMENT-HUB.

Acceptance: empty set preserves base/composition bytes and actual compiled
records/representative reconstructed state; unset bar refuses attempted
promotion before compiler work; malformed/duplicate/unregistered/fake-bar
inputs fail closed; records bind scope and refs without inventing evidence;
pure import/public boundary and historical contracts remain. Synthetic test
values stay fixtures. No measurement/host/provider/keys/hidden/sealed access.

Maturity ceiling: implemented/tested DEVELOPMENT record and empty-set
mechanism. Actual promotion, scientific/security acceptance, thresholds,
future base/version migration, S5 serving and LIVE remain owner-reserved.
Existing default-check activation and dual-loss holds are untouched.
