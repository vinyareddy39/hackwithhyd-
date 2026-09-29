"""Email draft generation engine with adaptive angle selection (Person 4)."""

import json
import os
import random
import re
import time
from typing import Any, Dict, Optional

from config import ANGLES, GROQ_MODEL, MAX_RETRIES

# Lazy Groq client
_client = None


def get_groq_client():
    """Lazily instantiate Groq client so importing without API key never crashes."""
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


def choose_angle(reflection: Optional[str] = None, rng: Optional[random.Random] = None) -> str:
    """Select personalization angle.
    
    With no reflection, choose an angle at random.
    With reflection, use the favored angle ~70% of the time, explore others ~30%.
    """
    _rng = rng if rng is not None else random

    if not reflection or not isinstance(reflection, str):
        return _rng.choice(ANGLES)

    # Parse favored angle (the angle named earliest in the reflection text)
    favored_angle = None
    earliest_pos = float("inf")
    for angle in ANGLES:
        pos = reflection.find(angle)
        if pos != -1 and pos < earliest_pos:
            earliest_pos = pos
            favored_angle = angle

    if not favored_angle:
        return _rng.choice(ANGLES)

    # 70% favored angle, 30% exploration across other angles
    if _rng.random() < 0.70:
        return favored_angle
    else:
        other_angles = [a for a in ANGLES if a != favored_angle]
        return _rng.choice(other_angles)


def build_prompt(prospect: Dict[str, Any], angle: str, reflection: Optional[str] = None) -> str:
    """Construct LLM prompt with strict formatting and angle-specific guidance."""
    name = prospect.get("name", "Prospect")
    company = prospect.get("company", "Company")
    bio = prospect.get("bio", "")
    persona_type = prospect.get("persona_type") or prospect.get("role", "Professional")
    content_summary = prospect.get("content_summary", "")

    if angle == "referenced_metric":
        angle_instruction = (
            f"Open by citing a specific number or achievement from their recent content below:\n"
            f"Content Summary: {content_summary}"
        )
    elif angle == "referenced_opinion":
        angle_instruction = (
            f"Open by engaging a specific view or opinion the prospect expressed below:\n"
            f"Content Summary: {content_summary}"
        )
    else:  # generic
        angle_instruction = (
            "Provide a friendly, relevant introduction. Do not reference their specific content summary "
            "or background metrics."
        )

    reflection_note = (
        f"Insight from past batches: {reflection}" if reflection else "Insight from past batches: None (initial exploration)"
    )

    prompt = f"""You are writing a concise cold email on behalf of Alex.

PROSPECT DETAILS:
- Name: {name}
- Company: {company}
- Persona Type: {persona_type}
- Bio: {bio}

PERSONALIZATION ANGLE: {angle}
INSTRUCTION FOR THIS ANGLE:
{angle_instruction}

PAST PERFORMANCE CONTEXT:
{reflection_note}

STRICT WRITING RULES:
1. Length: Exactly 3 to 5 sentences, strictly under 110 words.
2. Tone: Natural, conversational, respectful of their time.
3. No emojis whatsoever.
4. Do NOT use cliché phrases like 'I hope this finds you well' or 'Hope you are doing well'.
5. Must specifically reference the prospect's content summary when using referenced_metric or referenced_opinion.
6. Include exactly one low-friction, soft call to action.
7. Sign off with 'Alex'.
8. Output format: Return ONLY a valid JSON object with keys 'subject' and 'body'. No markdown formatting, no explanations.

Example JSON output format:
{{"subject": "Quick question regarding {company}", "body": "Hi {name.split()[0]}, ... Best,\\nAlex"}}
"""
    return prompt


def parse_json(text: str) -> Dict[str, str]:
    """Parse JSON email payload, stripping markdown fences or extracting {...} via regex."""
    if not text or not isinstance(text, str):
        raise ValueError("Invalid LLM response.")

    cleaned = text.strip()

    if cleaned.startswith("```"):
        lines = cleaned.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        cleaned = "\n".join(lines).strip()

    try:
        data = json.loads(cleaned)
        if isinstance(data, dict) and "subject" in data and "body" in data:
            return {"subject": str(data["subject"]).strip(), "body": str(data["body"]).strip()}
    except Exception:
        pass

    match = re.search(r"\{[\s\S]*\}", cleaned)
    if match:
        try:
            data = json.loads(match.group(0))
            if isinstance(data, dict) and "subject" in data and "body" in data:
                return {"subject": str(data["subject"]).strip(), "body": str(data["body"]).strip()}
        except Exception:
            pass

    raise ValueError("Could not parse valid JSON with subject and body.")


def get_fallback_email(prospect: Dict[str, Any], angle: str) -> Dict[str, str]:
    """Deterministic fallback email complying with all rules when LLM calls fail."""
    name = prospect.get("name", "there").split()[0]
    company = prospect.get("company", "your team")

    if angle == "referenced_metric":
        subject = f"Milestones at {company}"
        body = (
            f"Hi {name}, I saw your recent performance metrics and was impressed by the growth numbers your team has achieved. "
            f"We help teams personalize outreach workflows and sustain high customer acquisition velocity. "
            f"Would you be open to a brief 10-minute introductory conversation next Tuesday? "
            f"Best regards, Alex"
        )
    elif angle == "referenced_opinion":
        subject = f"Your perspective on scaling {company}"
        body = (
            f"Hi {name}, I recently read your perspective on team focus and strategic execution, and found your insights very compelling. "
            f"We help teams personalize outreach workflows and address scaling challenges smoothly. "
            f"Would you be open to exchanging ideas over a brief call later this week? "
            f"Best regards, Alex"
        )
    else:  # generic
        subject = f"Streamlining outreach for {company}"
        body = (
            f"Hi {name}, reaching out because our automated platform helps teams personalize outreach and boost response rates. "
            f"Organizations using our system typically see significant efficiency gains within the first two weeks of adoption. "
            f"Would you be open to reviewing a quick 5-minute case study? "
            f"Best regards, Alex"
        )

    return {
        "subject": subject,
        "body": body,
        "angle_used": angle,
    }


def call_llm(prompt: str) -> str:
    """Call Groq API using GROQ_MODEL."""
    client = get_groq_client()
    if client is None:
        raise ValueError("GROQ_API_KEY environment variable is not set.")

    completion = client.chat.completions.create(
        model=GROQ_MODEL,
        messages=[
            {
                "role": "system",
                "content": "You are an expert cold email copywriter. Output strictly raw JSON with keys 'subject' and 'body'.",
            },
            {"role": "user", "content": prompt},
        ],
        temperature=0.7,
    )
    return completion.choices[0].message.content


def draft_email(
    prospect: Dict[str, Any],
    reflection: Optional[str] = None,
    rng: Optional[random.Random] = None,
) -> Dict[str, str]:
    """Draft a cold email for a prospect, choosing angle via code and retrying on invalid length.
    
    Never raises an exception; returns fallback on error.
    """
    angle = choose_angle(reflection, rng=rng)

    # If offline / no API key and call_llm is not mocked by a test, return fallback immediately
    if get_groq_client() is None and getattr(call_llm, "__module__", "") == __name__:
        return get_fallback_email(prospect, angle)

    prompt = build_prompt(prospect, angle, reflection)

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            raw_response = call_llm(prompt)
            parsed = parse_json(raw_response)
            subject = parsed.get("subject", "").strip()
            body = parsed.get("body", "").strip()
            word_count = len(body.split())
            if 20 <= word_count <= 130 and subject and body:
                return {
                    "subject": subject,
                    "body": body,
                    "angle_used": angle,
                }
            else:
                err_msg = f"Invalid email length ({word_count} words)" if not (20 <= word_count <= 130) else "Missing subject or body"
                print(f"[draft_email] attempt {attempt} failed: {err_msg}")
        except Exception as e:
            print(f"[draft_email] attempt {attempt} failed: {e}")

        if attempt < MAX_RETRIES:
            time.sleep(0.01 * attempt)

    # Fallback email respecting the chosen angle
    return get_fallback_email(prospect, angle)


if __name__ == "__main__":
    sample = {
        "name": "Elena Rostova",
        "company": "Vanguard AI",
        "persona_type": "Founder",
        "bio": "Founder & CEO at Vanguard AI.",
        "content_summary": "Scaled ARR from $1.2M to $4.5M in 14 months with 135% net retention.",
    }
    print("Drafting without reflection:")
    print(draft_email(sample, reflection=None))
    print("\nDrafting with reflection favoring referenced_metric:")
    print(draft_email(sample, reflection="For Founder, referenced_metric has the best response rate (60%)"))
