"""`python -m carbon.agent_campaign.graphite run-checked ...` (`run_checked`)."""

from __future__ import annotations

import sys

from .run_checked import main

if __name__ == "__main__":
    sys.exit(main())
