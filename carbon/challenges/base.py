"""Base Challenge class with multi-backbone support."""

from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional


@dataclass
class Challenge:
    challenge_id: str
    name: str
    description: str = ""
    resolution: List[int] = field(default_factory=lambda: [128, 128])
    baseline_error: float = 1.0
    data_source: str = "synthetic"
    stress_data: Dict[str, Any] = field(default_factory=dict)
    symbolic_metadata: Dict[str, Any] = field(default_factory=dict)

    # NEW: Multi-backbone support
    backbone: str = "physicsnemo_fno"   # Default backbone
    supported_backbones: List[str] = field(default_factory=lambda: ["physicsnemo_fno", "fno", "deeponet"])

    def get_backbone(self) -> str:
        return self.backbone

    def set_backbone(self, backbone: str):
        if backbone not in self.supported_backbones:
            raise ValueError(f"Backbone {backbone} not supported. Supported: {self.supported_backbones}")
        self.backbone = backbone
