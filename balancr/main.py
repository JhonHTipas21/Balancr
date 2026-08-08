import os
import sys
from datetime import datetime
from dotenv import load_dotenv
from balancr.normalizers.gateway_csv import GatewayCSVSource
from balancr.normalizers.bank_csv import BankCSVSource
from balancr.matching.engine import ReconciliationEngine
from balancr.agent import agent_app
from balancr.reporting.generator import ReconciliationReportGenerator

def main():
    # Load environment variables from .env
    load_dotenv()

    # Define file paths
    gateway_path = os.environ.get("GATEWAY_CSV_PATH", "data/gateway_mock.csv")
    bank_path = os.environ.get("BANK_CSV_PATH", "data/bank_mock.csv")
    report_md_path = os.environ.get("REPORT_MD_PATH", "reports/reconciliation_report.md")
    report_pdf_path = os.environ.get("REPORT_PDF_PATH", "reports/reconciliation_report.pdf")

    print("==================================================")
    print("      Balancr — Autonomous Reconciliation Run     ")
    print("==================================================")
    print(f"[*] Ingesting Gateway CSV: {gateway_path}")
    print(f"[*] Ingesting Bank CSV: {bank_path}")

    # 1. Ingest Data
    if not os.path.exists(gateway_path) or not os.path.exists(bank_path):
        print("[!] Error: Gateway or Bank mock CSV file does not exist. Check paths.")
        sys.exit(1)

    try:
        gateway_source = GatewayCSVSource(gateway_path)
        bank_source = BankCSVSource(bank_path)

        gateway_txs = gateway_source.load_transactions()
        bank_txs = bank_source.load_transactions()
    except Exception as e:
        print(f"[!] Normalization failed: {e}")
        sys.exit(1)

    print(f"[+] Successfully loaded {len(gateway_txs)} gateway transactions")
    print(f"[+] Successfully loaded {len(bank_txs)} bank transactions")

    # 2. Run Deterministic Matching Engine
    print("[*] Running deterministic reconciliation engine...")
    engine = ReconciliationEngine(exact_date_tolerance_days=1, timing_date_tolerance_days=3)
    matched_pairs, anomalies = engine.reconcile(gateway_txs, bank_txs)

    print(f"[+] Deterministic Matcher found {len(matched_pairs)} exact matches")
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

    # 4. Generate Reports
    print("[*] Compiling reports...")
    try:
        # Generate Markdown Summary
        report_md = ReconciliationReportGenerator.generate_markdown_report(matched_pairs, resolved_cases)
        os.makedirs(os.path.dirname(os.path.abspath(report_md_path)), exist_ok=True)
        with open(report_md_path, "w") as f:
            f.write(report_md)
        print(f"[+] Markdown report saved to: {report_md_path}")

        # Generate PDF Summary
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
