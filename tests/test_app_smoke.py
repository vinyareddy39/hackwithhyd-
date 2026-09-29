"""Smoke tests for the Streamlit dashboard using AppTest."""

from pathlib import Path
import pytest
from streamlit.testing.v1 import AppTest

import make_dummy_log

APP_FILE = str(Path(__file__).resolve().parent.parent / "app.py")


@pytest.fixture(autouse=True)
def ensure_dummy_log():
    """Ensure memory_log.json exists before running smoke tests."""
    log_file = Path("memory_log.json")
    if not log_file.is_file():
        make_dummy_log.generate(str(log_file))


def test_app_smoke_runs_without_exceptions_and_renders_metrics():
    """AppTest runs app.py with the dummy log without exceptions and renders >= 3 metrics."""
    at = AppTest.from_file(APP_FILE, default_timeout=30)
    at.run()

    # Verify no unhandled exceptions occurred
    assert not at.exception, f"App threw unexpected exception: {at.exception}"

    # Verify metric cards are rendered (First batch, Last batch, Improvement)
    assert len(at.metric) >= 3, f"Expected at least 3 metrics rendered, found {len(at.metric)}"

    # Check metric labels match expected batches
    metric_labels = [m.label for m in at.metric]
    assert any("Batch 1" in label for label in metric_labels)
    assert any("Batch 3" in label for label in metric_labels)
    assert any("Improvement" in label for label in metric_labels)


def test_app_missing_file_with_toggle_off_shows_info():
    """When target file is missing and dummy fallback is toggled off, shows info and no exception."""
    at = AppTest.from_file(APP_FILE, default_timeout=30)
    at.run()
    assert not at.exception

    # Change settings in sidebar to nonexistent file and turn off fallback toggle
    at.sidebar.text_input[0].set_value("non_existent_memory_log_xyz.json")
    at.sidebar.toggle[0].set_value(False)
    at.run()

    # Must exit cleanly without exception
    assert not at.exception, f"App threw exception when file is missing: {at.exception}"

    # Must show an informational message explaining missing file
    assert len(at.info) > 0, "Expected an st.info message when log is missing and toggle is off"
    assert "not found" in at.info[0].value.lower()
