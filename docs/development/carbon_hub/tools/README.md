# Hub tools

## Render

```bash
python tools/render_hub.py
```

The dependency-free renderer reads `data/hub_data_v2.json` and
`data/change_events.json` and refreshes:

- the complete zero-script static `index.html`;
- the optional application in `interactive.html` from its checked-in template;
- every wave explainer;
- every ticket explainer;
- `Carbon_Development_Hub_v2.md`;
- `data/hub_index_v2.yaml`;
- the package README.

Use `python tools/render_hub.py --check` for a non-mutating byte comparison and
stale-explainer check.

## Validate

```bash
python tools/validate_hub.py --repo-root ../../..
```

The validator uses the Python standard library. It checks source schemas and
references, generated drift, static-first structure and links, current
wave/ticket/board parity, change-event coverage for structural diffs, and the
pull-request impact declaration when run in CI.

Neither script reads from or writes to GitHub. A person must reconcile the current repository state before changing the hub data.

## Route smoke test

```bash
node tools/test_routes.js
```

This checks all important static anchors and runs the optional interactive
hash-route renderer inside a dependency-free Node harness.

## Real browser smoke

```bash
python tools/browser_smoke_test.py
```

The browser test uses local Chrome, Chromium, or Edge. It loads the primary
page with JavaScript enabled and disabled at desktop and mobile widths, checks
text parity and external requests, exercises the optional interactive app,
rejects inline event or `javascript:` URL attributes, and verifies that the
mobile navigation is inert while closed and restores keyboard focus on Escape.

## Local server

```bash
python tools/serve_hub.py
```

Open `http://127.0.0.1:8000/index.html`. The server binds loopback only.
