"""Write the refused-capability log's header and backfilled rows (deterministic).

    PYTHONPATH=. python scripts/dev/onboarding/render_capability_log.py [--out PATH]

The committed log starts with exactly this output; rows appended by a live run
(`carbon/agent_campaign/graphite/capability_log.py`, opt-in) follow it. The backfill is
data (`refused_capability_backfill.json`), cited to its source.
"""

import argparse
import json
from pathlib import Path

from carbon.agent_campaign.graphite import capability_log

REPOSITORY = Path(__file__).resolve().parents[3]
BACKFILL = (
    REPOSITORY / "docs/development/graphite/level4/refused_capability_backfill.json"
)
LOG = REPOSITORY / capability_log.DEFAULT_LOG


def render():
    document = json.loads(BACKFILL.read_text(encoding="utf-8"))
    lines = [capability_log.HEADER]
    for item in document["rows"]:
        lines.append(
            capability_log.row(
                {
                    "when": document["when"],
                    "challenge": document["challenge"],
                    "level": document["level"],
                    "kind": "refusal",
                    "source": "stage A extract (backfill)",
                    **item,
                }
            )
        )
    return "".join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--out", type=Path, default=LOG)
    args = parser.parse_args(argv)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_bytes(render().encode("utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
