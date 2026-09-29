"""Tests for dashboard_utils.py (Person 5)."""

import pandas as pd
import pytest

from config import ANGLES, LOG_COLUMNS, OUTCOMES, PERSONAS
from dashboard_utils import (
    angle_distribution_by_batch,
    angle_success_by_persona,
    get_comparison,
    interested_rate_by_batch,
    load_log,
    response_rate_by_batch,
)
import make_dummy_log


@pytest.fixture
def handwritten_df():
    """Hand-written DataFrame with mathematically verified exact answers."""
    data = [
        # Batch 1: 4 records (2 positive = 50.0%, 1 interested = 25.0%)
        {
            "batch_id": 1,
            "prospect_id": "p1",
            "persona_type": "Founder",
            "angle_used": "referenced_metric",
            "message_sent": "Msg 1",
            "simulated_response": "Resp 1",
            "outcome": "interested",
            "timestamp": "2026-09-10T10:00:00Z",
        },
        {
            "batch_id": 1,
            "prospect_id": "p2",
            "persona_type": "Founder",
            "angle_used": "referenced_opinion",
            "message_sent": "Msg 2",
            "simulated_response": "Resp 2",
            "outcome": "reply",
            "timestamp": "2026-09-10T10:05:00Z",
        },
        {
            "batch_id": 1,
            "prospect_id": "p3",
            "persona_type": "HR Manager",
            "angle_used": "generic",
            "message_sent": "Msg 3",
            "simulated_response": "",
            "outcome": "no_reply",
            "timestamp": "2026-09-10T10:10:00Z",
        },
        {
            "batch_id": 1,
            "prospect_id": "p4",
            "persona_type": "HR Manager",
            "angle_used": "generic",
            "message_sent": "Msg 4",
            "simulated_response": "",
            "outcome": "no_reply",
            "timestamp": "2026-09-10T10:15:00Z",
        },
        # Batch 2: 4 records (3 positive = 75.0%, 2 interested = 50.0%)
        {
            "batch_id": 2,
            "prospect_id": "p1",
            "persona_type": "Founder",
            "angle_used": "referenced_metric",
            "message_sent": "Msg 1 b2",
            "simulated_response": "Resp 1 b2",
            "outcome": "interested",
            "timestamp": "2026-09-17T10:00:00Z",
        },
        {
            "batch_id": 2,
            "prospect_id": "p2",
            "persona_type": "Founder",
            "angle_used": "referenced_metric",
            "message_sent": "Msg 2 b2",
            "simulated_response": "Resp 2 b2",
            "outcome": "interested",
            "timestamp": "2026-09-17T10:05:00Z",
        },
        {
            "batch_id": 2,
            "prospect_id": "p3",
            "persona_type": "HR Manager",
            "angle_used": "referenced_opinion",
            "message_sent": "Msg 3 b2",
            "simulated_response": "Resp 3 b2",
            "outcome": "reply",
            "timestamp": "2026-09-17T10:10:00Z",
        },
        {
            "batch_id": 2,
            "prospect_id": "p4",
            "persona_type": "HR Manager",
            "angle_used": "generic",
            "message_sent": "Msg 4 b2",
            "simulated_response": "",
            "outcome": "no_reply",
            "timestamp": "2026-09-17T10:15:00Z",
        },
    ]
    return pd.DataFrame(data)


def test_handwritten_exact_rates(handwritten_df):
    """Verify exact response rates (interested + reply) on hand-written data."""
    resp_rates = response_rate_by_batch(handwritten_df)
    assert resp_rates.loc[1] == 50.0
    assert resp_rates.loc[2] == 75.0


def test_handwritten_exact_interested_rates(handwritten_df):
    """Verify exact interested-only outcome rates on hand-written data."""
    int_rates = interested_rate_by_batch(handwritten_df)
    assert int_rates.loc[1] == 25.0
    assert int_rates.loc[2] == 50.0


def test_angle_distribution_rows_sum_to_100(handwritten_df):
    """Verify angle distribution rows sum exactly to 100%."""
    dist = angle_distribution_by_batch(handwritten_df)
    assert list(dist.columns) == ANGLES
    # Row sums
    row_sums = dist.sum(axis=1)
    for total in row_sums:
        assert total == pytest.approx(100.0, abs=0.01)

    # Specific batch 1 breakdown: 1 metric (25%), 1 opinion (25%), 2 generic (50%)
    assert dist.loc[1, "referenced_metric"] == 25.0
    assert dist.loc[1, "referenced_opinion"] == 25.0
    assert dist.loc[1, "generic"] == 50.0


def test_angle_success_by_persona_matrix(handwritten_df):
    """Verify angle_success_by_persona calculates correct persona x angle matrix."""
    matrix = angle_success_by_persona(handwritten_df)
    assert list(matrix.index) == PERSONAS
    assert list(matrix.columns) == ANGLES
    # In handwritten_df, Founder with referenced_metric had 3 attempts (all interested) = 100.0%
    assert matrix.loc["Founder", "referenced_metric"] == 100.0


def test_get_comparison_existing_and_missing_batch(handwritten_df):
    """get_comparison returns valid dict when both batches exist, None when missing."""
    # Batch 1 and 2 exist for prospect p1
    comp = get_comparison(handwritten_df, "p1", batch_a=1, batch_b=2)
    assert comp is not None
    assert comp["prospect_id"] == "p1"
    assert comp["batch_a"]["batch_id"] == 1
    assert comp["batch_b"]["batch_id"] == 2
    assert comp["batch_a"]["angle_used"] == "referenced_metric"

    # Batch 3 does not exist -> returns None
    missing_comp = get_comparison(handwritten_df, "p1", batch_a=1, batch_b=3)
    assert missing_comp is None

    # Prospect not found -> returns None
    unknown_comp = get_comparison(handwritten_df, "unknown_p", batch_a=1, batch_b=2)
    assert unknown_comp is None


def test_load_log_missing_and_corrupt_file(tmp_path):
    """load_log returns empty DataFrame with LOG_COLUMNS on missing or corrupt files."""
    # Missing file
    non_existent = tmp_path / "non_existent.json"
    df = load_log(non_existent)
    assert isinstance(df, pd.DataFrame)
    assert df.empty
    assert list(df.columns) == LOG_COLUMNS

    # Empty file
    empty_file = tmp_path / "empty.json"
    empty_file.write_text("")
    df_empty = load_log(empty_file)
    assert df_empty.empty
    assert list(df_empty.columns) == LOG_COLUMNS

    # Corrupt JSON
    bad_file = tmp_path / "bad.json"
    bad_file.write_text("{not valid json")
    df_bad = load_log(bad_file)
    assert df_bad.empty
    assert list(df_bad.columns) == LOG_COLUMNS


def test_dummy_log_structure_and_performance_rise(tmp_path):
    """Verify dummy log has 36 rows, valid enums, and rate rising batch 1 < 2 < 3."""
    test_log_path = tmp_path / "memory_log.json"
    records = make_dummy_log.generate(str(test_log_path))
    assert len(records) == 36

    df = load_log(test_log_path)
    assert len(df) == 36

    # Verify enums
    for angle in df["angle_used"]:
        assert angle in ANGLES
    for outcome in df["outcome"]:
        assert outcome in OUTCOMES
    for persona in df["persona_type"]:
        assert persona in PERSONAS
    for batch_id in df["batch_id"]:
        assert batch_id in [1, 2, 3]

    # Verify rate rising batch 1 < batch 2 < batch 3
    rates = response_rate_by_batch(df)
    assert rates.loc[1] < rates.loc[2] < rates.loc[3], (
        f"Rates not strictly rising: {rates.to_dict()}"
    )
    # Check approximate targets (~17% -> ~42% -> ~67%)
    assert 14.0 <= rates.loc[1] <= 20.0
    assert 38.0 <= rates.loc[2] <= 46.0
    assert 62.0 <= rates.loc[3] <= 72.0
