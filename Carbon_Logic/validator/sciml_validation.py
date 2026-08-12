# carbon/validator/sciml_validation.py

class SciMLValidationMixin:
    """Mixin for Validator to use SciML reference solutions"""
    
    def __init__(self, config: Dict = None):
        self.config = config or {}
        self.sciml_client = SciMLClient(
            base_url=self.config.get("sciml_endpoint", "http://carbon-sciml:8083")
        )
    
    async def validate_against_sci_ml(self, 
        model_fn: Callable, 
        challenge_id: str, 
        params: Dict) -> Dict:
        """Validate model against SciML reference solution."""
        
        # Get challenge spec for PDE definition
        challenge_spec = self.get_challenge_spec(challenge_id)
        
        # Get reference solution from Julia/SciML
        reference = await self.sciml_client.solve_pde_reference(
            pde_spec=challenge_spec.pde_spec,
            params=params
        )
        
        # Evaluate model on same grid
        model_prediction = self._evaluate_on_grid(model_fn, reference["coords"])
        
        # Compute error metrics
        error_metrics = self._compute_error_metrics(model_prediction, reference["solution"])
        
        return {
            "passes": all(v < 1e-3 for v in error_metrics.values()),
            "error_metrics": error_metrics,
            "reference_solution": reference
        )
    
    def _run_physics_gates(self, state: TrainState) -> List[GateResult]:
        """Run physics gates with SciML validation for adjoint gate."""
        # Standard gates (pure JAX)
        gate_results = run_all_gates(
            model_fn=self.model_apply_fn,
            challenge=self.current_challenge,
            params=state.params,
            stress_data=self.stress_data,
            generator_version=self.generator_version
        )
        
        # Adjoint Consistency Gate via SciMLSensitivity.jl (Phase 1A+)
        if self.config.get("adjoint_consistency_gate", False):
            try:
                adjoint_result = await self.sciml_client.compute_adjoint_sensitivity(
                    model_fn=self.model_apply_fn,
                    params=state.params,
                    loss_fn="physics_residual"
                )
                rel_error = adjoint_result["rel_error"]
                score = 1.0 / (1.0 + jnp.exp(20.0 * (rel_error - 1e-4) / 1e-4))
                gate_results.append(GateResult(
                    gate_id="adjoint_consistency",
                    threshold=1e-4,
                    result=rel_error,
                    score=float(score),
                    status="PASS" if score > 0.5 else "FAIL"
                ))
            except Exception as e:
                logger.warning(f"SciML adjoint failed: {e}, using fallback")
                # Fallback to finite difference
                fd_grad = finite_difference_gradient(self.model_apply_fn, state.params)
                return GateResult(...)
        
        return gate_results
