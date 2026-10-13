## 2026-10-13 — OWNER-ANALYSIS-IMAGE-STANDING-ACCEPT-01: a rebuilt analysis image passing all six R8 hostile probes is accepted for dev and testnet

**Authority.** The owner, 2026-10-13. He answered the Test Lead's direct question
in that session, choosing the standing rule over per-image acceptance. The PR
Head then put the same rule to him directly and he confirmed it in the PR Head
session before this record was merged: this is a standing container-isolation
acceptance, and such a decision is not recorded on a relay alone.

**The standing rule.** A rebuilt analysis image is accepted into **development
and testnet** testing, on the same terms as `12e1b55b` and `20e18ff2`, when all
six R8 hostile probes pass:

| probe | required outcome |
|---|---|
| memory | CONTAINED |
| time | CONTAINED |
| scratch_flood | CONTAINED |
| fork_bomb | CONTAINED |
| outside_scratch | CONTAINED |
| network_socket | CONTAINED |

and a `hostile_probe` record **keyed to that image** records them. All six are
required; a missing or unkeyed record is not an acceptance.

**What stays with the owner.** Mainnet and LIVE need his word for each image,
every time. This rule does not reach them.

**What this is not.** It is not a production security audit. Six passing probes
in a development harness are evidence of containment under those six attacks,
not a general guarantee, and nothing here authorizes arbitrary participant code
on any surface that carries official evaluation authority (invariant 6, and the
construction/evaluation separation in §7.9).

**Maturity.** DEVELOPMENT and testnet acceptance only.
