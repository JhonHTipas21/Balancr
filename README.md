# Balancr

Balancr is an autonomous agent for continuous payment reconciliation. It matches transactions across payment gateways, bank statements, and internal ledgers, using deterministic algorithms and LLM-powered anomaly classification.

## Key Features

* **Three-Way Matching**: Deterministically matches records across Gateway, Bank, and Ledger sources.
* **LLM Anomaly Classification**: Uses LangGraph and Groq LLMs to analyze and classify discrepancies (e.g., partial amounts, timing mismatches).
* **Vector Memory**: Learns from manual resolutions by storing cases in an offline ChromaDB index.
* **Alerts**: Dispatches webhooks and mock emails for critical discrepancies.
* **Dashboard**: Includes a dark-themed responsive SPA dashboard for manual resolution.

## Installation

1. **Clone the repository**:
   ```bash
   git clone <repository_url>
   cd Balancr
   ```
2. **Create a virtual environment**:
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   ```
3. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```
4. **Environment Variables**:
   Create a `.env` file and configure `GROQ_API_KEY`, `ALERT_WEBHOOK_URL`, and `ALERT_EMAIL_TO` if necessary.

## Usage

### CLI Execution
Run the complete reconciliation flow from the terminal:
```bash
python3 -m balancr.main
```
This will parse mock files from `data/`, run the deterministic matcher, invoke the LLM agent for anomalies, send critical alerts, and generate Markdown/PDF reports in the `reports/` folder.

### Web Dashboard
Run the FastAPI web backend:
```bash
uvicorn balancr.api.app:app --reload
```
Navigate to `http://127.0.0.1:8000` to access the drag-and-drop dashboard interface for manual reconciliation.

## Architecture

* **`balancr/canonical.py`**: Defines the unified data models and discrepancy types using Pydantic.
* **`balancr/normalizers/`**: Adapters for loading and parsing data from disparate CSV structures.
* **`balancr/matching/`**: The deterministic matching engine that handles three-way exact matches.
* **`balancr/agent/`**: LangGraph nodes and orchestrator for querying Groq LLMs.
* **`balancr/memory/`**: The local ChromaDB vector store powered by a custom offline hashing embedding function.
* **`balancr/notifications/`**: Dispatch adapters for webhooks and emails.
* **`balancr/reporting/`**: Generators for Markdown and PDF summary reports.
* **`balancr/api/`**: The FastAPI server and single-page application dashboard.

## Testing

The project uses `pytest` for unit and integration testing. Tests are located in the `tests/` directory.

To run the entire test suite:
```bash
pytest -v
```

This covers unit tests for normalizers, the deterministic matching engine, mock integrations for LLMs, local ChromaDB instance, notifications dispatch, and the FastAPI application routes.

## Continuous Agent Evaluation (MLOps)

Balancr includes a continuous regression evaluation pipeline to measure the accuracy and performance of the LangGraph anomaly classification agent.

### Golden Dataset
The evaluation is based on a curated dataset of golden cases (`evals/golden_cases.json`) that represents representative mock scenarios including:
* Exact matching and timing mismatches.
* Partial amounts and currency discrepancies.
* Duplicate transactions and missing counterparts across gateways, banks, and ledgers.

### Evaluation Runner
The runner (`evals/run_eval.py`) executes the evaluation pipeline. It supports two modes:
1. **Online Mode (Default)**: Leverages the configured Groq LLM provider (`llama-3.3-70b-versatile`) to classify anomalies and check matching accuracy.
2. **Offline Mode (`EVAL_OFFLINE=true`)**: Monkey-patches the agent with deterministic mocks to verify pipeline orchestration structure without external network dependencies or LLM token costs.

### CI/CD Workflow
A GitHub Actions workflow (`.github/workflows/agent-eval.yml`) runs on every pull request and push to the main branch. The workflow:
* Standardizes on a Python 3.11 environment.
* Runs structural pytest checks under offline mode first.
* Computes classification accuracy against the golden cases.
* Publishes a summary report directly into the GitHub Actions run summary and updates the pull request comment with detailed accuracy metrics.
* Enforces a minimum accuracy threshold (defaults to 90%), failing the build if a regression is detected.

