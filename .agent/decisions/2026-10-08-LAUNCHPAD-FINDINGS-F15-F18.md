## 2026-10-08 — LAUNCHPAD-FINDINGS-F15-F18: one service and one set of images per install, and a queued verdict is read by submitting again

**Authority.** The Launchpad acceptance run of 2026-10-08 on `carbon-fresh`
found LA-F15 to LA-F18
(`docs/development/evidence/launchpad-acceptance-2026-10-07/FINDINGS.md`).
Two installs share one checkout there: minerB in the default state
directory with `--service` on 8788, and minerA with its own
`CARBON_STATE_DIR` on 8789. The choices below are engineering choices
delegated to the Launchpad acceptance work. No scientific value, threshold,
gate, price or budget changes. No closed code is renamed, and no public
interface is removed.

**Decisions.**

1. **LA-F15: each state directory has its own user service.**
   - The default state directory keeps `carbon-control-center.service`, so
     existing installs and the documented commands keep working. Any other
     state directory gets `carbon-control-center-<basename>-<hash12>.service`,
     where the hash is of its full resolved path. A readable name with a hash
     was chosen over a systemd template (`@`), which would need a template
     unit and an instance escape for a path.
   - An install treats a unit as its own only when the unit has its own name
     and its `ExecStart` runs its own state directory. A unit is written only
     with `--service`, or when the install's own unit was written by an
     earlier `--service` install, which is how `--update` keeps restarting
     the service. An install never writes, reloads, enables, starts or stops
     another state directory's unit.
   - A unit written by an earlier installer can carry the default name but
     run another state directory, as `carbon-fresh`'s does now. Both
     installs leave it alone and say so. Only the default install run with
     `--service` takes it back.
   - Without `--port`, an update keeps the port its own unit already has.
     Before this, an update without `--port` rewrote the unit to 8788.
   - `CARBON_STATE_DIR` is made absolute before step 2 changes directory.

2. **LA-F16: reuse a current image; no per-install manifest copies.**
   - Before it builds the worker or the GPU worker, the installer asks
     `installed.current`. That check is setup's own source-tree test
     (`verify_current_worker` against `accepted_implementation`), plus two
     checks on the image: Docker still holds that image id, and the image's
     `org.opencontainers.image.carbon.c03.source-tree` label is the
     manifest's. If both hold, the image is used again. Any doubt or error
     builds the image, as before. The analysis builder already reuses an
     image keyed by its parent's id, so a reused worker keeps its analysis
     image too.
   - Per-state-dir copies were rejected, because the shared checkout is
     itself shared state. Moving it to another revision makes every
     install's images stale (`verify_current_worker`), copies or not.
     Two installs can both be valid only at the same source tree, and reuse
     covers exactly that case. Copies would add a second record for setup
     to keep consistent, and nothing more.
   - Remaining case: if Docker no longer holds an image, the next install
     builds a new one under the shared manifest path. Any other install
     sharing the checkout must then be run again (`--no-start`) to check
     setup against it. The journey document says so. No image is ever
     removed or pruned (LA-F7).

3. **LA-F17: proposal only; nothing implemented.** The local bootstrap and
   the local practice calls are signed for the publisher's hotkey. The
   proposal is to sign them for the miner's own hotkey instead, and to have
   the signer allow that receiver for MCP requests by default. It changes
   authentication, so it needs an owner decision and security review before
   anyone implements it. The reasoning is in FINDINGS LA-F17.

4. **LA-F18: the next step tells the truth; the poll is a follow-up.**
   - Observe and the campaign view read only the campaign's local state.
     Only a submit asks the intake for `battery_status`
     (`remote_submission.submit_and_wait`), polling for up to `WAIT_S`. A
     replayed submit polls the recorded submission id, and no second
     admission happens.
   - `NEXT_ACTIONS["evaluation_queued"]` now says that observe does not ask
     the validator, and to submit again (`carbon_submit`) to ask for the
     result.
   - Proposed follow-up, not done: observe could poll the intake once, for
     an epoch that has an `intake-submission-epoch-N.json` record and no
     verdict. That needs the miner's signer on every observe, and observe is
     read-only today, so it needs its own decision.

**Tests.** `tests/cpu/test_miner_install.py` gains:
- the second install without `--service` leaves the first unit alone;
- each state directory gets its own service, and updates restart only
  their own;
- a rewritten default unit is left alone;
- a second install at the same revision reuses the first one's images, and
  a gone image or a new revision builds them;
- `installed.current`.

`tests/cpu/test_launchpad_supervisor.py` gains the LA-F18 next step. Also
re-run: `tests/cpu/test_launchpad_never_prunes.py` and
`tests/cpu/test_miner_setup_after_install.py`.
