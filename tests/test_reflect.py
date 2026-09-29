"""Tests for reflection engine analyzing past batch performance."""

import json
from config import PERSONAS
import reflect


def test_reflect_empty_memory(tmp_path):
    """Reflecting on empty or missing memory log returns empty string."""
    empty_log = tmp_path / "empty_memory.json"
    empty_log.write_text("[]", encoding="utf-8")

    for persona in PERSONAS:
        assert reflect.reflect(persona, path=str(empty_log)) == ""


def test_reflect_with_history(tmp_path):
    """Reflecting on persona records identifies favored angle and formats string."""
    memory_file = tmp_path / "memory.json"
    records = [
        # Founder: referenced_metric is 2/2 (100%), generic is 0/2 (0%)
        {"persona_type": "Founder", "angle_used": "referenced_metric", "outcome": "interested"},
        {"persona_type": "Founder", "angle_used": "referenced_metric", "outcome": "reply"},
        {"persona_type": "Founder", "angle_used": "generic", "outcome": "no_reply"},
        {"persona_type": "Founder", "angle_used": "generic", "outcome": "no_reply"},
        # Student: referenced_opinion is 2/2 (100%)
        {"persona_type": "Student", "angle_used": "referenced_opinion", "outcome": "interested"},
        {"persona_type": "Student", "angle_used": "referenced_opinion", "outcome": "reply"},
    ]
    memory_file.write_text(json.dumps(records), encoding="utf-8")

    founder_ref = reflect.reflect("Founder", path=str(memory_file))
    assert "referenced_metric" in founder_ref
    assert "100%" in founder_ref

    student_ref = reflect.reflect("Student", path=str(memory_file))
    assert "referenced_opinion" in student_ref
    assert "100%" in student_ref

    reflections = reflect.reflect_all(path=str(memory_file))
    assert isinstance(reflections, dict)
    assert len(reflections) == len(PERSONAS)
    assert reflections["Founder"] == founder_ref
    assert reflections["Student"] == student_ref
    assert reflections["Technical Buyer"] == ""
