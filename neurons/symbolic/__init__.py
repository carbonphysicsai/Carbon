# neurons/symbolic/__init__.py

"""
Symbolic Layer for Carbon.

Provides symbolic metadata extraction and PySR-based symbolic regression track.
"""

from .symbolic_models import SymbolicMetadata
from .pysr_runner import PySRTrackRunner, SymbolicRegressionResult

__all__ = ["SymbolicMetadata", "PySRTrackRunner", "SymbolicRegressionResult"]
