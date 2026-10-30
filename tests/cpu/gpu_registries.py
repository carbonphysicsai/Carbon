"""Test seam for the stage-2 registries: replaces the one loader, never a module constant."""

from carbon.backbone_catalog import gpu_receipt


def _state(monkeypatch):
    state = getattr(monkeypatch, "_stage2_state", None)
    if state is None:
        state = {"images": {}, "classes": frozenset()}
        monkeypatch._stage2_state = state
        monkeypatch.setattr(
            gpu_receipt,
            "stage2_registries",
            lambda directory=None: gpu_receipt.Stage2Registries(
                state["images"], state["classes"]
            ),
        )
    return state


def set_pins(monkeypatch, images):
    _state(monkeypatch)["images"] = {k: frozenset(v) for k, v in images.items()}


def set_classes(monkeypatch, classes):
    _state(monkeypatch)["classes"] = frozenset(classes)
