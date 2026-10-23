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

**Updating.** Run `~/carbon/scripts/install_miner.sh --update --pytorch`, repeating the other options you installed with (e.g. `--gpu`). If the disk is short, it lists Carbon's own images from earlier installs that this install no longer uses and asks before removing them; nothing else is touched. To say yes up front, add `--remove-old-images`. An update checks your setup's compute again, rewrites your runner profile, and says what changed. If it can't (for example, it rebuilt images your compute check named), it sets the check and your runner profile aside and says so in its **Next** lines: check Compute again on the page, or from your agent or `carbon-mcp` with `carbon_setup_recheck {confirm: true}`, then review.

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
3. **Who researches.** Choose one of three:
   - **Graphite**, Carbon's research agent, running on your model key.
   - **Your own agent**, e.g. Claude Code or Codex, connected over MCP (see below).
   - **Hermes**, Nous Research's open agent (see below).
4. **AI model.** Pick a provider and model, give the path to your key file, and agree to the small, quoted cost of a test call.
5. **Compute.** Where practice runs: this machine's CPU, this machine's GPU, or a GPU machine you rent yourself.
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

Your **grade** runs from 0 to 1, and **higher is better**. Half of it is accuracy and half is design value: how well the model supports real design decisions. You can make at most one graded submission per Challenge per round (one epoch, about 72 minutes; the page says round), up to a daily allowance per Challenge that depends on validator capacity (at least one a day). Resubmitting the same recipe returns its earlier grade; a failed build or an infrastructure failure doesn't use your allowance. A graded submission reads one of four ways: a new best, did not improve on your best, **not eligible** (it names the mandatory gate that failed), or **does not count**, which shows no total and says why: **not admitted** (an invalid result, an ineligible design decision, or a named score part below its required minimum) or **not graded** (an infrastructure problem or indeterminate evidence, which doesn't use your allowance).

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
| A practice says **not eligible** | It broke a physics rule; the card says which one. Try another recipe. |
| Freeze, submit, commit or check for result says **registration required** | You set up to practise without registering. Register, then follow the four steps under **Just want to practise?**. |
| A campaign says **practised without registering** and takes no new work | It was made with your practice identity before you registered. It stays readable; start a new campaign to practise, freeze and submit. |
| Setup or a campaign says your **practice identity** is missing, damaged or not readable by you alone | Run `chmod 600` on it if it is only readable by others, otherwise choose **Practise without registering** again at Setup's first step, then **Review and launch**. |
| Submit says the validator doesn't serve this Challenge | No validator grades that Challenge yet. Practise it now; submit when one appears. |

**Need help?** Ask in Carbon's Discord: <DISCORD_INVITE_URL>. Miners and the Carbon team answer there.
