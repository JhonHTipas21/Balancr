from abc import ABC, abstractmethod
from typing import List
from balancr.canonical import CanonicalTransaction

class TransactionSource(ABC):
    """
    Abstract Base Class defining the contract for all transaction sources.
    Every source (gateway, bank, ledger) must implement this interface to 
    normalize its raw inputs into CanonicalTransaction records.
    """
    @abstractmethod
    def load_transactions(self) -> List[CanonicalTransaction]:
        """
        Reads, parses, and converts raw transactions into a list of CanonicalTransaction objects.
        """
        pass
