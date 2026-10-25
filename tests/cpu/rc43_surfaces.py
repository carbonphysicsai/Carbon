"""Helpers for the tests that pin a graph route v2 version's kit as an earlier state
reproduces it ("moved by X alone").

The v8 head widened the learning-rate surface from `positive` to `finite`
(Validator, OWNER-SEVEN-LIMITS-APPROVED-01, row 7) and gave the trainer a loss graph (new
trainer sha256 and loss text). The adapter block published in each v2 version's limits
carries those, so the version's kit digest moved through them; an earlier-state invariant
puts them back first."""

from carbon.development_session import physical_graph_adapter_v2 as adapter


def learning_rate_as_in_rc43(monkeypatch):
    """Everything the v8 head changed in the published adapter block: the
    learning-rate kind, the trainer (a loss graph) and its sha256."""
    monkeypatch.setitem(
        adapter.TRAIN_SURFACES, "learning_rate", ("positive", None, 0.002)
    )
    monkeypatch.setattr(adapter, "TRAINER_SHA256", RC43_TRAINER_SHA256)
    monkeypatch.setattr(
        adapter, "TRAINER_LOSS_TEXT", "per-output weighted, over the member's outputs"
    )


RC43_TRAINER_SHA256 = "54152a38628862cad0f94314b830130fc6e3d39480a41be94af85eca669a517d"
