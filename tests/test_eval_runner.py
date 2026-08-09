"""
tests/test_eval_runner.py
--------------------------
Structural tests for the golden-case evaluation runner.
These tests run in EVAL_OFFLINE=true mode and do NOT call Groq.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

# Force offline mode before any import of run_eval
os.environ["EVAL_OFFLINE"] = "true"

# Ensure the project root is on the path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


GOLDEN_PATH = PROJECT_ROOT / "evals" / "golden_cases.json"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load_cases() -> list[dict]:
    return json.loads(GOLDEN_PATH.read_text())


# ---------------------------------------------------------------------------
# Golden dataset validation
# ---------------------------------------------------------------------------

class TestGoldenDataset:
    def test_golden_file_exists(self):
        assert GOLDEN_PATH.exists(), "evals/golden_cases.json must exist"

    def test_minimum_case_count(self):
        cases = _load_cases()
        assert len(cases) >= 15, "Need at least 15 golden cases"

    def test_required_fields_present(self):
        valid_statuses = {"MATCHED", "DISCREPANCY", "UNMATCHED"}
        valid_dtypes = {
            "DUPLICATE", "TIMING_MISMATCH", "PARTIAL_AMOUNT",
            "MISSING_COUNTERPART", "UNKNOWN", None,
        }
        for case in _load_cases():
            assert "case_id" in case, f"Missing case_id in {case}"
            assert "expected_status" in case, f"Missing expected_status in {case}"
            assert case["expected_status"] in valid_statuses, (
                f"Invalid status '{case['expected_status']}' in {case['case_id']}"
            )
            dtype = case.get("expected_discrepancy_type")
            assert dtype in valid_dtypes, (
                f"Invalid discrepancy_type '{dtype}' in {case['case_id']}"
            )

    def test_no_hardcoded_secrets(self):
        raw = GOLDEN_PATH.read_text()
        for kw in ("gsk_", "sk-", "Bearer ", "api_key", "password"):
            assert kw not in raw, f"Possible secret found in golden_cases.json: '{kw}'"

    def test_case_ids_unique(self):
        cases = _load_cases()
        ids = [c["case_id"] for c in cases]
        assert len(ids) == len(set(ids)), "Duplicate case_id values found"

    def test_at_least_one_match_case(self):
        cases = _load_cases()
        statuses = [c["expected_status"] for c in cases]
        assert "MATCHED" in statuses

    def test_at_least_one_timing_case(self):
        cases = _load_cases()
        dtypes = [c.get("expected_discrepancy_type") for c in cases]
        assert "TIMING_MISMATCH" in dtypes

    def test_at_least_one_duplicate_case(self):
        cases = _load_cases()
        dtypes = [c.get("expected_discrepancy_type") for c in cases]
        assert "DUPLICATE" in dtypes


# ---------------------------------------------------------------------------
# Runner structural tests (offline mode, no LLM)
# ---------------------------------------------------------------------------

class TestRunEvalOffline:
    """
    Runs the full evaluation pipeline in offline mode.
    Verifies structure and pass/fail logic without any network calls.
    """

    def test_runner_produces_results_file(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("EVAL_OFFLINE", "true")
        monkeypatch.delenv("GROQ_API_KEY", raising=False)

        # Import after env is patched
        import importlib

        import evals.run_eval as runner
        importlib.reload(runner)

        runner.RESULTS_PATH = tmp_path / "eval_results.json"
        with pytest.raises(SystemExit) as exc_info:
            runner.main()
        assert exc_info.value.code == 0

        assert runner.RESULTS_PATH.exists()
        data = json.loads(runner.RESULTS_PATH.read_text())
        assert "accuracy" in data
        assert "passed" in data
        assert "failures" in data

    def test_altered_case_fails_evaluation(self, tmp_path, monkeypatch):
        """Deliberately break one case to confirm the evaluator catches regressions."""
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("EVAL_OFFLINE", "true")
        monkeypatch.delenv("GROQ_API_KEY", raising=False)

        # Copy and corrupt the golden dataset
        cases = _load_cases()
        cases[0]["expected_status"] = "DISCREPANCY"  # force wrong expectation
        cases[0]["expected_discrepancy_type"] = None
        corrupted = tmp_path / "golden_cases.json"
        corrupted.write_text(json.dumps(cases))

        import importlib

        import evals.run_eval as runner
        importlib.reload(runner)

        runner.GOLDEN_CASES_PATH = corrupted
        runner.RESULTS_PATH = tmp_path / "eval_results.json"
        runner.MIN_ACCURACY = 1.0  # require 100% so any failure is caught

        with pytest.raises(SystemExit) as exc_info:
            runner.main()
        assert exc_info.value.code == 1

    def test_github_step_summary_written(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("EVAL_OFFLINE", "true")
        monkeypatch.delenv("GROQ_API_KEY", raising=False)
        summary_file = tmp_path / "step_summary.md"
        monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary_file))

        import importlib

        import evals.run_eval as runner
        importlib.reload(runner)

        runner.RESULTS_PATH = tmp_path / "eval_results.json"
        with pytest.raises(SystemExit) as exc_info:
            runner.main()
        assert exc_info.value.code == 0

        assert summary_file.exists()
        content = summary_file.read_text()
        assert "Balancr Agent Evaluation" in content
        assert "Accuracy" in content
        assert "balancr-agent-eval" in content

    def test_no_secrets_in_results_file(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("EVAL_OFFLINE", "true")
        monkeypatch.delenv("GROQ_API_KEY", raising=False)

        import importlib

        import evals.run_eval as runner
        importlib.reload(runner)

        runner.RESULTS_PATH = tmp_path / "eval_results.json"
        with pytest.raises(SystemExit) as exc_info:
            runner.main()
        assert exc_info.value.code == 0

        raw = runner.RESULTS_PATH.read_text()
        for kw in ("gsk_", "sk-", "Bearer ", "api_key"):
            assert kw not in raw
