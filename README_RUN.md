# Hindsight Sales Agent (Person 4 & Person 5)

An adaptive cold-email outreach system that remembers which personalization angles succeed across past batches and shifts its strategy over time.

- **Person 4 (Draft Engine - `draft_email.py`)**: Code-driven angle selection, strict prompt engineering, retry/backoff validation, and deterministic fallbacks.
- **Person 5 (Dashboard - `app.py`, `dashboard_utils.py`, `make_dummy_log.py`)**: Real-time batch analytics, response rate trajectory, angle distribution evolution, persona × angle success heatmaps, and prospect evolution comparisons.

---

## 1. Quickstart & Installation

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Set up environment variables
cp .env.example .env
# (Optional) Edit .env and supply your Groq API key:
# GROQ_API_KEY=gsk_your_groq_api_key_here

# 3. Generate dummy agent memory data (12 prospects x 3 batches = 36 rows)
python make_dummy_log.py

# 4. Run test suite (100% offline, requires no API key and no internet)
pytest -q

# 5. Launch the Streamlit judge dashboard
streamlit run app.py

# 6. Run the draft engine demo
python draft_email.py
```

---

## 2. Architecture & File Overview

| File | Description |
|------|-------------|
| `config.py` | Shared contracts, constants (`ANGLES`, `OUTCOMES`, `PERSONAS`, `POSITIVE_OUTCOMES`), column schemas, and model definition (`llama-3.3-70b-versatile`). |
| `prospects.json` | 12 realistic B2B prospects across 4 personas (3 each for Founder, Technical Buyer, HR Manager, Student) containing achievements, opinions, and scores. |
| `memory_log.json` | 36-record agent memory tracking performance progression from ~17% to ~42% to ~67%. |
| `draft_email.py` | Email drafting engine. Personalization angle selected by code (not LLM), Groq integration with lazy loading, JSON parser with regex fallback, word count validation (20-130 words), and deterministic fallback. |
| `make_dummy_log.py` | Deterministic synthetic log generator showing clear angle adaptation and response rate progression across Batches 1, 2, and 3. |
| `dashboard_utils.py` | Pure pandas analytical utilities (no Streamlit dependency) for response rates, angle distributions, persona heatmaps, and batch comparisons. |
| `app.py` | High-impact Streamlit judge dashboard featuring judge-friendly KPI metric cards, response rate trajectory line chart, angle shift stacked bar chart, persona success heatmap, and side-by-side prospect evolution. |
| `conftest.py` | Pytest environment configuration ensuring project root is on `sys.path`. |
| `tests/test_draft_email.py` | Unit tests for angle selection probabilities, prompt synthesis, parsing, retry behavior, and deterministic fallback without internet. |
| `tests/test_dashboard_utils.py` | Unit tests on hand-crafted data verifying exact mathematical rates, row percentage sums, missing file safety, and dummy log validity. |
| `tests/test_app_smoke.py` | Headless Streamlit smoke tests using `AppTest` verifying clean rendering of metrics, views, and missing file fallback states without exceptions. |

---

## 3. Verifying Output

When running `python draft_email.py` with or without an active `GROQ_API_KEY`, the script produces 3 exploratory drafts (reflection empty) and 3 adapted drafts (favoring `referenced_metric`). If no API key is provided, it falls back deterministically to compliant 3-5 sentence emails signed off by "Alex".
