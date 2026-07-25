"""T2 — Train/eval/stress seeds and payload hashes differ."""

from poc.generators.burgers1d import generate_batch, role_seed


def test_role_seeds_differ():
    a = role_seed("burgers1d_v0", "train", 1, "r")
    b = role_seed("burgers1d_v0", "eval", 1, "r")
    c = role_seed("burgers1d_v0", "stress", 1, "r")
    assert len({a, b, c}) == 3


def test_batch_hashes_differ():
    train = generate_batch("train", 7, "sep", fast=True, n=4)
    eval_ = generate_batch("eval", 7, "sep", fast=True, n=4)
    stress = generate_batch("stress", 7, "sep", fast=True, n=4)
    assert train.hash() != eval_.hash()
    assert eval_.hash() != stress.hash()
    assert train.seed != eval_.seed


def test_fixed_seed_reproducible():
    a = generate_batch("train", 99, "repro", fast=True, n=4)
    b = generate_batch("train", 99, "repro", fast=True, n=4)
    assert a.hash() == b.hash()
    assert (a.uT == b.uT).all()
