---
name: agent-eval-ci
description: Instructions for running and updating the MLOps regression testing pipeline and golden cases.
---

# Agent Evaluation & CI/CD Pipeline

Use this skill when modifying the LangGraph classifier agent, editing the reconciliation engine, or updating CI/CD pipelines.

## Evaluation Structure
- **Golden Cases (`evals/golden_cases.json`)**: Contains 15+ synthetic scenarios covering 2-way/3-way reconciliation anomalies. Uses enums from `balancr.canonical`.
- **Runner (`evals/run_eval.py`)**: Runs matching and routes discrepancies to the agent.
- **Workflow (`.github/workflows/agent-eval.yml`)**: GitHub Actions workflow. Runs structural tests and outputs metrics/accuracy to the action step summary and PR comments.

## Execution Modes
1. **Offline Mode (Default for CI in forks)**:
   Set `EVAL_OFFLINE=true` to skip Groq API calls. The runner monkey-patches the LLM call and returns a deterministic stub.
   ```bash
   EVAL_OFFLINE=true PYTHONPATH=. python evals/run_eval.py
   ```
2. **Online Mode**:
   Uses the real Groq client. Requires `GROQ_API_KEY` configured in the environment.
   ```bash
   PYTHONPATH=. python evals/run_eval.py
   ```

## Verification
Always execute the structural tests before committing pipeline changes:
```bash
EVAL_OFFLINE=true PYTHONPATH=. pytest tests/test_eval_runner.py -v
```
Ensure accuracy meets or exceeds the threshold (`MIN_ACCURACY`, defaults to `90.0%`).
