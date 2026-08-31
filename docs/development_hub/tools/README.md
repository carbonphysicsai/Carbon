# Carbon Development Hub tools

All required tools use the Python standard library.

## Render

```bash
python tools/render_hub.py
```

Generates the static-first `index.html`, Markdown explainers, compact map, README, and YAML index from:

- `data/hub_data_v2.json`
- `data/change_events.json`

Check that committed outputs are current:

```bash
python tools/render_hub.py --check
```

## Validate

Package-only validation:

```bash
python tools/validate_hub.py
```

Repository alignment validation from the hub directory:

```bash
python tools/validate_hub.py --repo-root ../../..
```

This compares the hub's active wave, selected ticket, active-board ticket set and statuses, and ticket source paths against the repository.

## Change coverage

```bash
python tools/check_change_coverage.py --repo-root ../../.. --base <base-sha> --head <head-sha>
```

Structural wave and ticket changes require `hub_data_v2.json`. Implementation, decision, evidence, plan, and specification changes require `change_events.json` or a structural hub update.

## Optional app smoke test

`interactive.html` preserves the optional JavaScript app. `test_routes.js` can smoke-test its route strings when Node is available. The static index remains the required default.

When Playwright and Chromium are available, test the actual local files with scripts enabled and disabled:

```bash
python tools/browser_smoke_test.py
```

The browser check is optional in minimal CI. `validate_hub.py` remains the required dependency-free blank-page regression guard.
