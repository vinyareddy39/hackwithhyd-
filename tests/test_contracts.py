"""Tests for locked configuration contracts and data schemas."""

import json
from pathlib import Path
import config


def test_locked_config_constants():
    """Verify Section 3 locked contracts in config.py."""
    assert config.PERSONAS == ["Founder", "Technical Buyer", "HR Manager", "Student"]
    assert config.ANGLES == ["referenced_metric", "referenced_opinion", "generic"]
    assert config.OUTCOMES == ["interested", "reply", "no_reply"]
    assert config.RESPONSE_OUTCOMES == ["interested", "reply"]
    assert config.MEMORY_PATH == "data/memory_log.json"
    assert config.PROSPECTS_PATH == "data/prospects.json"
    assert config.MAX_RETRIES == 3
    assert hasattr(config, "GROQ_MODEL")


def test_prospects_schema_and_counts():
    """Verify prospects.json and data/prospects.json exist and match schema requirements."""
    for path_str in [config.PROSPECTS_PATH, "prospects.json"]:
        path = Path(path_str)
        assert path.is_file(), f"Missing prospects file at {path_str}"
        with open(path, "r", encoding="utf-8") as f:
            prospects = json.load(f)

        assert isinstance(prospects, list)
        assert len(prospects) == 12, "Must contain exactly 12 prospects"

        required_keys = {"id", "name", "company", "content_summary", "persona_type", "lead_score", "bio"}
        for p in prospects:
            assert required_keys.issubset(p.keys()), f"Missing keys in prospect {p.get('id')}"
            assert len(p["content_summary"].strip()) > 10, "content_summary must be realistic"
            assert len(p["bio"].strip()) > 10, "bio must be realistic"


def test_reply_templates_contract():
    """Verify data/reply_templates.json has 4 templates for all 4 personas x 3 outcomes."""
    templates_path = Path("data/reply_templates.json")
    assert templates_path.is_file(), "data/reply_templates.json missing"
    with open(templates_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    for persona in config.PERSONAS:
        assert persona in data, f"Missing persona '{persona}' in reply templates"
        for outcome in config.OUTCOMES:
            assert outcome in data[persona], f"Missing outcome '{outcome}' for persona '{persona}'"
            templates = data[persona][outcome]
            assert isinstance(templates, list)
            if outcome == "no_reply":
                assert len(templates) == 4
                assert all(t in ("", "[no reply]") for t in templates)
            else:
                assert len(templates) == 4
                assert all(len(t.strip()) > 5 for t in templates)
