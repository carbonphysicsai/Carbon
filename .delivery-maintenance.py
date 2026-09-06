from pathlib import Path
import json

root = Path.cwd()
def read(p): return (root / p).read_text()
def write(p, s):
    (root / p).parent.mkdir(parents=True, exist_ok=True)
    (root / p).write_text(s)
def replace(p, a, b):
    s = read(p)
    assert a in s, (p, a[:100])
    write(p, s.replace(a, b))

write('.agent/DELIVERY_PROTOCOL.md', '''# Carbon Delivery Protocol

**Status:** owner-authorized delivery policy, effective 2026-09-06
**Decision:** OWNER-DX-03
**Applies to:** current and future engineering tickets, including open PRs

The owner directs: follow the ticket, test the changes, and ship. This policy
supersedes GOV-REVIEW-01 and older delivery-process requirements in tickets,
plans, Wave records, agent handoffs, and Hub instructions. Historical receipts
remain historical evidence. Scientific, security, economic, legal, deployment,
qualification, and LIVE acceptance remain human-reserved and unchanged.

## 1. Ticket to merge

1. Read the ticket and relevant authority. Keep working code under
   KEEP -> WRAP -> REPAIR -> REPLACE. Implement the ticket's Definition of Done.
2. Use one branch and one PR per ticket by default. Develop coherent slices
   with focused tests. Continue through slices without asking for permission
   at each checkpoint unless the owner requested a stop.
3. Record material decisions and update affected documentation. Batch Hub
   maintenance before acceptance. Do not create a contract-only PR, a separate
   plan, or a review checkpoint merely because a ticket has multiple modules.
   Split independently shippable work when an actual dependency or owner
   instruction requires it; explain the split in the PR.
4. Check the change for correctness and add regression tests for defects.
   An independent agent review is optional. There is no mandatory human
   reviewer, GPT receipt, bot approval, model score, clean-pass quota, or
   fresh-context full-diff review loop. Fix concrete defects; verify repairs
   with focused tests and inspect the affected interactions.
5. Finish the candidate, mark the PR ready, and run the applicable automated
   acceptance once. Required tests must pass. Merge the tested revision with
   the expected-head guard; do not merge code that changed after its checks.
6. Confirm GitHub reports the merge. Post one brief completion comment with
   the ticket, test result/CI link, remaining limitations, and next ticket.
   Close the ticket in its bounded engineering scope and continue when the
   owner authorized end-to-end execution. No second approval prompt, receipt
   schema, evidence-seal commit, or post-merge full-CI wait is required.

A valid bug, failed required test, actual merge conflict, or unresolved
human-reserved decision can stop the affected work. A review receipt, prose
formatting issue, bot outage, or incomplete historical ceremony cannot.
Never suppress a failing test, invent a pass, or relabel qualification.

## 2. Validation budget

During development, run focused ticket and affected-subsystem tests. Use the
canonical wrapper when available. A missing local Docker installation is
infrastructure unavailability, not a reason to repeat the same failed command
or to block implementation; GitHub's pinned environment supplies acceptance.
Native-host tests are diagnostics, not canonical qualification.

For a ready runtime PR, CI runs the CPU regression suite, invariant tests,
quality ratchet, package/import checks, and applicable Hub validation. Unknown
paths retain full runtime acceptance. Contract-only and generated-doc changes
retain their existing lighter classified suites. Test semantics remain intact.

The clean development-image build runs for environment, dependency, workflow,
or canonical-runner changes and unknown paths. Ordinary Python implementation
and test changes use the pinned canonical runner without rebuilding the image.
The aggregate Merge gate rejects failed or skipped required jobs.

Draft PR updates do not start acceptance. Marking a draft ready starts its
first acceptance run. Ready PR code pushes start acceptance for that revision.
PR title/body edits, review submissions, and comments do not start full CI.
The standalone Hub workflow is manual; CI owns normal Hub acceptance once.
Main smoke checks detect integration failures after merge; they are not a
second full acceptance or a ticket-closeout ceremony.

Batch changes before pushing a ready candidate. Do not rerun a green workflow
for reassurance, rewrite a PR body to force CI, create an empty commit, or
repeat a successful job after an infrastructure failure. Retry the failed job.
After a real code/test/environment change, validate the new revision. Docs and
status notes do not require another substantive code review. Do not copy a
success from different executable inputs and claim the new code passed.

## 3. Merge control and evidence

The intended repository rule is one required status check: `Merge gate` from
GitHub Actions, with zero required approvals and no last-push approval.
Thread-resolution bookkeeping is not an additional gate; actual unresolved
bugs and explicit owner blocks still require disposition. Use normal merge
commits and retain the API's inexpensive expected-head race guard.

Do not require a base refresh solely because main advanced. Inspect the
integration impact; reconcile conflicts or changed dependencies and validate
those changes. The merge guard prevents merging a different PR revision; it
does not prove scientific qualification or conflict-free semantic integration.

CI obtains revision identities from GitHub/Git. Do not ask a human to copy
head/tree/base SHAs, review counters, or rerun totals into a PR. The PR needs a
ticket/scope explanation, test summary, risks, and Hub impact where relevant.
Legacy receipt fields are historical metadata and are not merge authority.

The versioned intended rule remains `.github/rulesets/main.v1.json`; the file
format version is unchanged. The apply tool must verify live settings after
an administrative write. A committed artifact is not proof of live enforcement.
No receipt or merge operation grants scientific, security, production, LIVE,
network, frontier, settlement, weight, or emission authority.
''')

s = read('AGENTS.md')
s = s.replace('# 1. Mandatory authority read', '''## Current delivery direction: OWNER-DX-03

For engineering delivery, follow `.agent/DELIVERY_PROTOCOL.md` (2026-09-06).
It supersedes older review, receipt, exact-head ceremony, and post-merge-CI
requirements in tickets, boards, and handoffs. There is no mandatory human
reviewer or GPT receipt. Follow the ticket, run its tests and one applicable
automated acceptance, then merge. Keep all scientific and security invariants.

# 1. Mandatory authority read''', 1)
a = s.index('# 9. Ticket-based development')
b = s.index('# 11. Stub and fixture policy')
s = s[:a] + '''# 9. Ticket-based development

Work on the owner-authorized ticket. Use one branch/worktree and one PR by
default. Read the current contract and inspect working code before changing
it. Create a plan only when it helps implement a complex ticket; separate
contract, plan, or approval commits are not mandatory.

Implement coherent slices with focused tests and continue through the ticket.
Do not stop after each slice for another owner prompt. Record material
engineering decisions and notify the applicable lead without waiting for
routine approval. Human-reserved scientific or security decisions still stop
the affected behavior and remain fail closed.

Before acceptance, reconcile affected docs and Hub source, regenerate outputs,
and inspect the candidate for correctness. Independent agent review is
optional. No human approval, GPT receipt, fixed review count, or repeated
fresh-context complete-diff review is a routine delivery gate.

Run one applicable automated acceptance on the ready candidate. Fix failing
tests and concrete defects, validate affected interactions, and merge the
tested revision with the expected-head guard. Unless the owner requested a
stop, finish delivery and continue to the next authorized ticket. Follow
`.agent/DELIVERY_PROTOCOL.md`; do not resurrect superseded ticket boilerplate.

---

# 10. Testing and evidence

A completed ticket needs implemented behavior and passing evidence for its
Definition of Done. During implementation, run focused ticket/subsystem tests.
Before shipping, require CI's applicable regression, invariant, quality,
package/import, and Hub checks. Unknown paths retain full runtime acceptance.
Do not weaken scientific, leakage, isolation, or correctness tests to obtain
a green result. Owner-authorized delivery-policy tests must reflect the new
policy and continue to reject untested or failed required jobs.

Use `./scripts/dev/canonical.sh` when local canonical execution is available.
Do not repeat an unavailable Docker attempt. Use pinned GitHub CI for
acceptance and label native-host tests as diagnostics.

Keep scope, material decisions, tests, and limitations in the ticket/PR. CI
owns revision and run identities. A brief completion comment is sufficient;
no normalized receipt, evidence seal, or copied SHA inventory is required.
Closeout can be conditional in the shipping PR and takes effect after the
required automated acceptance and successful merge. Confirm the merge, report
remaining limitations, and proceed without waiting for a second full CI run.
A main smoke failure needs a repair; it does not justify fabricating success.

SPECIFIED, IMPLEMENTED, and TESTED remain separate from SCIENTIFICALLY_QUALIFIED,
SECURITY_QUALIFIED, and PRODUCTION_QUALIFIED. Engineering delivery grants none
of those human-reserved states.

---

''' + s[b:]
write('AGENTS.md', s)
for p in ['.agent/WAVE.md', '.agent/WAVE_B.md', 'agent_pack/EXECUTION_PROTOCOL.md', 'agent_pack/CODEX_TICKET_LAUNCHER.md', '.agent/DELEGATED_DECISION_PROTOCOL.md']:
    s = read(p); pos = s.index('\n') + 1
    s = s[:pos] + '''
> **OWNER-DX-03 delivery override (2026-09-06):** Follow the current
> `.agent/DELIVERY_PROTOCOL.md` for engineering delivery. No mandatory human
> reviewer, GPT receipt, repeated full-diff review, or post-merge full-CI gate
> applies. Older process descriptions below are superseded; ticket scope,
> historical evidence, and human-reserved scientific/security authority remain.
''' + s[pos:]
    write(p, s)
write('.agent/templates/EXTERNAL_COMPLETION_RECEIPT.md', '''# Completion comment

OWNER-DX-03 replaces the normalized receipt with a short PR comment.

State the completed ticket scope, passing test/CI result, merge link, remaining
limitations, and next authorized ticket. GitHub already records revisions and
run identities; do not transcribe them into a tracked evidence commit.

Do not infer scientific, security, or production qualification from delivery.
''')
write('.agent/templates/CODEX_GPT_REVIEW_RECEIPT.md', '''> **Historical template, not a delivery gate.** OWNER-DX-03 retires the
> mandatory human approval and GPT receipt. Retain old receipts as evidence;
> do not request a new one to merge an engineering PR.

''' + read('.agent/templates/CODEX_GPT_REVIEW_RECEIPT.md'))
write('.agent/DECISIONS.md', read('.agent/DECISIONS.md') + '''
## 2026-09-06 - OWNER-DX-03: tested ticket delivery without mandatory reviewers

The repository owner directs immediate removal of delivery ceremony. This
supersedes GOV-REVIEW-01 and the review/receipt/post-merge requirements of
OWNER-DX-01 for current and future engineering PRs. It does not rewrite
historical approvals or grant scientific, security, economic, legal, LIVE,
launch, deployment, or production acceptance.

Use one ticket PR, focused tests during slices, one applicable CI acceptance,
zero mandatory human approvals, no GPT receipt gate, an expected-head merge
race guard, and a brief completion comment. Stop full CI on metadata edits,
draft updates, and main merge events. Run clean-image acceptance when the
execution environment changes; preserve substantive tests and fail closed on
unknown paths. Independent code review remains available without a mandatory
fresh-context full-diff loop. Fix real defects and verify their regressions.

Implementation: `.agent/DELIVERY_PROTOCOL.md`, root `AGENTS.md`, CI/workflow and
ruleset tooling, plus the Hub declaration validator. Reversible through a
future owner-directed policy change; no runtime/schema/scientific migration.
Live administration settings must be verified separately from the artifact.
''')

p = '.github/rulesets/main.v1.json'; d = json.loads(read(p))
for rule in d['ruleset']['rules']:
    if rule['type'] == 'pull_request':
        rule['parameters'].update(dismiss_stale_reviews_on_push=False, require_last_push_approval=False, required_approving_review_count=0, required_review_thread_resolution=False)
    if rule['type'] == 'required_status_checks':
        rule['parameters']['strict_required_status_checks_policy'] = False
        rule['parameters']['required_status_checks'] = [x for x in rule['parameters']['required_status_checks'] if x['context'] == 'Merge gate']
write(p, json.dumps(d, indent=2) + '\n')
p = 'scripts/dev/apply_github_ruleset.py'; s = read(p)
for key in ['dismiss_stale_reviews_on_push', 'require_last_push_approval', 'required_review_thread_resolution', 'strict_required_status_checks_policy']:
    s = s.replace(f'"{key}": True', f'"{key}": False').replace(f'("{key}", True)', f'("{key}", False)')
s = s.replace('"required_approving_review_count": 1', '"required_approving_review_count": 0')
s = s.replace('    {"context": "GPT review gate", "integration_id": GITHUB_ACTIONS_APP_ID},\n', '')
s = s.replace('get("strict_required_status_checks_policy") is not True', 'get("strict_required_status_checks_policy") is not False').replace('required checks must use the strict status policy', 'required checks must use the owner-directed non-strict status policy').replace('required checks must be Merge gate and GPT review gate', 'required checks must be Merge gate')
write(p, s)
p = 'tests/cpu/test_github_ruleset.py'; s = read(p)
for key in ['dismiss_stale_reviews_on_push', 'require_last_push_approval', 'required_review_thread_resolution', 'strict_required_status_checks_policy']:
    s = s.replace(f'["{key}"] is True', f'["{key}"] is False')
s = s.replace('["required_approving_review_count"] == 1', '["required_approving_review_count"] == 0').replace('{("Merge gate", 15368), ("GPT review gate", 15368)}', '{("Merge gate", 15368)}')
s = s.replace('("dismiss_stale_reviews_on_push", False)', '("dismiss_stale_reviews_on_push", True)').replace('("require_last_push_approval", False)', '("require_last_push_approval", True)').replace('("strict_required_status_checks_policy", False, "strict status")', '("strict_required_status_checks_policy", True, "non-strict status")')
write(p, s)

p = 'scripts/dev/classify_changes.py'; s = read(p)
needle = '    @property\n    def unknown_paths'
assert needle in s
s = s.replace(needle, '''    @property
    def dev_image_required(self) -> bool:
        """Rebuild only when execution infrastructure changes or is unknown."""
        if self.scope is not ChangeScope.RUNTIME_FULL:
            return False
        return any(
            item.unknown
            or item.path in _IMAGE_EXACT
            or item.path.startswith(_IMAGE_PREFIXES)
            or re.fullmatch(r"requirements(?:[-_.][^/]*)?\.txt", item.path, re.IGNORECASE)
            for item in self.paths
        )

''' + needle)
s = s.replace('_RUNTIME_PREFIXES = (', '''# These files define the canonical execution environment or its acceptance.
_IMAGE_PREFIXES = (".devcontainer/", ".github/workflows/", "scripts/dev/")
_IMAGE_EXACT = frozenset({
    ".dockerignore", ".python-version", "pyproject.toml", "uv.lock",
    "MANIFEST.in", "setup.py", "setup.cfg", "tox.ini", "noxfile.py",
    "Pipfile", "Pipfile.lock", "poetry.lock",
})

_RUNTIME_PREFIXES = (''')
s = s.replace('"scope": classification.scope.value,', '"scope": classification.scope.value,\n        "dev_image_required": classification.dev_image_required,')
s = s.replace('"change_scope": classification.scope.value,', '"change_scope": classification.scope.value,\n        "dev_image_required": str(classification.dev_image_required).lower(),')
write(p, s)
p = 'scripts/dev/check_merge_gate.py'; s = read(p)
s = s.replace('def gate_failures(scope: ChangeScope, statuses: Mapping[str, str]) -> tuple[str, ...]:', '''def gate_failures(
    scope: ChangeScope, statuses: Mapping[str, str], *, dev_image_required: bool = True
) -> tuple[str, ...]:''')
s = s.replace('    required = REQUIRED_JOBS[scope]\n', '''    if type(dev_image_required) is not bool:
        raise ValueError("dev_image_required must be a bool")
    required = REQUIRED_JOBS[scope]
    if scope is ChangeScope.RUNTIME_FULL and not dev_image_required:
        required = required - {"dev_image"}
''')
s = s.replace('    for job in JOB_NAMES:\n        parser.add_argument(', '''    parser.add_argument("--dev-image-required", choices=("true", "false"), default="true")
    for job in JOB_NAMES:
        parser.add_argument(''')
s = s.replace('failures = gate_failures(scope, statuses)', 'failures = gate_failures(scope, statuses, dev_image_required=args.dev_image_required == "true")')
write(p, s)

p = '.github/workflows/ci.yml'; s = read(p)
s = s.replace('  push:\n    branches: [main]\n', '')
s = s.replace('types: [opened, synchronize, reopened, edited, ready_for_review]', 'types: [opened, synchronize, reopened, ready_for_review]')
s = s.replace('    name: Delivery preflight\n', '    name: Delivery preflight\n    if: github.event.pull_request.draft == false\n', 1)
s = s.replace('      change_scope: ${{ steps.delivery.outputs.change_scope }}', '      change_scope: ${{ steps.delivery.outputs.change_scope }}\n      dev_image_required: ${{ steps.delivery.outputs.dev_image_required }}')
a = s.index('      - name: Install pinned uv'); b = s.index('\n  canonical:', a)
s = s[:a] + s[b:]
s = s.replace("    name: Clean dev-container image\n    if: needs.preflight.outputs.change_scope == 'RUNTIME_FULL'", "    name: Clean dev-container image\n    if: needs.preflight.outputs.change_scope == 'RUNTIME_FULL' && needs.preflight.outputs.dev_image_required == 'true'")
s = s.replace('    name: Merge gate\n    if: always()', '    name: Merge gate\n    if: always() && github.event.pull_request.draft == false')
s = s.replace('          PREFLIGHT_SCOPE: ${{ needs.preflight.outputs.change_scope }}', '          PREFLIGHT_SCOPE: ${{ needs.preflight.outputs.change_scope }}\n          PREFLIGHT_IMAGE: ${{ needs.preflight.outputs.dev_image_required }}')
s = s.replace('          derived_scope=\n', '          derived_scope=\n          derived_image=\n')
s = s.replace('              derived_scope="${value}"\n            fi', '''              derived_scope="${value}"
            elif [[ "${key}" == "dev_image_required" ]]; then
              [[ -z "${derived_image}" ]] || { echo "Duplicate image requirement." >&2; exit 2; }
              derived_image="${value}"
            fi''')
needle = '          python3 "${gate}" \\\n            --scope "${derived_scope}" \\\n'
assert needle in s
s = s.replace(needle, '''          # Older protected bases require the image for all runtime changes.
          # The migration itself changes CI, so it still runs image acceptance.
          if [[ -z "${derived_image}" ]]; then
            if [[ "${derived_scope}" == "RUNTIME_FULL" ]]; then
              derived_image=true
            else
              derived_image=false
            fi
          fi
          [[ "${derived_image}" == true || "${derived_image}" == false ]]
          [[ "${PREFLIGHT_IMAGE}" == "${derived_image}" ]]
          image_args=()
          if [[ "${derived_scope}" == "RUNTIME_FULL" && "${derived_image}" == false ]]; then
            image_args=(--dev-image-required false)
          fi
          python3 "${gate}" "${image_args[@]}" \\
            --scope "${derived_scope}" \\
''')
write(p, s)
(root / '.github/workflows/gpt-review.yml').unlink()
p = '.github/workflows/development-hub.yml'; s = read(p)
a = s.index('on:\n'); b = s.index('\npermissions:', a)
s = s[:a] + '''# Normal PR Hub acceptance runs once in ci.yml.
on:
  workflow_dispatch:
''' + s[b:]
s = s.replace('steps.refresh_pr.outputs.base_sha || github.event.before', "steps.refresh_pr.outputs.base_sha || github.event.before || 'HEAD^'")
write(p, s)
write('.github/workflows/main-smoke.yml', '''name: Main smoke

on:
  push:
    branches: [main]

permissions:
  contents: read

concurrency:
  group: main-smoke
  cancel-in-progress: false

jobs:
  smoke:
    name: Main integration smoke
    runs-on: ubuntu-24.04
    timeout-minutes: 15
    steps:
      - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1
        with:
          persist-credentials: false
      - uses: astral-sh/setup-uv@20cfd1bf945f4377ade1205e4dbc17946fc9a30d
        with:
          version: "0.12.7"
          enable-cache: true
          cache-dependency-glob: uv.lock
      - run: ./scripts/dev/bootstrap.sh
      - name: Check integration invariants and public import
        run: |
          set -euo pipefail
          .venv/bin/python -c 'import carbon'
          .venv/bin/python -m pytest tests/invariants -m invariant -q
''')
replace('scripts/dev/check_gpt_review_gate.py', '"""Validate Carbon\'s exact-head manual Codex/GPT review receipt."""', '"""Parse historical Codex/GPT receipts; OWNER-DX-03 removes this delivery gate."""')

p = 'docs/development/carbon_hub/tools/validate_hub.py'; s = read(p)
needle = '    def validate_delivery_declaration(self) -> None:\n'
assert s.count(needle) == 1
s = s.replace(needle, '''    def validate_delivery_declaration(self) -> None:
        """Delivery metadata is descriptive, not an approval or identity gate.

        OWNER-DX-03 delegates revision identity and test outcome to GitHub CI.
        The separate Hub-impact validator still enforces mapping and drift.
        No PR body spelling, SHA, receipt, or throughput counter can grant a
        pass to code; the aggregate Merge gate requires actual successful jobs.
        """
        return

    def validate_legacy_delivery_declaration(self) -> None:
''')
write(p, s)
p = 'docs/development/carbon_hub/tools/test_validator.py'; s = read(p)
s = s.replace('.validate_delivery_declaration()', '.validate_legacy_delivery_declaration()')
pos = s.index('\nif __name__ == "__main__":')
s = s[:pos] + '''

class OwnerDeliveryPolicyTests(unittest.TestCase):
    def test_normal_delivery_does_not_require_human_metadata(self) -> None:
        for body in ("", "Ticket B-06. Tests passed.", "HUMAN_APPROVAL_REVIEW: PENDING", "FINAL_HEAD: stale"):
            validator = validate_hub.Validator(REPO_ROOT)
            validator.github_event = {"pull_request": {"body": body}}
            validator.validate_delivery_declaration()
            self.assertEqual(validator.errors, [])

''' + s[pos:]
s = s.replace('''        self.assertIn(
            "types: [opened, synchronize, reopened, edited, ready_for_review]",
            workflow,
        )''', '''        self.assertIn("  workflow_dispatch:", workflow)
        trigger = workflow.partition("permissions:")[0]
        self.assertNotIn("  pull_request:", trigger)
        self.assertNotIn("  push:", trigger)''')
write(p, s)
write('.github/pull_request_template.md', '''## Ticket and change

<!-- Link the ticket. Summarize the implemented behavior and scope. -->

## Tests

<!-- Focused tests, regressions, and CI. Do not paste SHA inventories or receipts. -->

## Risks and remaining work

<!-- Keep scientific/security/production limitations explicit. -->

## Development Hub impact

<!-- Complete one line and remove the other. -->
HUB_UPDATE_REQUIRED: <map refs and changed Hub source files>
HUB_IMPACT_NONE: <map owner and specific reason the Hub remains accurate>
''')
p = 'tests/cpu/test_code_authority.py'; s = read(p)
s = s.replace('''    assert _inline_run_commands(jobs["preflight"]) == (
        "./scripts/dev/ci_preflight.sh",
        "./scripts/dev/bootstrap.sh",
        "./scripts/dev/preflight.sh",
    )''', '''    assert _inline_run_commands(jobs["preflight"]) == ("./scripts/dev/ci_preflight.sh",)''')
s = s.replace('        "./scripts/dev/preflight.sh",\n        "./scripts/dev/ci.sh",', '        "./scripts/dev/ci.sh",')
s = s.replace('types: [opened, synchronize, reopened, edited, ready_for_review]', 'types: [opened, synchronize, reopened, ready_for_review]')
a = s.index('    assert (\n        jobs["preflight"].count('); b = s.index('    assert "cancel-in-progress:', a)
s = s[:a] + '''    assert "Install pinned uv" not in jobs["preflight"]
    assert "github.event.pull_request.draft == false" in jobs["preflight"]
    assert "dev_image_required == 'true'" in jobs["dev-image"]
    assert "--dev-image-required false" in jobs["merge-gate"]
    assert '[[ "${PREFLIGHT_IMAGE}" == "${derived_image}" ]]' in workflow
    assert "  push:" not in trigger_contract
    assert " edited," not in trigger_contract
''' + s[b:]
write(p, s)
p = 'tests/cpu/test_change_classifier.py'; s = read(p)
s += '''

@pytest.mark.parametrize(
    ("path", "required"),
    [
        ("carbon/measurement/models.py", False),
        ("tests/cpu/test_measurement.py", False),
        ("AGENTS.md", False),
        (".devcontainer/Dockerfile", True),
        (".github/workflows/ci.yml", True),
        ("scripts/dev/canonical.sh", True),
        ("uv.lock", True),
        ("pyproject.toml", True),
        ("requirements-dev.txt", True),
        ("unclassified-file", True),
    ],
)
def test_clean_image_follows_execution_environment(path: str, required: bool) -> None:
    assert classify_paths([path]).dev_image_required is required


def test_empty_manifest_retains_full_image_acceptance() -> None:
    assert classify_paths([]).dev_image_required is True


def test_runtime_source_still_requires_real_canonical_and_hub_success() -> None:
    statuses = {name: "skipped" for name in JOB_NAMES}
    for name in ("preflight", "canonical", "hub_validation"):
        statuses[name] = "success"
    assert not gate_failures(ChangeScope.RUNTIME_FULL, statuses, dev_image_required=False)
    for name in ("preflight", "canonical", "hub_validation"):
        for bad in ("skipped", "failure", "cancelled", ""):
            broken = dict(statuses, **{name: bad})
            assert gate_failures(ChangeScope.RUNTIME_FULL, broken, dev_image_required=False)
    assert gate_failures(ChangeScope.RUNTIME_FULL, statuses, dev_image_required=True)
    with pytest.raises(ValueError, match="bool"):
        gate_failures(ChangeScope.RUNTIME_FULL, statuses, dev_image_required="false")
'''
write(p, s)
p = 'docs/development/carbon_hub/orientation/AGENT_MAINTENANCE_CONTRACT.md'; s = read(p); pos = s.index('\n') + 1
s = s[:pos] + '''
> **OWNER-DX-03:** Batch Hub maintenance before acceptance. CI supplies run and
> revision identities; do not require human/GPT receipts or copied SHA/counter
> fields in PRs. Routine repair/testing detail stays in the PR. No per-slice
> Hub approval or post-merge evidence-seal commit is required.
''' + s[pos:]
write(p, s)
print('Owner-directed delivery changes prepared; no runtime science changed.')
