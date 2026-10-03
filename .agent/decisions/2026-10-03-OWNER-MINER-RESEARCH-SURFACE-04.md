## 2026-10-03 — OWNER-MINER-RESEARCH-SURFACE-04: GPU in the Tools tab, a GPU code cell, and kept error output

**Authority.** The owner, 2026-10-03, verbatim.

1. The owner asked: "on jax and pytorch CPU? where's the GPU option?" They
   had found that the Tools tab shows only "JAX (CPU, the default) or
   PyTorch (CPU)". The toolbox computed the gpu and remote_gpu lanes but never
   showed them, and the code cell always ran in the CPU analysis sandbox. No
   decision is needed for this item: the page must not hide what the
   campaign runs on.
2. GPU code cell. Question: "Should the code cell (run_python and run_julia)
   also be able to run on your GPU, your own machine's or your remote one
   over SSH, instead of only in the CPU analysis sandbox? It would use the
   same isolated container with the GPU attached. Practice already runs on
   your GPU when you choose one."

   Selected answer: "Yes, GPU code cell (Recommended)", whose option text
   reads:

   > Same isolation, network and file rules as today, with the GPU you set
   > up attached. You choose CPU or GPU per run, and it runs on your machine
   > and your bill. The validator stays on CPU.
3. Kept error output. Question: "Keep error output in the sandbox? Today a
   failed program keeps no output at all, and error messages are never
   kept, so a crash shows only a failure code."

   Selected answer: "Keep both, capped (Recommended)", whose option text
   reads:

   > Keep the last 64 KB of normal output and of error messages, including
   > for failed runs. Shown as plain text with the same size limits.

**Recorded engineering decisions (executor, same day, within delegated
authority).** Ticket: `.agent/tickets/C-MLP-05_miner_research_surface.md`.

- **RSURF-D19, the page shows where a campaign runs.**
  - The campaign record states its compute from its frozen runtime: CPU,
    your GPU on this machine, or your remote GPU over its transport. Until
    now the projection always said CPU.
  - The Tools tab says where practice and the code cell run, per runtime.
    PyTorch on a GPU campaign is shown as not served there, because the
    pinned GPU worker carries JAX only.
  - It names the remote route's transport and destination from the miner's
    own runner profile. When a lane is not set up it gives the reason and
    links to `#setup/compute`.
  - It says plainly that the validator rebuilds on its published exam
    environment (jax-cpu today), so a GPU speeds up the miner's own
    research only.
  - Each practice run's "Ran on" states CPU or GPU, and where.
- **RSURF-D20, the GPU code cell.**
  - `run_python` takes an optional `device`: `cpu` (the default, and the
    only meaning a request without it has ever had) or `gpu`. The same
    argument reaches the page and an MCP agent, through the same field
    table.
  - It is offered only when the campaign's frozen runtime has a GPU lane.
    Otherwise it is refused before dispatch, with a registered correction.
  - **Local GPU.** The miner lane's container, as before (no network,
    read-only root, no capabilities, non-root, only the run's input and
    scratch mounted, the same staging and the same miner limits), with one
    addition: the host's installed GPU device, by UUID, through the NVIDIA
    runtime. The container is inspected after create, and any other device,
    port, mount or capability is refused.
    - It runs the campaign's pinned GPU worker image, the one GPU practice
      runs, because the CPU analysis image has no CUDA. Its packages
      differ, and the page says so.
    - It takes the same device lease as GPU practice, so the two never share
      the device.
  - **Remote GPU.** The miner's own remote route (ssh-docker or
    ssh-container), the campaign's pinned GPU worker and their own SSH, as
    remote practice uses them.
    - Carbon starts, stops and bills nothing (OWNER-MINER-COMPUTE-LINK-ONLY-01).
    - The remote job server is part of the pinned image and is unchanged.
      Carbon's fixed wrapper runs the miner's program there and returns its
      stdout as a file.
    - The route needs a wall allowance of 40 to 3600 seconds, so a remote
      run without one is refused before dispatch.
  - **Files.** A program finds its outputs at `../output` in every lane (it
    is `/scratch/output` in the sandbox).
  - **Records.** A GPU run records the device it ran on in its result and
    request. A CPU run's request and result are unchanged.
  - **`run_julia` and GPU.** `run_julia` takes the same argument, but the
    pinned Julia environments carry no CUDA packages, so `device=gpu` for
    `run_julia` is refused with that reason. A GPU-capable Julia image is a
    separate image change.
  - **Security review.** This touches the sandbox. Tests show isolation
    unchanged except the GPU device, a refusal when no lane is set up, and
    no credential or key in the container. Tests are not a security audit
    (AGENTS.md §13): this needs a dedicated security review before any use
    beyond DEVELOPMENT, and it stays DEVELOPMENT.
- **RSURF-D21, kept output.**
  - The miner lane keeps the last 64 KiB of stdout and, separately, of
    stderr, for successful and failed runs alike. This covers `run_python`
    and `run_julia`, CPU and local GPU.
  - A remote run keeps the same two tails from what the job returns.
  - Failure classification is unchanged: a nonzero exit is still observed
    from the exit status, and a large stderr no longer fails a run.
  - Carbon's own practice lane is unchanged.
  - `run_output` shows both tails as plain text, with the same bounds, and
    the page drops its `sys.stderr = sys.stdout` workaround.

**Unchanged.** The validator's environment, exam and scoring; disclosure
(the output is the miner's own program's); registration and trial charging;
nothing reaches LIVE (invariants 5, 6, 9 and 7.9).
