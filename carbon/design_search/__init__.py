"""Challenge-neutral design search for engineering-value and adversarial testing.

GRAPHITE-ADMISSION-01 slice C (handoff §11-12). A Challenge's adapter supplies
its design and condition variables, its commitment engine and its fixed
baseline; this package supplies, for any Challenge:

- `methods`: Carbon-implemented search methods a proposal may name, with
  closed, bounded parameters. A proposal is data; nothing it carries runs.
- `experiment`: the neutral request and result, the freeze manifest, and the
  equal-query pilot that compares proposed methods with the Challenge's fixed
  baseline on development models, committing before any reference access.

A Challenge's adapter lives with the Challenge (battery's:
`carbon/battery/value/design_search_adapter.py`, and its priced choices in
`design_search_pricing.py`).

Development material only. Nothing here changes EV4, its contract, its panel
or `carbon/battery/value/optimizer.py`, passes or fails a model, or replaces
the declared baseline.
"""
