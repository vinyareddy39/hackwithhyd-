# Hindsight Outbound Agent

An adaptive, memory-driven outbound cold prospecting agent with full FastAPI backend, interactive frontend dashboard, Groq LLM integration, and Streamlit judge analytics.

## Overview
Hindsight Outbound Agent personalizes cold outreach emails by referencing past content and prospect data. It uses a **hindsight memory layer** that logs which personalization angles succeed across batches, adapting future outreach strategy dynamically using Laplace-smoothed ranking.

### Architecture & Capabilities
- **Backend API (`api.py`)**: FastAPI service with endpoints for running batches, resetting state, tagging prospects, checking health, fetching metrics, logs, and prospect data.
- **Draft Engine (`draft_email.py`)**: Code-driven angle selection, strict prompt engineering, backoff retry logic, and deterministic offline fallback.
- **Enrichment & Tagging (`tag_prospects.py`)**: Personalization tagging with deterministic fallback.
- **Response Simulation (`simulate_response.py`)**: Realistic persona-specific bias tables driving climb in response rates across batches.
- **Outcome Classification (`classify_outcome.py`)**: Rule-based classifier mapping responses to standardized outcomes.
- **Hindsight Memory (`reflect.py` & `run_batch.py`)**: Pipeline coordinator tracking historical effectiveness per persona.
- **Metrics Engine (`metrics.py`)**: Computes real-time response rates, delta points, and angle mix distributions.
- **Web Frontend (`frontend/`)**: Modern responsive UI with live Chart.js visualization, real-time batch breakdown, and comparison views.
- **Streamlit Analytics (`app.py` & `dashboard_utils.py`)**: Interactive judge-ready analytics dashboard.

---

## Quickstart

### 1. Installation
```bash
python -m venv venv
# Windows:
venv\Scripts\activate
# Linux/macOS:
source venv/bin/activate

pip install -r requirements.txt
```

### 2. Environment Configuration
```bash
cp .env.example .env
# Edit .env and supply your Groq API key:
# GROQ_API_KEY=gsk_your_groq_api_key_here
```
*(The system runs 100% offline with realistic fallbacks even without an API key).*

### 3. Running the FastAPI Backend & Web App
```bash
uvicorn api:app --reload --port 8000
```
Open your browser at `http://localhost:8000` to access the interactive dashboard.

### 4. Running the Streamlit Dashboard
```bash
streamlit run app.py
```

### 5. Running the Test Suite
```bash
pytest -v
```
All 48 unit and integration tests run offline without external dependencies.
