"""Helpers for the tests that pin a graph route v2 version's kit as an earlier state
reproduces it ("moved by X alone").

The v8 head widened the learning-rate surface from `positive` to `finite`
(Validator, OWNER-SEVEN-LIMITS-APPROVED-01, row 7). The adapter block published in each
v2 version's limits carries that kind, so the version's kit digest moved through that one
field; an earlier-state invariant puts it back first."""

from carbon.development_session import physical_graph_adapter_v2 as adapter


def learning_rate_as_in_rc43(monkeypatch):
    monkeypatch.setitem(
        adapter.TRAIN_SURFACES, "learning_rate", ("positive", None, 0.002)
    )
