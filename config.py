"""Configuration and locked contracts for Hindsight Outbound Agent."""

import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Section 3: Locked contracts
PERSONAS = ["Founder", "Technical Buyer", "HR Manager", "Student"]
ANGLES = ["referenced_metric", "referenced_opinion", "generic"]
OUTCOMES = ["interested", "reply", "no_reply"]
RESPONSE_OUTCOMES = ["interested", "reply"]  # counts toward response rate

MEMORY_PATH = "data/memory_log.json"
PROSPECTS_PATH = "data/prospects.json"

GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
MAX_RETRIES = 3

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")

# Aliases for compatibility
MODEL = GROQ_MODEL
POSITIVE_OUTCOMES = set(RESPONSE_OUTCOMES)
LOG_COLUMNS = [
    "batch_id",
    "prospect_id",
    "persona_type",
    "angle_used",
    "message_sent",
    "simulated_response",
    "outcome",
    "timestamp",
]
