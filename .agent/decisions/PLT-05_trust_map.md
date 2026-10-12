# PLT-05: offline public/released trust maps

Authority: owner-assigned TRUST-MAP-01 queue item (2026-10-12) and
PHYSICS_CONTRACT_01_DRAFT.md section 5.7. Reviewer: Carbon Validator.
Engineering scope: Challenge-neutral aggregate renderer and battery adapter.

KEEP battery's published input bounds, output shapes and near-limit constants.
ADD the offline carbon.trust_map core and carbon.battery.trust_map CLI beside
the pinned scientific implementation. No existing recipe/training/domain bytes
or score-selection path changes. Top models are named explicitly by the
operator; the map neither chooses them nor derives a new ranking.

Error is per-case RMS in native output units, summarized by cell median/p90.
Disagreement is RMS population standard deviation across the named top models,
also summarized by cell median/p90. Separate quantities retain separate units;
no weighted scientific score is invented. Empty cells are NO_DATA with null
measurements. c2 is pooled empirically, without claiming population weighting.
Battery display bins are six c1 bins, seven ambient bins and three equal SOC0
bands within existing public bounds. They are display choices, not new sampling
laws, gates or scientific tolerances. Near-limit outlines mark observed cells
using the existing 5 mV/55 C DEVELOPMENT definition.

A closed disclosed-panel projection refuses PRIVATE/HIDDEN/SEALED or unknown
disclosure, per-case extra metadata, missing/duplicate cases, malformed output
shapes, non-finite values and unaccepted/wrong-image reference verification.
Operator disclosure/release and accepted verification evidence remain external
authority: the offline tool cannot authenticate a caller's provenance. No
protected-data reader, deferred aggregate release policy, live disclosure or
scored-case selection integration is introduced.

The committed battery MMS verdict is HUMAN_INPUT with
accepted_development_pass=false. It is refused; producing measured battery maps
awaits owner-adopted verification for the exact reference image and an authorized
public/released panel. Synthetic regression fixtures confer no such acceptance.
No hidden files or solver outputs were read or produced by this ticket.

Alternatives: reject scalar normalized error (requires scientific weights),
automatic top-model ranking (changes ownership), and interpolation of empty
cells (creates unevidenced coverage). Reversible by removing the new modules;
schema v1 is prospective. A superseding decision changes this file and core.py.
Validation covers known numeric answers, boundaries, disclosure/verification,
determinism, CLI output and SVG structure. Required CI remains acceptance.
Maturity ceiling: IMPLEMENTED/TESTED DEVELOPMENT engineering only; no LIVE,
qualification, safety, economics, reference adoption or product assurance.
Development Hub retired: no regeneration or events under current authority.
