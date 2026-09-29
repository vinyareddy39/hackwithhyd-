"""FastAPI Backend for Hindsight Sales Agent."""

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import threading
from typing import Any, Dict, List, Optional
import uuid

from fastapi import BackgroundTasks, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from config import ANGLES, MEMORY_PATH, PERSONAS, RESPONSE_OUTCOMES
import classify_outcome
import draft_email
import metrics
import reflect
import simulate_response
import tag_prospects

app = FastAPI(title="Hindsight Sales Agent API", version="1.0.0")

# Enable CORS for all origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Concurrency lock for log writes
LOG_LOCK = threading.Lock()
LOG_PATH = Path("data/log.json")
MEM_PATH = Path(MEMORY_PATH)

# In-memory background job tracking
JOBS: Dict[str, Dict[str, Any]] = {}


class DraftRequest(BaseModel):
    prospect_id: str
    use_reflection: bool = False


class BatchRunRequest(BaseModel):
    batch_number: int
    size: int = 6


def _load_prospects() -> List[Dict[str, Any]]:
    """Load prospects list from data/prospects.json or prospects.json, enriching if untagged."""
    target = None
    for p in [Path("data/prospects.json"), Path("prospects.json")]:
        if p.is_file():
            target = p
            try:
                with open(p, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, list) and data:
                        # Auto-enrich if any prospect lacks persona_type
                        if any(not item.get("persona_type") for item in data):
                            data = tag_prospects.tag_all_prospects(str(p))
                        return data
            except Exception:
                continue
    return []


def atomic_write_log(records: List[Dict[str, Any]]) -> None:
    """Atomically write log records to disk under thread lock (syncing both paths)."""
    with LOG_LOCK:
        for path in [LOG_PATH, MEM_PATH]:
            path.parent.mkdir(parents=True, exist_ok=True)
            temp_file = path.parent / f"log_{uuid.uuid4().hex}.tmp"
            with open(temp_file, "w", encoding="utf-8") as f:
                json.dump(records, f, indent=2)
            os.replace(temp_file, path)


def _append_to_file(path: Path, item: Dict[str, Any]) -> None:
    existing: List[Dict[str, Any]] = []
    if path.is_file():
        try:
            with open(path, "r", encoding="utf-8") as f:
                content = f.read().strip()
                if content:
                    existing = json.loads(content)
        except Exception:
            existing = []
    existing.append(item)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_file = path.parent / f"log_{uuid.uuid4().hex}.tmp"
    with open(temp_file, "w", encoding="utf-8") as f:
        json.dump(existing, f, indent=2)
    os.replace(temp_file, path)


def append_record_to_log(record: Dict[str, Any]) -> None:
    """Atomically append a single log record to disk under thread lock (syncing both paths)."""
    with LOG_LOCK:
        exact_record = {
            "batch_id": int(record.get("batch_id", record.get("batch", 1))),
            "prospect_id": str(record.get("prospect_id", "")),
            "persona_type": str(record.get("persona_type", "")),
            "angle_used": str(record.get("angle_used", record.get("angle", "generic"))),
            "message_sent": str(record.get("message_sent", record.get("email", ""))),
            "simulated_response": str(record.get("simulated_response", record.get("reply", ""))),
            "outcome": str(record.get("outcome", "no_reply")),
            "timestamp": str(record.get("timestamp", datetime.now(timezone.utc).isoformat())),
        }
        _append_to_file(MEM_PATH, exact_record)

        compat_record = {
            **exact_record,
            "batch": exact_record["batch_id"],
            "angle": exact_record["angle_used"],
            "subject": record.get("subject", ""),
            "email": exact_record["message_sent"],
            "reply": exact_record["simulated_response"],
            "responded": record.get("responded", exact_record["outcome"] in RESPONSE_OUTCOMES),
        }
        _append_to_file(LOG_PATH, compat_record)


def run_batch_task(job_id: str, batch_number: int, size: int) -> None:
    """Execute background batch outreach pipeline and append real results."""
    JOBS[job_id]["status"] = "running"
    try:
        prospects = _load_prospects()
        if not prospects:
            JOBS[job_id]["status"] = "error"
            JOBS[job_id]["error"] = "No prospects available."
            return

        selected = [prospects[i % len(prospects)] for i in range(size)]

        for prospect in selected:
            persona = prospect.get("persona_type") or "Founder"
            # 1. Reflect on memory log (batch 1 uses no reflection, batches 2+ do)
            if int(batch_number) == 1:
                reflection = None
            else:
                reflection = reflect.reflect(persona, path=str(MEM_PATH))
                if not reflection:
                    log_data = metrics.load_log_data()
                    reflection = metrics.get_reflection_for_prospect(prospect, log_data)

            # 2. Draft email via Groq or deterministic fallback
            draft = draft_email.draft_email(prospect, reflection=reflection)
            angle = draft.get("angle_used", "generic")
            subject = draft.get("subject", "")
            body = draft.get("body", "")

            # 3. Simulate realistic response using persona bias tables
            sim_outcome, sim_reply = simulate_response.simulate(prospect, angle)

            # 4. Classify outcome
            classified = classify_outcome.classify_outcome(sim_reply, message_sent=body)
            final_outcome = classified if classified in ["interested", "reply", "no_reply"] else sim_outcome
            responded = final_outcome in RESPONSE_OUTCOMES

            # 5. Record with all locked keys
            record = {
                "batch": batch_number,
                "batch_id": batch_number,
                "prospect_id": prospect.get("id"),
                "persona_type": persona,
                "angle": angle,
                "angle_used": angle,
                "subject": subject,
                "email": body,
                "message_sent": body,
                "reply": sim_reply,
                "simulated_response": sim_reply,
                "outcome": final_outcome,
                "responded": responded,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
            append_record_to_log(record)
            JOBS[job_id]["done"] += 1

        JOBS[job_id]["status"] = "done"
    except Exception as e:
        JOBS[job_id]["status"] = "error"
        JOBS[job_id]["error"] = str(e)


@app.get("/health")
def health() -> Dict[str, str]:
    """Health check endpoint."""
    return {"status": "ok"}


@app.get("/api/angles")
def get_angles() -> List[str]:
    """Return all supported personalization angles."""
    return list(ANGLES)


@app.get("/api/prospects")
def get_prospects() -> List[Dict[str, Any]]:
    """Return list of prospects."""
    return _load_prospects()


@app.post("/api/tag-prospects")
def tag_prospects_endpoint(force: bool = False) -> Dict[str, Any]:
    """Trigger prospect enrichment to assign persona_type and lead_score."""
    enriched = tag_prospects.tag_all_prospects(force=force)
    return {"status": "ok", "count": len(enriched), "prospects": enriched}


@app.post("/api/batch/run")
def batch_run_endpoint(req: BatchRunRequest, background_tasks: BackgroundTasks) -> Dict[str, Any]:
    """Trigger background batch generation job."""
    job_id = f"job_{uuid.uuid4().hex[:8]}"
    JOBS[job_id] = {
        "status": "running",
        "done": 0,
        "total": req.size,
        "error": None,
    }
    background_tasks.add_task(run_batch_task, job_id, req.batch_number, req.size)
    return {"job_id": job_id, "status": "running"}


@app.get("/api/batch/status/{job_id}")
def batch_status_endpoint(job_id: str) -> Dict[str, Any]:
    """Check status of a running or completed batch job."""
    if job_id not in JOBS:
        raise HTTPException(status_code=404, detail="Job ID not found.")
    job = JOBS[job_id]
    return {
        "status": job["status"],
        "done": job["done"],
        "total": job["total"],
        "error": job["error"],
    }


@app.post("/api/reset")
def reset_endpoint() -> Dict[str, str]:
    """Clear data/log.json to reset the pipeline."""
    atomic_write_log([])
    return {"status": "ok", "message": "Log cleared."}


@app.post("/api/draft")
def draft_email_endpoint(req: DraftRequest) -> Dict[str, Any]:
    """Draft a cold email for a specific prospect."""
    prospects = _load_prospects()
    target_prospect = next((p for p in prospects if p.get("id") == req.prospect_id), None)

    if not target_prospect:
        raise HTTPException(status_code=404, detail=f"Prospect '{req.prospect_id}' not found.")

    try:
        if req.use_reflection:
            log_data = metrics.load_log_data()
            reflection = metrics.get_reflection_for_prospect(target_prospect, log_data)
        else:
            reflection = ""

        result = draft_email.draft_email(target_prospect, reflection=reflection)
        return {
            "prospect_id": req.prospect_id,
            "subject": result.get("subject", ""),
            "body": result.get("body", ""),
            "angle_used": result.get("angle_used", ""),
            "reflection_applied": reflection if req.use_reflection else None,
        }
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Pipeline failure: {str(e)}")


@app.get("/api/metrics")
def get_metrics_endpoint() -> Dict[str, Any]:
    """Return metrics computed live from data/log.json only."""
    return metrics.get_metrics_summary()


@app.get("/api/compare/{prospect_id}")
def get_compare_endpoint(prospect_id: str) -> Dict[str, Any]:
    """Compare prospect's first batch performance with their latest batch."""
    log_data = metrics.load_log_data()
    prospect_rows = [r for r in log_data if r.get("prospect_id") == prospect_id]

    if not prospect_rows:
        return {"batch1": None, "latest": None}

    # Sort rows by batch number
    prospect_rows.sort(key=lambda r: int(r.get("batch", r.get("batch_id", 1))))

    def format_entry(row: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        if not row:
            return None
        return {
            "batch": row.get("batch", row.get("batch_id", 1)),
            "prospect_id": row.get("prospect_id"),
            "angle": row.get("angle", row.get("angle_used")),
            "subject": row.get("subject", f"Outreach to {row.get('prospect_id')}"),
            "email": row.get("email", row.get("message_sent")),
            "reply": row.get("reply", row.get("simulated_response")),
            "outcome": row.get("outcome"),
            "responded": row.get("responded", row.get("outcome") in ("interested", "reply")),
        }

    first_entry = format_entry(prospect_rows[0])
    latest_entry = format_entry(prospect_rows[-1])

    return {
        "batch1": first_entry,
        "latest": latest_entry,
    }


@app.api_route("/api/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
def api_not_found(path: str):
    """Catch-all for unregistered API routes returning 404."""
    raise HTTPException(status_code=404, detail="API endpoint not found.")


# Mount frontend static directory AFTER all API routes
frontend_dir = Path("frontend")
if not frontend_dir.is_dir():
    frontend_dir.mkdir(parents=True, exist_ok=True)

app.mount("/", StaticFiles(directory="frontend", html=True), name="frontend")
