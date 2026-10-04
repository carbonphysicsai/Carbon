## 2026-10-03 — GRAPHITE-MINER-S5: the Control Center launches Graphite, shows its campaigns and gives the miner a Library

**Authority.** Delegated engineering decision (executor, slice S5 of the
Graphite miner edition), within OWNER-GRAPHITE-MINER-01 (Graphite replaces the
autonomous agent for new launches; Research, Build and Full modes; a Library
with shared and private cards, search, pins, bans, imports and plans;
"generous and tunable limits"), OWNER-LAUNCHPAD-PROD-01 (the miner front end
is a zero-friction, production-level application) and OWNER-LAUNCHPAD-PROD-02
(no Carbon-imposed cap: "It's their economics, compute, and choice!"). It
changes what the Control Center page offers, sends and shows. It changes no
scientific value, gate or tolerance, no economics, no chain write, no
exposure of a host and no authority boundary: the miner's signer holds every
key, miner compute stays link-only, nothing hidden reaches the page, and
every Graphite run is on the miner's model, key and budget. The page sets no
default spend: nothing it sends by default spends the miner's money beyond
the campaign they launch, and a hunt is sent only when they turn it on.

**Scope.** `scripts/dev/miner_launchpad/{app.js, index.html, research_view.js,
library_view.js, style.css, browser_smoke.py}` and the page checks
(`tests/cpu/control_center_page_check.cjs`, `control_center_graphite_fixture.py`,
`test_control_center_*.py`, UI assertions only). One deliberate, scoped
change to the shared harness `tests/cpu/control_center_dom.cjs`: it loads
exactly the scripts `index.html` loads (`pageScripts`), so a script the page
adds runs in every page check; nothing else in it changed. The page consumes
the Launchpad's JSON (slice S4, as of `claude/gm-launchpad` 9b9e00b02) and
slice S3's plan schema, and adds no route, operation or gate of its own.

**Decision.**

1. *Graphite replaces the autonomous choice.* Once the capability document
   offers a choice with `launch_agent: "graphite"`, or marks a choice
   `autonomous_agent_replaced`, the autonomous agent is treated as replaced,
   whether or not the controller still lists it (S4's does not): it is not
   offered in the wizard, the Launchpad strip, the readiness list or a
   template load (a template naming it is refused with that reason), and the
   Agents page says it was replaced and that its campaigns keep running and
   replay unchanged. A controller that predates Graphite offers what it
   offers. Where Graphite runs is read from each Challenge's
   `setup_offers.graphite`, else the options' `graphite.offered_for`
   ({id, version}); a Challenge it does not run on disables the choice with
   `graphite_not_offered_for_challenge` before launch.
2. *Modes, frozen at launch.* Under the Agent step, once Graphite is chosen:
   Full (the default), Research or Build, each described in plain words. The
   launch carries `graphite_mode` always; `research_share` (typed as a
   percentage, sent as the fraction it names, at most two places) only in
   Full; `plan` (a digest from the Library's plans) only in Build, and none
   means its Planner writes one first; `hunt` only in the modes the
   controller says a hunt runs in (`graphite.hunt.modes`: Research and Full;
   S3 runs no hunt in Build), and only when the hunt is on; `limits` only
   when one is set. The controller's own defaults and bounds are used when
   its options state them (the default mode, the share's default, the hunt's
   `default_records` and `max_records`, `max_queries`, `max_terms`, the limits'
   `maximum`), the launch rule's otherwise. Those fallbacks follow S4's door
   bounds as of 1bb9c7a2b: at most 5000 papers (S2's `hunt.MAX_RECORDS`) and a
   per-epoch limit of at most 100000 (S3's `edition.max_limit()`). The page
   checks and the fixture read the bound from the options, so the merged
   tree's shape-equality test flags any later change.
3. *Fail closed on fields the launch does not take.* When the controller's
   launch listing is read and does not declare a Graphite field the choice
   needs, the launch waits and says which field and what to do (update
   Carbon), rather than dropping it: a Research launch sent without its mode
   would run as Full.
4. *The hunt is off until the miner turns it on.* It spends their money on
   Reader calls; the launch takes none unless asked ("Omitted: no hunt"), and
   the owner described hunting as an option the miner has. Turned on, it
   reads the controller's default number of papers (200). Its query grammar
   (at most 8 queries of at most 6 terms of letters, digits and hyphens, a
   term at most 40 characters, a query at most 128; raw arXiv syntax never)
   is checked on the page as the controller checks it (`hunt_query_invalid`).
   A launch that hunts also reads the texts imported in the Library.
5. *A hunt's cost is an estimate, said as one.* Carbon's own per-paper
   estimate (`hunt.estimate.nanodollars_per_abstract`) when it is for the
   model chosen (`estimate.model`, provider:model); otherwise the controller's
   Reader tokens per paper (`reader_tokens_per_abstract`, 1000 in and 250 out)
   at the chosen model's listed price; with neither, no figure. Times the
   papers a hunt may read. It is never a cap or a default spend: the miner's
   ledger meters the real cost and their own model-spend ceiling binds.
6. *The research share is said as it binds.* It narrows only the
   model-spend and model-call ceilings the miner set; with neither set, the
   wizard says plainly that it does not limit research yet, and the review
   says it binds only once one is set.
7. *Limits are money and time.* Graphite's per-epoch call and trial counts
   and its Planner call count are optional, under Tools & limits, Advanced.
   Blank means only the campaign's own limits bind; a set value is a whole
   number from 1 to the controller's maximum.
8. *The Library* (`#library`, `#library/import`, `#library/plans[/<digest>|
   /new]`, `#library/card/<id>`): search over the shared pack and the miner's
   private cards, ranked for a chosen Challenge with the score, the reasons
   and whether the card is buildable under the Challenge's contract or a
   capability request candidate, each card with its origin (Shared pack, Your
   hunt, Your import) and UNCHECKED; pin and ban toggles; pinned and banned
   lists; "Your library" states what `library_list` gives (the shared pack's
   size and digest, or that it is missing with its next step; the private
   snapshot; imports waiting; plans) and says private cards are found by
   search, never a count it was not given; text import (at most 20,000
   characters; PDF is a follow-up); plans, a plan's view with its Challenge,
   its pins and how each was considered, its cited cards and their origins,
   and a plan editor. A banned card is never shown among results, even if a
   controller served one, and is named by its id (it is never served).
9. *The Library's requests.* Each goes to `/api/v1/library/<verb>` or
   `/api/v1/plans/<verb>` with S4's field names (`query`, `challenge`,
   `challenge_version`, `card_limit`, `card_id`, `plan`, `title`, `text`,
   `plan_document`), and to `/api/v1/operations/<operation>` only when the
   controller answers `route_not_found`. A controller whose listing has no
   Library operation is told so and asked nothing. A write (pin, unpin, ban,
   unban, import, plan edit) is sent under an idempotency key held until the
   controller answers (LP-PROD-F); a pin, unpin, ban or unban whose answer
   was lost is also released once the library's curation shows its effect, so
   a later toggle of the same card is a new request, never a replay of the
   first answer. A refusal is shown with the controller's next step.
10. *The plan editor* edits drafts held on the page, one per plan (and one
    for a new plan): opening another plan or starting a new one keeps each.
    Typing never redraws a draft. It saves Graphite's plan in S3's closed
    shape (`carbon.graphite.miner-plan.v1`: exactly `schema`, `challenge`
    {id, version}, `hypotheses` ranked by their place from 1, each with
    `hypothesis`, `expected_effect`, `stopping_rule`, `cites` [{card_id,
    origin}] and an optional object `recipe`, `pins_considered` [{card_id,
    consideration}], `parent`, `created_by: "miner"`). A new plan names the
    Library's chosen Challenge (the miner may change it); an edit keeps its
    plan's. Every pinned card needs a line saying how the plan considers it;
    a planner's lines are kept as written. Before anything is sent it refuses
    what S3's rule would: a pinned card not considered, a banned or malformed
    cite, a card in neither the pack nor the library (read first), a text
    over 2,000 characters, more than 8 hypotheses or 12 cites, a recipe that
    is not a JSON object. The new version is read back as stored.
11. *A Graphite campaign* shows, from the campaign view's `graphite`
    section: its mode; where it is now (an ended campaign says it ended,
    with the stage it ended in, never that it is still planning); each stage
    with its state and the code it ended on (`research_share_reached`); its
    plan (read from the Library by digest, its first three hypotheses);
    research spend against the share's cap as the campaign states it
    (`research_cap`); build spend (the campaign's model spend less research);
    and the hunt's progress, with an arXiv failure (`failed_infra`, a 0/1
    count or a boolean) said as `literature_fetch_failed` and its next step,
    never as a verdict on a paper. A campaign card shows the mode and where
    it is from the observe row's `graphite`.
12. *Stable rendering and the session link are unchanged.* Every new region
    is built once and patched in place, or redrawn only when what it shows
    changed and nothing holds it; fields are backed by the page's own state.
    The Library reads the address only after app.js has taken a session link
    from it, and stores nothing but the route.
13. *Tests.* The page checks run on S4's documents: S4's own where its code is
    present, and otherwise built in S4's shape field for field
    (`control_center_graphite_fixture.py`), which a test holds equal to S4's
    functions once merged. The scripted Library answers as S4's operations
    do, with the listing's closed fields and S3's plan rule, and every plan
    the page sends is checked with S3's own `check_shape` once S3 is merged.
    Each boundary is shown held by breaking it in a copy of the page.
    `browser_smoke.py` lists the Library, checks it in a real browser, picks
    Graphite or the autonomous agent as the controller offers, and expects
    Graphite's defaults with no hunt.

**Not adopted.** The review's nit to offer a hunt in Build with no plan: S4
and S3 now run no hunt in Build and refuse one (`graphite_field_not_used_by_mode`);
the page follows the controller's `hunt.modes`.

**Handoffs (S4).** `controller.STATIC` must serve `/library_view.js` (until
it does, `test_every_page_script_is_one_the_controller_serves` fails and the
Library is empty in a real browser).

**Maturity.** Implemented and tested against S4's and S3's own code on an
integration of S1 to S5, and in a real browser (with the STATIC entry applied
in-process). Nothing here is scientific, security or production
qualification.
