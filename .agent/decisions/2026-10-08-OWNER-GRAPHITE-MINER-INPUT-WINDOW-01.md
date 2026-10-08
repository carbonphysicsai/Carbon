## 2026-10-08 — OWNER-GRAPHITE-MINER-INPUT-WINDOW-01: a Graphite miner-edition plan defaults to the model's published input window

**Authority.** The owner, 2026-10-08, directly in the Launchpad Acceptance
session, verbatim: "I approve the LA-F9 exact-path exemption for the public
practice sets as the security owner. For LA-F8, default the miner edition to
the model's published input window (option a)." The first sentence is
recorded separately as OWNER-LA-F9-SECURITY-ACCEPT-01.

**Decision.** When a miner sets no `model_settings.max_input_tokens`, a new
Graphite miner-edition plan's input window is the selected model's published
input window. A `max_input_tokens` the miner sets still binds.

**What it amends.** LAUNCHPAD-FINDINGS-F8-F9, decision 2, left the default
window to the owner, and kept Carbon's shared default (65,536,
`model_provider.DEFAULT_SETTINGS`) for Graphite with an up-front advisory.
That is replaced for new Graphite miner-edition plans only. It mirrors
OWNER-LAUNCHPAD-PROD-02 decision 1 (no Carbon-imposed output cap) on the
input side: the campaign is the miner's own, on the miner's own budget, and
the miner's own cap binds.

**What it costs.** Each call reserves its whole window before it is sent, so
each call's reservation grows.
- On the default Engy model (`deepseek-v4-flash-0731`, 131,072-token output
  default) a call reserves about USD 0.053 instead of about USD 0.0147.
- A FULL launch therefore needs a higher money ceiling: its research share
  must hold one whole call. At the default 10% share that is about USD 0.53
  of `provider_nanodollars`, or about USD 1.06 with a hunt.
- The up-front warning from #810 (`graphite_input_window_too_small`) and the
  launch options state this. They show the window, the per-call reservation
  and the least FULL ceiling that a launch naming no model will freeze.

**Working decisions (the executor's, within the delegated engineering
authority).**
1. **"Published input window" is the published context less the output
   cap.** Engy publishes one context per model (`context_length`, equal to
   `max_model_len`), shared by the request and its reply. With the new
   plan's output default of 131,072 tokens, a window of the whole context
   would let a long request plus its reply pass `max_model_len`. The
   provider refuses that as an invalid request, which stops the campaign. So
   the default is the context less the plan's output cap: 917,504 tokens on
   the default model, the figure LA-F8 priced. If the miner caps the output,
   the window grows by the same amount.
2. **Only Carbon's recorded figures.** The context is read from
   `model_provider.published_context` (`PUBLISHED_CONTEXT_TOKENS`, the record
   #810 added, observed 2026-10-04). No model's size is hard-coded or
   guessed.
3. **Bounds.** The window is at most `INPUT_TOKEN_BOUNDS`' upper limit
   (1,048,576), and the plan records the bound when it applies. A model with
   no recorded context keeps 65,536, and the plan says so. So does a context
   too small to leave `INPUT_TOKEN_BOUNDS`' lower limit after the output cap;
   no recorded model is in that case.
4. **What freezes.** A new plan records how its window was chosen
   (`provider.input_window`: rule, basis, published context, output cap,
   bound) beside its selection. A frozen campaign keeps the window it froze
   with and resolves to the same record on resume. It is never
   reinterpreted.
5. **Scope.** Only new Graphite miner-edition product plans (battery, motor
   and cold plate). `DEFAULT_SETTINGS` is unchanged. So are autonomous and
   research-loop plans, internal Graphite (GRAPHITE-D34's table), Burgers
   and development-grant campaigns.
6. **Advisory.** The warning now applies only when a launch's window is at
   most 65,536, the window LA-F8 saw too small. That window is either the
   default for a model with no recorded context, or the miner's own
   `max_input_tokens`. It refuses nothing.

**Maturity.** Engineering only: implemented and tested with fixtures. No
campaign has run under the new default. No scientific value, threshold,
gate, price or ceiling changes.
