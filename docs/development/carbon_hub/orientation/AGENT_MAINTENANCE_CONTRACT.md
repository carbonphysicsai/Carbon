# Development Hub Agent Maintenance Contract

**Primary map location:** `SYSTEM/DEVELOPMENT-HUB`

**Authority ceiling:** documentation, orientation, routing, and maintenance
enforcement only.

The Development Hub is a derived navigation surface. Repository authority
controls exact semantics, implementation, decisions, review, tests, evidence,
and activation. A hub edit cannot select or close a ticket, activate a wave,
qualify science or security, declare commercial validation, enable `LIVE`, or
create frontier, treasury, settlement, network, weight, or emission authority.

## Ticket-start contract

For every development ticket:

1. read this contract after the repository authority set;
2. choose one primary stable hub `map_ref`;
3. classify hub impact before editing;
4. identify which hub nodes may be affected;
5. continue to use the active ticket and repository specifications as the
   implementation authority.

`SYSTEM/DEVELOPMENT-HUB` owns hub infrastructure. Scientific or protocol work
uses the relevant `WAVE-<ID>/<TICKET-ID>` location. A cross-cutting change has
one primary location and lists the others in `affects`.

## Source and generated output

Editable data source:

```text
data/hub_data_v2.json
data/change_events.json
data/change_event_template.yaml
```

Presentation/generation source:

```text
tools/render_hub.py
tools/templates/interactive_template.html
```

Generated; never hand-edit:

```text
index.html
interactive.html
Carbon_Development_Hub_v2.md
README.md
data/hub_index_v2.yaml
orientation/START_HERE.md
orientation/CHANGE_ROUTING.md
orientation/GLOSSARY.md
explainers/waves/*.md
explainers/tickets/*.md
```

## Required update points

Reconcile hub source at ticket start and again before closeout. Update it when
merged repository authority changes any of the following:

- purpose or plain-language system understanding;
- wave or ticket placement, selection, status, stage, or authority ceiling;
- dependency or downstream handoff;
- owner or accountable reviewer route;
- scientific, protocol, security, business, publication, or maturity boundary;
- recurring protocol-change route;
- material decision, adjustment, bug, blocker, risk, or evidence result;
- primary repository ticket, contract, decision, PR, or evidence link.

Do not add an event for routine code movement, implementation detail already
bounded by the ticket, or a link that is not supported by repository evidence.
Historical events remain immutable; use `supersedes` prospectively.

## PR declaration

Every PR completes exactly one declaration in the root PR template:

```text
HUB_UPDATE_REQUIRED: <map refs and changed hub source files>
```

or:

```text
HUB_IMPACT_NONE: <specific reason the hub remains accurate>
```

The data-owned impact policy classifies repository paths as `map_structural`,
`mapped_detail`, or `unmapped_authority`. `HUB_IMPACT_NONE` cannot cover a
map-structural change to selection, ownership, cross-wave placement, status,
dependencies, boundaries, maturity, primary links, or recurring routing. It
may cover a mapped-detail plan, evidence, decision, business, publication, or
implementation change only when the declaration names its map owner and gives
a specific reason the Hub's orientation meaning remains accurate. An unmapped
authority path always fails until an explicit bounded owner is recorded; it
never falls back to the active wave.

For a mapped authority update, make the authority/evidence change in commit
`A`, then build the Hub in commit `H`. The Hub records a parsed controlling-board
fingerprint plus exact `authority_source_checks`; all asserted paths must be
linked at `A`, and every asserted marker must remain present at candidate
`HEAD`. This proves the pinned records contain the state the Hub summarizes
without treating unrelated appended evidence detail as a structural rewrite.

## Validation and closeout

Run from repository root:

```bash
python docs/development/carbon_hub/tools/render_hub.py
python docs/development/carbon_hub/tools/render_hub.py --check
python docs/development/carbon_hub/tools/validate_hub.py --repo-root .
node docs/development/carbon_hub/tools/test_routes.js
python docs/development/carbon_hub/tools/browser_smoke_test.py
git diff --check
```

The primary page must stay static-first, complete with JavaScript disabled,
usable by `file://`, responsive, keyboard-visible, reduced-motion aware, and
free of automatic remote resources. Validation is engineering evidence only;
it grants no later maturity.

The completion report must include `Hub Impact`, the primary `map_ref`, changed
source/events or the specific no-impact reason, regeneration status, and exact
validation evidence.

## Publication boundary

This public repository contains only public-safe orientation. Manual Pages
deployment is available to authorized repository maintainers. The workflow
does not itself enforce owner approval; a required reviewer on the
`github-pages` environment, if desired, is a separate human-controlled
repository setting. Automatic deployment requires the repository variable
`CARBON_HUB_PUBLISH=true`; this task does not set it, enable Pages, or change
settings. Enabling Pages makes the hub public. Any future internal-only content
belongs on an access-controlled static host and remains subject to rights,
privacy, security, and customer-confidentiality authority.
