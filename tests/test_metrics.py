"""Unit tests for metrics pure analytical functions."""

import json
from pathlib import Path
from config import ANGLES
import metrics


def test_metrics_empty_and_missing_log(tmp_path):
    """Missing or empty log returns valid empty structures, never raises."""
    missing_file = tmp_path / "nonexistent.json"
    assert metrics.load_log_data(missing_file) == []
    assert metrics.rate_by_batch([]) == {}
    assert metrics.first_last_rate([]) == (0.0, 0.0)
    assert metrics.delta_pts([]) == 0.0
    assert metrics.angle_mix_by_batch([]) == {}
    assert metrics.most_improved_angle([]) is None

    empty_summary = metrics.get_metrics_summary([])
    assert empty_summary == {
        "rate_by_batch": {},
        "angle_mix_by_batch": {},
        "first_rate": 0.0,
        "last_rate": 0.0,
        "delta_pts": 0.0,
        "most_improved_angle": None,
    }


def test_metrics_rate_per_batch_and_delta():
    """Verify exact rates and delta points calculation."""
    sample_data = [
        # Batch 1: 1 pos out of 3 = 33.3%
        {"batch_id": 1, "angle_used": "referenced_metric", "outcome": "interested"},
        {"batch_id": 1, "angle_used": "referenced_opinion", "outcome": "no_reply"},
        {"batch_id": 1, "angle_used": "generic", "outcome": "no_reply"},
        # Batch 2: 2 pos out of 3 = 66.7%
        {"batch_id": 2, "angle_used": "referenced_metric", "outcome": "interested"},
        {"batch_id": 2, "angle_used": "referenced_metric", "outcome": "reply"},
        {"batch_id": 2, "angle_used": "generic", "outcome": "no_reply"},
        # Batch 3: 3 pos out of 3 = 100.0%
        {"batch_id": 3, "angle_used": "referenced_metric", "outcome": "interested"},
        {"batch_id": 3, "angle_used": "referenced_metric", "outcome": "interested"},
        {"batch_id": 3, "angle_used": "referenced_opinion", "outcome": "reply"},
    ]

    rates = metrics.rate_by_batch(sample_data)
    assert rates[1] == 33.3
    assert rates[2] == 66.7
    assert rates[3] == 100.0

    first, last = metrics.first_last_rate(sample_data)
    assert first == 33.3
    assert last == 100.0
    assert metrics.delta_pts(sample_data) == 66.7


def test_metrics_angle_mix_by_batch():
    """Verify angle mix rows sum to 100% per batch."""
    sample_data = [
        {"batch_id": 1, "angle_used": "referenced_metric", "outcome": "interested"},
        {"batch_id": 1, "angle_used": "referenced_opinion", "outcome": "no_reply"},
        {"batch_id": 1, "angle_used": "generic", "outcome": "no_reply"},
        {"batch_id": 1, "angle_used": "generic", "outcome": "no_reply"},
    ]
    mix = metrics.angle_mix_by_batch(sample_data)
    assert 1 in mix
    b1_mix = mix[1]
    assert b1_mix["referenced_metric"] == 25.0
    assert b1_mix["referenced_opinion"] == 25.0
    assert b1_mix["generic"] == 50.0
    assert round(sum(b1_mix.values()), 1) == 100.0


def test_metrics_most_improved_angle():
    """Verify identifying the angle with greatest positive rate increase between first and last batch."""
    sample_data = [
        # Batch 1: metric is 0/2 (0%), opinion is 1/2 (50%)
        {"batch_id": 1, "angle_used": "referenced_metric", "outcome": "no_reply"},
        {"batch_id": 1, "angle_used": "referenced_metric", "outcome": "no_reply"},
        {"batch_id": 1, "angle_used": "referenced_opinion", "outcome": "interested"},
        {"batch_id": 1, "angle_used": "referenced_opinion", "outcome": "no_reply"},
        # Batch 2: metric is 2/2 (100%), opinion is 1/2 (50%)
        {"batch_id": 2, "angle_used": "referenced_metric", "outcome": "interested"},
        {"batch_id": 2, "angle_used": "referenced_metric", "outcome": "reply"},
        {"batch_id": 2, "angle_used": "referenced_opinion", "outcome": "reply"},
        {"batch_id": 2, "angle_used": "referenced_opinion", "outcome": "no_reply"},
    ]
    improved = metrics.most_improved_angle(sample_data)
    assert improved == "referenced_metric"
