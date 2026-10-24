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

- **A Linux machine** (x86-64), or Windows with WSL2. It needs Docker and free disk for Carbon's images; the installer checks the space first and says how much it needs. A GPU is optional.
- **To practise: nothing to register.** You can run your agent and practise on any Challenge without a wallet, a registration or a signer (see **Just want to practise?** in step 4).
- **To freeze and submit: a Bittensor wallet with a hotkey registered on subnet 567.** Carbon never asks for your keys or seed phrase. Your hotkey stays in your own wallet.
- **A model key from a provider**, if you want Carbon's agent (Graphite) or Hermes to do the research. Setup lists the providers each agent can use. Save the key in a file only you can read; Carbon reads it from that file. Skip this if you bring your own agent, e.g. Claude Code, which uses its own model.

---

## 1. Install

```bash
git clone https://github.com/carbonphysicsai/Carbon.git ~/carbon
~/carbon/scripts/install_miner.sh --pytorch --service
```

Add `--gpu` if the machine has an NVIDIA GPU.

The installer checks your machine, sets up Carbon's environment, builds the images your practice runs use, and starts the **Control Center**, the web page where you run everything. It never asks for a key or password.

**Updating.** Run `~/carbon/scripts/install_miner.sh --update --pytorch`, repeating the other options you installed with (e.g. `--gpu`). If the disk is short, it lists Carbon's own images from earlier installs that this install no longer uses, and asks before removing them; nothing else is touched. To say yes up front, add `--remove-old-images`. If the disk is still short, the update separately offers to prune Docker's unused build cache. That cache is shared by every Docker build on the machine, not only Carbon's, so other projects' builds are slower the next time; it asks its own yes, never prunes by default, and `--prune-build-cache` says yes up front. An update checks your setup's compute again, rewrites your runner profile, and says what changed. If it can't (for example, it rebuilt images your compute check named), it sets the check and your runner profile aside and says so in its **Next** lines: check Compute again on the page, or from your agent or `carbon-mcp` with `carbon_setup_recheck {confirm: true}`, then review.

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
   - **Fund your wallet first.** Joining is paid in TAO from your money key (the coldkey), so put a little TAO there before you join. Paste your money-key address (public) into the **Put some TAO in your wallet** box: it shows the address to copy and as a QR code, and **Check my balance** reads your balance and the current joining cost from the chain, in TAO, with the block it was read at. It says **Ready to join** when your balance covers the cost, before transaction fees; your wallet shows the exact cost again when you sign, and that figure is the one that counts. The page only reads: it never moves your funds, and it never asks for a key, password or phrase. **How do I buy TAO?** lists the steps, with Coinbase and Kraken as plain links (examples only; Carbon has no link or share in either).
3. **Who researches.** Choose one of three:
   - **Graphite**, Carbon's research agent, running on your model key.
   - **Your own agent**, e.g. Claude Code or Codex, connected over MCP (see below).
   - **Hermes**, Nous Research's open agent (see below).
4. **AI model.** Pick a provider and model, give the path to your key file, and agree to the small, quoted cost of a test call.
5. **Compute.** Where practice runs: this machine's CPU, this machine's GPU, or a GPU machine you rent yourself. With a GPU, **Test my GPU** runs each GPU framework (JAX and PyTorch) once on your GPU, about a minute each, on synthetic data it makes itself; it shows the exact commands first and runs only when you agree. You get a plain answer per framework (works, or doesn't, with what to fix, e.g. an NVIDIA driver too old for the worker). It writes no score. Your agent can offer the same step: `carbon_setup_test_gpu`, with the consent `carbon_setup_status` lists under `test_gpu`.
6. **Review and launch.** **Save my settings** saves your settings and loads them. Carbon's own grader is used for each Challenge where one is published. To use your own, open **Advanced: where a Challenge's grader runs** and give its **grading address** and **the grader's mining key address** (public, starts with 5…; never a key, password or seed phrase).

Once you save your settings, the model catalog (the ready-made model types you can build from) installs itself in the background, and the page shows how far it has got. A Challenge can practise a catalog model as soon as that entry is installed. If it stops, its log says why; you can also install it yourself:

```bash
cd ~/carbon && .venv/bin/python -B -m scripts.dev.catalog_install --state-dir ~/.carbon/development-launchpad
```

## 5. Pick a Challenge and start a campaign

A **Challenge** is a physics task, e.g. motor magnetics, a chip cold plate or a ribbed bracket. Open **Challenges**, read one, and click **Start a campaign**.

With Graphite you set your limits up front: how many model calls, how many dollars, how much time. Graphite uses them to the end: near your money or time limit it shortens its last calls to fit what is left, and stops only when not even one short call fits (about 2 minutes, or a 512-token reply). The page then says which limit stopped it (money, model calls, practice runs or time) and what to raise next time. Graphite plans, builds models, practises them, and picks the best.

## 6. Practise, freeze, submit

- **Practise.** Pick a tested model type under **Backbone** and, if you like, **Training steps** and **Learning rate** (leave them empty for its tested default); the whole recipe is under **Advanced: the recipe as JSON** if you want to edit it by hand. Each practice trains a model from your recipe and scores it on public practice cases: one graded total from 0 to 1, higher is better, with its error details beside it. A practice that breaks a physics rule is marked **not eligible**, however good its error. Practice costs no exam and has no limit on how often you run it. It runs on your own compute, and if an AI agent researches for you, its model calls are billed to your model key.
- **Freeze.** When you have a good, eligible practice, freeze it. That fixes the exact recipe you'll send.
- **Submit.** The validator rebuilds your model from the recipe, then grades it on a hidden exam.
- **Rebuild resources.** On the newer versions (Motor 1.3 and 1.4, Cooling 1.2 to 1.4, Ribbed Bracket 1.3 to 1.5, Burst Thermal 2.2 to 2.4, Battery 2.1), your model is built and run with 4 CPUs, 16 GiB of memory, 4 GiB of scratch space and up to 2 GiB of output; earlier versions keep 2 CPUs and 4 GiB of memory. There is no limit on model size: only these resources and the time limit bind.
- **Build time limit.** On Motor 1.4, Cooling 1.4, Ribbed Bracket 1.5 and Burst Thermal 2.4, your model's build and its inference may each take up to 30 minutes; earlier versions keep 10 minutes each. The whole rebuild still has 30 minutes in total.

Your **grade** runs from 0 to 1, and **higher is better**. Half of it is accuracy and half is design value: how well the model supports real design decisions. You can make at most one graded submission per Challenge per round (one epoch, about 72 minutes; the page says round), up to a daily allowance per Challenge that depends on validator capacity (at least one a day). Resubmitting the same recipe returns its earlier grade; a failed build or an infrastructure failure doesn't use your allowance. A graded submission reads one of four ways: a new best, did not improve on your best, **not eligible** (it names the mandatory gate that failed), or **does not count**, which shows no total and says why: **not admitted** (an invalid result, an ineligible design decision, or a named score part below its required minimum) or **not graded** (an infrastructure problem or indeterminate evidence, which doesn't use your allowance).

## What the exam tests

The exam is not a surprise: you can read what it measures and what passes. What stays private is where its cases are and how they were chosen. The same text is served as structured fields by the describe tool (`published_exam`); each value below is Carbon's registered value for that version (scoring v2) at the time of writing, and where a value is not registered yet this page says **not yet registered**.

**The score** is `TOTAL = 0.5 * A + 0.5 * D`.

- **A** (accuracy and physics) is the mean of four legs: *A_acc* (accuracy on the exam's cases), *A_robust* (the same accuracy on the worse of two groups of cases: nearer the main limit and further from it), *A_law* (how far your model's outputs break the measured physics laws, as an equivalent normalised output error) and *A_response* (how far your model's sensitivity to each input departs from the slope fitted on public TRAIN, in the same units).
- **D** (design value) is `min(V, C)`. *V* is the mean of *V_pair* (design pairs ordered correctly), *V_feas* (cost of wrongly accepting or rejecting a design) and *V_var* (how good your model's pick is for the main limit and for that limit moved down and up by 5 %). *C* is how well your model predicts the decision margins of every candidate design. A pick the references do not verify as feasible gets D = 0.
- **Minimums.** No leg minimum is registered in the sealed pack. Each batch takes its minimums from Carbon's baseline run on that batch; a result below a minimum is *not eligible* (equal passes).
- **Gates come before the score.** A failed gate is never made up for by a good score. Physics laws marked *gated* below fail a model; laws marked *measured* count in *A_law* but are **not yet registered as gate margins**.
- **Practice and exam.** Practice uses the public bank, with public-seeded probes; its totals are not exam totals. The exam uses private cases, drawn near the design limit inside the published validity region, so that some designs pass and some fail. Exams rotate at most every 90 days, with a weekly overfit check.
- **King of the hill.** The best total wins. A challenger must beat the king by the registered margin, a tie keeps the king, and the first king must beat Carbon's baseline by the margin. The margin is **not yet registered**, so takeovers are paused.

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
| A practice says it **could not run on this machine** (a catalog entry with no CPU build here, whose GPU build did not run) | Fix the reason it names: update an NVIDIA driver that is too old for the worker, or pull the pinned uv image GPU builds prepare with (the command is in the message; the installer pulls it with `--gpu`). Or choose a catalog entry that has a CPU build. Nothing was scored. |
| A practice says **not eligible** | It broke a physics rule; the card says which one. Try another recipe. |
| Freeze, submit, commit or check for result says **registration required** | You set up to practise without registering. Register, then follow the four steps under **Just want to practise?**. |
| A campaign says **practised without registering** and takes no new work | It was made with your practice identity before you registered. It stays readable; start a new campaign to practise, freeze and submit. |
| Setup or a campaign says your **practice identity** is missing, damaged or not readable by you alone | Run `chmod 600` on it if it is only readable by others, otherwise choose **Practise without registering** again at Setup's first step, then **Review and launch**. |
| Submit says the validator doesn't serve this Challenge | No validator grades that Challenge yet. Practise it now; submit when one appears. |

**Need help?** Ask in Carbon's Discord: <DISCORD_INVITE_URL>. Miners and the Carbon team answer there.
