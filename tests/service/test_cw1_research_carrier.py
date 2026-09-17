"""Actual public research-script isolation; engineering only, no model calls."""

import json
import os
from pathlib import Path

from carbon.development_session.research_carrier import run_script
from carbon.development_session.research_ledger import (
    CEILINGS,
    ELAPSED_SECONDS,
    VERSION,
    CampaignLedger,
)
from carbon.reconstruction.worker.docker_runtime import load_image_identity


def test_script_has_only_public_stage_and_cleanup_reaps_background_child(tmp_path):
    image = load_image_identity(Path(os.environ["CARBON_C03_IMAGE_MANIFEST"]))
    ledger = CampaignLedger(tmp_path)
    ledger.freeze(
        {
            "schema": VERSION,
            "ceilings": CEILINGS,
            "elapsed_seconds": ELAPSED_SECONDS,
            "campaign_id": "engineering-isolation-test",
            "implementation": "candidate",
            "objective": "test-only",
            "sampling": "public-test-only",
            "control": "test-only",
            "selection": "test-only",
            "replica_policy": "test-only",
            "provider": "none",
            "owner": "synthetic-engineering-requester",
        }
    )
    source = """
import json,os,socket,subprocess
from pathlib import Path
assert Path('public.txt').read_bytes()==b'public-only'
assert not Path('/var/run/docker.sock').exists()
assert not Path('/home/carbon/Carbon').exists()
assert not any(k in os.environ for k in ('OPENAI_API_KEY','AWS_SECRET_ACCESS_KEY'))
try:
    Path('/forbidden-root-file').write_text('x')
except OSError:
    pass
else:
    raise AssertionError('root filesystem writable')
network=socket.socket();network.settimeout(.2)
try:
    network.connect(('192.0.2.1',443))
except OSError:
    pass
else:
    raise AssertionError('network access')
finally:
    network.close()
child=subprocess.Popen(['/opt/carbon-worker/bin/python','-I','-c','import time;time.sleep(120)'])
Path('/scratch/output/check.json').write_text(json.dumps({'public_input_only':True,'child_pid':child.pid}))
"""
    result = run_script(
        ledger,
        owner="synthetic-engineering-requester",
        identity="script-boundary-1",
        source=source,
        files={"public.txt": b"public-only"},
        image=image,
        seconds=90,
    )
    assert result["provenance"] == "MINER_SELF_REPORTED"
    assert result["official_eligible"] is False
    operation = tmp_path / result["operation"]
    assert json.loads((operation / "snapshot/check.json").read_bytes())[
        "public_input_only"
    ]
    assert (
        ledger.status(owner="synthetic-engineering-requester")["operations"][0]["state"]
        == "SUCCEEDED"
    )
    # Exact replay returns retained output without another container or worker charge.
    assert (
        run_script(
            ledger,
            owner="synthetic-engineering-requester",
            identity="script-boundary-1",
            source=source,
            files={"public.txt": b"public-only"},
            image=image,
            seconds=90,
        )
        == result
    )
    assert (
        len(ledger.status(owner="synthetic-engineering-requester")["operations"]) == 1
    )
