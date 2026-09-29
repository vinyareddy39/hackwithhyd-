"""End-to-end pipeline tests verifying loop execution, locked schemas, reflection rules, and learning."""

from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import random
from config import ANGLES, OUTCOMES, PERSONAS, RESPONSE_OUTCOMES
import draft_email
import reflect
import run_batch


def test_run_batch_exact_locked_keys_and_reflection_rules(tmp_path, monkeypatch):
    """Verify records have EXACTLY the 8 locked keys (no extras), batch 1 uses no reflection, batch 2+ does."""
    test_memory = tmp_path / "memory_log.json"
    test_prospects = tmp_path / "prospects.json"

    with open("data/prospects.json", "r", encoding="utf-8") as f:
        prospects = json.load(f)
    test_prospects.write_text(json.dumps(prospects, indent=2), encoding="utf-8")

    locked_keys = {
        "batch_id",
        "prospect_id",
        "persona_type",
        "angle_used",
        "message_sent",
        "simulated_response",
        "outcome",
        "timestamp",
    }

    reflections_received = {1: [], 2: []}
    real_draft = draft_email.draft_email

    def spy_draft(prospect, reflection=None, rng=None):
        b = 1 if not test_memory.is_file() or len(json.loads(test_memory.read_text())) == 0 else 2
        reflections_received[b].append(reflection)
        return real_draft(prospect, reflection=reflection, rng=rng)

    monkeypatch.setattr(draft_email, "draft_email", spy_draft)

    # Batch 1
    records_b1 = run_batch.run_batch(
        batch_id=1,
        size=12,
        memory_path=str(test_memory),
        prospects_path=str(test_prospects),
    )
    assert len(records_b1) == 12

    # Every record has EXACTLY the locked keys (no extra keys, no missing keys)
    for r in records_b1:
        assert set(r.keys()) == locked_keys, f"Record keys {set(r.keys())} do not match exact locked keys {locked_keys}"
        assert r["batch_id"] == 1
        assert r["persona_type"] in PERSONAS
        assert r["angle_used"] in ANGLES
        assert r["outcome"] in OUTCOMES

    # Batch 1 must use NO reflection (reflection is None)
    assert all(ref is None for ref in reflections_received[1]), "Batch 1 must use no reflection"

    # Batch 2
    records_b2 = run_batch.run_batch(
        batch_id=2,
        size=12,
        memory_path=str(test_memory),
        prospects_path=str(test_prospects),
    )
    assert len(records_b2) == 12

    for r in records_b2:
        assert set(r.keys()) == locked_keys

    # Batch 2+ uses reflection
    assert any(ref is not None for ref in reflections_received[2]), "Batch 2+ must use reflection"


def test_concurrent_appends_do_not_corrupt_log(tmp_path):
    """Concurrent appends to memory log under lock must not lose or corrupt records."""
    test_memory = tmp_path / "concurrent_memory.json"
    test_memory.write_text("[]", encoding="utf-8")

    def append_worker(worker_id):
        records = [
            {
                "batch_id": 1,
                "prospect_id": f"p_w{worker_id}_{i}",
                "persona_type": "Founder",
                "angle_used": "referenced_metric",
                "message_sent": "test message",
                "simulated_response": "test reply",
                "outcome": "interested",
                "timestamp": "2026-09-29T12:00:00Z",
            }
            for i in range(5)
        ]
        run_batch.append_records_atomic(records, path=str(test_memory))

    # 10 workers concurrently appending 5 records each (50 total)
    with ThreadPoolExecutor(max_workers=8) as executor:
        list(executor.map(append_worker, range(10)))

    with open(test_memory, "r", encoding="utf-8") as f:
        data = json.load(f)

    assert len(data) == 50
    prospect_ids = {r["prospect_id"] for r in data}
    assert len(prospect_ids) == 50


def test_learning_rate_climb_and_winning_angle_growth(tmp_path):
    """Learning test: Batches 1-3 with offline drafter and fixed seed.
    
    Assert batch 3 response rate > batch 1 and winning angle's share grows.
    """
    random.seed(42)
    test_memory = tmp_path / "memory_log.json"
    test_prospects = tmp_path / "prospects.json"

    with open("data/prospects.json", "r", encoding="utf-8") as f:
        prospects = json.load(f)
    test_prospects.write_text(json.dumps(prospects, indent=2), encoding="utf-8")

    # Winning angles per persona
    winning_angles = {
        "Founder": "referenced_metric",
        "Technical Buyer": "referenced_opinion",
        "HR Manager": "referenced_metric",
        "Student": "referenced_opinion",
    }

    batch_rates = {}
    winning_shares = {}

    for b in range(1, 4):
        records = run_batch.run_batch(
            batch_id=b,
            size=24,
            memory_path=str(test_memory),
            prospects_path=str(test_prospects),
        )
        pos = sum(1 for r in records if r["outcome"] in RESPONSE_OUTCOMES)
        batch_rates[b] = (pos / len(records)) * 100.0

        # Count how many emails used that persona's winning angle
        winning_count = sum(
            1 for r in records
            if r["angle_used"] == winning_angles.get(r["persona_type"])
        )
        winning_shares[b] = (winning_count / len(records)) * 100.0

    print(f"\n[Learning Test] Rates: B1={batch_rates[1]:.1f}%, B2={batch_rates[2]:.1f}%, B3={batch_rates[3]:.1f}%")
    print(f"[Learning Test] Winning Angle Share: B1={winning_shares[1]:.1f}%, B2={winning_shares[2]:.1f}%, B3={winning_shares[3]:.1f}%")

    # 1. Response rate climbs
    assert batch_rates[3] > batch_rates[1], (
        f"Expected Batch 3 rate ({batch_rates[3]:.1f}%) > Batch 1 rate ({batch_rates[1]:.1f}%)"
    )

    # 2. Winning angle's share grows
    assert winning_shares[3] > winning_shares[1], (
        f"Expected Batch 3 winning share ({winning_shares[3]:.1f}%) > Batch 1 winning share ({winning_shares[1]:.1f}%)"
    )
