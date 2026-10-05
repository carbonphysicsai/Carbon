## 2026-10-05 — LAUNCHPAD-PAGE-USABILITY-01: the Launch page offers the output cap, and says what a miner can do while no evaluation endpoint is published

**Authority.** The Test Engineer, for findings C3 and C10 of the Graphite
Test executor's Launchpad usability findings (2026-10-05), under the owner's
direction that the Control Center be usable by humans and agents alike.
Engineering decisions within that scope, recorded by the executor. No
scientific value, threshold, gate, tolerance, economic parameter or public
request field changes. Nothing is deployed, published or configured: an
evaluation endpoint for testnet 567 is an operator action reserved to the
owner (LP-PROD-E, LP-PROD-G).

**Ownership checked.** No ticket under `.agent/tickets/` and no LP-PROD
decision owns either finding. LP-PROD-A recorded that a miner "can already
set `max_output_tokens`" (over MCP); LP-PROD-E publishes endpoints as data and
LP-PROD-G builds the validator service; neither puts the cap on the page or
the no-endpoint state next to Submit.

### D1. The Model step offers `model_settings.max_output_tokens` (C3)

**Observed.** The launch operation already takes `model_settings`
(`operations.FIELDS`, both doors), and the runner validates it
(`runner._launch_choice` through `model_provider.select`: an integer in
`OUTPUT_TOKEN_BOUNDS`, 256 to 131,072, else `model_selection_refused`; settings
without a provider are `model_provider_required`). The page never sent it.

**Decision.**

1. **No new field.** The page sends the existing launch field
   `model_settings: {"max_output_tokens": N}`, only when the miner sets a
   cap, and only with `model_provider` and `model` (the runner refuses
   settings without a provider). Blank sends nothing: the runner's default
   applies. `capabilities._launch().browser_sends` names `model_settings`.
2. **The server's numbers.** The capability document's `model.output_cap`
   carries the bounds (`OUTPUT_TOKEN_BOUNDS`) and, per offered model, the
   default a launch with no cap gets: `model_provider.output_maximum`, the
   same value `select(output_default=OUTPUT_DEFAULT_V2)` chooses, with its
   basis. The page shows that default and its basis.
3. **The page mirrors, the runner decides.** The Model step does not pass a
   value outside the bounds or a non-integer, and says why. The runner
   re-validates every launch and its refusal stands. A cap above a model's
   documented maximum is not blocked (the runner does not block it); the
   page warns that the provider may refuse the call.
4. **MCP text.** The `model_settings` description now states the
   max_output_tokens bounds, read from `OUTPUT_TOKEN_BOUNDS`, and the
   refusal code.

### D2. The page and MCP text say what works while no intake is configured (C10)

**Observed.** With no validator deployment or intake for a Challenge in the
runner profile, every submit is refused `evaluation_unavailable`
(`runner.evaluation_refusal`). The page showed the HTTP refusal as the code
alone (it dropped the controller's `next_step`), and the next step itself
said to add an intake under setup, which a miner cannot do while Carbon
publishes none.

**Decision.**

1. **The next step.** `supervisor.NEXT_ACTIONS["evaluation_unavailable"]`
   says the frozen candidate is kept and cannot be evaluated yet; that when
   an intake is published the miner updates Carbon and reviews setup again
   (`carbon_setup_review`), or names an intake they run; and that until then
   they can still launch, practise, observe, and stop or pause. Both doors
   read it.
2. **The page shows it.** A refused keyed operation (practice, freeze,
   submit) shows the controller's `next_step` after the code. A refusal
   banner for `evaluation_unavailable` links to setup's Review.
3. **Before submitting.** The Submission tab (the miner's form, and the note
   on a Graphite campaign) and the launch Review read the prelaunch review's
   `evaluation_endpoints` for the campaign's Challenge. Unless it is
   `INTAKE_CONFIGURED` or `VALIDATOR_ON_THIS_MACHINE`, they say plainly that
   evaluation is unavailable today, what still works, and the review's next
   step. Submit stays enabled: the controller decides, and a configured
   intake can appear between reads.
4. **MCP text.** The `submit` operation description and
   `carbon/miner_mcp/README.md` say the same, and point at
   `carbon_setup_status`'s `evaluation` for which Challenges have one.
5. **Claim discipline.** The text says "evaluation", meaning the
   DEVELOPMENT comparison a validator runs. It makes no readiness,
   qualification or reward claim; a test holds that.

### Coordination

PR #651 (`claude/operator-usability`) edits the `halt` and `launch`
descriptions, `mcp_operations._door_notes` and the README's door paragraph.
This change edits neither description and adds its README paragraph after
that one.
