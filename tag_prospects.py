"""Tag prospects with persona_type and lead_score using Groq with deterministic fallback."""

import json
import os
from pathlib import Path
import re
from typing import Any, Dict, List, Optional, Tuple

from config import GROQ_MODEL, MAX_RETRIES, PERSONAS, PROSPECTS_PATH

# Lazy client reference
_client = None


def get_groq_client():
    """Lazily get Groq client."""
    global _client
    if _client is None:
        api_key = os.getenv("GROQ_API_KEY", "")
        if not api_key:
            return None
        try:
            from groq import Groq
            _client = Groq(api_key=api_key)
        except Exception:
            return None
    return _client


def fallback_tag_prospect(prospect: Dict[str, Any]) -> Tuple[str, int]:
    """Deterministic keyword-based tagging when LLM is unavailable or retries fail."""
    text = f"{prospect.get('name', '')} {prospect.get('company', '')} {prospect.get('bio', '')} {prospect.get('content_summary', '')}".lower()

    if any(k in text for k in ["student", "undergraduate", "collegiate", "hackathon", "robotics lab", "open source club"]):
        persona = "Student"
        score = 78
    elif any(k in text for k in ["founder", "ceo", "co-founder", "solo founder"]):
        persona = "Founder"
        score = 92
    elif any(k in text for k in ["chief people", "talent", "onboarding", "recruiter", "people & culture", "people officer", "wellness"]):
        persona = "HR Manager"
        score = 86
    elif any(k in text for k in ["infrastructure", "platform engineering", "ciso", "kubernetes", "latency", "security", "vp of"]):
        persona = "Technical Buyer"
        score = 88
    else:
        persona = "Founder"
        score = 80

    return persona, score


def tag_single_prospect(prospect: Dict[str, Any]) -> Tuple[str, int]:
    """Tag a single prospect with persona_type and lead_score (1-100)."""
    client = get_groq_client()

    if client is None:
        return fallback_tag_prospect(prospect)

    content_summary = prospect.get("content_summary", "")
    bio = prospect.get("bio", "")
    company = prospect.get("company", "")
    name = prospect.get("name", "")

    prompt = f"""Evaluate this sales prospect and assign exactly one persona_type from:
{PERSONAS}

And calculate a lead_score integer between 1 and 100 based on fit, seniority, and intent.

PROSPECT:
Name: {name}
Company: {company}
Bio: {bio}
Content Summary: {content_summary}

Respond ONLY with valid JSON:
{{"persona_type": "<one of {PERSONAS}>", "lead_score": <int 1-100>}}
"""

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            completion = client.chat.completions.create(
                model=GROQ_MODEL,
                messages=[
                    {"role": "system", "content": "You are a lead enrichment AI. Output strictly valid raw JSON."},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.1,
            )
            raw = completion.choices[0].message.content.strip()
            # Clean markdown code fences if present
            if raw.startswith("```"):
                lines = raw.splitlines()
                if lines[0].startswith("```"):
                    lines = lines[1:]
                if lines and lines[-1].startswith("```"):
                    lines = lines[:-1]
                raw = "\n".join(lines).strip()

            match = re.search(r"\{[\s\S]*\}", raw)
            if match:
                data = json.loads(match.group(0))
                p_type = data.get("persona_type")
                score = int(data.get("lead_score", 80))
                if p_type in PERSONAS and 1 <= score <= 100:
                    return p_type, score
        except Exception as e:
            print(f"[tag_prospects] attempt {attempt} failed: {e}")

    return fallback_tag_prospect(prospect)


def tag_all_prospects(path: Optional[str] = None, force: bool = False) -> List[Dict[str, Any]]:
    """Enrich all prospects in the prospects JSON file idempotently."""
    target_path = Path(path) if path else Path(PROSPECTS_PATH)
    if not target_path.is_file():
        # Check fallback
        fallback = Path("prospects.json")
        if fallback.is_file():
            target_path = fallback
        else:
            return []

    with open(target_path, "r", encoding="utf-8") as f:
        prospects = json.load(f)

    updated = False
    for p in prospects:
        # Idempotent: skip already tagged prospects unless forced
        if not force and p.get("persona_type") in PERSONAS and p.get("lead_score") is not None:
            continue

        persona, score = tag_single_prospect(p)
        p["persona_type"] = persona
        p["lead_score"] = score
        updated = True

    if updated:
        with open(target_path, "w", encoding="utf-8") as f:
            json.dump(prospects, f, indent=2)

    return prospects


if __name__ == "__main__":
    enriched = tag_all_prospects()
    print(f"Enriched {len(enriched)} prospects in {PROSPECTS_PATH}")
    for p in enriched[:4]:
        print(f"  {p['id']}: {p['name']} -> {p['persona_type']} (score: {p['lead_score']})")
