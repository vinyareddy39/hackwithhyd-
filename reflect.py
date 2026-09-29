"""Hindsight memory reflection engine analyzing past batch performance."""

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from config import ANGLES, MEMORY_PATH, PERSONAS, RESPONSE_OUTCOMES


def load_memory(path: Optional[str] = None) -> List[Dict[str, Any]]:
    """Load memory log records from JSON file."""
    target = Path(path) if path else Path(MEMORY_PATH)
    if not target.is_file():
        # Fallback to root memory_log.json if data/ not initialized
        alt = Path("memory_log.json")
        if alt.is_file():
            target = alt
        else:
            return []

    try:
        with open(target, "r", encoding="utf-8") as f:
            content = f.read().strip()
            if not content:
                return []
            data = json.loads(content)
            if isinstance(data, list):
                return data
    except Exception:
        return []
    return []


def reflect(persona: str, path: Optional[Union[str, List[Dict[str, Any]]]] = None) -> str:
    """Analyze memory records for a persona and generate an actionable reflection string.
    
    Returns text like:
    'For Founder, referenced_metric has the best response rate (60%)'
    Or empty string if insufficient history exists.
    """
    if isinstance(path, list):
        records = path
    else:
        records = load_memory(path)

    if not records:
        return ""

    persona_records = [
        r for r in records
        if (r.get("persona_type") or "").lower() == persona.lower()
    ]

    if not persona_records:
        return ""

    stats: Dict[str, Dict[str, int]] = {a: {"total": 0, "positive": 0} for a in ANGLES}

    for r in persona_records:
        angle = r.get("angle_used") or r.get("angle")
        outcome = r.get("outcome")
        if angle in stats:
            stats[angle]["total"] += 1
            if outcome in RESPONSE_OUTCOMES:
                stats[angle]["positive"] += 1

    # Filter angles that have at least one trial
    rates: Dict[str, float] = {}
    for a in ANGLES:
        tot = stats[a]["total"]
        if tot > 0:
            rates[a] = (stats[a]["positive"] / tot) * 100.0

    if not rates:
        return ""

    # Sort using Laplace-smoothed ranking (pos + 1)/(tot + 3) to prevent 1/1 outlier swings
    sorted_angles = sorted(
        rates.keys(),
        key=lambda a: (stats[a]["positive"] + 1.0) / (stats[a]["total"] + 3.0),
        reverse=True,
    )
    best_angle = sorted_angles[0]
    best_rate = rates[best_angle]

    other_summaries = [f"{a} ({rates[a]:.0f}%)" for a in sorted_angles[1:]]
    if other_summaries:
        other_text = " over " + " and ".join(other_summaries)
    else:
        other_text = ""

    return f"For {persona}, {best_angle} has the best response rate ({best_rate:.0f}%){other_text}."


def reflect_all(path: Optional[str] = None) -> Dict[str, str]:
    """Return reflections for all registered personas."""
    return {persona: reflect(persona, path) for persona in PERSONAS}


if __name__ == "__main__":
    for p in PERSONAS:
        r = reflect(p)
        print(f"[{p}] Reflection: '{r}'")
