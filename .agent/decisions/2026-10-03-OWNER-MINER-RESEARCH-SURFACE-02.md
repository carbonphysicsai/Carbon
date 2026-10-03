## 2026-10-03 — OWNER-MINER-RESEARCH-SURFACE-02: Carbon's agent reads the miner's messages; battery trainer v2 records a TRAIN-loss history

**Authority.** The owner, 2026-10-03, answering the two questions
OWNER-MINER-RESEARCH-SURFACE-01 left open. Each question as it was asked, and
the option the owner selected, verbatim.

1. **RSURF-D13.** Question:

   > May Carbon's own built-in agent read your Conversation messages? It would
   > read them between steps, and each message would be saved and
   > fingerprinted (hashed) as part of that step's recorded input. This
   > changes the earlier decision C-MLP-02-D6, which says the research task is
   > fixed at launch and the browser can't write the agent's prompts. Agents
   > you bring yourself (Claude Code, Codex, Hermes) can already read the
   > messages.

   Selected answer: "Yes, recorded (Recommended)", whose option text reads:

   > Carbon's agent reads new messages at each step boundary as your guidance.
   > Each message is saved and fingerprinted as part of that step's input, so
   > the campaign can still be replayed exactly. Messages still can't change
   > your limits, the Challenge, the scoring rules or the task fixed at
   > launch.

2. **RSURF-D3.** Question:

   > May the battery practice trainer record a short training-loss history,
   > from training data only, so the Learning curve chart has real data? This
   > changes the pinned trainer program, so it would ship as a new versioned
   > trainer image. Earlier records keep their old version.

   Selected answer: "Yes, as a new trainer version (Recommended)", whose
   option text reads:

   > A capped training-loss history from training data only, shipped as a new
   > versioned trainer image. Earlier evidence stays tied to the old version.
   > The Learning curve chart then shows real data.

**Decision 1: RSURF-D13 amends C-MLP-02-D6, prospectively.**
- **Which campaigns.** Only a campaign whose frozen provider plan carries the
  rule `carbon.autoresearch.miner-guidance.v1` reads messages. The battery
  provider plan freezes it for every Carbon-agent campaign launched from now
  on. A campaign launched before has no rule and reads none. Its plans,
  digests, replays and evidence are unchanged, and nothing about it is
  reinterpreted.
- **When and how much.** At each step boundary, before each model call, the
  agent reads the miner's messages that are new since the campaign's cursor.
  It takes at most 4 per step, the rest at later steps. Each message keeps the
  existing bound of 1 to 2000 characters, and is read only if its digest
  matches its text and time.
- **Recorded and fingerprinted.** Each step writes once
  `<step>-miner-guidance.json`, holding the messages read and their sequences
  and digests. Each record is chained from the epoch's frozen plan digest
  through every step. The epoch outcome and `verify_history` carry the chain,
  so the epoch's recorded input is its frozen effective input plus this
  chain. A replay reads the record, never the journal, and re-sends each turn
  exactly. A broken chain fails closed as changed input.
- **Guidance, not authority.** The messages are a separate user-role entry,
  JSON-encoded under one fixed key, `miner_guidance`, with an authority
  statement beside them. Text stays a string value, so it cannot read as the
  system prompt or the frozen research task.
- **Unchanged.** These are never written by a message, and tests hold it:
  - the frozen research task's text and digest;
  - the plan, its prompt and the effective input digest;
  - limits, budget and research permissions;
  - the Challenge, the feedback mode and the evaluation and scoring rules.
- **Replies.** The agent replies with `carbon_autoresearch_reply_to_miner`.
  That tool is offered only under the rule. It writes the same reply note an
  MCP agent's `carbon_note` writes, marked `author: carbon_agent`, and only to
  a message the agent was given. A malformed reply is a refused result, not a
  stopped epoch. It grants nothing.
- **No forgery.** Only the page's own message route writes a miner message.
  The agent's notebook tool refuses that schema.
- **C-MLP-02-D6 now reads.** The browser still cannot author the prompt, the
  tools or the frozen task. For a campaign under the rule, the miner's posted
  messages reach Carbon's agent as recorded user-role guidance.

**Decision 2: RSURF-D3, battery trainer v2.**
- **What is recorded.** `carbon.battery.trainer.v2` (`TRAINER_VERSION` in
  `carbon/battery/training.py`). Practice records at most 64 evenly spaced
  (update, loss) points of the trainer's own loss on TRAIN data. That loss is
  a value the loop already computes.
  - It covers the JAX trainer, the classic MLP loop and the PyTorch trainer.
    An ensemble records its first member.
  - k-nearest-neighbour recipes do not train and record none. An L-BFGS
    polish is not included.
- **Practice only.** Recording is off by default. Only the practice worker
  program turns it on (the GPU practice program extends it). The validator's
  reconstruction program never does.
- **Same computation.** With recording off, the traced program is the one
  before trainer v2. Recording reads the loss and changes no update.
  - Checked for JAX on CPU: identical `params_sha256` with recording on and
    off, for the classic MLP, the general MLP and DeepONet.
  - Checked for PyTorch in the canonical environment: identical
    `params_sha256` with recording on and off, for the MLP, the FNO and an
    FNO ensemble. The trainer reads the loss each update already computes.
- **The new version.** The trainer module bytes are part of
  `contracts.implementation_digest()`, so the battery implementation identity
  changes prospectively.
  - Earlier records keep the identity they were recorded under, and nothing
    is rescored.
  - A running battery deployment moves to the new identity by
    OWNER-BATTERY-CARRYOVER-01's recorded in-place carry-over
    (`operate upgrade`, `PoolStore.rebind`).
  - The validator's computation, the exam, the scoring rule and the seeds are
    unchanged.
- **Images.** The trainer program is staged into the existing worker image at
  run time, beside the recipe. So the new version ships as the staged program
  and its implementation identity, and no container image is rebuilt. This
  session did not touch shared Docker state.
- **The chart.** Practice feedback carries the checked history as
  `fit.loss_history`, and the Learning curve chart draws it.

**Unchanged.** Invariants 1, 4, 5, 7.9 and 10 hold:
- no hidden-evaluation material reaches a message, a record or the view;
- disclosure stays allow-listed;
- nothing flips LIVE;
- Carbon's verifier still grades;
- historical evidence keeps its meaning.

Ticket: `.agent/tickets/C-MLP-05_miner_research_surface.md`.
