"""Challenge registry for Hydrogen."""

from .poisson_2d import load_challenge as load_poisson
from .darcy_2d import load_challenge as load_darcy
from .burgers import load_challenge as load_burgers
from .heat import load_challenge as load_heat
from .elasticity_2d import load_challenge as load_elasticity
from .navier_stokes_2d import load_challenge as load_ns

CHALLENGE_LOADERS = {
    "poisson_2d_v1": load_poisson,
    "darcy_2d_v1": load_darcy,
    "burgers_v1": load_burgers,
    "heat_v1": load_heat,
    "elasticity_2d_v1": load_elasticity,
    "ns_2d_laminar_v1": load_ns,
}

def load_challenge(challenge_id: str):
    if challenge_id not in CHALLENGE_LOADERS:
        raise ValueError(f"Unknown challenge: {challenge_id}")
    return CHALLENGE_LOADERS[challenge_id](challenge_id)
