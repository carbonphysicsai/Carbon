<!-- Living guide (owner, 2026-10-22): keep this plain Markdown so anyone can
edit it. Whoever changes a step a miner sees (an installer flag, a Setup step,
a command, a message) updates this guide in the same change. Re-read it end to
end after each install round until launch. Fill DISCORD_INVITE_URL below with
the owner's invite link. -->

# Mining on Carbon: quick start

Carbon is built to reward miners for fast, accurate physics models. You build them with an AI research agent on your own machine. You practise as often as you like for free. Then you send your best model to a validator, which rebuilds it from your recipe and grades it on an exam you never see.

This guide gets you from a clean machine to your first graded model.

> **Testnet only, for now.** Everything here runs on Carbon's test network (subnet 567). Nothing is paid yet.

---

## What you need

- **A Linux machine** (x86-64; see [Supported setup](#supported-setup): 32 GB of RAM and 4 CPUs), or Windows with WSL2. It needs Docker ([install Docker Engine](https://docs.docker.com/engine/install/), start it, add yourself to the `docker` group) and free disk for Carbon's images; the installer checks the space first and says how much it needs. A GPU is optional; to practise on this machine's GPU, install the [NVIDIA driver](https://www.nvidia.com/en-us/drivers/) and the [NVIDIA Container Toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/install-guide.html), then install with `--gpu`.
- **To practise: nothing to register.** You can run your agent and practise on any Challenge without a wallet, a registration or a signer (see **Just want to practise?** in step 4).
- **To freeze and submit: a Bittensor wallet with a hotkey registered on subnet 567.** Carbon never asks for your keys or seed phrase. Your hotkey stays in your own wallet.
- **A model key from a provider**, if you want Carbon's agent (Graphite) or Hermes to do the research. Setup lists the providers each agent can use. Save the key in a file only you can read; Carbon reads it from that file. Skip this if you bring your own agent, e.g. Claude Code, which uses its own model.

---

## Supported setup

Carbon's launch supports **one** setup, and a run on it is guaranteed:

| | Supported |
|---|---|
| Operating system | Ubuntu 22.04 or 24.04, x86-64 |
| Docker | Docker 29 (the installer may install it) |
| Memory | **32 GB of RAM**. Practice runs its worker with a 16 GiB limit and needs Docker to see at least 17 GiB, so a 16 GB machine (about 15.6 GiB) cannot run it |
| CPUs | at least 4 |
| Disk | about 150 GB free |
| GPU | optional; any NVIDIA GPU with driver **580.65.06 or newer** |

**Minimum NVIDIA driver.** Carbon's GPU builds (the PyTorch and JAX runtimes) are built on CUDA 13.0, and NVIDIA's table of the driver each toolkit needs gives CUDA 13.0 on Linux x86-64 as 580.65.06 or newer (later CUDA 13.x runs on any 580 driver). Source: [NVIDIA CUDA Toolkit 13.0 release notes](https://docs.nvidia.com/cuda/archive/13.0.0/cuda-toolkit-release-notes/index.html). An older driver is not blocked; a GPU practice that cannot start on it says "driver too old" and practises on CPU.

**Any other setup gets a warning, not a block.** The installer, and a note at the top of the Control Center, say: *this is not a supported setup yet; it may work. Use the supported setup for a guaranteed run*, and list what differs (system, Docker, memory, CPUs, disk, driver) and anything it could not check. Other Docker versions and other Linux distributions are planned after launch.

**A rented GPU pod (for example Lium).** Measured on three different pods (RTX 3090, RTX 5070 Ti, RTX 6000 Ada), which all behave the same way:
- A "PyTorch (CUDA + DinD)" pod runs Docker inside a container and cannot bind-mount anything under `/root` (even a plain `docker run -v /root/x:/input:ro` fails with a `runc` "change mount propagation" error); `/tmp`, `/mnt`, `/run` and `/dev/shm` work. Carbon stages each worker's input under its state directory, so install with the state directory off `/root`, for example `CARBON_STATE_DIR=/mnt/carbon ~/carbon/scripts/install_miner.sh --gpu ...`. Otherwise every practice ends "practice could not run" with a worker start failure.
- Such a pod shows Docker 27, so setup prints the "not a supported setup yet" warning. It is a warning, not a block: everything else works.
- A pod has no systemd, so there is no `--service`; the Control Center runs in the foreground of the install command.
- The GPU check is per Challenge: when setup is driven through the page's door, name the Challenge with the compute choice.
- A catalog practice still runs on the CPU on a GPU machine (see What runs on the GPU, in Set up): the GPU speeds up your own graph's practice, not the catalog entries.
- A 16 GB machine cannot run practice; Docker must see at least 17 GiB (see above).

---

## 1. Install

```bash
git clone https://github.com/carbonphysicsai/Carbon.git ~/carbon
~/carbon/scripts/install_miner.sh --pytorch --service
```

Add `--gpu` if the machine has an NVIDIA GPU. Any NVIDIA GPU works, whatever the model, driver string or count: a field the GPU does not report (a virtual GPU's capability, for one) is recorded as unknown and never refuses the machine; with several GPUs setup uses the first usable one, prints which, and `--device` picks another.

The installer checks your machine, sets up Carbon's environment, builds the images your practice runs use, and starts the **Control Center**, the web page where you run everything. It never asks for a key or password.

**Updating.** Run `~/carbon/scripts/install_miner.sh --update --pytorch`, repeating the other options you installed with (e.g. `--gpu`). If the disk is short, it lists Carbon's own images from earlier installs that this install no longer uses, and asks before removing them; nothing else is touched. To say yes up front, add `--remove-old-images`. If the disk is still short, an update then offers the catalog images it has now, which it builds again over the new worker (that rebuild takes about as long as the first catalog install); it asks its own yes, and `--remove-catalog-images` says yes up front. If the disk is still short after that, the message says how many GiB more are needed and what frees them. Carbon removes only its own images, never Docker's build cache or another project's images; `docker system df` shows what Docker keeps, and what to clear there is your call. An update checks your setup's compute again, rewrites your runner profile, and says what changed. If it can't (for example, it rebuilt images your compute check named), it sets the check and your runner profile aside and says so in its **Next** lines: check Compute again on the page, or from your agent or `carbon-mcp` with `carbon_setup_recheck {confirm: true}`, then review.

## 2. Start your signer

Practising only? Skip this step: you need the signer only to freeze and submit.

Your signer signs your submissions with your hotkey. Keys stay in your wallet. In its own terminal:

```bash
~/carbon/.venv/bin/carbon-miner-signer --wallet <your wallet> --hotkey <your hotkey>
```

Leave it running.

## 3. Open the Control Center

On the same machine, open **http://127.0.0.1:8788**.

**On a rented server?** Run this on your own computer, then open the same address in your browser:

```bash
ssh -N -L 8788:127.0.0.1:8788 <you>@<your server's address>
```

The installer's last line, in a terminal, is the page's link with your **session token** in it. Otherwise the page asks for the token the first time. It is kept in your state folder, and an update or restart keeps the same one. Show it with:

```bash
cat ~/.carbon/development-launchpad/session-token
```

## 4. Set up (on the page)

The **Setup** page walks you through six steps. Each one is checked before you go on.

**Just want to practise?** At the first step, choose **Practise without registering**. You skip the signer and the registration. Setup makes a **practice identity** for this machine: a key kept in a file only you can read, registered nowhere and never sent. Carbon uses it to sign your practice locally. Then set up who researches, your AI model and your compute as usual, save your settings, and practise on any Challenge. Nothing from your practice is sent to Carbon or to a validator: your agent's model calls go to your own provider, and practice runs on your own compute.

In practice-only mode, **Freeze**, **Submit**, **Commit** and **Check for result** say *registration required*. Graphite can research and practise: launch it in **Research** mode, or with its submission policy set to retain only (`retain_only_v1`), when it plans and practises and then stops, *registration required*, where it would pick its final candidate. To unlock freezing and submitting later, register your hotkey in your own wallet, then:
1. confirm it at Setup's first step (**Join Carbon mining**);
2. start your signer;
3. choose **Who researches** again, so Setup checks your signer;
4. **Review and launch** again.

The other steps you checked are kept. Your practice campaigns stay on the page and readable, but to freeze and submit, start a new campaign.

1. **Start your signer.** Your signer holds your mining key on this machine; Carbon never sees your key.
2. **Join Carbon mining.** It confirms your hotkey's registration from the chain. You sign any registration in your own wallet.
   - **Fund your wallet first.** Joining is paid in TAO from your money key (the coldkey), so put a little TAO there before you join. **On the test network (the one Carbon launches on) it is test TAO: free, with no money value and no price, from the test network's faucet or from the Carbon team, never bought, and no dollar amount is shown.** Paste your money-key address (public) into the **Get some test TAO** box (**Put some TAO in your wallet** on a real-money network): it shows the address to copy and as a QR code, and **Check my balance** reads your balance and the current joining cost from the chain, in TAO, with the block it was read at. It says **Ready to join** when your balance covers the cost, before transaction fees; your wallet shows the exact cost again when you sign, and that figure is the one that counts. The page only reads: it never moves your funds, and it never asks for a key, password or phrase. **How do I get test TAO?** says where to ask for it. On a real-money network **How do I buy TAO?** lists the steps instead, with Coinbase and Kraken as plain links (examples only; Carbon has no link or share in either).
3. **Who researches.** Choose one of three:
   - **Graphite**, Carbon's research agent, running on your model key.
   - **Your own agent**, e.g. Claude Code or Codex, connected over MCP (see below).
   - **Hermes**, Nous Research's open agent (see below).
4. **AI model.** Pick a provider and model, give the path to your key file, and agree to the small, quoted cost of a test call.
5. **Compute.** Where practice runs: this machine's CPU, this machine's GPU, or a GPU machine you rent yourself. With a GPU, **Test my GPU** runs each GPU framework (JAX and PyTorch) once on your GPU, about a minute each, on synthetic data it makes itself; it shows the exact commands first and runs only when you agree. You get a plain answer per framework (works, or doesn't, with what to fix, e.g. an NVIDIA driver too old for the worker). It writes no score. With several GPUs, setup asks you to choose one (`--device GPU-<uuid>`, from `nvidia-smi -L`); it never picks for you. `carbon_accelerator.py doctor --miner-lane` exits 0 when your own practice is ready, and shows `miner_lane_ready`: a grant or approval it lists as blocked is for owner-authorised runs and does not stop your own practice. Your agent can offer the same step: `carbon_setup_test_gpu`, with the consent `carbon_setup_status` lists under `test_gpu`. **What runs on the GPU.** Your own graph's practice (its build, its inference and the speed query) runs on your GPU. A catalog entry (the starting recipes Carbon serves) has no GPU build yet, so a catalog practice runs on its CPU build and says so in its result ("Ran on CPU: this catalog entry has no GPU build yet"); start from your own graph to use the GPU. On Motor and Cooling the served example is the JAX **bcat** entry: its GPU rebuild is repeatable (bit-identical across runs). The PyTorch **CNO1d** entries stay in the catalog, but on a GPU machine they rebuild on the CPU (their GPU build is not repeatable), and the result says so.
6. **Review and launch.** **Save my settings** saves your settings and loads them. Carbon's own grader is used for each Challenge where one is published. To use your own, open **Advanced: where a Challenge's grader runs** and give its **grading address** and **the grader's mining key address** (public, starts with 5…; never a key, password or seed phrase).

Once you save your settings, the model catalog (the ready-made model types you can build from) installs itself in the background, and the page shows how far it has got. A Challenge can practise a catalog model as soon as that entry is installed. If it stops, its log says why; you can also install it yourself:

```bash
cd ~/carbon && .venv/bin/python -B -m scripts.dev.catalog_install --state-dir ~/.carbon/development-launchpad
```

## 5. Pick a Challenge and start a campaign

A **Challenge** is a physics task, e.g. motor magnetics, a chip cold plate or a ribbed bracket. Open **Challenges**, read one, and click **Start a campaign**.

Cooling 1.6 is a prospective pool-exam version. It removes the temperature-rise
sign check against hotspot ratio and that sensitivity's fitted exponent; the
other checks and ordinary output accuracy still apply. Older versions keep
their original rules. The new version remains reserved until its scoring
constants are registered, so it is not offered for campaigns yet.

With Graphite you set your limits up front: how many model calls, how many dollars, how much time. Graphite uses them to the end: near your money or time limit it shortens its last calls to fit what is left, and stops only when not even one short call fits (about 2 minutes, or a 512-token reply). The page then says which limit stopped it (money, model calls, practice runs or time) and what to raise next time. Graphite plans, builds models, practises them, and picks the best.

## 6. Practise, freeze, submit

**What the practice number is.** The number a practice shows (it may be labelled `score` in a result file) is an **error on the Challenge's registered scale, not a grade**: lower is better, **0 means the model matches the reference exactly** on every scored case, and 1 means an error as large as that scale (a spread taken from the public TRAIN data; F02 and F08 name theirs in the summary's `error_scale`). For Motor and Cooling it is the average over outputs of each output's error divided by its spread in the public TRAIN data. A first example recipe can sit above 1, which only says it predicts worse than the spread of the TRAIN values; improve it. It is never an exam score: the exam grades 0..1 with higher better, on hidden cases, and shows nothing of them.

- **Practise.** Pick a tested model type under **Backbone** and, if you like, **Training steps** and **Learning rate** (leave them empty for its tested default); the whole recipe is under **Advanced: the recipe as JSON** if you want to edit it by hand. Each practice trains a model from your recipe and scores it on public practice cases: one graded total from 0 to 1, higher is better, with its error details beside it. A practice that breaks a physics rule is marked **not eligible**, however good its error. Practice applies the exam's published score-part minimums and names a part below its minimum; until a version's minimums are set it says "minimums not yet set". A practice result is never an exam grade. Practice costs no exam and has no limit on how often you run it. It runs on your own compute, and if an AI agent researches for you, its model calls are billed to your model key.
- **Freeze.** When you have a good, eligible practice, freeze it. That fixes the exact recipe you'll send.
- **Submit.** The validator rebuilds your model from the recipe, then grades it on a hidden exam.
- **Rebuild resources.** On the newer versions (Motor 1.3 and 1.4, Cooling 1.2 to 1.4, Ribbed Bracket 1.3 to 1.5, Burst Thermal 2.2 to 2.4, Battery 2.1), your model is built and run with 4 CPUs, 16 GiB of memory, 4 GiB of scratch space and up to 2 GiB of output; earlier versions keep 2 CPUs and 4 GiB of memory. There is no limit on model size: only these resources and the time limit bind.
- **Build time limit.** On Motor 1.4, Cooling 1.4, Ribbed Bracket 1.5 and Burst Thermal 2.4, your model's build and its inference may each take up to 648 seconds (a little under 11 minutes); earlier versions keep 10 minutes each. The whole rebuild has 947 seconds (about 15 and a half minutes) in total.

Your **grade** runs from 0 to 1, and **higher is better**. Half of it is accuracy and half is design value: how well the model supports real design decisions. You can make at most one graded submission per Challenge per round (one epoch, about 72 minutes; the page says round), up to a daily allowance per Challenge that depends on validator capacity (at least one a day). Resubmitting the same recipe returns its earlier grade; a failed build or an infrastructure failure doesn't use your allowance. A graded submission reads one of four ways: a new best, did not improve on your best, **not eligible** (it names the mandatory gate that failed), or **does not count**, which shows no total and says why: **not admitted** (an invalid result, an ineligible design decision, or a named score part below its required minimum) or **not graded** (an infrastructure problem or indeterminate evidence, which doesn't use your allowance). When a mandatory gate fails, the result reads *graded: not admitted: failed the mandatory gate(s) <names>*, with the names the Ladder itself reports; a leg below its minimum names the leg only. **Not admitted** covers a leg minimum, an invalid candidate and an ineligible decision, and **not graded** covers an infrastructure problem and indeterminate evidence: these reasons are a closed list.

## What the exam tests

The exam is not a surprise: you can read what it measures and what passes. What stays private is where its cases are and how they were chosen. The same text is served as structured fields by the describe tool (`published_exam`); each value below is Carbon's registered value for that version (scoring v2) at the time of writing, and where a value is not registered yet this page says **not yet registered**.

**The score** is `TOTAL = 0.5 * A + 0.5 * D`.

- **A** (accuracy and physics) is the mean of four legs: *A_acc* (accuracy on the exam's cases), *A_robust* (the same accuracy on the worse of two groups of cases: nearer the main limit and further from it), *A_law* (how far your model's outputs break the measured physics laws, as an equivalent normalised output error) and *A_response* (how far your model's sensitivity to each input departs from the slope fitted on public TRAIN, in the same units).
- **D** (design value) is the mean, over the exam's design targets (6 per set), of one value per target, kept at or below *C*. For each target Carbon runs a fixed, seeded optimizer that searches for a good design using only your model's predictions, with a budget of *B* queries per target (*B*: **not yet registered**). It takes the best design your model predicts to be feasible among those it queried and looks that design up in Carbon's own pre-solved set of designs for the target (100 per target); nothing is solved at grading time. The target's value is 0 if the pick is not feasible. Otherwise it is *q* times *h*: *q* (closeness) is how near the pick's objective is to the best known, measured from the median feasible design, so a typical design scores 0 and only near-optimal ones score well; *h* (honesty) is exp(-*e* / *s_h*), which falls as your model's own error *e* at the pick grows (*s_h*: **not yet registered**). *C* is how well your model predicts the decision margins of every candidate design, and it caps D. The targets, the pre-solved designs and their true values, the best known designs and the optimizer's seeds are private and are never shown, so the only things you see are the rounded total and the closed reason codes. The same model and the same seed give an identical score.
- **Minimums.** No leg minimum is registered in the sealed pack. Each batch takes its minimums from Carbon's baseline run on that batch; a result below a minimum is *not eligible* (equal passes).
- **Gates come before the score.** A failed gate is never made up for by a good score. Physics laws marked *gated* below fail a model; laws marked *measured* count in *A_law* but are **not yet registered as gate margins**.
- **Practice and exam.** Practice uses the public bank, with public-seeded probes; its totals are not exam totals. The exam uses private cases, drawn near the design limit inside the published validity region, so that some designs pass and some fail. Exams rotate at most every 90 days, with a weekly overfit check.
- **King of the hill.** The best total wins. A challenger must beat the king by the registered margin, a tie keeps the king, and the first king must beat Carbon's baseline by the margin. The margin is **not yet registered**, so takeovers are paused.

### Ribbed Bracket 1.7 (reserved)

Scoring `f08-pool-sealed-v2`, with development scoring
`f08-dual-development-grid-v3`. This prospective version applies the owner's
frequency-band correction: answers must have the correct seven-value width,
finite values, non-negative compliance and strictly positive peak frequencies.
The 80–600 Hz band no longer gates individual answers. A frequency overshoot
is an accuracy error in A. Dynamic peaks must still be at least the static
compliance and ordered by damping; design feasibility limits are unchanged.
Practice and pool answers use the same rule. Pool constants remain **not yet
registered**, so 1.7 remains **RESERVED** and refuses official grading until
the owner selects them. Versions through 1.6 keep their original band gate
and evaluation identities; historical grades retain their meaning.

### Ribbed Bracket 1.5

Scoring `f08-dual-sealed-grid-8x1-v2`. Exam: 8 cells (8 designs x 1 condition); probes are random points inside the validity region with a step of 0.005 to 0.015 of each input's span.

- **Hard gates:**
  - `finite_native_summary`: the graded rows and both repeats are finite and non-negative, and the three peak frequencies lie in the band (frequency band 80 to 600 Hz)
  - `paired_repeat`: the graded run and the two fresh repeats are identical, per case (rule exact_equality)
  - `complete_accepted_reference`: the exam's references are complete and accepted
  - `verified_pick_feasible`: the model's pick is feasible by the references; otherwise D = 0 (mass at most 0.45 kg, static tip compliance at most 0.03 mm/N, dynamic tip compliance at most 0.15 mm/N)
  - `physics_laws`: no gated law is violated, no sign law fails, and the probe predictions are usable
- **Physics laws (gated):** `peak_not_below_static`: the peak dynamic compliance is at least the static compliance at every damping level; `peaks_ordered_by_damping`: the peak at zeta 0.005 is at least the peak at 0.01, which is at least the peak at 0.02
- **Physics laws (measured, not yet gate margins):** damping_scaling_005_010 (peak at 0.005 = 2 x peak at 0.01, the 1/zeta peak scaling); damping_scaling_010_020 (peak at 0.01 = 2 x peak at 0.02); frequency_independence_005_010 (peak frequency at 0.005 = at 0.01); frequency_independence_010_020 (peak frequency at 0.01 = at 0.02)
- **Sign laws:** static tip compliance rises with length and falls with width, thickness, rib height and rib thickness; peak frequency falls with length and rises with rib height
- **Design-value scales:** static margin 0.003 mm/N, dynamic margin 0.015 mm/N, resonance 10.0 Hz, objective D scale 0.01 mm/N
- **Limits:** `mass_kg_max` = 0.45, `static_tip_mm_per_n_max` = 0.03, `dynamic_tip_mm_per_n_max` = 0.15
- **Input ranges:** length 180–260, width 60–100, thickness 4–8, rib_height 8–16, rib_thickness 3–5, relief_length 20–60
- **Registered measurement uncertainty U:** static_tip_mm_per_n = 6.7e-07, worst_dynamic_mm_per_n = 3.9e-05, mass = not yet registered

### Burst Thermal 2.4

Scoring `f02-dual-sealed-grid-8x1-v2`. Exam: 8 cells (8 designs x 1 condition); probes are random points inside the validity region with a step of 0.005 to 0.015 of each input's span.

- **Hard gates:**
  - `finite_peak`: every predicted peak is a finite number
  - `paired_repeat`: both fresh repeats equal the graded outputs exactly, per case (tolerance ulp 0)
  - `reference_acceptance`: the exam holds only accepted references that were compared across solver rungs
  - `verified_pick`: the model's pick is feasible by the references (peak top c max 95.0)
  - `physics_laws`: no gated law is violated, no sign law fails, and the probe predictions are usable
- **Physics laws (gated):** `peak_not_below_initial`: every predicted peak is at least the initial temperature
- **Physics laws (measured, not yet gate margins):** affine_in_power (the peak is affine in power at fixed on-time)
- **Sign laws:** the temperature rise over the initial rises with peak power and with on-time
- **Design-value scales:** value scale 100.0 J, margin scale 1.0 degC
- **Limits:** `peak_top_c_max` = 95.0
- **Input ranges:** peak_w 70.0–100.0, on_time_s 4.0–6.0
- **Registered measurement uncertainty U:** peak_top_c = 0.012

### Motor 1.4

Scoring `motor-dual-sealed-batch-30-v2`. Exam: 30 cells (5 designs x 6 conditions); probes are random points inside the validity region with a step of 0.005 to 0.015 of each input's span.

- **Hard gates:**
  - `native_motor_valid`: no cell fails a native gate against either fresh repeat or between the repeats, and every cell is scorable
  - `complete_fixed_coverage`: all 30 cells are scored (cells 30)
  - `physics_laws`: no gated law is violated, no sign law fails, and the probe predictions are usable
  - `schema_finite`: the torque curve is present with 60 finite values (angle steps 60)
  - `motoring_mean_nonnegative`: mean(torque) is at least -(1e-3 x max|torque| + 1e-3 N.m) (relative 0.001, floor nm 0.001)
  - `paired_repeat`: a duplicate's prediction equals the original's within 32 float32 ulp (ulp 32)
- **Physics laws (gated):** `mean_torque_positive`: the mean torque of the predicted curve is positive wherever the current density exceeds 1 A/mm^2
- **Physics laws (measured, not yet gate margins):** linear_in_current (mean torque scales with current density, K = 1.5); zero_current_torque (mean torque tends to 0 as current density tends to 0)
- **Sign laws:** mean torque rises with current density and falls with current angle
- **Design-value scales:** torque margin 0.1 N.m, ripple margin 0.01 ripple fraction, objective D scale 0.01 ripple fraction
- **Limits:** `min_mean_torque_nm` = 4.0, `max_ripple_fraction` = 0.3
- **Input ranges:** magnet_mm 1.5–4.0, embrace 0.55–0.95, airgap_mm 0.3–1.0, slot_open_deg 1.0–6.0, tooth_mm 2.5–5.0, slot_bottom_mm 34.0–42.0, current_density_a_mm2 0.0–15.0, current_angle_deg 0.0–60.0
- **Registered measurement uncertainty U:** mean_torque_nm = 0.0052, ripple_fraction = 0.026

### Cooling 1.4

Scoring `cooling-dual-sealed-batch-16-v2`. Exam: 16 cells (4 designs x 4 conditions); probes are random points inside the validity region with a step of 0.005 to 0.015 of each input's span.

- **Hard gates:**
  - `native_cold_plate`: every cell is scorable against both fresh repeats and the two repeats agree
  - `complete_grid_common_mask`: the grid is a complete 4 x 4 cross
  - `selected_design_verified_feasible`: the model's pick is feasible by the references at every condition (die peak c max 100.0, hydraulic power w max 0.25)
  - `physics_laws`: no gated law is violated, no sign law fails, and the probe predictions are usable
  - `schema_finite`: peak, the 30-value profile and the pressure drop are present and finite (profile values 30)
  - `face_above_inlet`: the lowest profile value is above the inlet
  - `peak_bounds_profile`: the peak is at least the highest profile value less 32 float32 ulp (ulp 32)
  - `pressure_drop_positive`: the pressure drop is above zero
  - `paired_repeat`: a duplicate's prediction equals the original's within 32 float32 ulp (ulp 32)
- **Physics laws (gated):** `peak_above_profile`: the peak is at least the highest profile value; `profile_above_inlet`: the lowest profile value is at least the inlet; `pressure_positive`: the pressure drop is above zero
- **Physics laws (measured, not yet gate margins):** inlet_shift_temperatures (moving only the inlet by 5 degC moves the peak and every profile segment by the same amount); pressure_ignores_hotspot (mirroring only the hotspot inputs leaves the pressure drop unchanged)
- **Sign laws:** the temperature rise falls with flow and rises with heat load and hotspot ratio; the pressure drop rises with flow and falls with channel width and depth
- **Design-value scales:** die margin 1.0 degC, hydraulic margin 0.025 W, objective D scale 0.025 W
- **Limits:** `die_peak_c_max` = 100.0, `hydraulic_power_w_max` = 0.25
- **Input ranges:** channel_width_mm 0.2–0.5, fin_width_mm 0.2–0.5, channel_depth_mm 1.0–3.0, flow_lpm_per_kw 1.25–2.0, inlet_c 30.0–45.0, heat_load_w 500.0–1500.0, hotspot_ratio 1.0–3.0, hotspot_center_mm 3.0–27.0, hotspot_width_mm 1.5–3.5
- **Registered measurement uncertainty U:** die_peak_c = 0.037, hydraulic_w = 3 % of the cell's value

**Current kings** (Overview): for each Challenge whose grader you use, who holds it now (their mining key address and score on this exam version), and the **score to beat**: the king's score plus the registered margin. With no king yet, you need to beat Carbon's baseline. Until the margin has been measured, the card says **Takeovers paused** and shows no score to beat. The card never shows anyone's recipe.

---

## How you're tested

This is how a version graded by the new exam is tested; `describe` serves the same lines as `published_exam.how_you_are_tested`, and the Launchpad page shows them under the Challenge's **How you're tested**. Nothing hidden is listed here: not the targets, where the extended range ends, how far the limits move, or the optimizer's starting points.

- **The grade.** Your grade is 0.5 x A + 0.5 x D, from 0 to 1, higher is better. A is accuracy and physics. D is design value.
- **Inverse design.** Design value is inverse design. Carbon's own fixed optimizer (CMA-ES) uses your model to search for designs that meet each hidden target's limits, within a fixed number of model queries, and picks one design from a set Carbon has already solved. A pick that does not meet the limits scores 0 for that target; otherwise it scores how close it is to the best known design, times how honest your model's prediction was at that pick. You cannot change the search. The query budget is not yet registered.
- **The search, to copy.** You may copy this search for your own practice; it never enters the grade. In each target, CMA-ES proposes points in the normalised design box and each proposal snaps to the nearest solved design not yet queried; your model predicts that design's outputs; designs are ranked first by whether they are predicted to meet the limits and then by the predicted objective. After the fixed number of queries the pick is the best predicted-feasible design among those queried, and its true outputs are looked up. A pick that is not feasible scores 0. Otherwise the target scores closeness times honesty, where closeness = (objective of the pick - median feasible objective) / (best known objective - median feasible objective), clipped to 0..1, and honesty = exp(-e / s), with e your model's uncertainty-normalised error at the pick. D is the mean over the targets, limited by C. The query budget, the step size and s are not yet registered.
- **Tighter and looser limits.** Some targets are tighter or looser versions of the base problem: the same design question with its limits moved. A model that only works for the base limits loses there. How far the limits move is not published.
- **Outside the training range.** Some exam questions lie just outside the range your training data covers. They count: accuracy there, inverse-design picks there, and the physics gates there. How far that range extends, and where its questions are, is not published.
- **Physics gates.** The physics gates that check a single answer run on every answer your model gives, inside and outside the range. Failing any gate means no score at all, however good the rest. You are told which gate failed, never which design.
- **Speed.** Your model must answer each design in at most 1/500 of the time the reference solver needs for one design. The time is measured on the validator's machine, for the whole batch of exam designs with the model's loading included, divided by the number of designs. Failing it is a failed gate (speed), and no score. The ceilings per design are: Burst Thermal 0.38 s, Ribbed Bracket 2.08 s, Cooling 2.84 s, Motor 3.3 s.
- **Minimums.** Each score part also has a minimum, set from Carbon's own baseline on the exam. A part below its minimum makes the submission not eligible, and the part is named. Until a version's minimums are registered, the page says minimums are not yet set.
- **Practice.** Practice runs on the public bank and shows what it can of A, the gates and the minimums. It never touches the exam's hidden targets or its out-of-range questions, and a practice total is not an exam total.

**Motor 1.5: the values the owner has registered.** The search asks the model 60 times per target, from a first step of 0.25 of the normalised design box. Honesty is exp(-e / s) with s = 1, and e is the largest uncertainty-normalised error over the outputs at the pick. Each of the four accuracy parts of A is tightened as 1 / (1 + 3 x) of its normalised error x. A_gen is scored the same way on its own slice with a scale of 0.03 x the training spread of each output (mean_torque_nm 0.0743, ripple_fraction 0.0868), and the final A is the mean of A and A_gen. D is limited by C: it is the smaller of the two. Targets, pools and seeds stay sealed.

Your agent can read these rules as data: `carbon_challenges_v1__scoring_rules` with the Challenge id and version returns the formula, the legs, the gate names, the minimums (or "not yet registered"), the speed gate's ceiling per design, and the lines above, from the same published block `describe` serves. It refuses a version that publishes no exam rules, with the next step.

## Writing a graph

A graph recipe is a JAX program. Carbon lowers it on your machine, checks every operation, rebuilds it on its own side and trains it itself; your Python never runs there. Ribbed Bracket 1.5, Burst Thermal 2.4, Motor 1.4 and Cooling 1.4 take graphs on the open operation set (allowlist v8).

- **Operations.** Every pure, deterministic array operation JAX has is allowed: elementwise math (inverse trigonometric and hyperbolic functions, special functions, rounding), comparisons and bit operations, reductions and cumulative operations, sorting and `top_k`, pooling windows, gathers and scatters (`.at[].add` and the rest), FFTs, convolutions, dense linear algebra (`cholesky`, triangular solves, LU, QR, `eigh`, `eig`, `svd`, and through `jnp.linalg` also `solve`, `inv`, `det`), `scan` with a static length, `cond` and `switch`, `jax.checkpoint`, the matmul `precision` argument, and your own `custom_jvp` and `custom_vjp` rules, which Carbon carries and runs as you wrote them. Debug prints and sharding hints are dropped. Randomness comes only from Carbon's init key, in the init graph, and an init graph may build any structured table (identity, DFT, orthogonal bases).
- **Still refused**, with the operation named in the refusal: host callbacks (`pure_callback`, `io_callback`), `custom_call` and foreign-function calls, infeed and outfeed, collectives and device placement, hardware or unkeyed random numbers, and uninitialised memory. `while` loops are not served yet; use `scan` with a fixed length.
- **What Carbon does to your data.** It standardises each target column to zero mean and unit deviation from the selected TRAIN rows, trains in those units and decodes the outputs back. It does not standardise the inputs: normalise them inside your graph (the TRAIN box is in `describe`). Training runs in the interface's dtype (float32 on Ribbed Bracket and Burst Thermal, float64 on Motor and Cooling); your graph may compute in float64 inside, and Carbon turns 64-bit mode on when it holds a 64-bit value, with the outputs staying in the interface's dtype.
- **Your own loss.** A spec may define `loss(params, pred, target, *inputs)` returning one scalar over the whole training batch; Carbon trains with it in place of the menu loss (`mse`, `mae`, `huber` and the per-output weights are then unused). `pred` and `target` are in the units Carbon trains in (standardised), `inputs` are the batch's inputs, `params` are the model's parameters, so a loss can weigh cases against each other or regularise. It is a graph like the rest: every operation in it is checked, and the exam never uses it (the exam grades with the Challenge's own metric).
- **Constants and static values.** Everything written into the graph that can carry a fitted number counts against one 16 KiB budget for the whole submission, by what it holds: a float by its real size (half precision two bytes, float32 four, float64 eight, complex64 eight, complex128 sixteen), an integer by the bits its range needs (a lone scalar by the bits of its value), a boolean one bit, identical copies once. The static values of your nodes count too: every integer, boolean or float in an op's parameters (slice and gather indices, padding, strides, shapes, permutations, a scan's length), each by its own bits. A normal graph of a dozen conv or attention blocks costs a few hundred bytes of this, so the budget only bites when numbers are being carried. Build structure in the graph (`iota`, comparisons, one-hot products) rather than pasting tables; a table of small integers is cheap, a table of fitted floats is not.

## Bring your own agent

Any agent that speaks MCP can drive Carbon with the same tools the page uses: launch, practise, freeze, submit and check your result. The page shows everything your agent does, live, and you can message it from the campaign's Conversation box.

**Claude Code:**

```bash
claude mcp add carbon --scope user -- ~/carbon/.venv/bin/carbon-mcp --configuration ~/.carbon/development-launchpad/environment/runner-profile.json
```

Then ask it, for example: *"Launch a Carbon campaign on electric-motor-magnetics 1.3 with agent none, run two practices, freeze the better eligible one, submit it, and check the result."*

Your agent can set up practice-only too: `carbon_setup_status` lists `practice_choice` (the call is `carbon_setup_practice` with `{"confirm": true}`). An agent should offer it and take it only when you choose it.

**Hermes:** choose **Hermes** in Setup step 3. Setup writes a ready Hermes profile called `carbon`. Then run:

```bash
hermes -p carbon chat
```

Hermes asks you before each action that changes something (launch, practise, freeze, submit). To let it run unattended, set `trust: full` for the `carbon` server in `~/.hermes/profiles/carbon/config.yaml`, then run `hermes gateway stop` once.

---

## When something goes wrong

| You see | Do this |
|---|---|
| The page asks for your token | Show it with the `cat` command in step 3; an update keeps the same token. |
| Setup says **your compute check no longer matches this install** | Do the step it names next (check Compute again, or run the installer's update). |
| After an update, Setup says **an update set your compute check aside** | Check Compute again. An update re-checks your compute; this is shown when that could not finish. |
| `carbon-mcp` says **your runner profile cannot be used here** | It is serving setup instead, so your agent can fix it: call `carbon_setup_status`, then `carbon_setup_recheck {confirm: true}` (re-checks compute and writes your profile again). Once the profile is written, `carbon_launch` appears. |
| Submit says your receiver **could not be reached, or did not answer** | Start your tunnel if the receiver is on this machine, or wait, then submit again. If it did get your submission, you get that result back; it is never graded twice. |
| A submission says **rebuilt, not graded yet** | Click **Check for result** on the page (an agent runs `check_result`): that reads the latest grade from the validator; the campaign view shows the one last read. A grade from another of your submissions is shown apart and is not this one's. |
| A campaign says **Interrupted** | Click **Resume**. Your work is kept. |
| A practice says it **needs more time than the campaign has left** (time limit reached) | It is your own time limit, not a failure: each practice reserves its whole build-and-run allowance before it starts. Launch a new campaign with a larger time limit (`budget.elapsed_seconds`, or leave it out), or leave more of the time for practice (a long planning stage uses it up). |
| Setup or a practice says your GPU machine's **NVIDIA driver is older** than a GPU worker's CUDA runtime | Update the driver on your GPU machine (`nvidia-smi` shows the newest CUDA it runs), then check Compute again. Until then that backend practises on CPU; the other backend's GPU worker may still run. |
| A practice ends **practice_could_not_run** (no result, nothing counts against you) | An infrastructure problem (not your recipe): a host check, the build, or a step after it stopped. Check Setup (`carbon_setup_status`) and that Docker and the worker images are present, then practise again. The campaign's operation folder holds a `failure-<stage>.json` naming the stage (and, for a known cause, a closed reason such as `REQUIRED_LOCAL_IMAGE_ABSENT`). |
| A practice ends **practice_host_too_small** (it names the memory and CPUs Docker sees and the worker needs) | This machine is too small for the practice worker: Docker must see at least 17 GiB of memory and 4 CPUs (a 16 GB machine shows about 15.6 GiB). Nothing ran and nothing counts against you. Use the [supported setup](#supported-setup) (32 GB of RAM), or practise on a bigger machine. `docker info` shows what Docker sees (MemTotal, NCPU). |
| A practice says it **could not run on this machine** (a catalog entry with no CPU build here, whose GPU build did not run) | Fix the reason it names: update an NVIDIA driver that is too old for the worker, or pull the pinned uv image GPU builds prepare with (the command is in the message; the installer pulls it with `--gpu`). Or choose a catalog entry that has a CPU build. Nothing was scored. |
| A practice says **not eligible** | It broke a physics rule; the card says which one. Try another recipe. |
| Freeze, submit, commit or check for result says **registration required** | You set up to practise without registering. Register, then follow the four steps under **Just want to practise?**. |
| A campaign says **practised without registering** and takes no new work | It was made with your practice identity before you registered. It stays readable; start a new campaign to practise, freeze and submit. |
| Setup or a campaign says your **practice identity** is missing, damaged or not readable by you alone | Run `chmod 600` on it if it is only readable by others, otherwise choose **Practise without registering** again at Setup's first step, then **Review and launch**. |
| Submit says the validator doesn't serve this Challenge | No validator grades that Challenge yet. Practise it now; submit when one appears. |

**Need help?** Ask in Carbon's Discord: <DISCORD_INVITE_URL>. Miners and the Carbon team answer there.

---

## Questions miners ask

**Can I carry what I learn from my own data into my recipe, and hardcode fitted constants or tables in a Level 4 graph?**

Yes to design choices, and yes to a small amount of fitted numbers; no to a trained starting point.

- **Design choices: yes.** What you learn from your own data can shape the recipe: the structure of the model, your own loss, the hyperparameters, the priors you build in. The validator rebuilds your recipe and trains it from scratch with Carbon's trainer, so whatever you carry in has to be in the recipe.
- **Fitted constants and small tables inside the graph: yes, inside the 16 KiB constants budget.** Numbers written into the graph, and the static integers in its op parameters, count by their real size (see **Constants and static values** under *Writing a graph*): a float by its size (float64 eight bytes), an integer by the bits its range needs, a boolean one bit, identical copies once, all against one 16 KiB budget for the submission. Build structure in the graph (`iota`, comparisons, one-hot products) rather than pasting float tables; a table of small integers is cheap, a table of fitted floats is not.
- **A pretrained starting state: no.** A recipe cannot carry trained weights or an `initial_state`; the validator starts from scratch every time.
