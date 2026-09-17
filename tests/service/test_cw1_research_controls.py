"""Every advertised control reaches executed lab behavior, on engineering data.

No model-provider inference or Burgers generalization is asserted by this test.
"""

import json
import os
from pathlib import Path

from carbon.development_session.profile import canonical
from carbon.development_session.research_carrier import _run
from carbon.development_session.research_catalog import SURFACES, compile_recipe
from carbon.development_session.research_ledger import (
    CEILINGS,
    ELAPSED_SECONDS,
    VERSION,
    CampaignLedger,
)
from carbon.reconstruction.worker.docker_runtime import load_image_identity

PROGRAM = """
import json
from pathlib import Path
import numpy as np
import jax
import jax.numpy as jnp
from carbon.reconstruction._vendor.carbon_jax_lab.config import ModelConfig,TaskConfig,TrainConfig
from carbon.reconstruction._vendor.carbon_jax_lab.training import Trainer
from carbon.reconstruction._vendor.carbon_jax_lab.data import Trajectories
cases=json.loads(Path('/input/controls.json').read_bytes())
x=np.arange(16)*2*np.pi/16
initial=np.array([.1+.2*np.sin(x),-.05+.3*np.cos(x),.03+.1*np.cos(2*x)])
times=np.tile([0.,.1,.2],(3,1))
solution=np.stack([u.mean()+(u-u.mean())[None,:]*np.exp(-np.array([0.,.1,.2])[:,None]*(i+1)) for i,u in enumerate(initial)])
data=Trajectories(initial,np.array([.01,.02,.03]),times,solution,x,'train','MANUFACTURED_CONTROL_ONLY',domain_length=2*np.pi)
def trainer(config):
    return Trainer(ModelConfig(**config['model']),TaskConfig(**config['task']),TrainConfig(**config['train']),data,runtime_key_material=bytes(range(32)))
def array(tree):return np.concatenate([np.asarray(v).ravel() for v in jax.tree.leaves(tree)])
cache={}
def fit(config):
    key=json.dumps(config,sort_keys=True)
    if key not in cache:
        t=trainer(config);t.fit();cache[key]=t
    return cache[key]
passed={}
for name,pair in cases.items():
    a,b=pair
    if name in ('width','depth','n_modes','branch_points'):
        left,right=trainer(a),trainer(b)
        assert [v.shape for v in jax.tree.leaves(left.state.params)] != [v.shape for v in jax.tree.leaves(right.state.params)],name
        passed[name]='actual parameter shapes changed'
    elif name=='remat':
        left,right=trainer(a),trainer(b)
        inputs=(jnp.asarray(initial),jnp.array([.01,.02,.03]),jnp.array([.1,.1,.1]),jnp.asarray(x))
        one=left.predictor(left.state.params,*inputs);two=right.predictor(right.state.params,*inputs)
        np.testing.assert_allclose(one,two,rtol=1e-6,atol=1e-7)
        graph=str(jax.make_jaxpr(lambda p:right.predictor(p,*inputs))(right.state.params))
        assert 'remat' in graph
        passed[name]='rematerialization graph present with unchanged forward semantics'
    elif name in ('hard_initial_condition','enforce_mean'):
        left,right=trainer(a),trainer(b)
        time=0. if name=='hard_initial_condition' else .1
        args=(jnp.asarray(initial),jnp.array([.01,.02,.03]),jnp.full((3,),time),jnp.asarray(x))
        one=np.asarray(left.predictor(left.state.params,*args));two=np.asarray(right.predictor(right.state.params,*args))
        if name=='hard_initial_condition':np.testing.assert_allclose(two,initial,rtol=0,atol=1e-7)
        else:np.testing.assert_allclose(two.mean(axis=-1),initial.mean(axis=-1),rtol=0,atol=1e-7)
        assert np.max(abs(one-two))>1e-6
        passed[name]='actual permitted initial-field invariant enforced'
    else:
        left,right=fit(a),fit(b)
        if name=='inference_weights':
            # audit prohibits identical TRAIN membership; test predictor-selected weights directly.
            def prediction(t):
                weights=t.state.params if t.config.inference_weights=='params' else t.state.ema
                return np.asarray(t.predictor(weights,jnp.asarray(initial),jnp.array([.01,.02,.03]),jnp.array([.1,.1,.1]),jnp.asarray(x)))
            assert np.max(abs(prediction(left)-prediction(right)))>1e-8
        elif name=='ema_decay':assert np.max(abs(array(left.state.ema)-array(right.state.ema)))>1e-8
        else:
            l=array((left.state.params,left.state.optimizer));rr=array((right.state.params,right.state.optimizer))
            assert l.shape!=rr.shape or np.max(abs(l-rr))>1e-10,name
        passed[name]='executed update/optimizer or selected inference weights changed'
Path('/scratch/output/control-behavior.json').write_text(json.dumps({'provenance':'ENGINEERING_MANUFACTURED_ONLY','controls':passed}))
"""


def test_advertised_controls_change_actual_execution_as_registered(tmp_path):
    base = {
        "schema_version": "1.0",
        "challenge_id": "burgers-dynamics-v1",
        "backbone": "fno",
        "parameters": {
            "width": 4,
            "depth": 1,
            "n_modes": 4,
            "steps": 3,
            "batch_size": 2,
            "learning_rate": 0.01,
            "hard_initial_condition": False,
            "enforce_mean": False,
        },
    }
    changes = {
        "steps": 2,
        "width": 8,
        "depth": 2,
        "n_modes": 8,
        "branch_points": 8,
        "remat": True,
        "hard_initial_condition": True,
        "enforce_mean": True,
        "batch_size": 3,
        "microbatches": 2,
        "learning_rate": 0.005,
        "min_learning_rate_ratio": 0.8,
        "warmup_steps": 2,
        "weight_decay": 0.1,
        "clip_norm": 0.001,
        "beta1": 0.1,
        "beta2": 0.8,
        "adam_epsilon": 0.01,
        "ema_decay": 0.0,
        "relative_loss": True,
        "h1_weight": 0.1,
        "pde_weight": 0.001,
        "physics_warmup_steps": 2,
        "inference_weights": "ema",
    }
    assert set(changes) == set(SURFACES)

    def config(strategy):
        _, profile = compile_recipe(strategy)
        return {
            "model": json.loads(profile.model_config_json),
            "task": json.loads(profile.task_config_json),
            "train": json.loads(profile.train_config_json),
        }

    cases = {}
    for name, value in changes.items():
        first = {**base, "parameters": dict(base["parameters"])}
        if name == "branch_points":
            first["backbone"] = "deeponet"
            first["parameters"].pop("depth")
            first["parameters"].pop("n_modes")
            first["parameters"]["branch_points"] = 4
        if name == "physics_warmup_steps":
            first["parameters"]["pde_weight"] = 0.001
        second = {**first, "parameters": {**first["parameters"], name: value}}
        cases[name] = [config(first), config(second)]
    ledger = CampaignLedger(tmp_path / "ledger")
    ledger.freeze(
        {
            "schema": VERSION,
            "ceilings": CEILINGS,
            "elapsed_seconds": ELAPSED_SECONDS,
            **{
                name: "engineering-controls-only"
                for name in (
                    "campaign_id",
                    "implementation",
                    "objective",
                    "sampling",
                    "control",
                    "selection",
                    "replica_policy",
                    "provider",
                    "owner",
                )
            },
        }
    )
    result = _run(
        ledger,
        owner="engineering-controls-only",
        identity="executed-controls",
        source=PROGRAM,
        files={"controls.json": canonical(cases)},
        image=load_image_identity(Path(os.environ["CARBON_C03_IMAGE_MANIFEST"])),
        seconds=600,
        provenance="ENGINEERING_PARAMETER_BEHAVIOR",
        extra_resources={},
    )
    observed = json.loads(
        (
            ledger.root / result["operation"] / "snapshot/control-behavior.json"
        ).read_bytes()
    )
    assert set(observed["controls"]) == set(SURFACES)
