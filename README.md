# Balancr

Balancr is an autonomous agent for continuous payment reconciliation. It matches transactions across payment gateways, bank statements, and internal ledgers, using deterministic algorithms and LLM-powered anomaly classification.

## Key Features

* **Three-Way Matching**: Deterministically matches records across Gateway, Bank, and Ledger sources.
* **LLM Anomaly Classification**: Uses LangGraph and Groq LLMs to analyze and classify discrepancies (e.g., partial amounts, timing mismatches).
* **Vector Memory**: Learns from manual resolutions by storing cases in an offline ChromaDB index.
* **Alerts**: Dispatches webhooks and mock emails for critical discrepancies.
* **Dashboard**: Includes a dark-themed responsive SPA dashboard for manual resolution.
