# neurons/symbolic/symbolic_models.py

"""
Symbolic Metadata models for Carbon.

Basic structure for Phase 0 symbolic layer.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any


@dataclass
class SymbolicMetadata:
    challenge_id: str
    symmetries: List[str] = field(default_factory=list)
    conservation_laws: List[str] = field(default_factory=list)
    boundary_types: List[str] = field(default_factory=list)
    coupling_terms: List[str] = field(default_factory=list)
    dimensionless_groups: List[str] = field(default_factory=list)
    extracted_at: str = ""
    version: str = "v0.1"
    metadata: Dict[str, Any] = field(default_factory=dict)
