from balancr.canonical import DiscrepancyCase
from balancr.notifications.base import NotificationDispatcher

class MockEmailNotificationDispatcher(NotificationDispatcher):
    """
    Dispatcher that simulates sending critical anomaly alert emails.
    Logs details and saves output state locally for unit testing validation.
    """
    def __init__(self, target_email: str):
        self.target_email = target_email
        self.sent_emails = [] # In-memory list for testing verification

    def send_alert(self, case: DiscrepancyCase) -> bool:
        if not self.target_email:
            return False

        cat = case.discrepancy_type.value if case.discrepancy_type else "UNKNOWN"
        subject = f"[Balancr] Critical Reconciliation Anomaly: {cat}"
        
        body = (
            f"Subject: {subject}\n"
            f"To: {self.target_email}\n\n"
            f"Alert: A critical discrepancy was detected during the reconciliation run.\n"
            f"Case ID: {case.id}\n"
            f"Category: {cat}\n"
            f"Description: {case.explanation}\n\n"
            f"Please verify this discrepancy in the Balancr dashboard."
        )

        print(f"[MockSMTP] Dispatching mail alert to {self.target_email}")
        self.sent_emails.append({
            "to": self.target_email,
            "subject": subject,
            "body": body
        })
        return True
