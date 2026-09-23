# WEB-QA-06: Ask Carbon public activation, and what it did and did not settle

Programme: #139 website and public answering. Owner authority: `WEB-QA-05-D2`
(named production operators and authorization of public activation),
`WEB-QA-06-D1` (inactive publication of the re-baselined candidate) and
`WEB-QA-07-D1` (public content approval and activation), all recorded in
`.agent/DECISIONS.md`.

Status: **the successor ticket to WEB-QA-05, recorded after the fact.** The
decisions were made and recorded; the ticket that should have carried them was
never written, so the work existed only as decision entries and pull requests.
This records it. It authorizes nothing new.

Primary Development Hub map_ref: `SYSTEM/PUBLICATION-AUTHORITY`; impact
`map_structural`, matching every other ticket in this series.

## Why this ticket exists at all

`WEB-QA-05` ends with named production operators and an authorization to
activate. Everything after that — rebuilding the candidate against the
redesigned site, publishing it inactive, approving the content, and activating —
happened under decisions with no ticket above them. A decision record says what
was decided; a ticket says what was being attempted and what would count as
done. Without one, "what is the state of Ask Carbon" could only be answered by
reading four decision entries and inferring the order.

## What was decided, in order

| Decision | What it settled |
|---|---|
| `WEB-QA-05-D2` | Named production incident owners and disable/rollback operators; authorized public activation of the accepted release after inactive deployment and production checks succeed |
| `WEB-QA-06-D1` | Inactive publication of `ask-carbon-public-release-2026-09-22.1`, bundle `14e85a87…`, superseding the 2026-09-18.2 candidate |
| `WEB-QA-07-D1` | Public content approval for the 27 reviewed cards and 9 pinned sources, and activation; bundle `93bffeec…`, knowledge digest `3f22f87a…` |

Two approvals were required because `public/release-contract.js` gates
production on the knowledge record and not only on the Worker's activation flag.
Authorizing a release is not the same as approving what it will say, and the
contract was built to require both.

## Current state

Ask Carbon is live and answering. The three gates are satisfied:
`ASK_CARBON_ACTIVATION` in Worker configuration, `release.status`
`APPROVED_PUBLIC`, and `release.public_activation_allowed` true.

Deployed state is read from `/health`, never from a committed file. This
repository records the release record and the approved artifact identities; it
cannot observe what is deployed, and no document here should claim to.

## What remains open

- **The `current-progress` card expires `2026-09-25T00:00:00Z`.** An expired card
  lands in `ineligibleCards` and never reaches `reasons`, so the release stays
  eligible and the remaining 26 cards keep answering. It is a content deadline,
  not an outage. A refresh is prepared in
  `website/ask-carbon/CURRENT_PROGRESS_REFRESH_PROPOSAL.md` and is **not
  approved**; applying it is a knowledge change and is the owner's decision.
- **ZDR/MAM remains unestablished** with the observed provider project. The
  visitor notice describing that is accurate and stays exactly as it is: the
  fact it describes is what is being fixed, and rewriting the notice would
  describe a state that does not yet exist.
- **The general-Q&A model, the production route and any further activation
  package remain unapproved.** The content approval covers the reviewed cards
  and pinned sources only.

## Boundaries

Nothing in this ticket authorizes a deployment, a rebuild, a redeployment or an
activation change. Ask Carbon is live and working; the standing instruction is
that it is not to be touched, and introducing change into a working public
surface for no gain is the failure this ticket is most likely to be misread as
permitting.

No knowledge card, pinned source, release value, gate or Worker configuration is
changed by recording this.

## Maturity

SPECIFIED, IMPLEMENTED, TESTED and deployed as a public answering surface. Not
SCIENTIFICALLY_QUALIFIED, not SECURITY_QUALIFIED, not PRODUCTION_QUALIFIED in
the constitutional sense, and not evidence of customer traction. A reviewed
explanation being publicly readable is not a claim about Carbon's science.
