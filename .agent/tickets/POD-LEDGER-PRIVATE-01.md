# POD-LEDGER-PRIVATE-01 — keep pod accounting and limits off the public repository

**Status:** in progress.
**Primary Hub map_ref:** `SYSTEM/AGENT-EXECUTION`, `HUB_UPDATE_REQUIRED`.
**Authority:**
- the standing owner rule: the repository is public, so balances, spend
  figures, account identifiers, credentials and operator configuration are
  never committed;
- the owner's decisions of 2026-10-02, in session: pod rates and host machine
  ids stay private; campaign ceilings and the account balance floor are
  operator configuration; the narrative balance lines and spend totals are
  redacted; history is not rewritten (decided after the impact below);
- OWNER-DX-03.

## Outcome

`scripts/dev/exam_design/runpod/pod_control.py` committed each campaign's
full ledger to the repository: the RunPod account balance on every dispatch,
committed spend, the cap and each pod's rate. It also carried each campaign's
ceiling and the balance floor in source.
- Every event now goes to two ledgers. The full one is under
  `~/.runpod/accounting/<campaign>.jsonl` (mode 600). The repository copy is
  its projection: `PUBLIC_FIELDS`, an allow-list per event (pod ids, code
  refs, the image, plans, times, export digests). An event not listed is
  committed as its time and name alone.
- The budget and cap checks read the private ledger. They refuse when the
  repository holds a row the private ledger lacks, so spend is never
  undercounted. Recording a termination is never refused.
- `migrate-ledger` copies a campaign's full rows out and rewrites the
  repository ledger as its projection; it is idempotent. The exam-design,
  EV4 and ev4-regen ledgers are migrated here, row for row; ev4-regen arrived
  from main mid-review, with its ceiling in source, and that ceiling moved
  to the operator's configuration like the others.
- Ceilings and the floor come from `~/.runpod/campaigns.json`, through a
  `Limits` value only `operator_limits()` can build. Nothing that spends runs
  without it, and nothing is requested before it is read.
- `start`, `status`, `terminate` and dispatch print balances, spend, the cap
  and rates only with `--show-accounting`. Budget refusals carry no figures.
- `tests/cpu/test_pod_ledger_disclosure.py` fails if any committed
  `docs/development/evidence/*/accounting/*.jsonl` row carries a field outside
  the allow-list.
- Balance lines and spend totals in narrative documents are redacted.

## Working decisions

- **PLP-D1. Allow-list, not deny-list.** A new ledger field stays private
  until it is added to `PUBLIC_FIELDS`.
- **PLP-D2. A repository row is matched by containment.** It is present when
  a private row carries every one of its fields, so a later change to the
  allow-list never makes committed rows look missing.
- **PLP-D3. Frozen and pinned records are not edited.** The EV4
  pre-registration's frozen sections, its contract and freeze manifest, and
  other pre-registrations keep their figures. EV4's post-run results record
  the change instead.
- **PLP-D4. Planning tables stay.** Forward-looking budget plans (allocations,
  estimates, run matrices) are left for the owner; this ticket removes
  balances and actual spend.

## History is not rewritten

The owner first approved a rewrite, then decided against it on 2026-10-02
after seeing its impact. A rewrite from the first committed ledger would
change the identity of every later commit: 847 commits. Committed evidence
cites those SHAs (ledger `ref`s, the code refs pods fetched, Hub authority
pins, the Ask Carbon release, decisions), at least 1,071 full-length
citations in 59 files on main. It would also force-push 161 branches. The
figures already committed are treated as disclosed.

## Human input required

- **Workbench relay.** `EXAM_DESIGN_CAMPAIGN_RESULT.md` (a balance line) and
  `EXAM_DESIGN_CAMPAIGN_SPECIFICATION.md` (the ceiling formula) are pinned by
  digest in the Workbench relay and the Ask Carbon release. The Pilot
  Designer deliberately shows the campaign's billed compute. Redacting them
  needs a Workbench and website rebuild, and a decision on that display.
- **Hub events.** `BATTERY-EV4-01` and `MQ-008-R1-SIMULATED-VALIDATORS-01`
  carry spend figures. The Hub validator refuses any rewrite of a historical
  event.

## Definition of done

- `tests/cpu/test_pod_ledger_disclosure.py`, `test_challenge_pools_cloud.py`
  and the pod tests in `test_battery_engineering_value_ev4.py` pass.
- No committed ledger row carries a field outside the allow-list.
- Black, ruff, hygiene and the Hub pass.
