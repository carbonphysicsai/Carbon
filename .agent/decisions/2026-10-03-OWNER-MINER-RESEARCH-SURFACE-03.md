## 2026-10-03 — OWNER-MINER-RESEARCH-SURFACE-03: messages carry across epochs; the toolbox works from the page

**Authority.** The owner, 2026-10-03, verbatim.

1. The lead asked: "When a new epoch starts, should Carbon's agent carry
   forward the messages it already read in the previous epoch? Right now it
   starts fresh each epoch. I'd say yes, the last few, recorded the same
   way." The owner answered: "yes to your question".
2. The owner said: "my other request for the research surface was access to
   the tooling in the control center". The Tools tab only listed the tools
   and their MCP names. A miner should use them from the page, not only read
   about them.

**Recorded engineering decisions (executor, same day, within delegated
authority).** Ticket: `.agent/tickets/C-MLP-05_miner_research_surface.md`.

- **RSURF-D14, the last 3 messages carry forward, recorded the same way.**
  - A new rule, `carbon.autoresearch.miner-guidance.v2`, which every new
    battery agent plan freezes.
  - At an epoch's first step, Carbon's agent gets the last 3 messages it
    read in earlier epochs, each with at most 2 of its own replies.
  - They come in the same separate user-role `miner_guidance` entry, under
    `carried_forward`, with a note saying they were already read and change
    nothing.
  - They are read once, from the earlier step records and the journal. They
    are written into the new epoch's first record with their digests (a
    reply's digest covers its text and the message it answers) and bound
    into that step's chain link, so a replay re-sends them exactly and a
    changed one fails closed.
  - A campaign frozen under v1 carries nothing, and its records and chain
    links are unchanged.
  - Nothing frozen at launch is written. Tests hold the prompt, tools, task
    and effective input digest equal across epochs.
- **RSURF-D15, the page is one more client of the agent's own research
  tools, under the campaign's ownership lock.**
  - Opening a tool session from the Tools tab goes through the shared
    operation gates: an enabled profile, registration and a reachable signer,
    and the miner's own product campaign.
  - It then attaches through `standard_cli.attached`, the path an MCP
    `carbon_attach_campaign` takes. That takes the campaign's ownership lock
    and checks the authenticated owner, the campaign's run state and that no
    consumption is unresolved.
  - The page's tools are the Tool objects `standard_server._create_server`
    builds for that adapter, which an MCP agent gets. Each panel is built
    from that tool's own input schema, and each call is validated by that
    tool's own argument model (`Tool.run`).
  - Long tasks start, report progress and cancel through the adapter's task
    calls, which the MCP Tasks extension uses, with the same projection.
  - Every gate, disclosure class, limit, charge and refusal is that code's.
    The page adds no authority and no execution path. The sandboxed carrier
    and isolation are unchanged.
- **RSURF-D16, one holder at a time, said plainly.**
  - The lock decides who may run tools. Possible holders are an MCP agent
    with the campaign attached, Carbon's own agent while it runs, an
    operation in progress, or the page's session.
  - When the page cannot take the lock, it says which of these it can be
    and what to do: ask the agent to call `carbon_detach_campaign`, pause
    Carbon's agent, or wait.
  - While the page holds the lock, the agent's attach and the practice,
    freeze and submit operations answer `campaign_busy`, and the page says
    so.
  - The page's session ends on Close, when the server stops, and after 10
    idle minutes.
  - The freeze and submit shortcuts close the session, then call the
    existing operations with their own gates.
  - Rejected alternative: a shared session that lets two clients run tools
    at once. It would need a second ownership model, and the lock already
    serialises dispatch, accounting and cleanup.
- **RSURF-D17, a run's own output is read through one shared read-only
  operation.**
  - The research protocol returns a run's result by reference: the worker
    record and its exported workspace file names. Its retained stdout is not
    in that result.
  - `run_output` (campaign, task) is a read-only operation in the shared
    table, so the page and `carbon_run_output` return the same document. It
    holds:
    - the run's retained stdout, at most the last 64 KiB, as text;
    - its exported files, with name, size and media type;
    - each raster image (PNG, JPEG, GIF or WebP, recognised by its bytes
      and never by its name), inline as base64. Each image is at most
      1 MiB, at most 3 MiB in all and at most 6 images. SVG and other types
      are listed, never inlined.
  - This is the miner's own program's output, run on public and own files in
    the isolated analysis image, which receives no hidden evaluation
    material. It stays the miner's own, labelled MINER_SELF_REPORTED, and
    every surface shows it as text or as an image, never as HTML.
  - Recorded limits of the unchanged carrier:
    - stderr is not retained (it is a private diagnostic);
    - a run whose program fails keeps no stdout; its failure code is shown.
    - The page says both. Keeping either would change the carrier, which
      this decision does not do.
- **RSURF-D18, the demo shows the toolbox working and runs nothing.**
  - The fixture's tool session is the real tool set and argument validation
    (`_create_server`) over an adapter whose SDK has no connection, no
    composition and no ledger.
  - Its answers are synthetic: a workspace with a few files (kept in memory),
    one finished `run_python` with stdout and a PNG plot, and a
    `dry_validate` result.
  - Every start of new work is refused as `fixture_read_only`. Nothing it
    serves can reach a campaign, a ledger or LIVE.

**Unchanged.**
- The research protocol, its tools, argument bounds and results.
- Workspace limits: `read_file` reads 4096 bytes at a time, `write_file` is
  guarded by its expected digest, a workspace action's arguments are at most
  16 KiB (so the page writes about 11 KiB of file at a time), and a tool
  call's arguments are at most 32 KiB.
- Trial charging, registration and the carrier's isolation.
- Hidden evaluation material never reaches any of it (invariants 1, 2, 6,
  7.9 and 9).
