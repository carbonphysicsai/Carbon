# Carbon delivery policy

Repository defaults: OWNER-DX-03 (6 September 2026), amended by
OWNER-WORKFLOW-SPEED-01 (3 October 2026) and Ryan's direct engineering-delivery
amendment (17 October 2026): no approval ceremonies, regular PR testing, and fewer
coherent PRs. This supersedes earlier AGENTS/task requirements for distinct
human approval, GPT receipts/gates, fixed review counts, repeated fresh-context
reviews and Root reapproval. It changes no enforced branch protection or reserved
scientific, security, legal, LIVE or economic acceptance.

This is the single repository source for engineering delivery. Other agent
entry points and historical tickets must not add retired requirements back.
Current direct human instructions and actual enforced controls remain binding.
Do not reinstate those retired engineering ceremonies from an older task,
receipt or instruction snapshot, or ask for adoption again. A genuinely new
human restriction or actual enforced control still applies to its affected
action. Continue independent authorized source and testing work.

## Implement and validate

Use one coherent PR for meaningful structural, runtime or behavior changes,
including changes to public/data contracts or engineering policy. Bundle their
helper tasks, fixes, tests, documentation and formatting. Do not create a PR per
touch, run, receipt or minor subtask; fold small maintenance into a suitable
existing or upcoming PR. Split independently shippable work only for a real
dependency or reviewability need. Keep delivery on the established PR path;
"nonstructural" is not a direct-main shortcut or a way around required checks.

Risk matters regardless of size: even a small authentication, protocol, scoring,
economic or runtime change uses proportionate PR checks for its affected
behavior and boundaries. A multi-module task does not require a separate
contract PR, plan commit or approval checkpoint. Record material choices once,
reconcile affected docs and finish the user flow.

During development run focused tests for changed behavior and its affected
interactions. Before delivery run the applicable automated acceptance for the
candidate. The maintained change classifier, CI manifests and workflow own the
scope; do not duplicate their path lists or stale shard/test counts here.
Unknown changes retain their fail-closed classification. Required tests must
pass; failed, skipped or absent required evidence is not success. Preserve
scientific, leakage, isolation, correctness and invariant test semantics.

Use `./scripts/dev/canonical.sh` when available, or the pinned CI environment.
Label native-host results as diagnostics. Diagnose runner unavailability before
retrying; it does not block disjoint implementation. A missing development
package is addressed through trusted maintained bootstrap with pinned inputs,
not by weakening hostile-worker offline controls. Rebuild a development image
only when its actual environment inputs or required acceptance call for it.

Finish and check a candidate before pushing it ready. Do not repeatedly rerun
successful checks for reassurance, change prose to force CI, or create an empty
evidence-seal commit. After an actual code/environment change or concrete
failure, validate the affected revision. Retry the failed infrastructure job
when appropriate; do not relabel a failed broad run as a pass.

## Review and merge

Use regular PR testing and proportionate correctness/risk review; repair
concrete findings. Independent review is useful for risk, with no fixed review
quota, extra distinct-human approval, GPT receipt/bot gate, clean-pass count,
repeated fresh-context review loop or per-step Root reapproval. Do not add a
prescribed receipt ceremony. Actual protected requirements and real security
rejections remain controls, not paperwork to bypass.

Only the designated integration/merge owner performs delivery. Verify actual
PR head/checks and owner blocks. Use normal merge commits with the exact
expected-head race guard, after scope-required acceptance and `Merge gate`
succeed. Do not bypass a failed required check, actual conflict, security
rejection, unclosed material defect or applicable owner stop. No admin override
or alternative actor/destination may evade a rejection.

Do not refresh a suitable approved base solely because main advanced. Reconcile
real conflicts or changed dependencies and validate the resulting changes.
Never copy check success from different executable inputs. Actual merge
ordering and the established manager lane are described in
[MERGE_HYGIENE.md](../docs/development/MERGE_HYGIENE.md); that document does not
override current human constraints. No auto-merge is enabled by this cleanup.

Confirm GitHub reports the intended merge, then give one concise completion
record with behavior, test results, limitations and the next authorized action.
CI/Git supply revision identities. Do not require a human to transcribe SHA
inventories, counters or a normalized receipt schema. No second full acceptance,
post-merge evidence commit or copied receipt is a repository default. Diagnose
an actual main-smoke failure; never fabricate successful integration.

Finish through delivery only within the current session's authorization. Do not
start the next historical queue item, publish source, deploy, spend, sign or
resume a cancelled schedule merely because the current task completed.

## Retired process and historical evidence

The Development Hub is frozen history. No map_ref, Hub event, PR declaration,
regeneration, snapshot repin or Hub maintenance acceptance is required. Its
legacy contracts and templates cannot add those tasks. Leave frozen files
unchanged unless their deliberate migration is authorized. Historical decisions
stay in `.agent/DECISIONS.md`; durable new decisions use `.agent/decisions/`.

Old review receipts and exact-main ceremony records remain evidence of what
happened under their original rules. Do not rewrite them or use them to impose
superseded process. A repository ruleset file describes intended protection;
inspect actual settings when relevant. This task does not apply administrative
changes or claim that a committed ruleset proves live enforcement.

## Evidence and blockers

Prefer validation at an actual trust boundary and reuse its result internally;
do not add another schema/receipt layer for each consumer without a distinct
property to protect. For a claimed property, identify what establishes it and
whether another construction path can bypass it. A type, digest or closed
schema proves only the property actually checked, not scientific or security
qualification.

A result states what it examined and what it could not examine. An empty read,
missing check, unobserved process or unavailable measurement is unknown, not a
pass, zero or mismatch. Success without its basis is incomplete evidence.

A wait names a current satisfiable condition. If the head changed, the job
terminated, or the receiver already completed, update the action rather than
polling stale state. A blocker names its source, purpose, current applicability
and affected action. Scope it narrowly; continue independent authorized work.

Science, security acceptance, rights, production, LIVE, network economics,
frontier, settlement, weight and emission authority remain domain-owned.
Passing engineering checks or merging code grants none of them.
