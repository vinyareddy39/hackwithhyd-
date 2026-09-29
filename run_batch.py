"""Execute batch outreach loop: reflect -> draft -> simulate reply -> classify -> log."""

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import threading
from typing import Any, Dict, List, Optional
import uuid

import classify_outcome
from config import MEMORY_PATH, PROSPECTS_PATH, RESPONSE_OUTCOMES
import draft_email
import reflect
import simulate_response
import tag_prospects

LOG_LOCK = threading.Lock()


def load_prospects(path: Optional[str] = None) -> List[Dict[str, Any]]:
    """Load prospects list, ensuring tagging is performed."""
    target_path = Path(path) if path else Path(PROSPECTS_PATH)
    if not target_path.is_file():
        fallback = Path("prospects.json")
        if fallback.is_file():
            target_path = fallback
        else:
            return []

    # Tag if any prospect lacks persona_type
    prospects = tag_prospects.tag_all_prospects(str(target_path))
    return prospects


def append_records_atomic(records: List[Dict[str, Any]], path: Optional[str] = None) -> None:
    """Atomically append records to the memory log file (and data/log.json) under lock."""
    target_path = Path(path) if path else Path(MEMORY_PATH)

    with LOG_LOCK:
        existing: List[Dict[str, Any]] = []
        if target_path.is_file():
            try:
                with open(target_path, "r", encoding="utf-8") as f:
                    content = f.read().strip()
                    if content:
                        loaded = json.loads(content)
                        if isinstance(loaded, list):
                            existing = loaded
            except Exception:
                existing = []

        existing.extend(records)
        target_path.parent.mkdir(parents=True, exist_ok=True)
        temp_file = target_path.parent / f"mem_{uuid.uuid4().hex}.tmp"
        with open(temp_file, "w", encoding="utf-8") as f:
            json.dump(existing, f, indent=2)
        os.replace(temp_file, target_path)

        # Sync to data/log.json if target_path is default
        if not path and target_path != Path("data/log.json"):
            log_path = Path("data/log.json")
            existing_log: List[Dict[str, Any]] = []
            if log_path.is_file():
                try:
                    with open(log_path, "r", encoding="utf-8") as f:
                        c = f.read().strip()
                        if c:
                            existing_log = json.loads(c)
                except Exception:
                    existing_log = []
            compat_records = [
                {
                    **r,
                    "batch": r.get("batch_id"),
                    "angle": r.get("angle_used"),
                    "email": r.get("message_sent"),
                    "reply": r.get("simulated_response"),
                    "responded": r.get("outcome") in RESPONSE_OUTCOMES,
                }
                for r in records
            ]
            existing_log.extend(compat_records)
            log_path.parent.mkdir(parents=True, exist_ok=True)
            temp_file2 = log_path.parent / f"log_{uuid.uuid4().hex}.tmp"
            with open(temp_file2, "w", encoding="utf-8") as f:
                json.dump(existing_log, f, indent=2)
            os.replace(temp_file2, log_path)


def run_batch(
    batch_id: int,
    size: int = 12,
    memory_path: Optional[str] = None,
    prospects_path: Optional[str] = None,
    on_progress: Optional[Any] = None,
) -> List[Dict[str, Any]]:
    """Run one batch of the autonomous prospecting loop.
    
    1. Reflect: Read hindsight memory for each persona.
    2. Draft: Generate personalized email matching reflection insights.
    3. Simulate: Sample prospect reply via persona bias tables.
    4. Classify: Categorize reply into interested / reply / no_reply.
    5. Log: Save record with exact keys to memory_log.json.
    """
    prospects = load_prospects(prospects_path)
    if not prospects:
        return []

    selected = [prospects[i % len(prospects)] for i in range(size)]
    batch_records = []

    for idx, prospect in enumerate(selected):
        persona = prospect.get("persona_type") or "Founder"

        # 1. Reflect on past batches (batch 1 uses no reflection, batches 2+ do)
        if int(batch_id) == 1:
            reflection = None
        else:
            reflection = reflect.reflect(persona, path=memory_path)

        # 2. Draft email
        draft = draft_email.draft_email(prospect, reflection=reflection)
        angle = draft.get("angle_used", "generic")
        body = draft.get("body", "")

        # 3. Simulate response using persona bias tables
        sim_outcome, sim_reply = simulate_response.simulate(prospect, angle)

        # 4. Classify outcome
        classified = classify_outcome.classify_outcome(sim_reply, message_sent=body)
        final_outcome = classified if classified in ["interested", "reply", "no_reply"] else sim_outcome

        # 5. Build memory log record with EXACT locked keys (exactly these 8, no extras)
        record = {
            "batch_id": int(batch_id),
            "prospect_id": str(prospect.get("id")),
            "persona_type": str(persona),
            "angle_used": str(angle),
            "message_sent": str(body),
            "simulated_response": str(sim_reply),
            "outcome": str(final_outcome),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        batch_records.append(record)

        if on_progress:
            on_progress(idx + 1, size)

    # Atomically write to log
    append_records_atomic(batch_records, path=memory_path)
    return batch_records


def run_pipeline(
    total_batches: int = 3,
    batch_size: int = 12,
    memory_path: Optional[str] = None,
) -> Dict[int, float]:
    """Execute full sequential pipeline across multiple batches and report response rates."""
    target_path = Path(memory_path) if memory_path else Path(MEMORY_PATH)
    reset_paths = [target_path]
    if not memory_path and target_path != Path("data/log.json"):
        reset_paths.append(Path("data/log.json"))

    # Reset log for fresh pipeline run if starting from batch 1
    with LOG_LOCK:
        for p in reset_paths:
            p.parent.mkdir(parents=True, exist_ok=True)
            with open(p, "w", encoding="utf-8") as f:
                json.dump([], f, indent=2)

    results: Dict[int, float] = {}

    for b in range(1, total_batches + 1):
        print(f"\n--- Running Batch {b} (size={batch_size}) ---")
        records = run_batch(batch_id=b, size=batch_size, memory_path=str(target_path))
        pos_count = sum(1 for r in records if r["outcome"] in RESPONSE_OUTCOMES)
        rate = (pos_count / len(records)) * 100.0 if records else 0.0
        results[b] = round(rate, 1)
        print(f"Batch {b} Complete: {pos_count}/{len(records)} responded ({results[b]}%)")

    return results


if __name__ == "__main__":
    results = run_pipeline(total_batches=3, batch_size=12)
    print("\nSummary of Response Rates by Batch:")
    for b, rate in results.items():
        print(f"  Batch {b}: {rate}%")
