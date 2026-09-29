"""Generate deterministic synthetic memory log data showing agent learning across batches."""

import json
from pathlib import Path
from typing import Any, Dict, List

from config import ANGLES, LOG_COLUMNS, OUTCOMES, PERSONAS


# Persona best angle mapping
BEST_ANGLES = {
    "Founder": "referenced_metric",
    "Technical Buyer": "referenced_metric",
    "HR Manager": "referenced_opinion",
    "Student": "generic",
}

# Template messages sent by Alex
MESSAGE_TEMPLATES = {
    "referenced_metric": (
        "Hi {name},\n\n"
        "Congratulations on {metric_highlight}. We built an automated workflow pipeline "
        "that helps teams at your scale maintain operational velocity without adding headcount. "
        "Would you be open to a brief 10-minute chat next Tuesday?\n\nBest,\nAlex"
    ),
    "referenced_opinion": (
        "Hi {name},\n\n"
        "I resonated strongly with your insight regarding {opinion_highlight}. "
        "Our platform was designed specifically around that principle to ensure authentic outreach. "
        "Would love to share a short 3-minute demo video if you're interested.\n\nBest,\nAlex"
    ),
    "generic": (
        "Hi {name},\n\n"
        "Hope your week is going well. We help growing organizations at {company} streamline "
        "outreach campaigns and accelerate conversion rates. "
        "Would you be open to exploring a quick case study?\n\nBest,\nAlex"
    ),
}

# Realistic prospect simulated responses
REPLIES_BY_OUTCOME = {
    "interested": [
        "Hi Alex, thanks for the thoughtful note. Impressed that you caught that milestone. Do you have 15 mins this Thursday to discuss?",
        "Appreciate the context Alex! Your timing is great since we're re-evaluating tooling this month. Let's set up a call.",
        "Thanks Alex. Loved that you actually reviewed our setup. Send over a calendar link and we can connect Friday.",
        "Hey Alex, very relevant to what we're solving right now. Let's do a quick intro next Tuesday.",
    ],
    "reply": [
        "Thanks for reaching out Alex. We're currently in the middle of our sprint planning, but feel free to circle back next quarter.",
        "Appreciate the note Alex. We have an existing vendor in place, but I will keep your platform in mind if our needs shift.",
        "Hi Alex, forwarded this to our ops lead. If there's an immediate fit, they'll reach out directly.",
    ],
    "no_reply": ["", "", ""],
}


def load_prospects() -> List[Dict[str, Any]]:
    """Load prospects from prospects.json, enriching if untagged."""
    for p_path in [
        Path(__file__).resolve().parent / "data" / "prospects.json",
        Path(__file__).resolve().parent / "prospects.json",
    ]:
        if p_path.is_file():
            with open(p_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list) and data:
                    if any(not item.get("persona_type") for item in data):
                        import tag_prospects
                        for item in data:
                            if not item.get("persona_type"):
                                item["persona_type"], item["lead_score"] = tag_prospects.fallback_tag_prospect(item)
                    return data
    raise FileNotFoundError("prospects.json not found.")


def generate(path: str = "memory_log.json") -> List[Dict[str, Any]]:
    """Generate 12 prospects x 3 batches (36 rows) showing clear performance improvement.
    
    Response rates:
    - Batch 1: ~17% (2 / 12 positive)
    - Batch 2: ~42% (5 / 12 positive)
    - Batch 3: ~67% (8 / 12 positive)
    """
    prospects = load_prospects()
    records = []

    # Map prospect snippets for realistic personalization
    snippets = {
        "p01": ("scaling ARR to $4.5M", "authentic founder storytelling"),
        "p02": ("raising a $6.8M Seed round", "early customer discovery teaching 10x more"),
        "p03": ("bootstrapping to $2.1M ARR with 7 people", "respecting deep work blocks"),
        "p04": ("cutting database latency by 42%", "deterministic orchestration over fragile cron"),
        "p05": ("saving $380,000 annually across AWS", "developer ergonomics saving engineering time"),
        "p06": ("reducing security triage time from 4 days to 45 min", "shift-left security empowering engineers"),
        "p07": ("sustaining a 94% retention rate for 115 hires", "human-centric empathy in onboarding"),
        "p08": ("reducing time-to-hire from 54 to 21 days", "structured rubrics eliminating unconscious bias"),
        "p09": ("cutting voluntary attrition by 28%", "psychological safety driving team creativity"),
        "p10": ("organizing 450 hackathon participants", "shipping production code to real users"),
        "p11": ("achieving 98.4% perception accuracy", "open-source toolchains democratizing robotics"),
        "p12": ("driving 120 merged pull requests", "mentorship being decentralized and peer-driven"),
    }

    # BATCH 1 (Exploration - 4 of each angle across 12 prospects)
    # 2 positive (1 interested, 1 reply) -> 2/12 = 16.67%
    batch_1_plan = [
        # Founder (p01, p02, p03)
        ("p01", "referenced_metric", "interested", 0),  # hit!
        ("p02", "referenced_opinion", "no_reply", 0),
        ("p03", "generic", "no_reply", 0),
        # Technical Buyer (p04, p05, p06)
        ("p04", "referenced_metric", "reply", 0),       # hit!
        ("p05", "referenced_opinion", "no_reply", 0),
        ("p06", "generic", "no_reply", 0),
        # HR Manager (p07, p08, p09)
        ("p07", "referenced_metric", "no_reply", 0),
        ("p08", "referenced_opinion", "no_reply", 0),
        ("p09", "generic", "no_reply", 0),
        # Student (p10, p11, p12)
        ("p10", "referenced_metric", "no_reply", 0),
        ("p11", "referenced_opinion", "no_reply", 0),
        ("p12", "generic", "no_reply", 0),
    ]

    # BATCH 2 (Refining - 7 best angle, 5 exploratory)
    # 5 positive (3 interested, 2 reply) -> 5/12 = 41.67%
    batch_2_plan = [
        # Founder
        ("p01", "referenced_metric", "interested", 1),
        ("p02", "referenced_metric", "reply", 1),
        ("p03", "referenced_opinion", "no_reply", 0),
        # Technical Buyer
        ("p04", "referenced_metric", "interested", 2),
        ("p05", "referenced_metric", "reply", 2),
        ("p06", "generic", "no_reply", 0),
        # HR Manager
        ("p07", "referenced_opinion", "interested", 3),
        ("p08", "referenced_opinion", "no_reply", 0),
        ("p09", "referenced_metric", "no_reply", 0),
        # Student
        ("p10", "generic", "no_reply", 0),
        ("p11", "generic", "no_reply", 0),
        ("p12", "referenced_opinion", "no_reply", 0),
    ]

    # BATCH 3 (Exploitation - 10 best angle, 2 explore)
    # 8 positive (6 interested, 2 reply) -> 8/12 = 66.67%
    batch_3_plan = [
        # Founder
        ("p01", "referenced_metric", "interested", 0),
        ("p02", "referenced_metric", "interested", 1),
        ("p03", "referenced_metric", "reply", 0),
        # Technical Buyer
        ("p04", "referenced_metric", "interested", 2),
        ("p05", "referenced_metric", "interested", 3),
        ("p06", "referenced_metric", "reply", 1),
        # HR Manager
        ("p07", "referenced_opinion", "interested", 0),
        ("p08", "referenced_opinion", "interested", 2),
        ("p09", "referenced_metric", "no_reply", 0),
        # Student
        ("p10", "generic", "no_reply", 0),
        ("p11", "generic", "no_reply", 0),
        ("p12", "generic", "no_reply", 0),
    ]

    prospect_map = {p["id"]: p for p in prospects}
    batches = [
        (1, "2026-09-10T10:{:02d}:00Z", batch_1_plan),
        (2, "2026-09-17T11:{:02d}:00Z", batch_2_plan),
        (3, "2026-09-24T14:{:02d}:00Z", batch_3_plan),
    ]

    for batch_id, ts_pattern, plan in batches:
        for idx, (p_id, angle, outcome, reply_idx) in enumerate(plan):
            prospect = prospect_map[p_id]
            metric_h, opinion_h = snippets[p_id]
            body = MESSAGE_TEMPLATES[angle].format(
                name=prospect["name"].split()[0],
                company=prospect["company"],
                metric_highlight=metric_h,
                opinion_highlight=opinion_h,
            )
            sim_reply = REPLIES_BY_OUTCOME[outcome][reply_idx % len(REPLIES_BY_OUTCOME[outcome])]
            
            record = {
                "batch_id": batch_id,
                "prospect_id": p_id,
                "persona_type": prospect["persona_type"],
                "angle_used": angle,
                "message_sent": body,
                "simulated_response": sim_reply,
                "outcome": outcome,
                "timestamp": ts_pattern.format(idx * 4),
            }
            records.append(record)

    out_path = Path(path)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(records, f, indent=2)

    return records


if __name__ == "__main__":
    records = generate("memory_log.json")
    print(f"Generated {len(records)} records in memory_log.json")
