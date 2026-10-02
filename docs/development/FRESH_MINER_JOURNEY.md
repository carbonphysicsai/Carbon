# The fresh-miner journey (C-MLP-03 slice 6)

This runbook is the acceptance run for C-MLP-03
(`.agent/tickets/C-MLP-03_miner_environment.md`, slice 6). A person takes a
clean machine from nothing to a submitted battery candidate. Then they check
that every rented resource is gone and that every cost matches what the
provider charged.

The run confirms the provisions slices 2 to 5 closed: model, compute and
agent. It closes no Gap itself, and nothing in it qualifies anything.

It needs things this repository cannot supply: a clean machine, a registered
hotkey on subnet 567, and the miner's own inference key. For a rented GPU it
also needs the miner's own provider account, plus a validator to submit to.
Record each run under `docs/development/evidence/fresh-miner-<date>/` with
the fields in [Record](#record).

## Before you start

- **A clean machine.** Linux x86-64 with Docker. For the GPU paths it also
  needs an NVIDIA GPU with the NVIDIA Container Toolkit. Nothing Carbon-related
  may already be installed: no checkout, images, keys or `~/.hermes/profiles/carbon`.
- **A registered hotkey on subnet 567.** Register it in your own wallet;
  Wallet & Identity prepares the unsigned call.
- **Your inference key** for Engy (Chat Completions) or Chutes.
- **For a rented GPU,** a RunPod, Lium or Targon key on your own account,
  with a balance.
  - For Lium, scope the key to `read`, `rent` and `manage`, plus `billing` if
    you want charges read, and give it a budget.
  - Targon rents a VM, which this machine reaches over SSH, so it needs an
    OpenSSH client here. It also needs a Targon VM image with Docker and the
    NVIDIA Container Toolkit; the GPU type is Targon's VM type, such as
    `h100-small`.
- **The validator.** Either it runs on this machine (`battery_validator` in
  the profile), or it runs elsewhere and you have its intake URL.
  - **Today the intake binds loopback only.** It needs the owner's exposure
    record (`OWNER-…INTAKE-EXPOSURE-NN`) before another machine can reach it.
  - **Until that record exists,** run the validator on this machine, or
    tunnel to its loopback yourself.

## Steps

1. **Clone and build.** Clone Carbon at the accepted revision and build the
   images:
   - the worker: `./scripts/dev/c03_worker_image.sh`;
   - the analysis image: `python -m carbon.development_session.research_image --parent-manifest <worker manifest> --root <directory>`;
   - for GPU, the GPU worker: `./scripts/dev/accelerator_worker_image.sh`.

   For a rented GPU, push the GPU worker to a registry you control and note
   its `repository@sha256:` digest.
2. **Start your signer.** Run `carbon-miner-signer` for your registered
   hotkey, in your own terminal.
3. **Open the Launchpad.** Start the controller and confirm your registration
   under Wallet & Identity. Setup opens.
4. **Inference.**
   - Choose Engy (the default) or Chutes, and type the model id.
   - Read the quoted maximum, tick to agree, and check.
   - Record the quote and the check's result.
5. **Compute.** Choose one of three:
   - this machine's CPU;
   - this machine's GPU (setup installs the host device record or names the
     `prepare` command);
   - a GPU rented on your account (provider, key, pushed image, GPU type,
     ceilings; for Targon, also the VM image).

   Record the check: the device, or the balance and offer price.
6. **Agent.** Choose Carbon's autonomous agent or Hermes.
   - For Hermes, install it first (its installer), read the files setup will
     write, and tick to agree.
   - Record the Hermes version and the files written.
7. **Review.** Write the profile. If the validator runs elsewhere, give its
   intake URL; setup reads its public facts.
8. **Launch battery.** For Carbon's agent, launch from Campaigns with finite
   ceilings. For Hermes, run `hermes -p carbon chat` and ask it to launch,
   practise, freeze and submit; it asks you before each such tool.
9. **Practise on the GPU.** Every practice feedback records its backend:
   - local GPU: `ISOLATED_CARRIER_GPU`, with the device record and what JAX
     observed;
   - rented: `RENTED_GPU`, with provider, resource, rate, teardown and charge.

   Record two practices.
10. **Freeze and submit.** Record the submission and its verdict. When the
    validator runs elsewhere, also record the intake URL and the submission id.
11. **Verify teardown.** Each rented trial terminates its own pod or VM. In
    your provider's console, confirm none remains. For Targon, also confirm
    no `carbon-…` SSH key remains. Run
    `python -m carbon.compute reconcile` (RunPod) to adopt and terminate any
    orphan. Record the list's state.
12. **Reconcile cost.** For each rented resource, compare the provider's own
    charge (or its console statement) with the hourly rate times the time it
    ran. Targon reports no per-VM charge, so its console statement is the
    only record. Record any difference; never replace a missing charge with an
    estimate.

## Record

For every run, record:

- **When and where.** Date, the machine (OS, GPU), and the accepted revision.
- **Profile.** The runner profile's digest, never its contents.
- **Inference.** Provider, model, quote and check result.
- **Compute.** The choice. For a GPU, the device record digest; for a rented
  GPU, provider, GPU type, ceiling and the pushed image digest.
- **Agent.** The choice and its version.
- **Practice.** Each practice's backend record.
- **Submission.** The submission id and its verdict.
- **Teardown.** The teardown check for each rented resource.
- **Cost.** Each provider charge against its estimate.
- **Anything that failed,** with its refusal code and the step it names.
