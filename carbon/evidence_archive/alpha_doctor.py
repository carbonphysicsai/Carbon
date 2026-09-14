"""Safe configuration doctor for the prospective C-EA1 alpha profile."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .alpha_profile import (
    MAX_DEPLOYMENT_CONFIG_BYTES,
    assess_alpha_deployment,
    parse_alpha_deployment_configuration,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Check C-EA1 alpha archive deployment inputs without connecting."
    )
    parser.add_argument("config", type=Path)
    arguments = parser.parse_args()
    with arguments.config.open("rb") as source:
        payload = source.read(MAX_DEPLOYMENT_CONFIG_BYTES + 1)
    configuration = parse_alpha_deployment_configuration(payload)
    report = assess_alpha_deployment(
        configuration,
        isolated_preflight_passed=False,
    )
    print(json.dumps(report.public_document(), sort_keys=True, separators=(",", ":")))
    return 2 if report.missing_external_inputs else 1


if __name__ == "__main__":
    raise SystemExit(main())
