# Offline onboarding automation

Owner workload ONBOARDING-AUTOMATION-01..04. These are deterministic local
drafting tools, not scientific approvals, runtime registrations or runners.
They do not read hidden banks, call solvers/providers, or spend money.

## Packet (01)

`python -m carbon.challenge_pipeline.onboarding --root . packet --brief brief.json`

The closed JSON input has `schema: carbon.onboarding.brief.v1`, `challenge`
(a planning token), and four strings: `buyer`, `decision`, `physics`, `solver`.
Optional `fields` supplies named ten-section fields, each with `value` and
`sources`. An unsourced value is a HUMAN_INPUT recommendation. A sourced value
must be an exact excerpt in a pinned public repository file: sources have
`path`, `sha256`, `excerpt`. Extraction proves bytes, not relevance/approval.
It cannot turn a role-play customer into observed demand. Remaining prompts
name the decision owner and behavior held closed.

`--format json` retains the structured draft. `--compare <real-packet-path>`
returns a unified text diff, source coverage, section coverage and missing
fields. This is explicitly not semantic equivalence. Stdout only; the tool
does not overwrite canonical packets. Input bound is 2 MB; source references
are explicit repository-relative public documentation, never host discovery.

Tests regenerate battery v3 and motor v2 from a genuinely short brief: ten
sections result, but all detailed laws/limits/pins remain missing. That is the
intended first draft, not a claim to recreate months of evidence from four
sentences. Human source extraction can progressively enrich it.

## Motor first, timing basis

Use the mock precision-joint integrator, selecting a geometry/holding/peak
command; magnetostatics; Gmsh/GetDP. Keep 6/12 N m and safety/ripple/cogging
requirements in the real packet, not inferred generator defaults. Battery
v3 chooses a five-band charge/cooling map using PyBaMM DFN/OKane2022.
The historical battery records contain dates, not drafting person-hours.
Human time saved against battery is therefore **UNKNOWN** until a matched
effort baseline is supplied. Machine drafting time is measured separately;
missing source verification and review work is not counted as saved.

Hub is retired. Existing packets and frozen results remain unchanged.
