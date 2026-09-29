"""Dashboard data processing utilities using pure pandas (no Streamlit dependency)."""

import json
from pathlib import Path
from typing import Any, Dict, Optional, Union
import pandas as pd

from config import ANGLES, LOG_COLUMNS, PERSONAS, POSITIVE_OUTCOMES


def load_log(path: Union[str, Path]) -> pd.DataFrame:
    """Load the memory log JSON into a DataFrame.
    
    If the file is missing, empty, or contains invalid JSON,
    returns an empty DataFrame with LOG_COLUMNS.
    """
    file_path = Path(path)
    if not file_path.is_file():
        return pd.DataFrame(columns=LOG_COLUMNS)

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read().strip()
            if not content:
                return pd.DataFrame(columns=LOG_COLUMNS)
            data = json.loads(content)
            
        if not isinstance(data, list):
            return pd.DataFrame(columns=LOG_COLUMNS)

        df = pd.DataFrame(data)
        for col in LOG_COLUMNS:
            if col not in df.columns:
                df[col] = None

        return df[LOG_COLUMNS].copy()
    except Exception:
        return pd.DataFrame(columns=LOG_COLUMNS)


def response_rate_by_batch(df: pd.DataFrame) -> pd.Series:
    """Calculate the overall response rate (interested + reply) per batch in percent (0-100)."""
    if df.empty or "batch_id" not in df.columns or "outcome" not in df.columns:
        return pd.Series(dtype=float, name="response_rate")

    rates = df.groupby("batch_id")["outcome"].apply(
        lambda s: float((s.isin(POSITIVE_OUTCOMES)).mean() * 100.0)
    ).round(2)
    rates.name = "response_rate"
    return rates


def interested_rate_by_batch(df: pd.DataFrame) -> pd.Series:
    """Calculate the interested outcome rate per batch in percent (0-100)."""
    if df.empty or "batch_id" not in df.columns or "outcome" not in df.columns:
        return pd.Series(dtype=float, name="interested_rate")

    rates = df.groupby("batch_id")["outcome"].apply(
        lambda s: float((s == "interested").mean() * 100.0)
    ).round(2)
    rates.name = "interested_rate"
    return rates


def angle_distribution_by_batch(df: pd.DataFrame) -> pd.DataFrame:
    """Compute angle distribution percentage per batch.
    
    Rows are batch_ids, columns are ANGLES, and rows sum to 100.0.
    """
    if df.empty or "batch_id" not in df.columns or "angle_used" not in df.columns:
        return pd.DataFrame(columns=ANGLES)

    # Normalize by row index to get percentage per batch
    crosstab = pd.crosstab(df["batch_id"], df["angle_used"], normalize="index") * 100.0

    # Ensure all registered angles exist as columns
    for angle in ANGLES:
        if angle not in crosstab.columns:
            crosstab[angle] = 0.0

    crosstab = crosstab[ANGLES].round(2)
    return crosstab


def angle_success_by_persona(df: pd.DataFrame) -> pd.DataFrame:
    """Compute persona x angle success rate matrix (% of positive outcomes).
    
    Index is PERSONAS, columns are ANGLES, values are 0-100.
    """
    if df.empty or "persona_type" not in df.columns or "angle_used" not in df.columns:
        return pd.DataFrame(0.0, index=PERSONAS, columns=ANGLES)

    temp_df = df.copy()
    temp_df["is_positive"] = temp_df["outcome"].isin(POSITIVE_OUTCOMES).astype(float) * 100.0

    pivot = temp_df.pivot_table(
        index="persona_type",
        columns="angle_used",
        values="is_positive",
        aggfunc="mean",
    ).fillna(0.0)

    # Reindex to guarantee all PERSONAS and ANGLES are present
    pivot = pivot.reindex(index=PERSONAS, columns=ANGLES, fill_value=0.0).round(2)
    return pivot


def get_comparison(
    df: pd.DataFrame, prospect_id: str, batch_a: int, batch_b: int
) -> Optional[Dict[str, Any]]:
    """Compare a prospect's email performance between two batches.
    
    Returns a dictionary with details for both batches, or None if either batch is missing.
    """
    if df.empty or "prospect_id" not in df.columns or "batch_id" not in df.columns:
        return None

    prospect_df = df[df["prospect_id"] == prospect_id]
    row_a_df = prospect_df[prospect_df["batch_id"] == batch_a]
    row_b_df = prospect_df[prospect_df["batch_id"] == batch_b]

    if row_a_df.empty or row_b_df.empty:
        return None

    row_a = row_a_df.iloc[0].to_dict()
    row_b = row_b_df.iloc[0].to_dict()

    return {
        "prospect_id": prospect_id,
        "persona_type": row_a.get("persona_type"),
        "batch_a": {
            "batch_id": batch_a,
            "angle_used": row_a.get("angle_used"),
            "message_sent": row_a.get("message_sent"),
            "simulated_response": row_a.get("simulated_response"),
            "outcome": row_a.get("outcome"),
            "timestamp": row_a.get("timestamp"),
        },
        "batch_b": {
            "batch_id": batch_b,
            "angle_used": row_b.get("angle_used"),
            "message_sent": row_b.get("message_sent"),
            "simulated_response": row_b.get("simulated_response"),
            "outcome": row_b.get("outcome"),
            "timestamp": row_b.get("timestamp"),
        },
    }
