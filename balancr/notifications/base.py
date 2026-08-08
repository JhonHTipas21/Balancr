from abc import ABC, abstractmethod
from balancr.canonical import DiscrepancyCase

class NotificationDispatcher(ABC):
    """
    Abstract Base Class defining the interface for alert dispatchers.
    Dispatches alerts (e.g. webhooks, mock emails) when critical discrepancies are found.
    """
    @abstractmethod
    def send_alert(self, case: DiscrepancyCase) -> bool:
        """
        Sends an alert containing transaction details and LLM classification.
        
        Args:
            case: The DiscrepancyCase details.
            
        Returns:
            bool: True if alert successfully dispatched, False otherwise.
        """
        pass
