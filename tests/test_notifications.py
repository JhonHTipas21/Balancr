import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime
from balancr.canonical import CanonicalTransaction, DiscrepancyCase, DiscrepancyType, ReconciliationStatus
from balancr.notifications.webhook import WebhookNotificationDispatcher
from balancr.notifications.email import MockEmailNotificationDispatcher

@pytest.fixture
def sample_case():
    g_tx = CanonicalTransaction(
        id="gw_test", amount=150.0, currency="USD", date=datetime.now(), reference="REF_999", source="gateway"
    )
    return DiscrepancyCase(
        id="case_test",
        transaction_gateway=g_tx,
        transaction_bank=None,
        status=ReconciliationStatus.DISCREPANCY,
        discrepancy_type=DiscrepancyType.MISSING_COUNTERPART,
        explanation="No matching bank transaction."
    )

@patch("requests.post")
def test_webhook_dispatcher_success(mock_post, sample_case):
    # Mock successful POST response
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_post.return_value = mock_response

    dispatcher = WebhookNotificationDispatcher("http://localhost/webhook")
    success = dispatcher.send_alert(sample_case)

    assert success is True
    mock_post.assert_called_once()
    
    # Assert JSON payload parameters
    called_args, called_kwargs = mock_post.call_args
    assert called_kwargs["json"]["case_id"] == "case_test"
    assert called_kwargs["json"]["event"] == "reconciliation.anomaly_detected"
    assert called_kwargs["json"]["discrepancy_type"] == "MISSING_COUNTERPART"

@patch("requests.post")
def test_webhook_dispatcher_failure(mock_post, sample_case):
    # Mock error response
    mock_response = MagicMock()
    mock_response.status_code = 500
    mock_post.return_value = mock_response

    dispatcher = WebhookNotificationDispatcher("http://localhost/webhook")
    success = dispatcher.send_alert(sample_case)

    assert success is False

def test_email_dispatcher_success(sample_case):
    dispatcher = MockEmailNotificationDispatcher("admin@company.com")
    success = dispatcher.send_alert(sample_case)

    assert success is True
    assert len(dispatcher.sent_emails) == 1
    assert dispatcher.sent_emails[0]["to"] == "admin@company.com"
    assert "Critical Reconciliation Anomaly" in dispatcher.sent_emails[0]["subject"]
    assert "case_test" in dispatcher.sent_emails[0]["body"]
