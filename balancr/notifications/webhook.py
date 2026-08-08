import requests
from balancr.canonical import DiscrepancyCase
from balancr.notifications.base import NotificationDispatcher

class WebhookNotificationDispatcher(NotificationDispatcher):
    """
    Dispatcher that dispatches critical anomaly alerts to an external webhook URL via HTTP POST.
    """
    def __init__(self, webhook_url: str):
        self.webhook_url = webhook_url

    def send_alert(self, case: DiscrepancyCase) -> bool:
        if not self.webhook_url:
            return False

        g_id = case.transaction_gateway.id if case.transaction_gateway else None
        b_id = case.transaction_bank.id if case.transaction_bank else None
        g_amt = case.transaction_gateway.amount if case.transaction_gateway else None
        b_amt = case.transaction_bank.amount if case.transaction_bank else None
        ref = case.transaction_gateway.reference if case.transaction_gateway else (case.transaction_bank.reference if case.transaction_bank else "N/A")

        payload = {
            "event": "reconciliation.anomaly_detected",
            "case_id": case.id,
            "reference": ref,
            "status": case.status.value,
            "discrepancy_type": case.discrepancy_type.value if case.discrepancy_type else "UNKNOWN",
            "explanation": case.explanation or "",
            "gateway": {
                "id": g_id,
                "amount": g_amt
            },
            "bank": {
                "id": b_id,
                "amount": b_amt
            }
        }

        try:
            response = requests.post(self.webhook_url, json=payload, timeout=5)
            return response.status_code in [200, 201, 202]
        except Exception as e:
            print(f"[WebhookAlert] HTTP POST request failed: {e}")
            return False
