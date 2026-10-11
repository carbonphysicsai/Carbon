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

## LA-F15: a second install rewrites the first install's systemd unit

- **Cell:** `carbon-fresh`, 2026-10-08. Two installs share the checkout
  `~/carbon`. minerB has the default state directory, `--service`, and port
  8788. minerA has `CARBON_STATE_DIR=$HOME/.carbon/minerA`, `--no-start` and
  `--port 8789`.
- **Failure:** minerA's install, without `--service`, rewrote
  `~/.config/systemd/user/carbon-control-center.service` to minerA's state
  directory and port. minerB's running service escaped only because the unit
  was not reloaded. A restart or a reboot would have started minerA's
  Control Center in minerB's place.
- **Cause:** the installer had one fixed unit name. It treated any existing
  unit as its own, so it rewrote and restarted that unit whether or not
  `--service` was given.
- **Fix:**
  - Each state directory has its own service. The default one keeps
    `carbon-control-center`; any other is
    `carbon-control-center-<directory>-<hash>`.
  - A unit is written only with `--service`, or when this install's own
    unit, which runs its own state directory, already exists. An install
    never touches another state directory's unit.
  - A default unit that runs another state directory is left alone, with a
    note. The default install with `--service` takes it back.
  - The installer prints its own service's restart, stop, status and log
    commands.
  - `--update` stops (in the hint) and restarts its own unit, and keeps its
    unit's port.
  - `FRESH_MINER_JOURNEY.md` gives the per-install commands.
- **On `carbon-fresh` now:** `carbon-control-center.service` still runs
  minerA's state directory. Run minerB's install with `--service` to take
  it back.
- **Decision:** `.agent/decisions/2026-10-08-LAUNCHPAD-FINDINGS-F15-F18.md`.
- **Status:** fixed in the PR that carries this entry.

## LA-F16: installs sharing a checkout overwrite each other's image manifests

- **Cell:** the same two installs, 2026-10-08.
- **Failure:**
  - Both installs record `~/carbon/.carbon-artifacts/c03-worker-image.json`
    and `accelerator-worker-image.json`, at fixed paths.
  - minerA's install rebuilt both images and overwrote both manifests. A
    rebuild at the same revision is a new image id: the worker went from
    `0dd482db` to `28adde3c`, and the GPU worker from `7b485044` to
    `3d8daedd`.
  - minerA's record then paired an analysis image whose parent was an
    earlier worker build (`575cc2b0`) with the overwritten worker manifest
    (`28adde3c`). Setup refused it, first `analysis_image_unverified`, then
    `compute_check_is_stale`.
  - minerB's recorded compute check also silently stopped matching the
    manifests.
- **Cause:** every install rebuilt every image, even when the existing
  image was built from the same source tree and Docker still held it.
- **Fix:**
  - Before it builds the worker or the GPU worker, the installer asks
    `installed.current`. That check is setup's own source-tree test, plus
    two checks on the image: Docker holds that id, and its source-tree label
    matches the manifest. If both hold, the image is used again, so a second
    install at the same revision builds nothing.
  - The analysis image is keyed by its parent, so it is reused with its
    worker.
  - Per-install manifest copies were not added. Moving the shared checkout
    makes every install's images stale anyway, so copies would protect no
    valid state. The reasons are in the decision.
  - Nothing is removed or pruned.
- **Still true:** a gone image, or a new revision, is built again under the
  shared path. Every other install on that checkout must then be run again
  (`--no-start`). The journey document says so.
- **On `carbon-fresh` now:** installing this fix moves the checkout, so the
  first install after it builds new images. Then run the other install with
  `--no-start` and its own `CARBON_STATE_DIR`, with each Control Center
  stopped. It reuses those images, and setup checks both installs against
  the same ones.
- **Decision:** `.agent/decisions/2026-10-08-LAUNCHPAD-FINDINGS-F15-F18.md`.
- **Status:** fixed in the PR that carries this entry.

## LA-F17: the local bootstrap signs for the subnet publisher

- **Cell:** `carbon-fresh`, 2026-10-08. The miner's signer was started with
  `--receiver <their validator>` only. Preparing a campaign was refused with
  `signer_refused`.
- **What the signature authenticates:**
  - `research_campaign.requester` (used by battery, motor and cold plate),
    `standard_cli`'s bootstrap and every local practice call
    (`research_tools`, and the Burgers `service`) sign a `btauth/1` request
    for `/carbon/v1/mcp` with `receiver=connection.publisher`, UID 0 of
    subnet 567.
  - The verifier is `transport.AuthenticatedGateway`, built inside
    `LocalMinerConnection` in the Control Center's own process. Its receipt
    journal is the campaign's `research-auth/transport.sqlite3`.
  - It proves that the miner's signer holds the registered hotkey: a fresh
    signature, the registration snapshot, and the journal's nonce and replay
    checks. It then derives the campaign owner from the hotkey, coldkey and
    registration block (`requester_for_receipt`).
  - The receiver is not part of the owner. It is checked only to be
    registered and to match the signature.
- **Who else sees it:** nobody off the machine. The body and headers go
  in-process to `gateway.receive`; the journal and the evidence ledger are
  local files. A submission to a validator intake is a separate message,
  signed for that intake's own receiver (`remote_submission`).
- **Why it matters anyway:** a publisher-addressed signature on
  `/carbon/v1/mcp` is a valid credential at the publisher's own endpoint,
  within the nonce window. To prepare a campaign today, the miner's signer
  must be willing to sign that for any local process of the same user.
- **Proposal (narrowest change; not implemented):**
  - Address the local gateway, and the local calls signed for it, to the
    miner's own hotkey. That is one receiver field in `LocalMinerConnection`
    and the four local sign sites. `publisher` stays for the chain context
    and the registration check.
  - Have `carbon-miner-signer` sign `mcp` requests whose receiver is its own
    hotkey, even when `--receiver` restricts every other receiver. It never
    does so for `answer-key`.
  - Optionally, give local calls their own path (for example
    `/carbon/v1/local-mcp`) and let only the local gateway accept it.
- **Security reasoning:**
  - Proof of possession stays. The gateway still verifies a fresh signature
    from the registered hotkey.
  - The owner derivation does not change, so frozen campaigns and their
    owners need no migration.
  - A self-addressed signature is refused by every validator and by the
    publisher, which check `receiver` against their own hotkey
    (`AUTH_WRONG_RECEIVER`). It cannot be replayed off the machine.
  - The signer can then be limited to the validators the miner chose.
  - One residual: a service that runs under the miner's own hotkey would
    accept a self-addressed signature. The separate local path closes that.
  - Rejected alternative: trusting the hotkey the signer reports, without a
    signature. That drops proof of possession and leaves unauthenticated
    receipts in the journal.
- **What would break:** tests that pin `receiver=publisher` on these calls,
  and campaigns prepared by an older Carbon that resume against a newer
  signer. Their journals hold publisher-addressed receipts, which stay
  valid as history. Each new request is signed fresh, so nothing
  re-verifies them. The local battery deployment's submit
  (`battery.campaign`, `gateway.receive` for a validator on this machine)
  addresses a validator and should keep a validator receiver. It is not
  part of this change.
- **Decision needed (owner):** whether to adopt this proposal. It changes
  authentication, so it needs security review before it is implemented.
- **Status:** open; proposal only.

## LA-F18: observe never fetches a queued verdict

- **Cell:** `carbon-fresh`, 2026-10-08. `carbon_submit` returned
  `evaluation_queued` (intake outcome `QUEUED`), and the next action said
  "Observe later". The sealed verdict arrived only through a replayed
  `carbon_submit`.
- **Answer:** observe never asks the validator.
  - Observe (`runner.observe_admitted`) and the campaign view
    (`campaign_view.ledger_view`) read only the campaign's local state and
    its `last_refusal`. The supervisor does not poll either.
  - Only a submit reaches `battery_status`, through
    `battery.campaign.submit_through_intake` and then
    `remote_submission.submit_and_wait`. It polls for up to `WAIT_S`, 30
    minutes, then answers `evaluation_queued`.
  - A replayed submit finds `intake-submission-epoch-N.json` and only polls
    the recorded submission. It sends no second admission, and the
    commitment gate does not ask again.
  - So submitting again is today's only way to read a queued verdict.
- **Fixed here (the honest minimum):**
  - The `evaluation_queued` next step now says that observe does not ask
    the validator, and to submit again (`carbon_submit`) for the result.
  - `FRESH_MINER_JOURNEY.md` says the same at step 10.
- **Proposed follow-up:** for an epoch with a recorded submission and no
  verdict, observe, or the supervisor on a timer, would poll the intake
  once. That puts the signer on the observe path, which is read-only today,
  so it needs its own decision.
- **Fixed (2026-10-11, the Test Lead's ruling):** observe now asks.
  - In a campaign where the miner selects, observe reads the open epoch's
    recorded submission once, only when it has no verdict, at most once a
    minute per epoch (the read's time is recorded first,
    `intake-status-read-epoch-N.json`), and only when submit itself would be
    admitted and nothing runs for the campaign
    (`scripts/dev/miner_launchpad/verdict_read.py`).
  - The read is signed through the signer's new read-only kind,
    `status_read` (`carbon_miner_signer/status_read.py`). The signer is sent
    the request body too and signs only one `battery_status` read of one
    submission id, unasked; it never reaches the commit path or the
    auto-confirm allow-list. Observe never asks for `sign` or `commit`.
  - A verdict is stored as a replayed submit stores it (`record_verdict`,
    `after_stored_verdict`), so observe, the campaign view and the journey
    show it. The `evaluation_queued` next step and `FRESH_MINER_JOURNEY.md`
    step 10 no longer say to submit again.
- **Decision:** `.agent/decisions/2026-10-08-LAUNCHPAD-FINDINGS-F15-F18.md`.
- **Status:** fixed. Touches the signer: the owner's security review is
  needed before merge.

## LA-F19: a campaign frozen on an old revision fails its submit untyped

- **Cell:** `carbon-fresh`, 2026-10-10. The minerH and minerI incentive
  campaigns were frozen while the shared checkout was at `93875b7dc`. The
  checkout then moved to `b2eb2e222` and the installer re-recorded each
  profile (`accepted_revision` at the new revision). `carbon_submit` was
  answered SUBMITTING, then the campaign went INTERRUPTED with
  `last_refusal.code` `operation_interrupted`. Its `interruptions.jsonl`
  read `{"code": null, "error_type": "builtins.ValueError", "stage":
  "operation"}`.
- **Cause:**
  - The operation thread prepares the campaign on this checkout
    (`research_campaign.prepare`, then the Challenge's own prepare).
  - `accepted_implementation` passed: the checkout was the accepted one.
  - The Challenge's prepare then compared the frozen runtime, which embeds
    the frozen `implementation`, with the runtime this checkout composes:
    `battery.campaign.prepare_battery` raised a bare `ValueError("configured
    runtime differs from the battery runtime")`. Cold plate and motor have
    the same check.
  - A bare ValueError carries no code, so the thread recorded an untyped
    interruption.
- **Fix:**
  - Practice, freeze and submit are refused before the operation starts,
    with the closed code `campaign_frozen_on_old_revision`
    (`runner.frozen_revision_refusal`), when the frozen manifest names a
    revision other than the profile's `accepted_revision`.
  - `research_campaign.prepare` raises the same code as `OperationRefused`
    before any Challenge's checks, so the thread records a named refusal,
    never an untyped interruption.
  - The refusal catalog's next step, the same at every door: launch a new
    campaign, practise and freeze the same recipe, then submit. The hotkey's
    on-chain commitment still applies, since its digest binds the
    Challenge, contract and strategy, not the campaign.
  - Resume already refused this as `profile_changed_since_launch` and is
    unchanged. Observe and reads stay open.
- **Recovery used:** a new campaign with the same recipe, under the same
  commitment.
- **Status:** fixed in this PR.
