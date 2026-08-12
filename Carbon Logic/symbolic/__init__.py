"""Symbolic module for Hydrogen.

Contains tools for symbolic regression (PySR), symbolic metadata handling,
and future hybrid symbolic-neural methods.
"""

from .pysr_evolver import evolve_loss_weights as pysr_evolve_loss_weights

__all__ = ["pysr_evolve_loss_weights"]
