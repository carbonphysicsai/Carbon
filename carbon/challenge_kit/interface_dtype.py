"""The output dtype a registered Challenge's numeric interface declares.

Interface documents keep it in different places: the synthetic and Battery
documents under ``outputs.dtype``, Motor and Cooling at the top level as
``dtype``, F08 as ``train_dtype``. One reader, so a new spelling is added once.
"""

from __future__ import annotations


def output_dtype(interface: dict) -> str:
    outputs = interface.get("outputs")
    if type(outputs) is dict and type(outputs.get("dtype")) is str:
        return outputs["dtype"]
    for name in ("dtype", "train_dtype"):
        if type(interface.get(name)) is str:
            return interface[name]
    raise ValueError("interface declares no output dtype")
