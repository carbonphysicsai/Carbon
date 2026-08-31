# Repository Integration

The checked-in hub lives at:

```text
docs/development_hub/
```

Root `AGENTS.md`, `agent_pack/EXECUTION_PROTOCOL.md`, the scoped hub `AGENTS.md`, and `.github/workflows/development-hub.yml` make maintenance part of the normal ticket loop.

## Required checks

```bash
python docs/development_hub/tools/render_hub.py --check
python docs/development_hub/tools/validate_hub.py --repo-root .
python docs/development_hub/tools/check_change_coverage.py \
  --repo-root . --base <base-sha> --head <head-sha>
```

The optional browser check requires Playwright and Chromium:

```bash
python docs/development_hub/tools/browser_smoke_test.py
```

## Publication

Serve `docs/development_hub/` as a static directory. `index.html` needs no JavaScript, build server, database, network request, credential, or secret. `interactive.html` remains an optional client-side view.
