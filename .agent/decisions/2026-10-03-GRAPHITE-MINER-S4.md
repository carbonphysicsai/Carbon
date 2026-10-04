## 2026-10-03 — GRAPHITE-MINER-S4: Graphite in the Launchpad (agent choice, launch fields, Library, views)

**Authority.** OWNER-GRAPHITE-MINER-01 (Graphite replaces the `autonomous`
agent for new Launchpad campaigns; Research, Build and Full modes; a Library
with pins, bans and imports; focused hunts; money and time as the limits),
within the boundaries OWNER-LAUNCHPAD-PROD-01 lists and the answers
OWNER-LAUNCHPAD-PROD-02 gave (no Carbon-imposed output cap; the closing
Control Center pauses its campaigns; one combined delivery). The choices
below are engineering decisions delegated to slice S4 of the agreed design.
No scientific value, threshold or gate is set or changed here.

**Decisions.**
1. **The autonomous agent is refused for new launches, after the replay
   gate.** `runner.replayed` looks the key up first. A launch recorded under
   `autonomous` (or setup's `carbon-autonomous`) replays as it was, reading no
   chain; a new one is refused `autonomous_agent_replaced` before the chain is
   read. `launch_admitted` refuses it again, so no other path admits one.
   - The browser door still reads a body that names no agent as `autonomous`,
     as it always has. A browser launch recorded that way keeps its digest and
     replays. A new one is refused, and the page names its agent.
   - A queued launch is still carried out from its record
     (`_recorded_launch`), and a frozen autonomous campaign still resumes and
     runs `run_agent` unchanged.
   - `options` and the capability document offer `none` and `graphite`;
     `autonomous` stays a value the MCP schema accepts, only so a recorded
     launch replays through that door.
2. **Graphite's launch fields** are `graphite_mode`, `research_share`, `plan`,
   `hunt` and `limits`, validated by `runner.graphite_launch` before anything
   is digested or created:
   - Defaults: mode FULL; research share 0.10 for FULL, none otherwise; no
     hunt unless asked (`hunt: {}` asks with Carbon's derived queries and 200
     records); no caps, so only the campaign's own ceilings bind.
   - A field with another agent is refused
     `graphite_fields_need_the_graphite_agent`. A field the mode does not read
     is refused `graphite_field_not_used_by_mode`: a share outside FULL, a plan
     outside BUILD, a hunt where no Planner runs (BUILD with a plan).
   - Shapes: a share in [0, 1], never a boolean or NaN; up to 8 hunt queries
     of 1 to 6 terms of `[A-Za-z0-9-]` (raw query syntax is refused
     `hunt_query_invalid`); `max_records` 1 to 10000; limits only
     `calls_per_epoch`, `trials_per_epoch` and `planner_calls`, each 1 to
     1000000 (`graphite_limits_invalid`). The shapes are refused by name at
     the replay gate, before the request is digested.
   - A model selection is for an agent that calls one: `MODEL_AGENTS` is
     autonomous and graphite. The refusal for `agent=none` keeps its
     historical code, `model_selection_needs_the_autonomous_agent`, with a
     step naming graphite.
3. **Admission checks what a Graphite run needs**, by name, before the
   chain is read and again in the body:
   - The Challenge has a registered research campaign
     (`graphite_not_offered_for_challenge`).
   - The shared card pack loads (`literature_pack_missing`).
   - The miner's library opens (`library_unavailable`).
   - A BUILD plan exists in the library (`plan_not_found`) and passes S3's
     plan rule against the current pins and bans (`plan_invalid`, with the
     rule's own closed reason in the next step).
4. **The curation digest is captured at admission.** It is recorded beside the
   request, in the launch record under `graphite_admission`. That key is never
   a request field (the closed-request gate refuses it), so it never joins the
   launch's identity. A launch carried out where it was not received keeps the
   captured digest, never reads the library's current one, and its plan is not
   judged again against pins and bans changed since. Only the plan's existence
   is checked again.
5. **What the campaign receives (the S3 interface).** On creation only,
   `LaunchChoice.apply` sets `args.graphite` = `{edition, mode,
   research_share, plan_digest, hunt: {queries, max_records} | None, limits,
   curation_digest}`. The edition is `carbon.graphite.miner-edition.v1`. On
   every run, resume and operation of a Graphite campaign, `args.graphite_library`
   is the library's path. It is never frozen, since a path is private and may
   move. Other campaigns' args are as they were. `args.agent_policy` stays the
   autonomous policy for every campaign, as before.
6. **The Library is eleven rows of the one operations table.**
   - Reads `library_search`, `library_card`, `library_list`, `plan_list` and
     `plan_get` run the gates request and profile.
   - Writes `library_pin`, `library_unpin`, `library_ban`, `library_unban`,
     `library_import` and `plan_edit` run request, profile and replay.
   - None admits work, so none reads registration, and the miner's signer is
     not asked.
   - The browser routes are `/api/v1/library/<action>` and
     `/api/v1/plans/<action>` (with `GET /api/v1/library` and
     `GET /api/v1/plans`). MCP tools are `carbon_library_*` and
     `carbon_plan_*`, generated from the table.
   - An import or plan edit may be 128 KiB at its routes; every other route
     keeps 4 KiB.
7. **Where the library lives.** It is `<setup root>/graphite-library`, the
   directory of the runner profile, so both doors read one library. A host
   with no profile file has none: `library_unavailable`.
8. **Keyed library writes replay their answer.** A write claims its key in
   `launchpad_operation_keys` (campaign `""`) before it writes, and keeps its
   answer in the new `result` column. The column is added in place; a
   campaign operation's row leaves it NULL. A retry replays the answer; the
   same key with another request is `operation_replay_conflict`. A failed
   write frees its key. A claim still being written answers
   `operation_not_completed`.
9. **The door filters what it serves**, whatever the library answers:
   - only a card's own fields (`runner.CARD_FIELDS`), its origin, `pinned`,
     and a search's score and reasons;
   - `check_status` is always UNCHECKED;
   - a banned card, a card whose origin is not shared, miner_hunt or
     miner_import, and a card naming protected material
     (`agent_campaign.graphite.tools.protected`) are never served;
   - an import's text is never listed, only its title and size;
   - query, title and imported text with control or bidirectional
     characters are refused.

   A pin of a banned card is refused `card_banned`. `plan_edit` stamps
   `created_by: miner`, needs its parent in the library, and runs the plan
   rule.
10. **Progress in observe and the campaign view** comes from three sources:
    - The frozen plan's `provider.graphite` block gives the mode, plan digest
      and share.
    - The ledger gives the stage, in S1's namespace: `research-epoch-N-<stage>`
      and `epoch-N-<stage>-provider|tool-NNN`. An unstaged epoch call counts
      as `build`, and a hunt's Reader calls are `graphite-hunt-*`.
    - The driver's hunt report, `<root>/graphite/hunt-report.json`, gives the
      hunt.

    Research spend is what every stage except `construct`, `constructor` and
    `build` booked: settled where settled, reserved otherwise. Stage
    subfolders `epoch-N/<stage>/` are never read as an epoch's own outcome or
    candidate. The projection labels a Graphite campaign `carbon-graphite`.
11. **Setup** offers `carbon-graphite`, the miner's own agent and Hermes. A
    new `carbon-autonomous` choice is refused `autonomous_agent_replaced` with
    a step naming carbon-graphite. A setup that recorded it keeps it, and its
    Inference step is still required.
12. **The capability document** offers Graphite named as setup names it, and
    states its modes, share, hunt bounds, limits and the Challenges it runs
    on. It gives a hunt's planning estimate: 1000 input and 250 output tokens
    per abstract at the selection's price, about USD 0.0001 on a cheap model.
    The estimate is a figure for planning, never a cap or a charge. Each
    Challenge's `setup_offers` says whether Graphite runs on it.
13. **The MCP door gains a `number` field type** (an integer or a float, never
    a boolean) for `research_share`.
14. **Existing tests are adapted.** Tests that launched through the browser's
    implicit `autonomous` default are adapted, each without weakening what it
    pins:
    - Door and runner mechanics name `agent=none`.
    - Model selection names `agent=graphite`, over in-memory fakes of S2 and
      S3.
    - The LP-PROD-A agent-loop stages and the supervisor handover tests run a
      recorded autonomous launch carried out from its record.
    - Stage 7 of the journey launches Graphite.

**Not decided here.**
- The driver's own records are S3's. S4 reads them as item 10 states and
  shows nothing it cannot read.
- Contributing cards back to the shared pack, and PDF import, are deferred
  by the owner decision.

**Unchanged.** Every scientific value, threshold and gate. No chain write, no
weights, no hidden-test material. Every recorded launch key, frozen plan,
prompt, digest and journal replays as before. A launch not Graphite's has the
identity and args it had.
