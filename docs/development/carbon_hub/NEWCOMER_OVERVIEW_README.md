# Carbon Hub Newcomer Overview

This branch implements owner decision `OWNER-HUB-01`: one Carbon Development Hub with progressive disclosure.

## Reader path

1. Start with the generated `newcomer.html` Overview.
2. Read plain-English Wave and ticket explanations first.
3. Open Technical Detail for the existing canonical Hub record, exact status, maturity, dependencies, specifications, and evidence.

The newcomer projection is not a second roadmap or authority layer. It binds each plain-English record to the existing stable `WAVE-*` or `WAVE-*/TICKET` map reference.

## Generate

```bash
python docs/development/carbon_hub/tools/render_newcomer.py
python docs/development/carbon_hub/tools/render_newcomer.py --check
```

The renderer requires exact coverage of all Waves and all tickets captured by the canonical Hub. Missing, extra, duplicate, or wrongly bound records fail generation.

## Current scope

This branch adds the presentation contract, Wave A-N newcomer copy, newcomer copy for every currently captured Wave A and Wave B ticket, and the deterministic renderer.

It does not change scientific authority, Wave or ticket status, Bittensor economics, commercial canon, or the existing technical Hub. Public Pages front-door staging remains a separate validated change because the current Hub treats publication workflow changes as an authority-repin boundary.
