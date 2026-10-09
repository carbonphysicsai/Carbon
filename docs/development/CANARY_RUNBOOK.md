# Canary runbook (CANARY-01 S1)

**Status:** IMPLEMENTED and TESTED at fixture level (engineering evidence
only). Not run against the live path yet. Nothing here is security-qualified.

**Authority:** OWNER-CANARY-MINER-01, OWNER-CANARY-LIST-01 and
OWNER-SIGNER-TESTNET-AUTOCONFIRM-01. The plan is
[`CANARY_MINER_PLAN.md`](./CANARY_MINER_PLAN.md).

The canary is `carbon-canary`, UID 13 on testnet 567, hotkey
`5GBmHPBLwyKheugbtAVgxtWdX9YmWjfeCaBwmeFHr4rEWiB5`. Its submissions are
scored. It is never an incumbent, never in standings, never weighted and
never promoted.

## What the runner does

`python -m scripts.dev.canary.runner once --config <file>` runs one cycle
through the canary's own Launchpad MCP door, as an own-agent client. It uses
no LLM and spends nothing on models.

1. **`door`:** it reads the intake's public facts. They must name testnet 567,
   the configured Challenge and the configured receiver.
2. **`window`:** it reads `submission_rule.current_window`. A window that
   goes backward is a failure. While the hotkey's current window already
   holds an admitted canary submission, no new cycle starts: the run
   journals `DEFERRED` and sends no ping.
3. **The variant.** It claims the next entry of
   `scripts/dev/canary/variants.json`.
   - There are 320 kNN recipes: `neighbours` 1–64 at each `train_fraction`
     in 1.0, 0.95, 0.9, 0.85 and 0.8.
   - The cursor moves past a variant before its campaign is launched, so no
     variant is ever used twice.
   - When the list runs out, the runner stops with `variant_list_exhausted`.
     It never wraps.
4. **The campaign.** It launches an `agent: none` campaign (or resumes an
   interrupted one), practises once and freezes the recipe.
5. **`commit`:** it calls `carbon_commit`, then observes until the commitment
   reads back on chain. The signer auto-confirms. The runner never confirms
   or signs anything.
6. **`admission`, `scoring` and `verdict`:** it calls `carbon_submit`. To poll
   a queued result it submits again (LA-F18). A replayed submit polls the same
   submission id, with no second admission.
7. **`weights`** is S2. It is reported `NOT_BUILT`.

Every run appends one JSONL line to the journal: stage timings, closed codes,
the variant index and the submission id. A completed cycle within every set
deadline sends a success ping. A closed failure, or a set deadline missed,
sends a `/fail` ping whose body is `stage=<stage> code=<code> ...`.

A run that waits longer than `poll.max_wait_seconds` leaves the cycle open
(`PENDING`). The next run resumes it with the same campaign and variant.

**Limit.** The Launchpad's submit waits for a verdict, up to
`remote_submission.WAIT_S` (30 minutes), before it answers
`evaluation_queued`. The miner side therefore sees admission only when a
submit returns. If the verdict comes back on the first submit, admission and
scoring cannot be told apart, and the journal says so in each stage's `note`.

**Never:**
- a Docker prune;
- the AX42 or the distribution host;
- hidden material;
- a signature or a confirmation;
- any hotkey but a registered canary. A config naming another hotkey is
  refused before anything runs, and so is a Launchpad whose registered
  hotkey is another.

## Owner steps on carbon-fresh

These are attended runs first (plan §6). The checkout is `~/carbon`. The
steps match the owner sheet for the carbon-fresh lanes, where the ports are:

| Lane | Port |
|---|---|
| minerB | 8788 |
| minerA | 8789 |
| canary | 8790 |
| minerD to minerG | 8791 to 8794 |

1. **Install the canary's Launchpad.** This is a third install on the
   checkout, with its own state directory, port and user service. Since #843
   (LA-F15, LA-F16) it is safe beside minerA and minerB: it gets its own
   service name, leaves theirs alone, and reuses their images at the same
   revision.

   ```bash
   CARBON_STATE_DIR=$HOME/.carbon/canary ~/carbon/scripts/install_miner.sh --service --port 8790
   ```

2. **Set it up** in that Control Center (`http://127.0.0.1:8790`), or with any
   MCP agent using setup's status loop.
   - The hotkey is `carbon-canary`, already registered as UID 13.
   - Choose your own agent (`own-agent`) and CPU compute.
   - At review, pin valV2's battery intake and its receiver hotkey.
   - Note the MCP command setup shows under "Connect your agent". It holds
     the Python path and the checkout the config names.

3. **Write the auto-confirm allow-list** at
   `~/.config/carbon/autoconfirm-allowlist.json`, in the format of #861
   (`docs/development/MINER_EXTERNAL_SIGNER.md`).
   - It must be a regular file, not a symlink, yours, `chmod 600`, and at most
     4096 bytes.
   - One file serves five signers. It holds five hotkeys: the canary and
     minerD to minerG.
   - minerA and minerB are not on it. They stay manual.

   Its content is exactly:

   ```json
   {"schema": "carbon.signer.autoconfirm-allowlist.v1", "network": "testnet",
    "netuid": 567, "hotkeys": ["5GBmHPBLwyKheugbtAVgxtWdX9YmWjfeCaBwmeFHr4rEWiB5",
                               "<minerD>", "<minerE>", "<minerF>", "<minerG>"]}
   ```

4. **Start the canary's signer** with the flag, in its own terminal (the
   owner sheet runs it in the `signers` tmux session):

   ```bash
   ~/carbon/.venv/bin/carbon-miner-signer --wallet carbon-canary --hotkey default \
     --expect 5GBmHPBLwyKheugbtAVgxtWdX9YmWjfeCaBwmeFHr4rEWiB5 \
     --receiver <valV2's receiver hotkey> \
     --receiver <the subnet publisher's hotkey, until LA-F17> \
     --auto-confirm-commitments ~/.config/carbon/autoconfirm-allowlist.json
   ```

   - The publisher's `--receiver` is needed only until LA-F17 merges. Then
     drop it, so the signer signs only for valV2.

   - If the key is encrypted, you type its password there.
   - The signer reads the allow-list once, at start: restart it after changing
     the file.
   - It refuses to start off testnet 567, or for an unlisted hotkey.

5. **Write the ping file** (optional). Create a healthchecks.io check for the
   canary:
   - period: one cycle;
   - grace: your deadline, once it is set.

   Then, in an editor, write `~/.carbon/canary-runner/hc.env` with one line,
   `HC_CANARY=<the check's ping URL>`, and `chmod 600` it. Use an editor
   rather than `echo`, so the URL stays out of your shell history. The runner
   reads the file by path and never logs the URL. Set
   `healthcheck_env_file` to `null` to send no pings.

6. **Write the config** at `~/.carbon/canary-runner/config.json`, `chmod 600`.
   Every deadline stays `null` until you set it from measured runs
   (HUMAN_INPUT). A null deadline only measures and never alerts.
   - `poll` sets how often a run observes and how long one run waits. These
     are your choice, not deadlines, and they never alert.
   - Keep `max_wait_seconds` under the timer's period.
   - The config holds no key, password or URL secret.
   - Every path is absolute. Write `HOME` below as your home directory's
     absolute path: JSON does not expand `~`.

   ```json
   {
     "schema": "carbon.canary.config.v1",
     "hotkey": "5GBmHPBLwyKheugbtAVgxtWdX9YmWjfeCaBwmeFHr4rEWiB5",
     "launchpad": {
       "state_dir": "HOME/.carbon/canary",
       "python": "<the Python in setup's MCP command>",
       "checkout": "HOME/carbon"
     },
     "challenge": {"id": "battery-fastcharge-ageing-development-v1", "version": "1.0"},
     "intake": {"url": "<valV2's intake URL, as review pinned it>", "receiver": "<valV2's receiver hotkey>"},
     "variants": "HOME/carbon/scripts/dev/canary/variants.json",
     "cursor": "HOME/.carbon/canary-runner/cursor.json",
     "journal": "HOME/.carbon/canary-runner/journal.jsonl",
     "deadlines": {"door": null, "window": null, "commit": null, "admission": null,
                   "scoring": null, "verdict": null, "weights": null},
     "poll": {"interval_seconds": 30, "max_wait_seconds": 10800},
     "healthcheck_env_file": "HOME/.carbon/canary-runner/hc.env"
   }
   ```

7. **Run one cycle:**

   ```bash
   cd ~/carbon && .venv/bin/python -m scripts.dev.canary.runner once \
     --config ~/.carbon/canary-runner/config.json
   ```

   - It prints one JSON summary.
   - Exit codes:
     - 0: completed, pending or deferred;
     - 1: a failure, or a missed deadline;
     - 2: refused to run (config, variant list or cursor);
     - 3: another run holds the lock.
   - Each stage's timing is in the journal's last line. After three attended
     cycles, set the deadlines from those measurements (plan §8.5).

8. **Optional, later: the timer.** Run one cycle per producer rotation: 1080
   blocks, about 216 minutes. As systemd user units:

   ```ini
   # ~/.config/systemd/user/carbon-canary.service
   [Unit]
   Description=Carbon canary: one cycle

   [Service]
   Type=oneshot
   WorkingDirectory=%h/carbon
   ExecStart=%h/carbon/.venv/bin/python -m scripts.dev.canary.runner once --config %h/.carbon/canary-runner/config.json

   # ~/.config/systemd/user/carbon-canary.timer
   [Unit]
   Description=Carbon canary: one cycle per 1080-block rotation

   [Timer]
   OnBootSec=10min
   OnUnitActiveSec=216min
   Persistent=true

   [Install]
   WantedBy=timers.target
   ```

   Then run `systemctl --user enable --now carbon-canary.timer`. Unattended
   runs need the signer running with the flag. They also need its key unlocked
   on an always-on box, which is a test-only key (plan §3).

## When the variant list or contract changes

- The list records the contract digest it was compiled under. When the
  Challenge's contract changes, the runner refuses with `variant_list_stale`.
- To regenerate the list:
  - `python -m scripts.dev.canary.variants generate` compiles every entry and
    takes minutes;
  - `python -m scripts.dev.canary.variants check` verifies the committed file.
- A regenerated list has a new digest. The old cursor then refuses
  (`cursor_names_another_variant_list`), so point `cursor` at a new path.
  Changing the contract digest also changes every submission id, so no
  scored recipe is sent again.
