## 2026-10-02 — OWNER-MINER-RESEARCH-SURFACE-01: a branded research surface for the miner and their agent

**Authority.** The owner, in chat on 2026-10-02, after sending a mockup of a
dark dashboard (left rail, a "Launch a New Campaign" strip, an "Active
Campaign" panel with a stage tracker, live metrics, experiment output, events
and agent thoughts). The owner's words, verbatim:

> we were supposed to be working to a branded version of this. Whatever you as
> an agent think is an optimal work surface for you and the miner

**Resolved.**
- The Control Center gets a research surface in Carbon's brand: the screen a
  miner and their agent work from once setup is done.
- Design choices are delegated to the executor, within Carbon's invariants.
  Nothing here changes what is disclosed, what is evaluated or who grades.

**Recorded engineering decisions (executor, same day, within delegated
authority).** Ticket: `.agent/tickets/C-MLP-05_miner_research_surface.md`.

- **RSURF-D1, one projection for both.** Every panel is drawn from one
  allow-listed document, `carbon.control-center.campaign-view.v1`
  (`scripts/dev/miner_launchpad/campaign_view.py`). It is an operation in the
  shared table, so the browser's route and the MCP tool `carbon_campaign_view`
  are generated from it and return the same payload. It reads only; its gates
  are observe's.
- **RSURF-D2, per-case public practice curves are allowed, and are computed
  locally.** Findings:
  - The practice scorer has dropped the per-case rows (`_rows` in
    `carbon/battery/research.py`) since BATTERY-TESTNET-M5A (`66ba55ff8`). No
    commit message, decision, ticket or document records a reason. The stored
    practice feedback is defined as the exam aggregate on public PRACTICE.
  - The battery practice population's own disclosure contract makes
    `public_practice_cases` and `public_practice_labels` public, with the
    aggregation policy `detailed_own_public_practice` and the release policy
    `public_research_only`.
  - The practice references are public material a miner already downloads
    (`practice_data`). The worker's predictions are the miner's own files on
    their own machine.
  - "Never disclosed" names per-case *evaluation* errors, private evaluation
    cases, seeds and duplicate maps. Amendment 4's "what no rung shows" is
    about the screening outcome on the private pool. Neither covers public
    practice.
  - Invariant 12 still holds: practice scores a fixed public set that shares
    no case with the exam's private pools (amendment 4, D4: practice has no
    channel into realized exam cases).

  So the view draws predicted-vs-reference curves for public PRACTICE cases
  only. They are computed on the miner's host from the worker's
  `predictions.json`, after its digest matches the ledger's worker record,
  and the pinned public references. They are never written into the practice
  feedback record, never sent anywhere, and never include an evaluation case.
  The Challenge-neutral rule (`carbon/challenge_registry/research_view.py`)
  enables them only when a Challenge's practice disclosure contract says so.
  Any other case (no adapter, a contract that does not disclose, an
  unverified or missing file) fails closed to the aggregate view with a
  reason.
- **RSURF-D3, no battery learning curve yet: an owner question.** Battery
  trains inside one `jax.lax.scan` in the staged worker modules (`recipes.py`,
  `training.py`, `torch_training.py`). Their exact bytes are staged into the
  practice worker and are part of the implementation identity the validator
  rebuilds with. Recording a loss history changes that trusted program. The
  view keeps an empty learning-curve slot that says why, and draws a curve
  wherever one is recorded (`inline_curve`). **Owner input:** may the battery
  worker program record a bounded TRAIN-only loss history (for example 64
  evenly spaced steps), at the cost of a new implementation identity and
  rebuilt worker images? *Answered 2026-10-03: yes, as a new trainer version
  (OWNER-MINER-RESEARCH-SURFACE-02).*
- **RSURF-D4, the frozen feedback mode applies to the view.** A validator
  outcome is shown through the campaign's frozen feedback mode, using the
  Challenge's own ladder. A miner's own agent reading the view therefore sees
  what that mode allows and no more. An unknown mode shows the state only.
- **RSURF-D5, `carbon_note` is a journal write that starts no work.** Any MCP
  client, or the browser, can post a hypothesis, plan or observation to a
  campaign's research journal. The rules:
  - It takes the gates of observe and halt.
  - Product campaigns only.
  - 1 to 2000 characters. Control characters other than newline and tab, and
    bidirectional overrides, are refused.
  - It is stored through the existing journal path (`CampaignLedger.note`,
    kind `notebook`, schema `carbon.research-surface.note.v1`).
  - Notes are shown as untrusted text: every door renders them as text, never
    HTML. They are never fed to Carbon's own agent.
- **RSURF-D6, attach brings the research prompts and skill.** Attaching a
  campaign now copies the research server's prompts as well as its tools and
  resources, and detaching removes them. The skills extension is registered
  when the operations server is built, because an MCP extension cannot be
  added after a client has initialized.
- **RSURF-D7, the demo fixture is structurally outside the research path.**
  The fixture lives under `scripts/dev`. Its runner refuses every operation
  that admits work, and writes no ledger and no campaign root. Every document
  it serves is labelled `SYNTHETIC_FIXTURE`.
- **RSURF-D8, charts by output kind, with no chart library.** A Challenge
  declares its outputs as time series, scalar, checkpoint vector or 2D field,
  with names, units and axes read from its own I/O description. One SVG
  renderer draws by kind in the brand's colors. Battery is the first adapter,
  and a synthetic second Challenge is tested through the same code.
- **RSURF-D9, the stage tracker is the real lifecycle.** Research, then
  practice runs (with the count done), then candidate frozen, then
  DEVELOPMENT submit. Each stage's state is read from the campaign's records.
  Halt and resume are the real operations.
- **RSURF-D10, the construction level is an empty slot.** The Contract view
  reserves `construction_level`, which is null until the construction ladder
  is merged and supplies it as data.

**Boundaries.** DEVELOPMENT and testnet 567 only. Practice evidence is not
qualification: there is no leaderboard, rank or official score. Spend shown
is the miner's own campaign ledger, and their provider bills them; Carbon
caps and bills nothing.

**Second request, same day (owner, 2026-10-02), relayed by the lead,
verbatim:** "where can you see the Julia/JAX/Pytorch tooling and all of that
in the control center? And where can you talk to your agent?" Neither had an
answer, so both are built under the same delegation.

- **RSURF-D11, the toolbox is read from data.** One document,
  `carbon.control-center.toolbox.v1` (`scripts/dev/miner_launchpad/toolbox.py`),
  answers the first question. It is shown as the campaign's Tools tab and as
  a Toolbox on each Challenge card, and it is the operation `toolbox`, so
  `carbon_toolbox` returns the same document. Its sources:
  - the Challenge's description: its backends, workflow, limits, families and
    backend control;
  - the capability registry: Julia's status and blocker;
  - the published exam environment: what the validator rebuilds with;
  - the research protocol's workspace actions and the operations table, for
    the exact MCP tool names;
  - this host's research lanes, which say whether `run_julia` can run here.

  The only text kept in code is one line per workspace action, and a test
  holds that the set equals the protocol's. Each practice run also shows the
  framework its recipe named and the image its worker record names.
- **RSURF-D12, the miner talks to their own agent through the journal.**
  - The page posts a `miner_message` to its own route,
    `/api/v1/conversation/<campaign>`. That route is behind the local session
    token, and no MCP tool can post a miner message.
  - A message is one journal entry (`CampaignLedger.note`, kind `notebook`,
    schema `carbon.research-surface.miner-message.v1`). It records the text,
    the time and a digest of both, and the journal assigns its sequence.
  - Any MCP agent reads messages after a cursor with `carbon_messages`, and
    replies with `carbon_note`, `note_kind=reply`, naming the message's
    sequence in `reply_to`. The page shows the thread.
  - A message is guidance to the miner's own agent only. The route writes
    one note and never touches the frozen manifest, so a message cannot
    change limits, budget, research permissions, the Challenge, the feedback
    mode, evaluation rules or the frozen research task and its digest.
    Messages and replies are untrusted text, shown as text.
- **RSURF-D13, Carbon's own agent does not read messages: stopped, owner
  question.** The request was for Carbon's autonomous agent to read new
  messages at its next step and reply. That conflicts with C-MLP-02-D6:
  - the research task is frozen at launch, and each epoch's effective input
    is digest-bound;
  - the browser "cannot author prompts";
  - "adding another prompt store/runner" was a rejected alternative.

  Feeding messages into Carbon's agent would make the browser author its
  input mid-campaign. That sub-part is stopped and fails closed: the
  conversation says Carbon's agent does not read messages, and why.
  **Owner input:** may Carbon's own agent read the miner's messages as
  user-role input at step boundaries, recorded and digested in the epoch's
  effective input? That would amend C-MLP-02-D6. *Answered 2026-10-03: yes,
  recorded (OWNER-MINER-RESEARCH-SURFACE-02).*
