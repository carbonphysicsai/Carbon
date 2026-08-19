# carbon/sciml/client.py
import httpx
import asyncio
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from jaxtyping import Array
import asyncio
import numpy as np

@dataclass
class SciMLClient:
    """Async client for Julia/SciML Ground Truth Service"""
    base_url: str = "http://localhost:8083"
    timeout: float = 300.0  # 5 min for complex PDE solves
    
    def __init__(self, base_url: str = "http://localhost:8083"):
        self.base_url = base_url.rstrip('/')
        self.client = httpx.AsyncClient(timeout=httpx.Timeout(self.timeout))
    
    async def solve_pde_reference(self, pde_spec: Dict, params: Dict) -> Dict:
        """Get high-fidelity reference solution from Julia/SciML."""
        response = await self.client.post(
            f"{self.base_url}/solve_pde",
            json={"action": "solve_pde", "pde_spec": pde_spec, "params": params}
        )
        response.raise_for_status()
        return response.json()
    
    async def compute_adjoint_sensitivity(self, 
        initial_state: Array, 
        params: Dict, 
        loss_fn: str) -> Dict:
        """Compute adjoint gradients via SciMLSensitivity.jl."""
        response = await self.client.post(
            f"{self.base_url}/adjoint",
            json={
                "action": "adjoint_sensitivity",
                "initial_state": initial_state.tolist() if hasattr(initial_state, 'tolist') else initial_state,
                "params": params,
                "loss_function": loss_fn
            }
        )
        response.raise_for_status()
        return response.json()
    
    async def generate_symbolic_loss(self, 
        symbolic_expression: str, 
        variables: list) -> Dict:
        """Get symbolic loss term from ModelingToolkit.jl."""
        response = await self.client.post(
            f"{self.base_url}/symbolic_loss",
            json={
                "action": "symbolic_loss",
                "symbolic_expression": symbolic_expression,
                "variables": variables
            }
        )
        response.raise_for_status()
        return response.json()
    
    async def validate_against_reference(self, 
        model_prediction: Array, 
        pde_spec: Dict, 
        params: Dict) -> Dict:
        """Validate model against SciML reference solution."""
        response = await self.client.post(
            f"{self.base_url}/validate",
            json={
                "action": "validate_solution",
                "model_prediction": model_prediction.tolist() if hasattr(model_prediction, 'tolist') else model_prediction,
                "pde_spec": pde_spec,
                "params": params
            }
        )
        response.raise_for_status()
        return response.json()
    
    async def health_check(self) -> bool:
        """Check service health."""
        try:
            response = await self.client.get(f"{self.base_url}/health", timeout=5.0)
            return response.status_code == 200
        except:
            return False
    
    async def close(self):
        await self.client.aclose()

# Context manager for easy usage
async def get_sciml_client() -> 'SciMLClient':
    client = SciMLClient()
    try:
        yield client
    finally:
        await client.close()
