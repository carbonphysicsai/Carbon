"""Controller-only isolated prospective draws; never a miner capability."""

from __future__ import annotations

import os
from pathlib import Path

from carbon.generators import burgers_dynamics
from carbon.scoring.development import rule_digest

from .data import write_once
from .profile import CHALLENGE, canonical, digest
from .research_carrier import _run
from .research_profile import ROLE_ROOTS, document

PROGRAM = """
import json,hashlib
from pathlib import Path
from carbon.generators.burgers_dynamics import BurgersCaseCoordinates,PublicDevelopmentRole,generate_development_case
from carbon.registry import ChallengeKey
from carbon.seeding import EvaluationBinding,MockContext,MockEntropy,SeedPin
def canonical(value):return json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
def digest(value):return 'sha256:'+hashlib.sha256(value).hexdigest()
config=json.loads(Path('/input/generation.json').read_bytes())
out=Path('/scratch/output');seen=set();manifest={}
for role,entropy in config['roots'].items():
    pin=SeedPin(ChallengeKey(*config['challenge']),'c-auth1-1.0',config['generator_digest'],'balanced-v2-autoresearch-v1',config['rule_digest'],EvaluationBinding(bytes.fromhex(config['profile_digest'][7:])))
    ctx=MockContext(MockEntropy(bytes.fromhex(entropy)),pin)
    coordinates=([BurgersCaseCoordinates(PublicDevelopmentRole.TRAIN,c,o,b) for b in range(2) for c in range(12) for o in range(3)] if role=='research-train' else [BurgersCaseCoordinates(d,c,0,0) for d in (PublicDevelopmentRole.EVAL,PublicDevelopmentRole.STRESS) for c in range(12)])
    cases=[generate_development_case(ctx,c) for c in coordinates]
    signatures=[digest(canonical([c.cosine_coefficients,c.sine_coefficients,c.mean,c.viscosity])) for c in cases]
    if len(set(signatures))!=len(signatures) or seen.intersection(signatures):raise ValueError('parent overlap; no replacement draws')
    seen.update(signatures)
    payload=canonical([case.public_record() for case in cases]);(out/(role+'-cases.json')).write_bytes(payload)
    manifest[role]={'count':len(cases),'digest':digest(payload),'parent_signatures':signatures}
(out/'private-role-manifest.json').write_bytes(canonical(manifest))
"""


def generate_roles(ledger, *, owner, image):
    root = ledger.root / "private-roles"
    private = root / "role-roots"
    private.mkdir(parents=True, exist_ok=True, mode=0o700)
    for role in ROLE_ROOTS:
        path = private / (role + ".bin")
        if not path.exists():
            write_once(path, os.urandom(32))
    roots = {role: (private / (role + ".bin")).read_bytes() for role in ROLE_ROOTS}
    if (
        any(len(value) != 32 for value in roots.values())
        or len(set(roots.values())) != 4
    ):
        raise ValueError("distinct role roots required")
    config = {
        "roots": {role: value.hex() for role, value in roots.items()},
        "challenge": [CHALLENGE.challenge_id, CHALLENGE.version],
        "generator_digest": digest(Path(burgers_dynamics.__file__).read_bytes()),
        "rule_digest": rule_digest(),
        "profile_digest": digest(canonical(document())),
    }
    worker = _run(
        ledger,
        owner=owner,
        identity="prospective-role-generation",
        source=PROGRAM,
        files={"generation.json": canonical(config)},
        image=image,
        seconds=120,
        provenance="CONTROLLER_PRIVATE_PROSPECTIVE_GENERATION",
        extra_resources={},
        phase="selection",
    )
    snapshot = ledger.root / worker["operation"] / "snapshot"
    for name in ["private-role-manifest.json"] + [
        role + "-cases.json" for role in ROLE_ROOTS
    ]:
        body = (snapshot / name).read_bytes()
        if digest(body) != worker["files"].get(name):
            raise ValueError("generation output changed")
        write_once(root / name, body)
    write_once(root / "research-profile.json", canonical(document()))
    return root
