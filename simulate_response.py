"""Simulate prospect responses with locked persona-specific bias tables."""

import random
from typing import Any, Dict, Optional, Tuple

from config import OUTCOMES, PERSONAS, RESPONSE_OUTCOMES
import reply_templates

# Locked bias tables per persona: {persona: {angle: {outcome: probability}}}
# Probabilities for interested and reply; the remainder is no_reply.
BIAS_TABLES = {
    "Founder": {
        "referenced_metric": {"interested": 0.65, "reply": 0.15},  # WINNING ANGLE (80%)
        "referenced_opinion": {"interested": 0.15, "reply": 0.10}, # (25%)
        "generic": {"interested": 0.05, "reply": 0.05},            # (10%)
    },
    "Technical Buyer": {
        "referenced_opinion": {"interested": 0.60, "reply": 0.20}, # WINNING ANGLE (80%)
        "referenced_metric": {"interested": 0.15, "reply": 0.10},  # (25%)
        "generic": {"interested": 0.05, "reply": 0.05},            # (10%)
    },
    "HR Manager": {
        "referenced_metric": {"interested": 0.60, "reply": 0.20},  # WINNING ANGLE (80%)
        "referenced_opinion": {"interested": 0.15, "reply": 0.10}, # (25%)
        "generic": {"interested": 0.05, "reply": 0.05},            # (10%)
    },
    "Student": {
        "referenced_opinion": {"interested": 0.60, "reply": 0.20}, # WINNING ANGLE (80%)
        "referenced_metric": {"interested": 0.15, "reply": 0.10},  # (25%)
        "generic": {"interested": 0.05, "reply": 0.05},            # (10%)
    },
}


def simulate(
    prospect: Dict[str, Any],
    angle: str,
    rng: Optional[random.Random] = None,
) -> Tuple[str, str]:
    """Sample an outcome based on persona bias tables, then retrieve realistic reply text.
    
    Returns:
        (outcome, reply_text) where outcome is one of OUTCOMES.
    """
    _rng = rng if rng is not None else random
    persona = prospect.get("persona_type") or prospect.get("role") or "Founder"
    if persona not in BIAS_TABLES:
        persona = "Founder"

    persona_biases = BIAS_TABLES.get(persona, {})
    angle_probs = persona_biases.get(angle, {"interested": 0.20, "reply": 0.15})

    p_interested = angle_probs.get("interested", 0.15)
    p_reply = angle_probs.get("reply", 0.15)

    roll = _rng.random()
    if roll < p_interested:
        outcome = "interested"
    elif roll < (p_interested + p_reply):
        outcome = "reply"
    else:
        outcome = "no_reply"

    reply_text = reply_templates.get_reply(persona, outcome, rng=_rng)
    return outcome, reply_text


def simulate_response(
    prospect: Dict[str, Any],
    angle: str,
    message: str = "",
    rng: Optional[random.Random] = None,
) -> Dict[str, Any]:
    """Compatibility wrapper returning dict format."""
    outcome, reply_text = simulate(prospect, angle, rng=rng)
    return {
        "outcome": outcome,
        "reply": reply_text,
        "responded": outcome in RESPONSE_OUTCOMES,
    }


if __name__ == "__main__":
    sample_prospect = {"name": "Elena Rostova", "persona_type": "Founder"}
    for angle in ["referenced_metric", "referenced_opinion", "generic"]:
        outcome, reply = simulate(sample_prospect, angle)
        print(f"Angle: {angle} -> Outcome: {outcome} | Reply: '{reply[:40]}...'")
