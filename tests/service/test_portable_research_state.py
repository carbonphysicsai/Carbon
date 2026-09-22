"""Two actual CPU research workers transport logical state through one ledger.

Synthetic engineering admission only. No campaign/model spend or qualification.
The helper is explicit public source input, not a new trusted image capability.
"""

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
from carbon.reconstruction.worker.docker_runtime import DockerCLI

_SETUP = """
import json,runpy,shutil
from pathlib import Path
import jax
import numpy as np
from carbon.reconstruction._vendor.carbon_jax_lab.config import ModelConfig,TaskConfig,TrainConfig
from carbon.reconstruction._vendor.carbon_jax_lab.data import Trajectories
from carbon.reconstruction._vendor.carbon_jax_lab.training import Trainer
helper=runpy.run_path('portable_helper.py')
x=np.arange(16,dtype=np.float64)/16
initial=np.stack([np.sin(2*np.pi*x+phase) for phase in (0.,.5,1.,1.5)])
data=Trajectories(initial,np.full(4,.02),np.tile([.05,.1],(4,1)),np.stack([initial*.98,initial*.96],axis=1),x,'train','SYNTHETIC_PORTABILITY_SERVICE_CONTROL')
def make_trainer():
    return Trainer(ModelConfig(kind='fno1d',width=8,depth=1,n_modes=4),TaskConfig(),TrainConfig(steps=4,warmup_steps=0,batch_size=2),data)
trainer=make_trainer()
"""
_SAVE = _SETUP + """
trainer.fit(until_step=2)
fingerprint=helper['save_research_state'](trainer,Path('/scratch/output/bundle'),principal='fixture',operation_id='portable-source')
Path('/scratch/output/digest.txt').write_text(fingerprint)
"""
_CONTINUE = _SETUP + """
bundle=Path('bundle');(bundle/'checkpoint').mkdir(parents=True)
shutil.copyfile('binding.json',bundle/'binding.json')
shutil.copyfile('manifest.json',bundle/'checkpoint/manifest.json')
shutil.copyfile('state.npz',bundle/'checkpoint/state.npz')
receipt=helper['load_research_continuation'](trainer,bundle,principal='fixture',operation_id='portable-continuation',expected_digest=Path('digest.txt').read_text())
assert int(trainer.state.step)==2
trainer.fit()
baseline=make_trainer();baseline.fit()
for expected,actual in zip(jax.tree.leaves(baseline.state),jax.tree.leaves(trainer.state),strict=True):
    np.testing.assert_array_equal(expected,actual)
receipt.update(final_step=int(trainer.state.step),fresh_cpu_control_equal=True)
Path('/scratch/output/continuation.json').write_text(json.dumps(receipt,sort_keys=True))
"""


def test_two_admitted_cpu_research_operations_transport_state_and_replay(tmp_path):
    parent = Path(os.environ["CARBON_C03_IMAGE_MANIFEST"])
    image = build_analysis_image(parent, parent.parent / "portable-analysis-acceptance")
    ledger = CampaignLedger(tmp_path)
    ledger.freeze(
        {
            "schema": VERSION,
            "ceilings": DEVELOPMENT_CEILINGS,
            "elapsed_seconds": DEVELOPMENT_ELAPSED_SECONDS,
            "campaign_id": "engineering-portable-state",
            "implementation": "candidate",
            "objective": "synthetic-state-transport-only",
            "sampling": "public-test-only",
            "control": "same-cpu-fresh-training",
            "selection": "none",
            "replica_policy": "none",
            "provider": "none",
            "owner": "fixture",
        }
    )
    helper = (
        Path(__file__).resolve().parents[2] / "carbon/reconstruction/portable_state.py"
    ).read_bytes()
    first = run_script(
        ledger,
        owner="fixture",
        identity="portable-source",
        source=_SAVE,
        files={"portable_helper.py": helper},
        image=image,
        seconds=90,
    )
    snapshot = tmp_path / first["operation"] / "snapshot"
    files = {
        "portable_helper.py": helper,
        "binding.json": (snapshot / "bundle/binding.json").read_bytes(),
        "manifest.json": (snapshot / "bundle/checkpoint/manifest.json").read_bytes(),
        "state.npz": (snapshot / "bundle/checkpoint/state.npz").read_bytes(),
        "digest.txt": (snapshot / "digest.txt").read_bytes(),
    }
    second = run_script(
        ledger,
        owner="fixture",
        identity="portable-continuation",
        source=_CONTINUE,
        files=files,
        image=image,
        seconds=90,
    )
    receipt = json.loads(
        (tmp_path / second["operation"] / "snapshot/continuation.json").read_bytes()
    )
    assert receipt["source_operation"] == "portable-source"
    assert receipt["operation_id"] == "portable-continuation"
    assert receipt["continued_from_step"] == 2 and receipt["final_step"] == 4
    assert receipt["fresh_cpu_control_equal"] is True
    assert receipt["backend_changed"] is False
    assert receipt["scientifically_qualified"] is False
    assert second["official_eligible"] is False
    before = ledger.status(owner="fixture")
    assert (
        run_script(
            ledger,
            owner="fixture",
            identity="portable-continuation",
            source=_CONTINUE,
            files=files,
            image=image,
            seconds=90,
        )
        == second
    )
    after = ledger.status(owner="fixture")
    assert before["used"] == after["used"]
    assert len(after["operations"]) == 2
    assert after["used"]["research_trials"] == 2
    assert after["used"]["provider_nanodollars"] == 0
    for result in (first, second):
        intent = json.loads(
            (tmp_path / result["operation"] / "intent.json").read_bytes()
        )
        assert (
            not DockerCLI()
            .run(
                ["ps", "-aq", "--filter", "name=^" + intent["container"] + "$"],
                timeout=10,
            )
            .stdout.strip()
        )
    print(
        json.dumps(
            {
                "case": "two-cpu-research-workers-portable-state",
                "image": image.image_id,
                "used": after["used"],
                "receipt": receipt,
            },
            sort_keys=True,
        )
    )
