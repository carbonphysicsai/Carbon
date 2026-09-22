"""Actual public research-script isolation; engineering only, no model calls."""

import json
import os
from pathlib import Path

from carbon.development_session.research_carrier import run_script
from carbon.development_session.research_image import build_analysis_image
from carbon.development_session.research_ledger import (
    DEVELOPMENT_CEILINGS,
    DEVELOPMENT_ELAPSED_SECONDS,
    VERSION,
    CampaignLedger,
)


def test_script_has_only_public_stage_and_cleanup_reaps_background_child(tmp_path):
    parent = Path(os.environ["CARBON_C03_IMAGE_MANIFEST"])
    image = build_analysis_image(parent, parent.parent / "d4-analysis-acceptance")
    ledger = CampaignLedger(tmp_path)
    ledger.freeze(
        {
            "schema": VERSION,
            "ceilings": DEVELOPMENT_CEILINGS,
            "elapsed_seconds": DEVELOPMENT_ELAPSED_SECONDS,
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
assert not list(Path('/home').glob('*/Carbon'))
import importlib.util
for name in ('carbon.measurement_runtime','carbon.reference_runtime','carbon.development_session','carbon.audit','carbon.registry','carbon.chain'):
    assert importlib.util.find_spec(name) is None,name
from carbon.reconstruction._vendor.carbon_jax_lab.config import ModelConfig
assert ModelConfig(kind='fno1d',width=4,heads=2).kind=='fno1d'
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


def test_cancel_live_script_removes_container_and_retains_charge(tmp_path):
    import concurrent.futures
    import time

    import pytest

    from carbon.development_session.research_carrier import (
        reconcile_worker,
        request_cancel,
    )
    from carbon.reconstruction.worker.docker_runtime import DockerCLI
    from carbon.reconstruction.worker.model import WorkerFailure

    parent = Path(os.environ["CARBON_C03_IMAGE_MANIFEST"])
    image = build_analysis_image(parent, parent.parent / "d4-analysis-acceptance")
    ledger = CampaignLedger(tmp_path)
    ledger.freeze(
        {
            "schema": VERSION,
            "ceilings": DEVELOPMENT_CEILINGS,
            "elapsed_seconds": DEVELOPMENT_ELAPSED_SECONDS,
            "campaign_id": "engineering-cancel-test",
            "implementation": "candidate",
            "objective": "test-only",
            "sampling": "test-only",
            "control": "none",
            "selection": "none",
            "replica_policy": "none",
            "provider": "none",
            "owner": "fixture",
        }
    )
    source = "import subprocess,time;from pathlib import Path;subprocess.Popen(['/opt/carbon-worker/bin/python','-I','-c','import time;time.sleep(120)']);Path('/scratch/workspace/ready').write_text('ready');print('SCRIPT_READY',flush=True);time.sleep(120)"
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(
            run_script,
            ledger,
            owner="fixture",
            identity="cancel-test-worker",
            source=source,
            files={},
            image=image,
            seconds=90,
        )
        deadline = time.monotonic() + 20
        while time.monotonic() < deadline:
            intents = list(tmp_path.glob("operation-*/intent.json"))
            if intents:
                active = json.loads(intents[0].read_bytes())
                try:
                    ready = DockerCLI().run(
                        [
                            "exec",
                            active["container"],
                            "/usr/bin/test",
                            "-f",
                            "/scratch/workspace/ready",
                        ],
                        timeout=2,
                        accepted=(0, 1),
                    )
                    if ready.returncode == 0:
                        break
                except WorkerFailure:
                    pass
            if future.done():
                future.result()
            time.sleep(0.1)
        else:
            pytest.fail("script did not become active")
        request_cancel(ledger, owner="fixture", identity="cancel-test-worker")
        with pytest.raises((ValueError, WorkerFailure)):
            future.result(timeout=45)
    intent = json.loads(next(tmp_path.glob("operation-*/intent.json")).read_bytes())
    assert (
        not DockerCLI()
        .run(
            ["ps", "-aq", "--filter", "name=^" + intent["container"] + "$"], timeout=10
        )
        .stdout.strip()
    )
    result = reconcile_worker(ledger, owner="fixture", identity="cancel-test-worker")
    assert result["cleanup_observed"] and not result["retry_dispatched"]
    assert ledger.status(owner="fixture")["used"]["research_trials"] == 1
    assert ledger.status(owner="fixture")["used"]["numerical_milliseconds"] == 90000
