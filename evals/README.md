# Balancr Agent Evaluation (MLOps)

This directory contains the continuous evaluation pipeline (Regression Testing) for the Balancr reconciliation agent.

## Purpose
The scripts in this module test the **structural orchestration** and **accuracy** of the LangGraph agent against a baseline of known "golden cases" (`golden_cases.json`). 

> [!WARNING]
> **This evaluation measures regressions in the agent's classification behavior. It DOES NOT constitute financial validation or auditing for production use.** A 100% accuracy score here simply means the agent is behaving exactly as we expect on our synthetic baseline scenarios.

## Components

1. **`golden_cases.json`**: A dataset of 15+ synthetic scenarios covering exact matches, duplicate transactions, timing mismatches, and partial amounts across up to 3 sources (Gateway, Bank, Ledger). No real financial data or credentials are included.
2. **`run_eval.py`**: The evaluation runner. It instantiates the deterministic matching engine and passes the discrepancies to the LangGraph agent, comparing the output to the `expected_status` and `expected_discrepancy_type`.
3. **`test_eval_runner.py`** (in `tests/`): Pytest suite that validates the dataset's structural integrity and the runner's offline fallback logic.
4. **`.github/workflows/agent-eval.yml`**: GitHub Actions workflow that runs this suite automatically on every PR affecting the agent or schemas.

## Offline vs. Online Mode

To prevent CI pipelines on forks from crashing (where the `GROQ_API_KEY` secret is unavailable) and to avoid unnecessary LLM api costs during structural development, the evaluator supports an **Offline Mode**.

- **Online Mode (Default)**: If `GROQ_API_KEY` is present, the script hits the real Groq API to query the `llama-3.3-70b-versatile` model.
- **Offline Mode (`EVAL_OFFLINE=true`)**: The script monkey-patches the LLM call to return a stubbed classification based strictly on the deterministic engine's preliminary guess. **This mode does NOT measure LLM quality.**

## Running Locally

To test structural integrity (fast, no Groq cost):
```bash
EVAL_OFFLINE=true PYTHONPATH=. python evals/run_eval.py
```

To run a full LLM evaluation (requires `.env` with `GROQ_API_KEY`):
```bash
PYTHONPATH=. python evals/run_eval.py
```
