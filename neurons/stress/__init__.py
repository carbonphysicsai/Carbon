# neurons/stress/__init__.py

"""
Carbon Stress Test System

Provides hidden, physics-grounded, deterministic stress testing
for robust and anti-gaming evaluation.

See docs/STRESS_TEST_DESIGN.md for full specification.
"""

from .stress_models import StressVariant, StressTestSet, StressSource

__all__ = ["StressVariant", "StressTestSet", "StressSource"]
