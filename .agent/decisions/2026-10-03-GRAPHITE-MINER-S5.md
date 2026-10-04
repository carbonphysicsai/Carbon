## 2026-10-03 — GRAPHITE-MINER-S5: the Control Center launches Graphite, shows its campaigns and gives the miner a Library

**Authority.** Delegated engineering decision (executor, slice S5 of the
Graphite miner edition), within OWNER-GRAPHITE-MINER-01 (Graphite replaces the
autonomous agent for new launches; Research, Build and Full modes; a Library
with shared and private cards, search, pins, bans, imports and plans;
"generous and tunable limits"), OWNER-LAUNCHPAD-PROD-01 (the miner front end
is a zero-friction, production-level application) and OWNER-LAUNCHPAD-PROD-02
(no Carbon-imposed cap: "It's their economics, compute, and choice!"). It
changes what the Control Center page offers, sends and shows. It changes no
scientific value, gate or tolerance, no economics or default spend, no chain
write, no exposure of a host and no authority boundary: the miner's signer
holds every key, miner compute stays link-only, nothing hidden reaches the
page, and every Graphite run is on the miner's model, key and budget.

**Scope.** `scripts/dev/miner_launchpad/{app.js, index.html, research_view.js,
library_view.js, style.css, browser_smoke.py}` and the page checks
(`tests/cpu/control_center_page_check.cjs`, `control_center_dom.cjs`,
`control_center_graphite_fixture.py`, `test_control_center_*.py`, UI
assertions only). The page consumes the Launchpad's JSON (slice S4) and adds
no route, operation or gate of its own.

**Decision.**

1. *Graphite replaces the autonomous choice.* Once the capability document
   offers a choice with `launch_agent: "graphite"`, or marks a choice
   `autonomous_agent_replaced`, the autonomous choice is not offered in the
   wizard, the Launchpad strip, the readiness list or a template load (a
   template carrying it is refused with that reason). The Agents page says it
   was replaced and that its campaigns keep running and replay unchanged. A
   controller that predates Graphite offers what it offers, as before. When
   the capability document lists the Challenges Graphite is offered for
   (`offered_challenges`, or a Challenge's `graphite.offered`), the choice is
   disabled with `graphite_not_offered_for_challenge` before launch;
   otherwise the launch's own refusal says it.
2. *Modes, frozen at launch.* Under the Agent step, once Graphite is chosen:
   Full (the default), Research or Build, each described in plain words. The
   launch carries `graphite_mode` always; `research_share` (typed as a
   percentage, sent as the fraction it names, at most two places) only in
   Full; `plan` (a digest from the Library's plans) only in Build, and none
   means its Planner writes one first; `hunt` only in Research and Full, and
   only when the hunt is on; `limits` only when one is set. Each field is
   sent only as the launch operation's listing declares it. The controller's
   own defaults are used when its options state them, the design's otherwise
   (Full, 10%, 200 papers).
3. *The hunt is on by default in Research and Full,* because the owner
   described Research as "hunt and read, then write a ranked plan"; one
   click turns it off. Its query grammar (at most 8 queries of at most 6
   terms of letters, digits and hyphens; raw arXiv syntax never) is checked
   on the page as the controller checks it (`hunt_query_invalid`).
4. *A hunt's cost is an estimate, said as one.* The controller's own
   per-paper estimate when its options state it; otherwise about 600 input
   and 150 output tokens a paper at the selected model's listed price (from
   the capability document, setup's model listing or the price setup
   checked), times the papers a hunt may read. With no listed price, no
   figure is shown. It is never a cap or a default spend: the miner's
   ledger meters the real cost and their own model-spend ceiling binds.
5. *Limits are money and time.* Graphite's per-epoch call and trial counts
   and its Planner call count are optional, under Tools & limits, Advanced.
   Blank means only the campaign's own limits bind; a set value is a whole
   number, 1 or more.
6. *The Library* (`#library`, `#library/import`, `#library/plans[/<digest>|
   /new]`, `#library/card/<id>`): cards from the shared pack and the miner's
   private library, each with its origin (Shared pack, Your hunt, Your
   import) and UNCHECKED; search ranked for a chosen Challenge, with the
   score and the reasons the controller gives; pin and ban toggles; pinned
   and banned lists; text import (at most 20,000 characters, checked here
   and again by the controller; PDF is a follow-up); plans, a plan's view
   with its cited cards and their origins, and a plan editor. A banned card
   is never shown among results, even if a controller served one.
7. *The Library's requests.* Each goes to `/api/v1/library/<verb>` or
   `/api/v1/plans/<verb>`, and to `/api/v1/operations/<operation>` only when
   the controller answers `route_not_found` (a route it does not have ran
   nothing). Fields are named as the controller's operation listing names
   them; a controller whose listing has no Library operation is told so and
   asked nothing. A write (pin, unpin, ban, unban, import, plan edit) is sent
   under an idempotency key held until the controller answers, as practice,
   freeze and submit are (LP-PROD-F): a retry after a lost answer replays it,
   and a refusal is shown with the controller's next step.
8. *The plan editor* edits a draft held on the page: typing never redraws
   it, and adding, moving or removing a hypothesis redraws it from the draft.
   Before anything is sent it refuses a plan that ignores a pinned card
   (`plan_invalid`), cites a banned card (`card_banned`), cites a card in
   neither the pack nor the library (read first; `card_not_found`) or has a
   recipe that is not a JSON object. Saving sends `carbon.graphite.miner-plan.v1`
   with the plan it came from as `parent` and `created_by: "miner"`; the
   new version is read back as stored, and the earlier one is kept.
9. *A Graphite campaign* shows, from the campaign view's `graphite` block,
   its mode, its stage now, its plan (read from the Library by digest, its
   first three hypotheses), research spend against its share, build spend
   (the campaign's model spend less research) and the hunt's progress. A
   campaign card shows the mode and stage from the observe row's `graphite`.
10. *Stable rendering and the session link are unchanged.* Every new region
    is built once and patched in place, or redrawn only when what it shows
    changed and nothing holds it; fields are backed by the page's own state.
    The Library reads the address only after app.js has taken a session link
    from it, and stores nothing but the route.
11. *Tests.* The page checks load the scripts `index.html` loads. Every new
    view has scenarios against documents built by the real code with
    Graphite's part added in the interface's shape (and S4's own documents
    once merged), and each boundary is shown held by breaking it in a copy of
    the page. `browser_smoke.py` lists the Library, checks it in a real
    browser and picks Graphite or the autonomous agent as the controller
    offers; its journey's refusal check now accepts the refusal's
    `next_step`, which the base already sends.

**Handoffs (S4).** `controller.STATIC` must serve `/library_view.js` (until
it does, `test_every_page_script_is_one_the_controller_serves` fails and the
Library is empty in a real browser). The Library routes need a body limit
above 4 KiB for `library_import` (20,000 characters) and `plan_edit`.

**Maturity.** Implemented and tested against fixture documents and in a real
browser (with the STATIC entry applied in-process). Not yet run against S4's
own documents. Nothing here is scientific, security or production
qualification.
