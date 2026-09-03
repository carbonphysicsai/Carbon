# Carbon Hub Newcomer Overview

This branch implements owner decision `OWNER-HUB-01`: one Carbon Development Hub with progressive disclosure.

## Reader path

1. Start with the generated `newcomer.html` Overview.
2. Read plain-English Wave and ticket explanations first.
3. Open Technical Detail for the existing canonical Hub record, exact status, maturity, dependencies, specifications, and evidence.

The newcomer projection is not a second roadmap or authority layer. It binds each plain-English record to the existing stable `WAVE-*` or `WAVE-*/TICKET` map reference.

## Generate

```bash
python docs/development/carbon_hub/tools/render_hub.py
python docs/development/carbon_hub/tools/render_hub.py --check
```

`render_hub.py` generates and checks `newcomer.html`/`technical.html` as part
of the Hub's single deterministic generation/check pass, so drift is caught by
the same required CI step as the rest of the Hub. `tools/render_newcomer.py`
and `tools/render_newcomer.py --check` remain available for focused iteration
on newcomer copy alone.

The renderer requires exact coverage of all Waves and all tickets captured by the canonical Hub. Missing, extra, duplicate, or wrongly bound records fail generation.

## Current scope

This change adds the presentation contract, Wave A-N newcomer copy, newcomer copy for every currently captured Wave A and Wave B ticket, the deterministic renderer integrated into `render_hub.py`, a reciprocal link from `index.html` to `newcomer.html`, and route-test coverage for the new Overview.

It does not change scientific authority, Wave or ticket status, Bittensor economics, commercial canon, or the existing technical Hub. Public Pages front-door staging remains a separate validated change because the current Hub treats publication workflow changes as an authority-repin boundary.
