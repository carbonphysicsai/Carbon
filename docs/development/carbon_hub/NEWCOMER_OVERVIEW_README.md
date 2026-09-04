# Carbon Hub Newcomer Overview

This branch implements owner decision `OWNER-HUB-01`: one Carbon Development Hub with progressive disclosure.

## Reader path

1. Open the generated `index.html` Hub.
2. Read plain-English Wave and ticket explanations first.
3. Expand Technical detail on the same Wave or ticket card for the canonical
   record, exact status, maturity, dependencies, specifications, and evidence.
4. Use the Independent Exam map to follow one target qualified-exam process
   from Q1 through R15, expanding the same step for Investor, Engineer, CFD,
   or Physics PhD depth.

The newcomer projection is not a second roadmap or authority layer. It binds each plain-English record to the existing stable `WAVE-*` or `WAVE-*/TICKET` map reference.

## Generate

```bash
python docs/development/carbon_hub/tools/render_newcomer.py
python docs/development/carbon_hub/tools/render_newcomer.py --check
```

The compatibility command invokes the same normal Hub renderer. The normal
generation and CI path requires exact coverage of all Waves and all tickets
captured by the canonical Hub. Missing, extra, duplicate, or wrongly bound
records fail generation.

## Current scope

This change adds the presentation contract, Wave A-N newcomer copy, newcomer
copy for every currently captured Wave A and Wave B ticket, and deterministic
integration into the normal Hub renderer and CI path.

It does not change scientific authority, Wave or ticket status, Bittensor
economics, commercial canon, or technical content. The existing Pages payload
already publishes `index.html`, so integrating newcomer-first content into that
same generated page requires no alternate publication product or workflow.
