# Miner FAQ

For the current DEVELOPMENT Launchpad. This is testing software, not a promise
of scientific qualification or earnings. Start with the
[installation guide](MINER_LAUNCHPAD_HANDOFF.md#installing-starting-and-updating-today-lp-prod-e-2026-10-03).

## Who can see my work?

Your local research, extra data and unsubmitted recipes stay in the environment
you control. If you connect an AI provider or remote computer, that service
also receives the work you send it. Keep keys and private files out of exports.

At **commit**, Carbon puts a hash on chain, not your recipe. The transaction
still identifies your hotkey. At **submit**, Carbon's validator receives your
recipe and rebuilds it independently. Submission is not private from the
receiving validator. See the [commit code](../../carbon/chain/commitment_poster.py)
and [submission/rebuild path](../../carbon/battery/daemon.py).

Carbon does not publish your recipe to other miners. The public board shows
permitted scores, standing and public showcase predictions, not recipes.
Under the current sealed rule, hidden-window scores wait for the material's
registered release; a missing live score is not a failed submission.
[Public feed code](../../carbon/challenge_validator/score_feed.py).

Recipe publication is **opt-in only** under the
[owner's dashboard policy](../../.agent/decisions/2026-10-08-OWNER-DASHBOARD-01.md).
**HUMAN_INPUT:** the opt-in mechanism is not decided. Do not assume that an
upload or a submission means consent to publish. This policy is not a guarantee
against an operator, provider or security failure.

## Can I make my own data?

Yes. Extra public cases are encouraged for researching and **choosing** a
recipe. Use your own seed root, never Carbon's private exam material. For
battery, the supported command on your own machine is:

```sh
python -m carbon.challenge_kit.battery generate --root-hex YOUR_64_HEX_ROOT --count 100 --workdir runs/my-data --out my-data.jsonl
```

It needs the pinned solver environment/Docker; it can take compute time.
This FAQ does not start it. Read the [battery kit](../../carbon/challenge_kit/battery.py)
before use. Motor and cooling do **not** yet have equivalent miner-runnable
`generate` kits; check the [provisions and gaps](../../carbon/challenge_kit/standard.py).

The official rebuild trains only on Carbon's approved training data, or the
registered selection from its training pool. Your extra local data is not
uploaded as official TRAIN. [Pinned data](../../carbon/battery/challenge.py),
[registered pool selection](../../carbon/battery/development_rebuild.py).

## Is practice the same as the exam?

No. Practice gives feedback on **public cases only**. It can show accuracy,
gates and indicative safety diagnostics. It cannot show your hidden exam result.
[Practice path](../../carbon/battery/practice.py),
[feedback boundaries](../../carbon/practice_safety_feedback.py).

The exam can also test decision quality on hidden questions under its registered
Challenge rule. That integration is Challenge/version-specific, not a promise
that every proposed customer packet is already live. A mandatory gate failure
makes a candidate ineligible, however small its average error. It cannot beat
an eligible candidate. A reference or infrastructure failure is different:
it is unavailable/unresolved, not automatically a bad model.
[Exam rule](../../carbon/battery/exam.py),
[decision evaluation](../../carbon/challenge_validator/battery.py).

## How do I find a failed gate?

Check your own practice feedback's gate counts and checked/unmeasured coverage.
Zero reported failures with no measured cases is **not** a pass. Keep your full
recipe/export local; do not share it to ask which gate failed.

**Pending [PR #918](https://github.com/carbonphysicsai/Carbon/pull/918), not on
this FAQ's starting main:** the aggregate diagnostic will be:

```sh
python -m scripts.dev.battery.gate_pass_diagnosis EXPORT.json --counts-only
```

Use it only after that tool is installed. Share counts-only output if useful,
not the full export. It diagnoses public practice, never hidden exam cases.

## Why use testnet?

Use it to rehearse freeze, commit, submit and gate feedback before mainnet.
This DEVELOPMENT path grants **no mainnet emissions or reward entitlement**;
the [miner outcome](../../carbon/battery/daemon.py) declares `reward: false`.
The owner separately permits [testnet winner weights](../../.agent/decisions/2026-10-05-OWNER-TESTNET-WEIGHTS-01.md)
for testing. That is not a payment promise or proof of launch readiness.
Do not interpret this as a claim about every test network's emission settings.
