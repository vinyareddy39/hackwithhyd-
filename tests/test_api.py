"""Unit and integration tests for FastAPI backend and real pipeline."""

from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import re
import pytest
from fastapi.testclient import TestClient

from api import app, append_record_to_log, atomic_write_log, LOG_PATH
from config import ANGLES, OUTCOMES
import draft_email
import metrics


@pytest.fixture
def client():
    return TestClient(app)


def test_batch_run_and_status(client, monkeypatch):
    """POST /api/batch/run executes, reaches status done, and writes valid records."""
    # Reset log before test
    atomic_write_log([])

    res = client.post("/api/batch/run", json={"batch_number": 1, "size": 3})
    assert res.status_code == 200
    data = res.json()
    assert "job_id" in data
    assert data["status"] == "running"
    job_id = data["job_id"]

    # Poll status (in TestClient background tasks execute synchronously or quickly)
    status_res = client.get(f"/api/batch/status/{job_id}")
    assert status_res.status_code == 200
    s_data = status_res.json()
    assert s_data["status"] == "done"
    assert s_data["done"] == 3
    assert s_data["total"] == 3
    assert s_data["error"] is None

    # Verify records written to data/log.json
    log_data = metrics.load_log_data()
    assert len(log_data) == 3
    for record in log_data:
        assert record["batch"] == 1
        assert record["angle"] in ANGLES
        assert record["outcome"] in OUTCOMES
        assert isinstance(record["responded"], bool)


def test_metrics_reflect_log_data(tmp_path, monkeypatch):
    """Metrics calculation accurately reflects exact log contents."""
    custom_log = [
        {"batch": 1, "angle": "referenced_metric", "outcome": "interested", "responded": True},
        {"batch": 1, "angle": "generic", "outcome": "no_reply", "responded": False},
        {"batch": 2, "angle": "referenced_metric", "outcome": "interested", "responded": True},
        {"batch": 2, "angle": "referenced_opinion", "outcome": "reply", "responded": True},
    ]
    log_file = tmp_path / "test_log.json"
    log_file.write_text(json.dumps(custom_log), encoding="utf-8")

    monkeypatch.setattr("api.LOG_PATH", log_file)
    monkeypatch.setattr("metrics.load_log_data", lambda path=None: custom_log)

    client = TestClient(app)
    res = client.get("/api/metrics")
    assert res.status_code == 200
    m = res.json()

    assert m["first_rate"] == 50.0
    assert m["last_rate"] == 100.0
    assert m["delta_pts"] == 50.0
    assert m["rate_by_batch"]["1"] == 50.0
    assert m["rate_by_batch"]["2"] == 100.0


def test_reset_clears_log_and_metrics_returns_empty_structure(client):
    """POST /api/reset empties log and /api/metrics returns valid empty structure."""
    # Write sample data
    atomic_write_log([{"batch": 1, "angle": "generic", "outcome": "interested", "responded": True}])
    assert len(metrics.load_log_data()) == 1

    # Reset
    reset_res = client.post("/api/reset")
    assert reset_res.status_code == 200
    assert reset_res.json()["status"] == "ok"

    # Verify log is empty
    assert len(metrics.load_log_data()) == 0

    # Verify metrics returns empty structure
    m_res = client.get("/api/metrics")
    assert m_res.status_code == 200
    assert m_res.json() == {
        "rate_by_batch": {},
        "angle_mix_by_batch": {},
        "first_rate": 0.0,
        "last_rate": 0.0,
        "delta_pts": 0.0,
        "most_improved_angle": None,
    }


def test_dummy_log_endpoint_removed_returns_404(client):
    """POST /api/dummy-log has been removed and returns 404."""
    res = client.post("/api/dummy-log")
    assert res.status_code == 404


def test_unknown_prospect_returns_404(client):
    """POST /api/draft with unknown prospect returns 404."""
    res = client.post("/api/draft", json={"prospect_id": "unknown_prospect_999", "use_reflection": False})
    assert res.status_code == 404
    assert "not found" in res.json()["detail"].lower()


def test_pipeline_failure_returns_502(client, monkeypatch):
    """Uncaught pipeline / Groq exception returns 502 with message, never a bare 500."""
    def broken_draft(*args, **kwargs):
        raise RuntimeError("Groq rate limit exceeded or connection broken")

    monkeypatch.setattr(draft_email, "draft_email", broken_draft)

    res = client.post("/api/draft", json={"prospect_id": "p01", "use_reflection": False})
    assert res.status_code == 502
    assert "pipeline failure" in res.json()["detail"].lower()
    assert "groq rate limit" in res.json()["detail"].lower()


def test_cors_header_present(client):
    """CORS Access-Control-Allow-Origin header is returned on requests."""
    res = client.get("/health", headers={"Origin": "http://localhost:3000"})
    assert res.status_code == 200
    assert "access-control-allow-origin" in res.headers
    assert res.headers.get("access-control-allow-origin") in ["*", "http://localhost:3000"]


def test_concurrent_writes_do_not_corrupt_log(tmp_path, monkeypatch):
    """Concurrent writes via append_record_to_log must not corrupt data/log.json."""
    test_log = tmp_path / "concurrent_log.json"
    monkeypatch.setattr("api.LOG_PATH", test_log)

    atomic_write_log([])

    def worker(idx):
        record = {
            "batch": 1,
            "prospect_id": f"p_{idx}",
            "angle": "generic",
            "subject": f"Subj {idx}",
            "email": f"Body {idx}",
            "outcome": "interested",
            "responded": True,
        }
        append_record_to_log(record)

    # 20 concurrent threads writing to the log
    with ThreadPoolExecutor(max_workers=8) as executor:
        list(executor.map(worker, range(20)))

    # Verify JSON integrity and full count
    assert test_log.is_file()
    with open(test_log, "r", encoding="utf-8") as f:
        data = json.load(f)
    assert len(data) == 20
    prospect_ids = {r["prospect_id"] for r in data}
    assert len(prospect_ids) == 20


def test_static_check_frontend_no_fake_data():
    """Grep frontend/ files to ensure no hardcoded 'Alex' emails or fake arrays exist."""
    frontend_dir = Path("frontend")
    files = list(frontend_dir.glob("*.html")) + list(frontend_dir.glob("*.js"))
    assert len(files) >= 2, "Expected index.html and app.js in frontend/"

    for f in files:
        content = f.read_text(encoding="utf-8")
        
        # Check no hardcoded mock email signed by Alex
        assert "Best,\nAlex" not in content
        assert "Best regards, Alex" not in content
        assert "dummy-log" not in content
        assert "Load dummy data" not in content

        # Check no hardcoded fake metric arrays
        assert "[16.7, 41.7, 66.7]" not in content
        assert "[33.3, 33.3, 33.3]" not in content


def test_tag_prospects_endpoint(client):
    """POST /api/tag-prospects enriches prospects and returns 200."""
    res = client.post("/api/tag-prospects")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "ok"
    assert data["count"] == 12

