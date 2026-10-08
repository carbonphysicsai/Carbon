# Launchpad acceptance findings (LAUNCHPAD-ACCEPT-01)

This register lists every defect a real acceptance cell, or Graphite as the
first heavy user, hits. Each entry gives the cell, the closed code or failure,
the cause, and the slice or PR that fixes it. The plan is
`docs/development/LAUNCHPAD_ACCEPTANCE_PLAN.md`.

## LA-F1: `install_miner.sh --gpu` stops with "Permission denied" on a clean clone

- **Cell:** F01 (fresh-machine install, plan §4 step 1), on the `carbon-fresh`
  WSL distro, 2026-10-07.
- **Failure:** the C-03 worker image built. Then `install_miner.sh` line 269
  ran `./scripts/dev/accelerator_worker_image.sh` and failed with
  `Permission denied`; the installer exited 126.
- **Cause:** the script is mode 100644 in the git index, so no clean clone
  could ever run the `--gpu` path. `tests/cpu/test_miner_install.py` writes
  its stand-in scripts as 0755, so it could not see the checkout's mode.
- **No miner workaround:** a local `chmod` dirties the checkout, and the
  installer then refuses to run.
- **Fix:**
  - the script is now 100755;
  - `tests/cpu/test_installer_script_modes.py` reads the index and asserts
    that the installer and every script it runs directly, on every path,
    `--update` included, are 100755.
- **Checked and not affected:**
  - `julia_worker_image.sh`, `julia_worker_service.sh` and
    `workbench_science_checks.sh` are 100644, but every caller runs them
    with `bash`;
  - the accelerator script's own helpers are also run with `bash`.
- **Noted, outside the installer:** `workspace_preflight.sh`,
  `c07_development_vertical.sh` and `tpu_worker_image.sh` are 100644.
  - The first two have usage lines that say to run them directly.
  - No miner path runs them.

## LA-F2: the installer leaves the analysis image and GPU worker dangling

- **Cell:** F01 run 2, on `carbon-fresh`, 2026-10-07, revision `f1dd652debdf`.
- **Observed:** the installer recorded the analysis image `2872bb294218` and
  the GPU worker `8776a915560b` by image id, and tagged neither.
  `docker images -f dangling=true` lists both. The C-03 worker parent is
  tagged (`carbon-cw1d4-parent:<id>`).
- **Risk:** a `docker image prune` deletes both images without a prompt, and
  so does Docker Desktop's "clean up". Both are routine disk-space steps.
  Setup would then find the images missing and need a reinstall. A remote
  `ssh-docker` send-worker would also have nothing to send.
- **Fix:** each image a miner host builds is named by its own id, as the
  worker parent already is:
  - `carbon-analysis:<id>` (`research_image.local_tag`);
  - `carbon-gpu-worker:<id>` (`accelerator_worker_image.sh`).

  Each name is checked to point at its image, and everything still verifies
  by image id. An install made before the fix gets its analysis image named
  by the next install, and the GPU worker is rebuilt on every install
  anyway. Release builds are unchanged.
- **Status:** fixed in the PR that carries this entry.

## LA-F4: a Graphite launch without both provider ceilings is queued, then dies untyped

- **Cell:** a Graphite launch on the fresh machine, 2026-10-07.
- **Failure:**
  - `carbon_launch` with `agent: graphite` and `budget.ceilings`
    `{epochs: 1, provider_nanodollars: 500000000}` was admitted and QUEUED.
  - The run then died in `carbon/battery/campaign.py` `graphite_plan` with a
    bare `ValueError` ("needs finite provider_attempts and
    provider_nanodollars ceilings").
  - The interruption recorded `builtins.ValueError` with code null. The
    miner saw `campaign_interrupted` and "Resume", and a resume can never
    succeed.
- **Cause:** the launch doors did not check what the plan needs. The plan
  needs both `provider_attempts` and `provider_nanodollars` as whole numbers,
  and its refusal carried no closed code.
- **Fix:**
  - `agent_plan.finite_ceilings` is now the one predicate. The plans and the
    launch doors both read it.
  - Both doors refuse such a launch `graphite_ceilings_required`, field
    `budget`, before the chain is read or anything is queued. The next step
    names both ceilings.
  - A plan that still meets one raises the typed `CeilingsRequired`, so its
    interruption records the code.
  - Decision: `.agent/decisions/2026-10-07-LAUNCHPAD-FINDINGS-F4-F6.md`.

## LA-F5: resuming a campaign interrupted before its manifest froze is refused the key

- **Cell:** the resume after LA-F4's interruption, 2026-10-07.
- **Failure:** `carbon_resume` was refused
  `model_provider_credential_not_configured`. The runner profile has
  `provider_credentials.engy-chat`, and the launch named
  `model_provider: engy-chat`.
- **Cause:**
  - `_frozen_credential` reads the provider from the frozen manifest, and
    there was none yet.
  - It fell back to the pinned default provider. `foreign_default_key`
    refused it, because the default key slot names engy-chat's key.
- **Fix:**
  - Before a manifest exists, the resume check now uses the provider the
    admitted launch recorded (`runner.launch_provider`, read with
    admission's own rule).
  - Its key is checked for that provider only.
  - With nothing recorded, the pinned default's rule stands, and it still
    fails closed.

## LA-F6: the Control Center service cannot reach Docker on a fresh WSL distro

- **Cell:** F01 (fresh-machine install) with `--service`, on the
  `carbon-fresh` WSL distro, 2026-10-07.
- **Failure:**
  - The owner added the user to the `docker` group after the user's systemd
    manager had started.
  - `install_miner.sh --service` checked Docker from the interactive shell,
    which has the group, and passed.
  - The service ran without the group. `systemd-run --user --wait id -Gn`
    lacks `docker`, and `docker info` there is "permission denied".
  - The worker doctor then failed in the service and every user unit:
    `accepted numerical host unavailable`.
- **Cause:** the installer asked the shell, not the manager that runs the
  service.
- **Fix:**
  - With the service, step 1 asks the user manager itself to run
    `docker info` (`systemd-run --user`), before anything changes.
  - If the manager cannot reach Docker, the install stops with the fix and
    what that fix stops. On WSL, `wsl --terminate <distro>` from Windows.
    Elsewhere, `sudo systemctl restart user@<uid>.service`.
  - `docs/development/FRESH_MINER_JOURNEY.md` says so at the Install step.

## LA-F3: the Launchpad's prepared registration command was not the form that ran

- **Cell:** F03, on `carbon-fresh`, 2026-10-07.
- **Observed:** `carbon_onboarding_prepare` gave
  `btcli subnet register --netuid 567 --network test --wallet.name <w> --wallet.hotkey <h>`,
  marked UNVERIFIED.
  - The owner registered minerB (UID 4, extrinsic 8173606-6) with btcli
    9.23.2's documented form,
    `btcli subnets register --netuid 567 --wallet-name <w> --hotkey <h> --network test`.
  - btcli 9.23.2's `--help` lists `subnet` as an alias, and `--wallet.name`
    and `--wallet.hotkey` as option aliases, so the Launchpad's form is valid
    syntax. It was never run.
- **Proposed fix:** prepare the form that ran, and replace the UNVERIFIED
  note with the btcli version it ran on.
- **Status:** open, minor.

## LA-F7: never prune Docker on a shared host

- **Incident (2026-10-07, overnight):** a `docker image prune` on the
  shared main WSL host deleted Data Collection's motor stage-1 images, and
  100 solves with them.
- **Not caused by this acceptance:**
  - No step, script, test or agent of the Launchpad acceptance ran a prune.
    The only image command run was a read-only
    `docker images -f dangling=true`, inside `carbon-fresh`'s own engine.
  - On main, no miner-path code calls prune.
- **Rule** (Test Lead, 2026-10-08):
  - No Launchpad step, test or clean-up ever prunes on a shared host.
  - Pruning happens only inside a miner's own dedicated engine (here
    `carbon-fresh`), and only for images Carbon built, removed by their tag.
- **Guard:** `tests/cpu/test_launchpad_never_prunes.py` fails if any
  command on the miner path, or any of its tests, runs `docker … prune`. The
  miner path covers the installer and image builds, setup, campaigns, the
  remote transports and the signer.
- **LA-F2's fix fits the rule:** it names the images, so they can be kept
  or removed by tag; it never prunes.
- **Status:** guard added.

## LA-F8: Graphite on the default Engy model stops at the context ceiling before it plans

- **Cell:** the Launchpad smoke run on `carbon-fresh`, 2026-10-08 (install
  `f1dd652de`). Campaign `14d573bb4c425ecf12c185dd223f7ece`: Graphite,
  `graphite_mode: BUILD` with no plan, `engy-chat` /
  `deepseek-v4-flash-0731`, CPU practice, ceilings `{epochs: 1,
  provider_nanodollars: 500000000, provider_attempts: 100}`, no
  `model_settings`.
- **Failure:**
  - The campaign COMPLETED after 34 provider attempts, USD 0.0189 and 12
    research trials, but both Graphite stages ended STOPPED with code
    `context_ceiling`. No plan was written and nothing was frozen.
  - `plan` stopped before its third turn. Turn 0 reported 10,274 input
    tokens and turn 1 13,562. Turn 1 made five calls whose results came to
    78,501 bytes: the `capabilities` (30,388), `roadmap` (22,411),
    `objective` (12,177) and `reference_method` (9,203) documents and a
    `lit_search` (4,322). Compaction could not apply: it needs more than
    six turns.
  - `build` ran 31 turns and compacted once, before turn 14. Turn 30 (46,535
    input tokens) read the 22,411-byte `roadmap` again. Before turn 31 a
    compaction was due, but the compaction request itself did not fit:
    "context admission ceiling: the compaction request does not fit; no
    history silently discarded".
- **Cause:**
  - The limit is Carbon's default `max_input_tokens`, 65,536
    (`model_provider.DEFAULT_SETTINGS`), not the model's capacity. The miner
    set no `model_settings`, so the admission ceiling was 65,536 - 4,096 =
    61,440 tokens and the compaction trigger 85% of it, 52,224.
  - The loop bounds a request at the provider's last reported count plus one
    token for every byte added since (`research_agent.input_token_bound`).
    The bound is sound for any tokenizer, but on this content it is about six
    times the real growth: the build's turn 1 added about 59.5 KB of results
    and the reported count rose by 9,414 tokens. The plan's third request
    would have been about 26,000 real tokens; the bound put it above 61,440.
  - One turn can add more bytes than the 9,216 tokens between the trigger
    and the ceiling: Graphite reads whole discovery documents, several per
    turn under the parallel-call rule. A compaction request carries the whole
    history plus its note, so after such a turn it cannot fit either.
  - The model's figure is right. Engy publishes a 1,048,576-token context
    for `deepseek-v4-flash-0731`, recorded on 2026-10-04 (GRAPHITE-D34). The
    budget arithmetic is as designed (GRAPHITE-MINER-S1).
  - This is GRAPHITE-D34's defect again. Internal Graphite hit it in phase 3
    session 2, and the owner's ruling gave its whole-context roles the
    model's whole published window. The miner edition runs on the miner's own
    selection, so it never got that window.
- **Fix in this PR** (engineering, additive; no default changes and nothing
  new is refused):
  - The published context table is one record in the miner-facing provider
    registry (`model_provider.ENGY_CONTEXT_TOKENS`, `published_context`).
    Internal Graphite's `roles` re-exports it with its values unchanged.
  - Before a launch spends, the capability document's model block now
    carries `input_window`: the launch field, its bounds, the default, the
    admission ceiling at the default, and each offered model's published
    context. The launch options' `graphite` block carries the same advisory.
    Both use the closed code `graphite_input_window_too_small`, and the
    refusal catalog gives its next step: set
    `model_settings.max_input_tokens` higher, up to the model's published
    context, knowing each call is reserved at that window.
  - The stop code `context_ceiling` now has its own next step in the catalog
    instead of the generic fallback.
  - Tests: `tests/cpu/test_launchpad_findings_f8_f9.py`.
- **Open, owner decision:** whether a Graphite launch should get a larger
  input window by default, and how large.
  - A miner can set `model_settings.max_input_tokens` today, up to 1,048,576.
    With the default 131,072-token output cap, 917,504 keeps a request and
    its reply inside the model's context.
  - Giving Graphite that window by default, as D34 did internally, raises
    each call's reservation on the default model from about USD 0.0147 to
    about USD 0.053. A FULL launch at the default 10% research share would
    then be refused `research_share_too_small` below a budget of about USD
    0.53.
  - The other routes are to require the miner to choose a window before a
    Graphite launch, or a compaction rule v2 that bounds how many bytes one
    turn may add. Each changes behaviour or a frozen rule, so none is taken
    here.
  - Decision: `.agent/decisions/2026-10-08-LAUNCHPAD-FINDINGS-F8-F9.md`.
- **Status:** advisory fixed in the PR that carries this entry. The default
  window is open and needs an owner decision.
  2026-10-08: decided. A new Graphite miner-edition plan's default window is
  now the model's published window (its context less the output cap,
  917,504 tokens on the default Engy model), under
  OWNER-GRAPHITE-MINER-INPUT-WINDOW-01.

## LA-F9: every practice result was withheld from Graphite as protected material

- **Cell:** the same campaign as LA-F8.
- **Failure:** the campaign's refusals list holds five
  `REFUSED_PROTECTED_MATERIAL_IN_RESULT` entries, at note sequences 16, 23,
  26, 30 and 44. Each was the Constructor's
  `carbon_research_v2__start_research_task`:

  | Seq | Call | What it asked | Result withheld |
  |---|---|---|---|
  | 16 | `epoch-1-tool-008` | practice, the scaffold MLP | 3,525 bytes |
  | 23 | `epoch-1-tool-012` | practice, a larger MLP | 4,071 bytes |
  | 26 | `epoch-1-tool-014` | practice, a minimal MLP | 3,464 bytes |
  | 30 | `epoch-1-tool-018` | `read_file` of its own practice trial file | 3,906 bytes |
  | 44 | `epoch-1-tool-026` | practice, to see if practice still worked | 4,071 bytes |

  - Each practice ran and spent its trial slot; only its result was
    withheld. Every result is `carbon.battery.practice-feedback.v3` with
    fields `adaptively_seen`, `backbone`, `backend`, `challenge`,
    `final_exam` (false), `fit`, `official_eligible` (false), `provenance`,
    `recipe`, `recipe_digest`, `safety`, `schema`,
    `scientific_qualification` (false), `seed_source`, `summary` and
    `worker`. The `read_file` result carried the same document as text.
- **Cause: false positives.**
  - The classifier is Graphite's shared check
    (`graphite.protected_material.protected`), run by the miner toolbox on
    every result. It refuses any string that names a Graphite marker or
    matches the checkout deny rule (`boundaries._denied`).
  - In all five results the one match was the deny prefix
    `docs/development/evidence/`, at `safety.material.path`. That field
    holds the public PRACTICE set's own repository path,
    `docs/development/evidence/exam-design-2026-09-24/refs-a-part2/out/records.jsonl`,
    with its sha256 (`battery.practice.PRACTICE_SOURCE_PATH`). No marker
    matched.
  - That file is committed in the public repository. It holds the 200
    public practice references, adaptively seen practice evidence that is
    not the exam (invariant 12); the exam's private pools come from the seed
    service. The result names its path and digest, not its content. The
    check's own `result_material` classes the match `attack_target`, not
    protected material.
  - The motor and cold-plate practice results pin their practice paths the
    same way, so every Challenge's practice results were withheld.
  - The agent was starved of its own results. It re-ran practice to see
    whether practice was blocked, then read the same trial files through
    `run_python`, whose printed text did not trip the prefix rule.
- **Fix in this PR:**
  - `protected_material.PUBLIC_PRACTICE_PATHS` names the three public
    practice paths. A string exactly equal to one is exempt from the
    checkout deny rule, and only from that rule.
  - Still refused: every Graphite marker (seeds, draw ids, hidden cases, the
    sealed tuning set, verification references, validator state, canaries);
    any other path under the evidence prefix, including the battery
    reference pools and EV5; the public path with anything before or after
    it, or in another case; and every other deny rule.
  - A test holds each exempt path to its Challenge's own constant. Re-run
    read-only over the campaign's 31 recorded research results, the fixed
    check withholds none of them; the old check withheld exactly the five
    above.
  - Follow-up, not changed here: the result refusal says `dispatched:
    false` although the practice ran and spent its slot. Carbon's attack
    analysis reads `dispatched: false` as Graphite's own refusal, so
    changing it needs its own review.
  - Security: the change narrows a disclosure filter, so it needs
    security review before merge.
  - Decision: `.agent/decisions/2026-10-08-LAUNCHPAD-FINDINGS-F8-F9.md`.
- **Status:** fixed in the PR that carries this entry, pending security
  review.
  2026-10-08: security-accepted by the owner under
  OWNER-LA-F9-SECURITY-ACCEPT-01. The `dispatched: false` follow-up stays
  open.

## LA-F10: the Launchpad cannot practise on Carbon's released worker images

- **Cause:**
  - Both remote and local setup accept a worker only when it was built from
    the install's exact source revision. `research_campaign.verify_current_worker`
    compares the worker's source-tree digest with the install's.
  - `scripts/dev/worker_image_release.py pull` exists, but no miner install
    path calls it.
  - So an install on current main refuses the released, mainnet-shaped
    images (`worker-images-v1`), which were built from an earlier revision.
- **Proposed fix:** `install_miner.sh --release <tag>`, which checks out the
  release tag and pulls the images by digest. Local builds remain the
  fallback.
- **Status:** open. It needs a release cut after the commit operation
  merges.

## LA-F11: own-agent campaigns refuse every practice for a model key they never use

- **Cell:** C3 on `carbon-fresh`, 2026-10-08. An own-agent campaign
  (`agent: none`, id `9cd07892c064f4b9f4f40e8ac1297a7d`) refused both of its
  practices with `model_provider_credential_not_configured`.
- **Cause:**
  - Setup wrote the Engy key as `provider_credentials.engy-chat` and also as
    `paths.api_key_file`.
  - A campaign with no selection schema gets the pinned default provider's
    rule in `runner.RunnerAdapter._frozen_credential`. There
    `foreign_default_key(cfg)` is true, so the check refuses.
  - Yet an `agent: none` campaign calls no model, and
    `battery.campaign.prepare` opens no key for it.
- **Impact:** any miner who set up a non-default provider is blocked on the
  whole own-agent and MCP-client path: A3, A4 and the first real submit, A5.
- **Fix:** for agent `none`, the credential check returns no key, read from
  the frozen manifest or, before it freezes, from the admitted launch.
  Campaigns whose Carbon agent calls a model keep the refusal. It is written
  and tested (107 passed) but not yet committed.
- **Status:** fix pending.
