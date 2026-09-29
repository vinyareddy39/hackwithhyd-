"""Pure function analytical metrics for Hindsight Sales Agent."""

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

try:
    from config import ANGLES
except ImportError:
    ANGLES = ["referenced_metric", "referenced_opinion", "generic"]


def load_log_data(path: Optional[Union[str, Path]] = None) -> List[Dict[str, Any]]:
    """Load log records strictly from data/log.json (or specified path).
    
    Returns an empty list on missing, empty, or corrupt files.
    """
    target_path = Path(path) if path else Path("data/log.json")
    if not target_path.is_file():
        return []

    try:
        with open(target_path, "r", encoding="utf-8") as f:
            content = f.read().strip()
            if not content:
                return []
            data = json.loads(content)
            if isinstance(data, list):
                return data
    except Exception:
        return []

    return []


def _normalize_row(row: Dict[str, Any]) -> Tuple[int, str, bool]:
    """Extract (batch, angle, responded) from row supporting multiple schema versions."""
    batch = int(row.get("batch", row.get("batch_id", 1)))
    angle = str(row.get("angle", row.get("angle_used", "generic")))
    
    if "responded" in row and isinstance(row["responded"], bool):
        responded = row["responded"]
    elif "outcome" in row:
        responded = row["outcome"] in ("interested", "reply")
    else:
        responded = False

    return batch, angle, responded


def rate_by_batch(log_data: Optional[List[Dict[str, Any]]] = None) -> Dict[int, float]:
    """Calculate the response rate percentage per batch.
    
    Returns an empty dict if log_data is empty.
    """
    if log_data is None:
        log_data = load_log_data()
    if not log_data:
        return {}

    batch_totals: Dict[int, int] = {}
    batch_positive: Dict[int, int] = {}

    for row in log_data:
        batch, _, responded = _normalize_row(row)
        batch_totals[batch] = batch_totals.get(batch, 0) + 1
        if responded:
            batch_positive[batch] = batch_positive.get(batch, 0) + 1

    rates: Dict[int, float] = {}
    for b in sorted(batch_totals.keys()):
        total = batch_totals[b]
        pos = batch_positive.get(b, 0)
        rates[b] = round((pos / total) * 100.0, 1)

    return rates


def first_last_rate(log_data: Optional[List[Dict[str, Any]]] = None) -> Tuple[float, float]:
    """Return (first_batch_rate, last_batch_rate) or (0.0, 0.0) if empty."""
    rates = rate_by_batch(log_data)
    if not rates:
        return 0.0, 0.0
    sorted_batches = sorted(rates.keys())
    return rates[sorted_batches[0]], rates[sorted_batches[-1]]


def delta_pts(log_data: Optional[List[Dict[str, Any]]] = None) -> float:
    """Return net improvement points (last_rate - first_rate) or 0.0 if empty."""
    first, last = first_last_rate(log_data)
    return round(last - first, 1)


def angle_mix_by_batch(log_data: Optional[List[Dict[str, Any]]] = None) -> Dict[int, Dict[str, float]]:
    """Compute angle distribution percentage per batch, rows summing to 100.0."""
    if log_data is None:
        log_data = load_log_data()
    if not log_data:
        return {}

    batch_counts: Dict[int, Dict[str, int]] = {}
    batch_totals: Dict[int, int] = {}

    for row in log_data:
        batch, angle, _ = _normalize_row(row)
        if batch not in batch_counts:
            batch_counts[batch] = {a: 0 for a in ANGLES}
            batch_totals[batch] = 0
        batch_counts[batch][angle] = batch_counts[batch].get(angle, 0) + 1
        batch_totals[batch] += 1

    mix: Dict[int, Dict[str, float]] = {}
    for b in sorted(batch_counts.keys()):
        total = batch_totals[b]
        mix[b] = {}
        for a in ANGLES:
            count = batch_counts[b].get(a, 0)
            mix[b][a] = round((count / total) * 100.0, 1) if total > 0 else 0.0

    return mix


def most_improved_angle(log_data: Optional[List[Dict[str, Any]]] = None) -> Optional[str]:
    """Identify the angle with the greatest positive rate increase between first and last batch."""
    if log_data is None:
        log_data = load_log_data()
    if not log_data:
        return None

    stats: Dict[int, Dict[str, Dict[str, int]]] = {}
    for row in log_data:
        batch, angle, responded = _normalize_row(row)
        if batch not in stats:
            stats[batch] = {a: {"total": 0, "pos": 0} for a in ANGLES}
        if angle not in stats[batch]:
            stats[batch][angle] = {"total": 0, "pos": 0}
        stats[batch][angle]["total"] += 1
        if responded:
            stats[batch][angle]["pos"] += 1

    sorted_batches = sorted(stats.keys())
    if len(sorted_batches) < 2:
        return None

    first_b = sorted_batches[0]
    last_b = sorted_batches[-1]

    best_angle: Optional[str] = None
    max_gain = -float("inf")

    for angle in ANGLES:
        b1_tot = stats[first_b].get(angle, {}).get("total", 0)
        b1_pos = stats[first_b].get(angle, {}).get("pos", 0)
        b1_rate = (b1_pos / b1_tot * 100.0) if b1_tot > 0 else 0.0

        b3_tot = stats[last_b].get(angle, {}).get("total", 0)
        b3_pos = stats[last_b].get(angle, {}).get("pos", 0)
        b3_rate = (b3_pos / b3_tot * 100.0) if b3_tot > 0 else 0.0

        gain = b3_rate - b1_rate
        if gain > max_gain:
            max_gain = gain
            best_angle = angle

    return best_angle


def get_reflection_for_prospect(
    prospect: Dict[str, Any],
    log_data: Optional[List[Dict[str, Any]]] = None,
) -> str:
    """Derive reflection insight for a prospect based on historical batch performance."""
    if log_data is None:
        log_data = load_log_data()
    if not log_data:
        return ""

    persona = prospect.get("persona_type") or prospect.get("role") or "Founder"

    # Compute success rate per angle for this persona
    angle_totals: Dict[str, int] = {a: 0 for a in ANGLES}
    angle_positive: Dict[str, int] = {a: 0 for a in ANGLES}

    for row in log_data:
        row_persona = row.get("persona_type") or row.get("role") or ""
        if row_persona.lower() == persona.lower():
            _, angle, responded = _normalize_row(row)
            if angle in angle_totals:
                angle_totals[angle] += 1
                if responded:
                    angle_positive[angle] += 1

    rates = {}
    for a in ANGLES:
        tot = angle_totals[a]
        if tot > 0:
            rates[a] = (angle_positive[a] / tot) * 100.0

    if rates:
        sorted_angles = sorted(rates.keys(), key=lambda a: rates[a], reverse=True)
        best = sorted_angles[0]
        best_pct = rates[best]
        return f"For {persona} prospects, past data favors {best} ({best_pct:.0f}% positive) over other angles."

    # Fallback to overall most improved or best angle
    improved = most_improved_angle(log_data)
    if improved:
        return f"past data favors {improved}"

    return ""


def get_metrics_summary(log_data: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
    """Return all dashboard metrics in a clean dictionary structure."""
    if log_data is None:
        log_data = load_log_data()

    if not log_data:
        return {
            "rate_by_batch": {},
            "angle_mix_by_batch": {},
            "first_rate": 0.0,
            "last_rate": 0.0,
            "delta_pts": 0.0,
            "most_improved_angle": None,
        }

    first, last = first_last_rate(log_data)
    return {
        "rate_by_batch": rate_by_batch(log_data),
        "angle_mix_by_batch": angle_mix_by_batch(log_data),
        "first_rate": first,
        "last_rate": last,
        "delta_pts": delta_pts(log_data),
        "most_improved_angle": most_improved_angle(log_data),
    }
