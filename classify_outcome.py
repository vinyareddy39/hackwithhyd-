"""Classify prospect replies into outcomes (interested, reply, no_reply)."""

import json
import os
import re
from typing import Optional

from config import GROQ_MODEL, MAX_RETRIES, OUTCOMES

# Lazy client reference
_client = None


def get_groq_client():
    """Lazily instantiate Groq client."""
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


def fallback_classify_outcome(reply_text: str) -> str:
    """Deterministic keyword-based outcome classification."""
    if not reply_text or not reply_text.strip() or reply_text.strip() == "[no reply]":
        return "no_reply"

    text = reply_text.lower()

    # Rejection and negative intent keywords -> reply
    rejection_indicators = [
        "out of office", "automatic reply", "auto-reply", "leave returning",
        "remove me", "unsubscribe", "not interested", "not a fit",
        "freeze", "not taking vendor", "not relevant"
    ]
    if any(ind in text for ind in rejection_indicators):
        return "reply"

    # Positive interest indicators -> interested
    interest_indicators = [
        "thursday", "tuesday", "wednesday", "friday", "calendar", "sync",
        "call", "demo", "pricing", "discount", "deck", "loom",
        "timeline", "trial", "schedule", "connect", "drop a link",
        "loop in", "learn more", "discuss", "walkthrough", "15-minute",
        "15 minutes", "case study", "send over", "looks awesome", "awesome",
        "love to", "chat", "partnership", "how does", "how steep"
    ]
    if any(ind in text for ind in interest_indicators):
        return "interested"

    return "reply"


def classify_outcome(reply_text: str, message_sent: str = "") -> str:
    """Classify prospect reply into one of OUTCOMES: 'interested', 'reply', or 'no_reply'."""
    if not reply_text or not reply_text.strip() or reply_text.strip() == "[no reply]":
        return "no_reply"

    client = get_groq_client()
    if client is None:
        return fallback_classify_outcome(reply_text)

    prompt = f"""You are an email response classifier. Classify this prospect's reply into one of:
{OUTCOMES}

Definitions:
- 'interested': The prospect expresses curiosity, willingness to meet, asks for a demo, or asks about pricing/architecture.
- 'reply': The prospect responded with a polite pass, rejection, out-of-office message, or dismissal.
- 'no_reply': No response was provided.

ORIGINAL EMAIL:
{message_sent}

PROSPECT REPLY:
{reply_text}

Respond ONLY with valid JSON:
{{"outcome": "<one of {OUTCOMES}>"}}
"""

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            completion = client.chat.completions.create(
                model=GROQ_MODEL,
                messages=[
                    {"role": "system", "content": "You are a precise sales outcome classification model. Output strictly raw JSON."},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.0,
            )
            raw = completion.choices[0].message.content.strip()
            match = re.search(r"\{[\s\S]*\}", raw)
            if match:
                data = json.loads(match.group(0))
                outcome = data.get("outcome")
                if outcome in OUTCOMES:
                    return outcome
        except Exception as e:
            print(f"[classify_outcome] attempt {attempt} failed: {e}")

    return fallback_classify_outcome(reply_text)


if __name__ == "__main__":
    test_cases = [
        "",
        "Hi Alex, send over your calendar link and we can connect Thursday!",
        "Thanks Alex, we already have an existing vendor. Best of luck.",
        "Automatic reply: I am out of the office until Monday.",
    ]
    for text in test_cases:
        print(f"Reply: '{text}' -> Classified: {classify_outcome(text)}")
