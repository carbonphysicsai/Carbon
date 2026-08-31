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

`HUB_IMPACT_NONE` cannot cover wave registers, ticket definitions, Build Out or
master-plan structure, decision records, evidence records, or changes to
ownership, cross-wave placement, status, dependencies, boundaries, maturity,
or recurring change routing.

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
deployment is owner-controlled. Automatic deployment requires the repository
variable `CARBON_HUB_PUBLISH=true`; this task does not set it or enable Pages.
Enabling Pages makes the hub public. Any future internal-only content belongs
on an access-controlled static host and remains subject to rights, privacy,
security, and customer-confidentiality authority.
