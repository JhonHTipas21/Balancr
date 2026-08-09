"""
evals/run_eval.py
-----------------
Regression evaluator for the Balancr reconciliation agent.

This script is NOT a substitute for financial validation in production.
It measures regression in the agent's classification behavior against
a fixed golden dataset. A passing score does not constitute a financial audit.

Usage:
    PYTHONPATH=. python evals/run_eval.py
    EVAL_OFFLINE=true PYTHONPATH=. python evals/run_eval.py   # structural test only
    MIN_ACCURACY=0.85 PYTHONPATH=. python evals/run_eval.py   # custom threshold
"""
from __future__ import annotations

import json
import os
import sys
import textwrap
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Offline LLM adapter
# ---------------------------------------------------------------------------
# When EVAL_OFFLINE=true the agent's classify_anomaly node is replaced with a
# deterministic stub that echoes the classification already produced by the
# deterministic engine.  This mode DOES NOT measure LLM quality — it only
# verifies that the orchestration pipeline is structurally correct.
# ---------------------------------------------------------------------------

EVAL_OFFLINE = os.environ.get("EVAL_OFFLINE", "false").lower() == "true"

if EVAL_OFFLINE:
    # Monkey-patch before importing the graph so graph.py never calls Groq
    import balancr.agent.llm as _llm_module

    def _offline_call(_messages: list[dict[str, str]], **_kwargs: Any) -> str:
        """Return a stub classification that mirrors the deterministic engine's guess."""
        # Extract the current discrepancy_type from the user prompt and echo it.
        for msg in _messages:
            if msg.get("role") == "user":
                for line in msg["content"].splitlines():
                    if "Preliminary classification:" in line:
                        dtype = line.split(":", 1)[-1].strip()
                        return json.dumps({
                            "discrepancy_type": dtype,
                            "explanation": "[OFFLINE EVAL] Deterministic echo.",
                        })
        return json.dumps({
            "discrepancy_type": "UNKNOWN",
            "explanation": "[OFFLINE EVAL] Could not extract type from prompt.",
        })

    _llm_module.call_llm_with_backoff = _offline_call


# ---------------------------------------------------------------------------
# Import public Balancr API
# ---------------------------------------------------------------------------
from balancr.canonical import (
    CanonicalTransaction,
    ReconciliationStatus,
)
from balancr.matching.engine import ReconciliationEngine

# Only import agent graph if we actually need LLM (non-offline mode)
if not EVAL_OFFLINE:
    from balancr.agent.graph import app as _agent_graph

GOLDEN_CASES_PATH = Path(__file__).parent / "golden_cases.json"
RESULTS_PATH = Path("eval_results.json")
MIN_ACCURACY = float(os.environ.get("MIN_ACCURACY", "0.90"))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _build_tx(raw: dict[str, Any]) -> CanonicalTransaction:
    return CanonicalTransaction(
        id=raw["id"],
        amount=float(raw["amount"]),
        currency=raw["currency"],
        date=datetime.fromisoformat(raw["date"]),
        reference=raw["reference"],
        source=raw["source"],
        raw_payload=raw,
    )


def _run_case(case: dict[str, Any]) -> tuple[str, str | None]:
    """
    Runs one golden case through the Balancr pipeline.

    Returns:
        (actual_status, actual_discrepancy_type | None)
    """
    engine = ReconciliationEngine(
        exact_date_tolerance_days=1,
        timing_date_tolerance_days=3,
    )

    gateway_txs = [_build_tx(t) for t in case.get("gateway", [])]
    bank_txs = [_build_tx(t) for t in case.get("bank", [])]
    ledger_txs = [_build_tx(t) for t in case.get("ledger", [])]
    mode = case.get("mode", "2way")

    # Step 1 — Deterministic matching
    if mode == "3way":
        matched, discrepancies = engine.reconcile_3way(gateway_txs, bank_txs, ledger_txs)
    else:
        matched, discrepancies = engine.reconcile(gateway_txs, bank_txs)

    if matched and not discrepancies:
        return ReconciliationStatus.MATCHED.value, None

    if not discrepancies:
        return ReconciliationStatus.MATCHED.value, None

    # Step 2 — Agent classification (only for discrepancies)
    if EVAL_OFFLINE or not discrepancies:
        # In offline mode skip LLM; use engine classification directly
        first = discrepancies[0]
        return first.status.value, first.discrepancy_type.value if first.discrepancy_type else None

    # Online mode: run LangGraph agent
    initial_state = {
        "anomalies": discrepancies,
        "resolved_cases": [],
        "current_index": 0,
        "memory_matches": [],
        "summary": "",
    }
    final_state = _agent_graph.invoke(initial_state)
    resolved = final_state.get("resolved_cases", [])
    if not resolved:
        first = discrepancies[0]
        return first.status.value, first.discrepancy_type.value if first.discrepancy_type else None

    first_resolved = resolved[0]
    return (
        first_resolved.status.value,
        first_resolved.discrepancy_type.value if first_resolved.discrepancy_type else None,
    )


def _check_groq_secret() -> bool:
    """Returns False and prints a safe warning if GROQ_API_KEY is absent."""
    if not EVAL_OFFLINE and not os.environ.get("GROQ_API_KEY"):
        print(
            "WARNING: GROQ_API_KEY is not set and EVAL_OFFLINE is not 'true'.\n"
            "Switching to offline mode automatically.  "
            "This run DOES NOT measure real LLM quality.",
            file=sys.stderr,
        )
        return False
    return True


# ---------------------------------------------------------------------------
# Main evaluation loop
# ---------------------------------------------------------------------------

def main() -> None:
    global EVAL_OFFLINE

    if not _check_groq_secret():
        # Force offline mode rather than crashing silently
        EVAL_OFFLINE = True  # type: ignore[assignment]

    if not GOLDEN_CASES_PATH.exists():
        print(f"ERROR: golden_cases.json not found at {GOLDEN_CASES_PATH}", file=sys.stderr)
        sys.exit(1)

    cases: list[dict[str, Any]] = json.loads(GOLDEN_CASES_PATH.read_text())

    total = len(cases)
    correct = 0
    failures: list[dict[str, Any]] = []
    by_category: dict[str, dict[str, int]] = defaultdict(lambda: {"total": 0, "correct": 0})

    print(f"Running {total} golden cases  [offline={EVAL_OFFLINE}]")
    print("-" * 60)

    for case in cases:
        case_id = case["case_id"]
        expected_status = case["expected_status"]
        expected_dtype = case.get("expected_discrepancy_type")
        category = expected_dtype or expected_status

        try:
            actual_status, actual_dtype = _run_case(case)
        except Exception as exc:  # noqa: BLE001
            actual_status, actual_dtype = "ERROR", str(exc)

        by_category[category]["total"] += 1

        status_ok = actual_status == expected_status
        dtype_ok = expected_dtype is None or actual_dtype == expected_dtype
        passed = status_ok and dtype_ok

        if passed:
            correct += 1
            by_category[category]["correct"] += 1
            print(f"  PASS  {case_id}")
        else:
            failures.append({
                "case_id": case_id,
                "description": case.get("description", ""),
                "expected_status": expected_status,
                "expected_discrepancy_type": expected_dtype,
                "actual_status": actual_status,
                "actual_discrepancy_type": actual_dtype,
            })
            print(
                f"  FAIL  {case_id}  "
                f"expected=({expected_status}, {expected_dtype})  "
                f"actual=({actual_status}, {actual_dtype})"
            )

    accuracy = correct / total if total else 0.0
    passed_threshold = accuracy >= MIN_ACCURACY

    print("-" * 60)
    print(f"Accuracy: {accuracy:.1%}  ({correct}/{total})  threshold={MIN_ACCURACY:.1%}")
    print(f"Result:   {'PASS' if passed_threshold else 'FAIL'}")

    # Per-category breakdown
    print("\nBreakdown by expected category:")
    for cat, counts in sorted(by_category.items()):
        pct = counts["correct"] / counts["total"] if counts["total"] else 0
        print(f"  {cat:<30} {counts['correct']}/{counts['total']}  ({pct:.0%})")

    # ----- GitHub Step Summary -----
    step_summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if step_summary:
        status_label = "PASSED" if passed_threshold else "FAILED"
        md = textwrap.dedent(f"""\
            ## Balancr Agent Evaluation <!-- balancr-agent-eval -->

            | Metric | Value |
            |--------|-------|
            | Accuracy | {accuracy:.1%} |
            | Correct cases | {correct} / {total} |
            | Threshold | {MIN_ACCURACY:.1%} |
            | Mode | {"offline (structural only)" if EVAL_OFFLINE else "online (real LLM)"} |
            | Status | **{status_label}** |

            ### Per-category results

            | Category | Correct | Total | % |
            |----------|---------|-------|---|
        """)
        for cat, counts in sorted(by_category.items()):
            pct = counts["correct"] / counts["total"] if counts["total"] else 0
            md += f"| {cat} | {counts['correct']} | {counts['total']} | {pct:.0%} |\n"

        if failures:
            md += "\n### Failed cases\n\n"
            md += "| Case ID | Expected status | Expected type | Actual status | Actual type |\n"
            md += "|---------|----------------|---------------|---------------|-------------|\n"
            for f in failures:
                md += (
                    f"| {f['case_id']} "
                    f"| {f['expected_status']} "
                    f"| {f['expected_discrepancy_type']} "
                    f"| {f['actual_status']} "
                    f"| {f['actual_discrepancy_type']} |\n"
                )
        else:
            md += "\n**All cases passed.**\n"

        md += (
            "\n> **Note:** This evaluation measures regression in agent classification "
            "behavior. It does not constitute financial validation for production use.\n"
        )

        Path(step_summary).write_text(md)

    # ----- Artifact for github-script -----
    RESULTS_PATH.write_text(
        json.dumps(
            {
                "accuracy": round(accuracy, 4),
                "min_accuracy": MIN_ACCURACY,
                "total": total,
                "correct": correct,
                "passed": passed_threshold,
                "offline_mode": EVAL_OFFLINE,
                "failures": [
                    {
                        "case_id": f["case_id"],
                        "description": f["description"],
                        "expected_status": f["expected_status"],
                        "expected_discrepancy_type": f["expected_discrepancy_type"],
                        "actual_status": f["actual_status"],
                        "actual_discrepancy_type": f["actual_discrepancy_type"],
                    }
                    for f in failures
                ],
            },
            indent=2,
        )
    )

    sys.exit(0 if passed_threshold else 1)


if __name__ == "__main__":
    main()
