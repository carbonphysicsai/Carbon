# neurons/symbolic/pysr_runner.py

"""
PySR Track Runner - Skeleton for Symbolic Regression track in Carbon.

Follows docs/SYMBOLIC_LAYER_DESIGN.md
"""

from dataclasses import dataclass
from typing import Dict, Optional, Any

import numpy as np


@dataclass
class SymbolicRegressionResult:
    equation: str
    complexity: int
    score: float
    loss: float
    metadata: Dict[str, Any]


class PySRTrackRunner:
    """
    Wrapper around PySR for the Symbolic Regression track.

    In Phase 0 this is a skeleton that can optionally call PySR.
    Later versions will support physics-informed losses and integration
    with scoring / Landscape Agent.
    """

    def __init__(self, config: Optional[Dict] = None):
        self.config = config or {}
        self.available = False

        try:
            from pysr import PySRRegressor
            self.PySRRegressor = PySRRegressor
            self.available = True
        except ImportError:
            self.PySRRegressor = None

    def run(
        self,
        trajectories: Dict[str, np.ndarray],
        challenge_id: str,
        config: Optional[Dict] = None,
    ) -> SymbolicRegressionResult:
        """
        Run symbolic regression on trajectory data.

        Returns a scored equation (or placeholder if PySR not available).
        """
        if not self.available:
            return SymbolicRegressionResult(
                equation="PySR not installed",
                complexity=0,
                score=0.0,
                loss=float("inf"),
                metadata={"warning": "pysr package not found"},
            )

        # Default PySR config (can be overridden)
        pysr_config = {
            "niterations": 50,
            "populations": 20,
            "maxsize": 20,
            "parsimony": 0.003,
        }
        if config:
            pysr_config.update(config)

        # Prepare data (simple concatenation for Phase 0)
        X = []
        y = []
        for key, arr in trajectories.items():
            if arr.ndim == 2 and arr.shape[1] >= 2:
                X.append(arr[:, :-1])
                y.append(arr[:, -1])

        if not X:
            return SymbolicRegressionResult(
                equation="no valid trajectory data",
                complexity=0,
                score=0.0,
                loss=float("inf"),
                metadata={},
            )

        X = np.vstack(X)
        y = np.concatenate(y)

        model = self.PySRRegressor(**pysr_config)
        model.fit(X, y)

        best = model.get_best()

        return SymbolicRegressionResult(
            equation=str(best.equation),
            complexity=int(best.complexity),
            score=float(best.score),
            loss=float(best.loss),
            metadata={"sympy": str(best.sympy_expr)},
        )
