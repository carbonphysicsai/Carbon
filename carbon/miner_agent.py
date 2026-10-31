"""The one agent string the miner's HTTP calls to a door send.

Cloudflare refuses Python's default urllib agent with 403 (the same refusal
`carbon/dashboard/__main__.py` FETCH_HEADERS names), so a miner call to a
published door (`<name>-door.carbonphysics.ai`) names itself plainly. Every
miner-side read or post to an intake uses these headers, from this one
constant; a test pins that none goes out with urllib's default agent.
"""

from carbon import __version__

MINER_USER_AGENT = f"carbon-miner/{__version__} (+https://carbonphysics.ai)"
MINER_HEADERS = {"User-Agent": MINER_USER_AGENT}
