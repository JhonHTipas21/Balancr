import pandas as pd
from typing import List, Dict, Optional
from datetime import datetime
from balancr.canonical import CanonicalTransaction
from balancr.normalizers.base import TransactionSource

class LedgerDBSource(TransactionSource):
    """
    Adapter to parse internal ledger database transaction outputs from a CSV file.
    """
    def __init__(self, file_path: str, col_mapping: Optional[Dict[str, str]] = None):
        """
        Args:
            file_path: Absolute path to the CSV file.
            col_mapping: Dict mapping canonical field names to CSV header names.
                         Canonical fields: id, amount, currency, date, reference.
        """
        self.file_path = file_path
        self.col_mapping = col_mapping or {
            "id": "ledger_tx_id",
            "amount": "amount",
            "currency": "currency",
            "date": "recorded_at",
            "reference": "order_reference"
        }

    def load_transactions(self) -> List[CanonicalTransaction]:
        transactions = []
        try:
            df = pd.read_csv(self.file_path)
        except Exception as e:
            raise ValueError(f"Failed to read Ledger CSV file at {self.file_path}: {e}")

        # Check required columns
        for canonical_key, csv_header in self.col_mapping.items():
            if csv_header not in df.columns:
                raise ValueError(f"Required header '{csv_header}' for canonical field '{canonical_key}' not found in Ledger CSV.")

        for _, row in df.iterrows():
            raw_data = row.to_dict()
            
            tx_id = str(row[self.col_mapping["id"]])
            
            raw_amount = row[self.col_mapping["amount"]]
            if isinstance(raw_amount, str):
                raw_amount = raw_amount.replace("$", "").replace(",", "").strip()
            amount = float(raw_amount)
            
            currency = str(row[self.col_mapping["currency"]]).upper()
            
            raw_date = row[self.col_mapping["date"]]
            if isinstance(raw_date, datetime):
                dt = raw_date
            else:
                try:
                    dt = pd.to_datetime(raw_date).to_pydatetime()
                except Exception as e:
                    raise ValueError(f"Error parsing ledger date '{raw_date}' in row {tx_id}: {e}")
            
            raw_ref = row[self.col_mapping["reference"]]
            reference = str(raw_ref) if not pd.isna(raw_ref) else ""
            
            transactions.append(
                CanonicalTransaction(
                    id=tx_id,
                    amount=amount,
                    currency=currency,
                    date=dt,
                    reference=reference,
                    source="ledger",
                    raw_payload=raw_data
                )
            )
        return transactions
