## 2026-10-13 — OWNER-ANALYSIS-IMAGE-STANDING-ACCEPT-01: a rebuilt analysis image passing all six R8 hostile probes is accepted for dev and testnet

**Authority.** The owner, 2026-10-13. He answered the Test Lead's direct question
in that session, choosing the standing rule over per-image acceptance. The PR
Head then put the same rule to him directly and he confirmed it in the PR Head
session before this record was merged: this is a standing container-isolation
acceptance, and such a decision is not recorded on a relay alone.

**The standing rule.** A rebuilt analysis image is accepted into **development
and testnet** testing, on the same terms as `12e1b55b` and `20e18ff2`, when all
six R8 hostile probes pass:

| probe | required result |
|---|---|
| memory | `PASS` |
| time | `PASS` |
| scratch_flood | `PASS` |
| fork_bomb | `PASS` |
| outside_scratch | `PASS` |
| network_socket | `PASS` |

and a `hostile_probe` record **keyed to that image** records them, each with its
own result digest. All six are required; a missing or unkeyed record is not an
acceptance.

**A note on the word, and on whose word it was.** The owner's own text, the
option he chose, was:

> Any rebuilt analysis image that passes all 6 sandbox escape tests is accepted
> into dev/testnet testing on the same terms as before. Mainnet/LIVE still needs
> you each time.

"CONTAINED" was **the Test Lead's relay word, not the owner's**, and this record
first attributed it to him in error. The PR Head's confirmation question
inherited that word from the relay and put it to the owner, so his "yes" was to
the relay's phrasing: a confirmation can carry a term the owner never used, and
checking the words against the evidence is what caught it. His own wording,
"passes all 6 sandbox escape tests", is closer to the schema than the relay's
was. The schema's success value is `PASS`, and
`carbon/challenge_pipeline/readiness/checks.py:832` requires "one PASS result
with a digest per" probe, so this table names the term the data actually
carries. The first record written under this
rule, `hostile_probe.20e18ff2.json` for image
`sha256:28815c8eb808b93dad1a3dd80a715c4ba0282bf7378932e5b90f61548fedeca5`,
carries `PASS` for all six.

**What stays with the owner.** Mainnet and LIVE need his word for each image,
every time. This rule does not reach them.

**What this is not.** It is not a production security audit. Six passing probes
in a development harness are evidence of containment under those six attacks,
not a general guarantee, and nothing here authorizes arbitrary participant code
on any surface that carries official evaluation authority (invariant 6, and the
construction/evaluation separation in §7.9).

**Maturity.** DEVELOPMENT and testnet acceptance only.
