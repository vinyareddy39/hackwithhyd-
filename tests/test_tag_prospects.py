"""Tests for prospect tagging and enrichment."""

import copy
import json
from pathlib import Path
from config import PERSONAS
import tag_prospects


def test_fallback_tagging_distribution():
    """Verify fallback tagging classifies prospects with 3 of each persona."""
    with open("data/prospects.json", "r", encoding="utf-8") as f:
        raw_prospects = json.load(f)

    tagged_prospects = []
    persona_counts = {p: 0 for p in PERSONAS}

    for p in raw_prospects:
        p_copy = copy.deepcopy(p)
        persona, score = tag_prospects.fallback_tag_prospect(p_copy)
        assert persona in PERSONAS
        assert 1 <= score <= 100
        persona_counts[persona] += 1
        p_copy["persona_type"] = persona
        p_copy["lead_score"] = score
        tagged_prospects.append(p_copy)

    # Must have 3 per persona
    for persona in PERSONAS:
        assert persona_counts[persona] == 3, f"Expected 3 prospects for {persona}, got {persona_counts[persona]}"


def test_tag_all_prospects_idempotency(tmp_path):
    """Calling tag_all_prospects() must enrich blank prospects and be idempotent."""
    with open("data/prospects.json", "r", encoding="utf-8") as f:
        prospects = json.load(f)

    # Ensure blank
    for p in prospects:
        p["persona_type"] = ""
        p["lead_score"] = None

    test_file = tmp_path / "prospects.json"
    test_file.write_text(json.dumps(prospects, indent=2), encoding="utf-8")

    # First pass: enriches all
    result1 = tag_prospects.tag_all_prospects(str(test_file))
    assert len(result1) == 12
    assert all(p["persona_type"] in PERSONAS for p in result1)
    assert all(1 <= p["lead_score"] <= 100 for p in result1)

    # Manually tweak one lead score to verify idempotency doesn't overwrite it
    with open(test_file, "r", encoding="utf-8") as f:
        saved = json.load(f)
    saved[0]["lead_score"] = 99
    with open(test_file, "w", encoding="utf-8") as f:
        json.dump(saved, f, indent=2)

    # Second pass: should not overwrite modified score because already tagged
    result2 = tag_prospects.tag_all_prospects(str(test_file), force=False)
    assert result2[0]["lead_score"] == 99

    # Third pass with force=True should re-tag
    result3 = tag_prospects.tag_all_prospects(str(test_file), force=True)
    assert result3[0]["lead_score"] != 99
