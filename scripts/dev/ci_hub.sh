#!/usr/bin/env bash
set -euo pipefail

script_dir="$(CDPATH= cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
repo_root="$(CDPATH= cd -- "${script_dir}/../.." && pwd -P)"

cd "${repo_root}"

echo "==> deterministic Development Hub generation"
python3 docs/development/carbon_hub/tools/render_hub.py --check

echo "==> Development Hub authority, links, and live PR contract"
python3 docs/development/carbon_hub/tools/validate_hub.py --repo-root .

echo "==> Development Hub validator enforcement"
python3 docs/development/carbon_hub/tools/test_validator.py

echo "==> Development Hub static and interactive routes"
node docs/development/carbon_hub/tools/test_routes.js

echo "==> Development Hub JavaScript-on/off browser smoke"
python3 docs/development/carbon_hub/tools/browser_smoke_test.py --timeout 30

echo "Carbon Development Hub gates passed."
