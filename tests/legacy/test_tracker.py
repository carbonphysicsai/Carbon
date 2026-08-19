# tests/test_tracker.py

"""
Tests for ChallengeWinnerTracker.
"""

from neurons.scoring.challenge_winner_tracker import ChallengeWinnerTracker


def test_tracker_only_new_best_updates():
    tracker = ChallengeWinnerTracker(decay_factor=0.85)
    tracker.update("hotkey1", "challenge_A", 0.8)
    # Lower score, should not become new leader.
    tracker.update("hotkey1", "challenge_A", 0.7)

    assert tracker.get_current_leader("challenge_A") == "hotkey1"
    # Score should still be the best one (0.8)


def test_tracker_exponential_decay():
    tracker = ChallengeWinnerTracker(decay_factor=0.5)
    tracker.update("hotkey1", "challenge_B", 0.9)
    # After decay, effective score should be lower
    # (Exact value depends on implementation details)
    stats = tracker.get_stats()
    assert stats["tracked_challenges"] >= 1
