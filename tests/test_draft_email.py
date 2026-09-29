"""Tests for draft_email.py (Person 4).

Ensures all requirements are met with no network access and no API key.
"""

import json
import random
import time
import pytest

from config import ANGLES
import draft_email
from draft_email import (
    build_prompt,
    choose_angle,
    draft_email as run_draft_email,
    get_fallback_email,
    parse_json,
)


@pytest.fixture
def sample_prospect():
    return {
        "id": "p01",
        "name": "Elena Rostova",
        "company": "Vanguard AI",
        "content_summary": "Scaled ARR from $1.2M to $4.5M in 14 months with 135% net revenue retention. Believes sales automation should prioritize authentic founder storytelling rather than aggressive high-volume cadence scripts.",
        "bio": "Founder & CEO at Vanguard AI.",
        "persona_type": "Founder",
        "lead_score": 92,
    }


def test_choose_angle_empty_reflection():
    """choose_angle('') always returns a valid angle over 200 runs."""
    for _ in range(200):
        angle = choose_angle("")
        assert angle in ANGLES, f"Unexpected angle returned: {angle}"


def test_choose_angle_favors_first_named():
    """choose_angle with favored angle picks it >= 70% of 500 seeded runs."""
    rng = random.Random(42)
    favored = "referenced_metric"
    reflection = f"past data favors {favored} (60% positive) over referenced_opinion"
    
    count = 0
    total = 500
    for _ in range(total):
        chosen = choose_angle(reflection, rng=rng)
        assert chosen in ANGLES
        if chosen == favored:
            count += 1
            
    ratio = count / total
    assert ratio >= 0.70, f"Expected >= 70% selection of {favored}, got {ratio:.2%}"


def test_draft_email_keys_and_valid_angle(monkeypatch, sample_prospect):
    """draft_email returns dictionary with keys 'subject', 'body', 'angle_used' in ANGLES."""
    monkeypatch.setattr(time, "sleep", lambda s: None)
    
    mock_payload = {
        "subject": "Quick inquiry regarding Vanguard AI",
        "body": "Hi Elena, noticed your ARR milestone and wanted to reach out. Our platform helps scale outreach smoothly without adding headcount. Would you be open to a 10-minute chat next Tuesday? Best, Alex",
    }
    monkeypatch.setattr(draft_email, "call_llm", lambda prompt: json.dumps(mock_payload))

    result = run_draft_email(sample_prospect, reflection="")
    assert "subject" in result
    assert "body" in result
    assert "angle_used" in result
    assert result["angle_used"] in ANGLES
    assert result["subject"] == mock_payload["subject"]
    assert result["body"] == mock_payload["body"]


def test_referenced_metric_prompt_contains_summary(sample_prospect):
    """referenced_metric prompt contains content_summary; generic prompt lacks the metric instruction."""
    metric_prompt = build_prompt(sample_prospect, "referenced_metric", "")
    assert sample_prospect["content_summary"] in metric_prompt
    assert "citing a specific number or achievement" in metric_prompt

    generic_prompt = build_prompt(sample_prospect, "generic", "")
    assert "citing a specific number or achievement" not in generic_prompt
    assert "Do not reference" in generic_prompt


def test_reflection_string_appears_in_prompt(sample_prospect):
    """The exact reflection string appears in the prompt."""
    custom_reflection = "For Founder prospects, past data favors referenced_metric (60% positive)."
    prompt = build_prompt(sample_prospect, "referenced_metric", custom_reflection)
    assert custom_reflection in prompt
    assert "Insight from past batches" in prompt


def test_parse_json_markdown_fences():
    """JSON wrapped in ```json code fences parses correctly."""
    fenced = """```json
{
  "subject": "Growth metrics at Vanguard AI",
  "body": "Hi Elena, saw your ARR growth and wanted to connect. Alex"
}
```"""
    parsed = parse_json(fenced)
    assert parsed["subject"] == "Growth metrics at Vanguard AI"
    assert "Hi Elena" in parsed["body"]


def test_parse_json_regex_fallback():
    """JSON surrounded by conversational text is extracted via regex."""
    surrounded = """Here is the draft email you requested:
{"subject": "Partnership idea", "body": "Hi Elena, would love to connect. Alex"}
Let me know if you need anything else!"""
    parsed = parse_json(surrounded)
    assert parsed["subject"] == "Partnership idea"


def test_garbage_3_times_returns_fallback_no_exception(monkeypatch, sample_prospect):
    """Garbage response 3 times results in deterministic fallback email without exception."""
    monkeypatch.setattr(time, "sleep", lambda s: None)
    monkeypatch.setattr(draft_email, "call_llm", lambda prompt: "I am unable to generate that response.")

    result = run_draft_email(sample_prospect)
    assert isinstance(result, dict)
    assert "subject" in result and "body" in result and "angle_used" in result
    assert result["angle_used"] in ANGLES
    # Verify fallback rules
    word_count = len(result["body"].split())
    assert 20 <= word_count <= 130
    assert "Alex" in result["body"]


def test_api_exception_returns_fallback(monkeypatch, sample_prospect):
    """API network or auth exception results in deterministic fallback without crash."""
    monkeypatch.setattr(time, "sleep", lambda s: None)

    def mock_fail(prompt):
        raise RuntimeError("Groq rate limit or connection timeout")

    monkeypatch.setattr(draft_email, "call_llm", mock_fail)

    result = run_draft_email(sample_prospect)
    assert isinstance(result, dict)
    assert "subject" in result and "body" in result
    assert result["angle_used"] in ANGLES


def test_300_word_body_rejected_then_accepted(monkeypatch, sample_prospect):
    """A 300-word body is rejected on attempt 1, then retried and accepted on attempt 2."""
    monkeypatch.setattr(time, "sleep", lambda s: None)
    attempts = []

    long_body = "word " * 300
    valid_body = (
        "Hi Elena, I noticed your impressive ARR growth. "
        "We help high-growth SaaS founders automate pipeline tasks without losing personalization. "
        "Would you be open to a 10-minute chat next week? Best, Alex"
    )

    def mock_llm(prompt):
        attempts.append(prompt)
        if len(attempts) == 1:
            return json.dumps({"subject": "Too long", "body": long_body})
        return json.dumps({"subject": "Optimal length", "body": valid_body})

    monkeypatch.setattr(draft_email, "call_llm", mock_llm)

    result = run_draft_email(sample_prospect)
    assert len(attempts) == 2, f"Expected 2 attempts, but got {len(attempts)}"
    assert result["subject"] == "Optimal length"
    assert result["body"] == valid_body
