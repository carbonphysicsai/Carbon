#!/usr/bin/env bash
set -euo pipefail

# The Python interpreter a Carbon shell script runs its small embedded programs with.
#
# Usage: resolve_python.sh [PREFERRED]
#
# Prints the first that exists, in order: PREFERRED (when given and executable; by default the checkout's own
# `.venv/bin/python`), `python3`, `python`, found on PATH. A host or a sandbox may have no `python3` on PATH at all
# (Targon's canonical test container has only the project's venv python), so no script assumes one. Exits 3 with the typed
# code `python_not_found` when there is none. Uses shell builtins only, so it works with an empty PATH.

here="$(CDPATH= cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
preferred="${1:-${here}/../../.venv/bin/python}"
if [[ -n "${preferred}" && -f "${preferred}" && -x "${preferred}" ]]; then
  printf '%s\n' "${preferred}"
  exit 0
fi
for candidate in python3 python; do
  found="$(command -v "${candidate}" 2>/dev/null || true)"
  if [[ -n "${found}" ]]; then
    printf '%s\n' "${found}"
    exit 0
  fi
done
echo "python_not_found: no Python interpreter (the checkout's .venv/bin/python, python3 or python) is available. Next: install python3 from your OS packages, or run the installer so the project's environment exists." >&2
exit 3
