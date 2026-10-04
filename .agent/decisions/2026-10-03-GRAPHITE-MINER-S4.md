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
     outside BUILD, and a hunt in BUILD, with or without a plan. S3 runs a
     hunt only before RESEARCH's and FULL's Planner and its `launch_fields`
     refuses one in BUILD, so admission refuses it first rather than letting
     a created campaign fail its preparation. Queued imports are therefore
     read by the next launch that hunts. If S3 later runs a hunt before a
     BUILD's own Planner, this rule relaxes with it.
   - A Graphite field sent as null means what leaving it out means. The
     request gate drops null Graphite fields before anything is digested, so
     the browser (which keeps nulls) and MCP (which strips them) send one
     launch with one identity, whichever agent it names. The fields are new,
     so no recorded launch's identity changes.
   - A plan is named by its digest as the library and S3 name it,
     `sha256:` and 64 hex digits; anything else is `plan_not_found`.
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
   - A BUILD plan exists in the library (`plan_not_found`), is the launch's
     own Challenge's (`plan_invalid`, reason `plan_for_another_challenge`),
     and passes S3's plan rule against the current pins and bans
     (`plan_invalid`, with the rule's own closed reason in the next step).
     S3's preparation checks the same again; admission refuses first so no
     campaign is created only to fail.
   - S2's library refuses by a typed `LibraryError` carrying a closed code.
     The doors answer `card_not_found`, `card_banned`, `plan_not_found`,
     `plan_invalid` and `import_invalid` by that code, and S2's
     `search_invalid` as `library_query_invalid`; any other library failure
     is `library_unavailable`, never its text.
4. **The curation digest is captured at admission.** It is recorded beside the
   request, in the launch record under `graphite_admission`. That key is never
   a request field (the closed-request gate refuses it), so it never joins the
   launch's identity. A launch carried out where it was not received keeps the
   captured digest, never reads the library's current one, and its plan is not
   judged again against pins and bans changed since. Only the plan's existence
   is checked again.
5. **What the campaign receives (the S3 interface).** On creation only,
   `LaunchChoice.apply` sets `args.graphite` to exactly the names S3's
   `edition.launch_fields` reads - `{mode, research_share, plan, hunt:
   {queries, max_records} | None, limits}` - and, beside it,
   `args.graphite_curation_digest`, the curation digest admission captured.
   The edition is the campaign's to name (S3 freezes its own published
   edition and digest). S3 freezes the curation recorded under that digest
   (`MinerLibrary.curation_state`), so a queued launch runs with the pins and
   bans its miner launched with. On every run, resume and operation of
   a Graphite campaign, `args.graphite_library` is the library's path. It is
   never frozen, since a path is private and may move. The library root is
   absolute: the profile path a host is built on is already absolute and
   resolved, and the root is made absolute regardless. Other campaigns' args
   are as they were. `args.agent_policy` stays the autonomous policy for
   every campaign, as before; S3's preparation accepts it for Graphite.
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
   `operation_not_completed`. The host's lock is held only while a key is
   claimed and while its answer is kept, never across the write: S2's
   library serialises its own writes, and a write may read the whole pack.
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
10. **Progress in observe and the campaign view** is S3's own view of its
    records, never a second reading of them under other names:
    - The frozen plan's `provider.graphite` block gives the edition and mode;
      the research share is shown for FULL only, the one mode that applies
      it.
    - S3's `driver.view(root, operations=...)` gives the stages with their
      state and closed code, the current stage (`complete` once done), the
      plan digest - the miner's chosen plan, or the one the campaign's
      Planner wrote - and what the research stages (the Reader's
      `graphite-reader-*` calls and the Planner's `epoch-1-plan-*` calls)
      spent against the cap the share sets.
    - The hunt's counts come from S3's hunt stage record
      (`<root>/graphite/stages/hunt.json`, S2's report), and its Reader calls
      and their cost live from the ledger. S2's `failed_infra` flag is shown
      as a count, 0 or 1.
    - Without S3's view (an unreadable record) only the frozen block's values
      show, and the stage and spend are unknown (null), never invented.

    Stage subfolders `epoch-N/<stage>/` are never read as an epoch's own
    outcome or candidate. The projection labels a Graphite campaign
    `carbon-graphite`. Library search results also carry S2's buildability
    flags (`plan_input`, `capability_request_candidate`); plans list newest
    first with S2's timestamp text; an import's size is S2's `chars`.
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

15. **The journey's stage 8 runs Graphite end to end** through the launch
    door, over the real S1 to S3 code where it is present: the preparation
    fixture freezes Graphite's block as S3's preparation does
    (`driver.freeze_launch`), Reader calls are counted by S3's ledger
    identity, the compaction is recognised by the engine's own note and its
    `-compact-` identity and its summary by its `SUMMARY` label, the FULL
    stop by its stage code, and the limits scenario runs until the miner's
    own ceiling stops it. A launch's money ceiling is its attempts times
    what one call of a new plan reserves under the base's own rule: the
    model's full output once new plans default to it
    (OWNER-LAUNCHPAD-PROD-02), the historical reservation before. A
    research share is a share of that money as well as of attempts, and a
    share smaller than one call's reservation admits no research call.

16. **The Launchpad reaches Graphite's package, so the package must not
    reach the internal edition.** S2's and S3's modules live inside
    `carbon.agent_campaign.graphite`, so importing any of them runs that
    package's `__init__` in the product process. Today that file eagerly
    imports the internal edition (`provider`, which reaches `next_level`,
    `experiment` and `pods`), and the key-material invariant
    (`tests/invariants/test_product_process_holds_no_key.py`) refuses the
    product closure on `pods.py`'s `key_file`. That boundary also says the
    miner edition never uses pods. S4 does not route around it: importing by
    a computed name would only hide the reach from the invariant's closure
    walk. The repair is a package `__init__` that imports nothing eagerly.
    That file has no slice owner, so the lead owns the fix. With it, S4's
    own reach is clean on this branch and on the merged tree, as a scratch
    walk of the invariant's own closure showed.

**The OWNER-LAUNCHPAD-PROD-02 smoke test.** Item 12 approves one live smoke
test before Graphite's remaining phase-3 runs: a single-epoch autonomous
Launchpad campaign. After this slice a new autonomous Launchpad launch is
refused at both doors. The smoke test therefore runs on the Launchpad
wiring head this slice is stacked on (`claude/lp-prod-wiring`, 9bfd9add, or
its merged successor) before the Graphite miner stack lands. Running it
instead as a single-epoch Graphite BUILD campaign would change what the
owner approved, so that substitution is the owner's to make, not this
slice's.

**Not decided here.**
- The driver's own records are S3's. S4 reads them as item 10 states and
  shows nothing it cannot read.
- How a session ends at the miner's own ceiling is the engine's and the
  driver's (S1, S3). Today the campaign ledger refuses past a ceiling with a
  bare error, which interrupts the campaign; S4 adds a catalog step for the
  typed stop it proposes (`miner_ceiling_reached`).
- Whether a FULL launch whose research share holds less than one model
  call's reservation is refused at admission or only explained. With no
  Carbon output cap, the default share of 0.10 needs a money ceiling of at
  least ten full-output reservations (about USD 2.72 on gpt-5-mini) before
  research can make one call; below that the research stage stops
  `research_share_reached` before any call and the build goes on. The share
  arithmetic is S3's (`budget.share_caps`), so S4 does not copy it into
  admission. A check S3 publishes could be called at admission.
- Contributing cards back to the shared pack, and PDF import, are deferred
  by the owner decision.

**Unchanged.** Every scientific value, threshold and gate. No chain write, no
weights, no hidden-test material. Every recorded launch key, frozen plan,
prompt, digest and journal replays as before. A launch not Graphite's has the
identity and args it had.
