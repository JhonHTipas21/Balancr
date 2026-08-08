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
