"""Reply templates loader and retrieval helper."""

import json
from pathlib import Path
import random
from typing import Dict, List, Optional

TEMPLATES_PATH = Path(__file__).resolve().parent / "data" / "reply_templates.json"

_TEMPLATES: Optional[Dict[str, Dict[str, List[str]]]] = None


def load_templates() -> Dict[str, Dict[str, List[str]]]:
    """Load reply templates from JSON file."""
    global _TEMPLATES
    if _TEMPLATES is None:
        if TEMPLATES_PATH.is_file():
            with open(TEMPLATES_PATH, "r", encoding="utf-8") as f:
                _TEMPLATES = json.load(f)
        else:
            _TEMPLATES = {}
    return _TEMPLATES


def get_reply(persona: str, outcome: str, rng: Optional[random.Random] = None) -> str:
    """Retrieve a random realistic reply template for a given persona and outcome.
    
    If outcome is 'no_reply', returns an empty string.
    """
    if outcome == "no_reply":
        return ""

    templates = load_templates()
    persona_templates = templates.get(persona, {})
    outcome_options = persona_templates.get(outcome, [])

    if not outcome_options:
        # Fallback if persona not mapped
        fallback_map = {
            "interested": "Hi Alex, thanks for reaching out. Let's schedule 15 minutes to discuss.",
            "reply": "Thanks Alex, not a priority for us right now, but feel free to check back later.",
            "no_reply": "",
        }
        return fallback_map.get(outcome, "")

    _rng = rng if rng is not None else random
    return _rng.choice(outcome_options)
