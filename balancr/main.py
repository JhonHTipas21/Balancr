import os
import sys
from datetime import datetime
from dotenv import load_dotenv
from balancr.normalizers.gateway_csv import GatewayCSVSource
from balancr.normalizers.bank_csv import BankCSVSource
from balancr.normalizers.ledger_db import LedgerDBSource
from balancr.matching.engine import ReconciliationEngine
from balancr.agent import agent_app
from balancr.reporting.generator import ReconciliationReportGenerator
from balancr.canonical import ReconciliationStatus

def main():
    """
    Main entry point for the Balancr autonomous reconciliation runner.
    Ingests data, runs three-way matching, dispatches LLM anomaly analysis,
    triggers alerts, and outputs Markdown and PDF summary reports.
    """
    # Load environment variables from .env
    load_dotenv()

    # Define file paths
    gateway_path = os.environ.get("GATEWAY_CSV_PATH", "data/gateway_mock.csv")
    bank_path = os.environ.get("BANK_CSV_PATH", "data/bank_mock.csv")
    ledger_path = os.environ.get("LEDGER_CSV_PATH", "data/ledger_mock.csv")
    report_md_path = os.environ.get("REPORT_MD_PATH", "reports/reconciliation_report.md")
    report_pdf_path = os.environ.get("REPORT_PDF_PATH", "reports/reconciliation_report.pdf")

    print("==================================================")
    print("      Balancr - Autonomous Reconciliation Run     ")
    print("==================================================")
    print(f"[*] Ingesting Gateway CSV: {gateway_path}")
    print(f"[*] Ingesting Bank CSV: {bank_path}")
    print(f"[*] Ingesting Ledger CSV: {ledger_path}")

    # 1. Ingest Data
    if not os.path.exists(gateway_path) or not os.path.exists(bank_path) or not os.path.exists(ledger_path):
        print("[!] Error: Ingest mock CSV files do not exist. Check configuration.")
        sys.exit(1)

    try:
        gateway_source = GatewayCSVSource(gateway_path)
        bank_source = BankCSVSource(bank_path)
        ledger_source = LedgerDBSource(ledger_path)

        gateway_txs = gateway_source.load_transactions()
        bank_txs = bank_source.load_transactions()
        ledger_txs = ledger_source.load_transactions()
    except Exception as e:
        print(f"[!] Normalization failed: {e}")
        sys.exit(1)

    print(f"[+] Successfully loaded {len(gateway_txs)} gateway transactions")
    print(f"[+] Successfully loaded {len(bank_txs)} bank transactions")
    print(f"[+] Successfully loaded {len(ledger_txs)} ledger transactions")

    # 2. Run Deterministic Three-Way Matching Engine
    print("[*] Running deterministic three-way matching...")
    engine = ReconciliationEngine(exact_date_tolerance_days=1, timing_date_tolerance_days=3)
    matched_pairs, anomalies = engine.reconcile_3way(gateway_txs, bank_txs, ledger_txs)

    print(f"[+] Deterministic Matcher found {len(matched_pairs)} three-way matches")
    print(f"[+] Deterministic Matcher flagged {len(anomalies)} anomalies")

    # 3. Run Stateful LLM Agent (LangGraph)
    resolved_cases = []
    has_groq_key = bool(os.environ.get("GROQ_API_KEY"))

    if anomalies:
        if has_groq_key:
            print("[*] GROQ_API_KEY detected. Starting LangGraph Agent workflow...")
            initial_state = {
                "anomalies": anomalies,
                "resolved_cases": [],
                "current_index": 0,
                "memory_matches": [],
                "summary": ""
            }
            try:
                final_state = agent_app.invoke(initial_state)
                resolved_cases = final_state["resolved_cases"]
                print(f"[+] LangGraph Agent successfully analyzed all {len(resolved_cases)} cases")
            except Exception as e:
                print(f"[!] LangGraph Agent failed: {e}")
                print("[*] Falling back to rule-based explanations.")
                resolved_cases = anomalies
        else:
            print("[!] Warning: GROQ_API_KEY not found in environment.")
            print("[*] Skipping LangGraph Agent analysis. Writing raw discrepancies to report.")
            resolved_cases = anomalies
    else:
        resolved_cases = []

    # 3.5 Dispatch critical alerts if dispatchers are configured
    webhook_url = os.environ.get("ALERT_WEBHOOK_URL")
    email_to = os.environ.get("ALERT_EMAIL_TO")

    if webhook_url or email_to:
        from balancr.notifications import WebhookNotificationDispatcher, MockEmailNotificationDispatcher
        print("[*] Checking critical discrepancies to dispatch alerts...")
        
        webhook_dispatcher = WebhookNotificationDispatcher(webhook_url) if webhook_url else None
        email_dispatcher = MockEmailNotificationDispatcher(email_to) if email_to else None
        
        for case in resolved_cases:
            if case.status != ReconciliationStatus.MATCHED:
                if webhook_dispatcher:
                    print(f"[*] Dispatching webhook alert for case {case.id}...")
                    webhook_dispatcher.send_alert(case)
                if email_dispatcher:
                    print(f"[*] Dispatching email alert for case {case.id}...")
                    email_dispatcher.send_alert(case)

    # 4. Generate Reports
    print("[*] Compiling reports...")
    try:
        report_md = ReconciliationReportGenerator.generate_markdown_report(matched_pairs, resolved_cases)
        os.makedirs(os.path.dirname(os.path.abspath(report_md_path)), exist_ok=True)
        with open(report_md_path, "w") as f:
            f.write(report_md)
        print(f"[+] Markdown report saved to: {report_md_path}")

        ReconciliationReportGenerator.generate_pdf_report(matched_pairs, resolved_cases, report_pdf_path)
        print(f"[+] PDF report saved to: {report_pdf_path}")
        
    except Exception as e:
        print(f"[!] Report generation failed: {e}")
        sys.exit(1)

    print("\n================ Run Completed Successfully ================")
    # Print a brief preview of the markdown report
    preview_lines = report_md.split("\n")[:14]
    print("\n".join(preview_lines))
    print("...\n============================================================")

if __name__ == "__main__":
    main()
