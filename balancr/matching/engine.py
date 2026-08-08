from datetime import timedelta, datetime
from typing import List, Tuple, Dict, Set, Optional
import uuid
from balancr.canonical import (
    CanonicalTransaction,
    DiscrepancyCase,
    DiscrepancyType,
    ReconciliationStatus
)

class ReconciliationEngine:
    """
    Deterministic matching engine that compares gateway and bank transactions.
    Resolves exact matches and flags discrepancies for LLM review.
    """
    def __init__(self, exact_date_tolerance_days: int = 1, timing_date_tolerance_days: int = 3):
        self.exact_tolerance = timedelta(days=exact_date_tolerance_days)
        self.timing_tolerance = timedelta(days=timing_date_tolerance_days)

    def reconcile(
        self, 
        gateway_txs: List[CanonicalTransaction], 
        bank_txs: List[CanonicalTransaction]
    ) -> Tuple[List[Tuple[CanonicalTransaction, CanonicalTransaction]], List[DiscrepancyCase]]:
        """
        Reconciles gateway and bank transactions.
        
        Returns:
            A tuple containing:
              - matched_pairs: List of (gateway_tx, bank_tx) tuples
              - discrepancies: List of DiscrepancyCase objects
        """
        matched_pairs: List[Tuple[CanonicalTransaction, CanonicalTransaction]] = []
        discrepancies: List[DiscrepancyCase] = []

        # Group transactions by reference
        gateway_by_ref: Dict[str, List[CanonicalTransaction]] = {}
        for tx in gateway_txs:
            if tx.reference:
                gateway_by_ref.setdefault(tx.reference, []).append(tx)
        
        bank_by_ref: Dict[str, List[CanonicalTransaction]] = {}
        for tx in bank_txs:
            if tx.reference:
                bank_by_ref.setdefault(tx.reference, []).append(tx)

        # Track matched transaction IDs to find orphans
        matched_gateway_ids: Set[str] = set()
        matched_bank_ids: Set[str] = set()

        # Find all unique references
        all_references = set(gateway_by_ref.keys()).union(bank_by_ref.keys())

        for ref in all_references:
            g_list = gateway_by_ref.get(ref, [])
            b_list = bank_by_ref.get(ref, [])

            # Scenario 1: One-to-One Reference Match
            if len(g_list) == 1 and len(b_list) == 1:
                g_tx = g_list[0]
                b_tx = b_list[0]

                # Match by absolute amount to handle bank sign differences (e.g. positive/negative deposits)
                amounts_match = abs(g_tx.amount) == abs(b_tx.amount)
                date_diff = abs(g_tx.date - b_tx.date)

                if amounts_match:
                    if date_diff <= self.exact_tolerance:
                        # Perfect exact match!
                        matched_pairs.append((g_tx, b_tx))
                        matched_gateway_ids.add(g_tx.id)
                        matched_bank_ids.add(b_tx.id)
                    elif date_diff <= self.timing_tolerance:
                        # Timing mismatch (matched amount, but slightly delayed date)
                        discrepancies.append(
                            DiscrepancyCase(
                                id=str(uuid.uuid4()),
                                transaction_gateway=g_tx,
                                transaction_bank=b_tx,
                                status=ReconciliationStatus.DISCREPANCY,
                                discrepancy_type=DiscrepancyType.TIMING_MISMATCH,
                                explanation=f"Timing mismatch: reference matches but date difference is {date_diff.days} days."
                            )
                        )
                        matched_gateway_ids.add(g_tx.id)
                        matched_bank_ids.add(b_tx.id)
                    else:
                        # Exceeds timing tolerance
                        discrepancies.append(
                            DiscrepancyCase(
                                id=str(uuid.uuid4()),
                                transaction_gateway=g_tx,
                                transaction_bank=b_tx,
                                status=ReconciliationStatus.DISCREPANCY,
                                discrepancy_type=DiscrepancyType.TIMING_MISMATCH,
                                explanation=f"Severe timing mismatch: date difference is {date_diff.days} days, exceeding limit."
                            )
                        )
                        matched_gateway_ids.add(g_tx.id)
                        matched_bank_ids.add(b_tx.id)
                else:
                    # Amounts do not match (partial amount discrepancy)
                    discrepancies.append(
                        DiscrepancyCase(
                            id=str(uuid.uuid4()),
                            transaction_gateway=g_tx,
                            transaction_bank=b_tx,
                            status=ReconciliationStatus.DISCREPANCY,
                            discrepancy_type=DiscrepancyType.PARTIAL_AMOUNT,
                            explanation=f"Amount mismatch: gateway shows {g_tx.amount} and bank shows {b_tx.amount}."
                        )
                    )
                    matched_gateway_ids.add(g_tx.id)
                    matched_bank_ids.add(b_tx.id)

            # Scenario 2: Duplicate References (Many-to-One, One-to-Many, Many-to-Many)
            elif len(g_list) > 1 or len(b_list) > 1:
                # Mark all as duplicate discrepancies for LLM agent investigation
                # We group them together in a single case or create individual cases
                explanation = f"Duplicate references found: {len(g_list)} in gateway, {len(b_list)} in bank."
                
                # We pair them if possible or create individual cases
                for g_tx in g_list:
                    matched_gateway_ids.add(g_tx.id)
                for b_tx in b_list:
                    matched_bank_ids.add(b_tx.id)

                discrepancies.append(
                    DiscrepancyCase(
                        id=str(uuid.uuid4()),
                        transaction_gateway=g_list[0] if g_list else None,
                        transaction_bank=b_list[0] if b_list else None,
                        status=ReconciliationStatus.DISCREPANCY,
                        discrepancy_type=DiscrepancyType.DUPLICATE,
                        explanation=f"{explanation} Gateway transaction ID: {g_list[0].id if g_list else 'N/A'}, Bank transaction ID: {b_list[0].id if b_list else 'N/A'}."
                    )
                )

        # Scenario 3: Orphan Transactions (Missing counterparts)
        for g_tx in gateway_txs:
            if g_tx.id not in matched_gateway_ids:
                discrepancies.append(
                    DiscrepancyCase(
                        id=str(uuid.uuid4()),
                        transaction_gateway=g_tx,
                        transaction_bank=None,
                        status=ReconciliationStatus.UNMATCHED,
                        discrepancy_type=DiscrepancyType.MISSING_COUNTERPART,
                        explanation=f"Gateway transaction has no bank counterpart."
                    )
                )

        for b_tx in bank_txs:
            if b_tx.id not in matched_bank_ids:
                discrepancies.append(
                    DiscrepancyCase(
                        id=str(uuid.uuid4()),
                        transaction_gateway=None,
                        transaction_bank=b_tx,
                        status=ReconciliationStatus.UNMATCHED,
                        discrepancy_type=DiscrepancyType.MISSING_COUNTERPART,
                        explanation=f"Bank transaction has no gateway counterpart."
                    )
                )

        return matched_pairs, discrepancies

    def reconcile_3way(
        self, 
        gateway_txs: List[CanonicalTransaction], 
        bank_txs: List[CanonicalTransaction],
        ledger_txs: List[CanonicalTransaction]
    ) -> Tuple[List[Tuple[CanonicalTransaction, CanonicalTransaction, CanonicalTransaction]], List[DiscrepancyCase]]:
        """
        Performs three-way reconciliation between gateway, bank, and internal ledger records.
        """
        matched_3way: List[Tuple[CanonicalTransaction, CanonicalTransaction, CanonicalTransaction]] = []
        discrepancies: List[DiscrepancyCase] = []

        # Group transactions by reference
        gateway_by_ref: Dict[str, List[CanonicalTransaction]] = {}
        for tx in gateway_txs:
            if tx.reference:
                gateway_by_ref.setdefault(tx.reference, []).append(tx)
        
        bank_by_ref: Dict[str, List[CanonicalTransaction]] = {}
        for tx in bank_txs:
            if tx.reference:
                bank_by_ref.setdefault(tx.reference, []).append(tx)

        ledger_by_ref: Dict[str, List[CanonicalTransaction]] = {}
        for tx in ledger_txs:
            if tx.reference:
                ledger_by_ref.setdefault(tx.reference, []).append(tx)

        # Track matched transaction IDs to find orphans
        matched_gateway_ids: Set[str] = set()
        matched_bank_ids: Set[str] = set()
        matched_ledger_ids: Set[str] = set()

        all_references = set(gateway_by_ref.keys()).union(bank_by_ref.keys()).union(ledger_by_ref.keys())

        for ref in all_references:
            g_list = gateway_by_ref.get(ref, [])
            b_list = bank_by_ref.get(ref, [])
            l_list = ledger_by_ref.get(ref, [])

            # Perfect 1-1-1 Match
            if len(g_list) == 1 and len(b_list) == 1 and len(l_list) == 1:
                g_tx = g_list[0]
                b_tx = b_list[0]
                l_tx = l_list[0]

                amounts_match = abs(g_tx.amount) == abs(b_tx.amount) == abs(l_tx.amount)
                diff_gb = abs(g_tx.date - b_tx.date)
                diff_gl = abs(g_tx.date - l_tx.date)
                diff_bl = abs(b_tx.date - l_tx.date)

                if amounts_match:
                    if diff_gb <= self.exact_tolerance and diff_gl <= self.exact_tolerance and diff_bl <= self.exact_tolerance:
                        matched_3way.append((g_tx, b_tx, l_tx))
                        matched_gateway_ids.add(g_tx.id)
                        matched_bank_ids.add(b_tx.id)
                        matched_ledger_ids.add(l_tx.id)
                    else:
                        # Timing Mismatch in at least one connection
                        discrepancies.append(
                            DiscrepancyCase(
                                id=str(uuid.uuid4()),
                                transaction_gateway=g_tx,
                                transaction_bank=b_tx,
                                status=ReconciliationStatus.DISCREPANCY,
                                discrepancy_type=DiscrepancyType.TIMING_MISMATCH,
                                explanation=f"Timing mismatch: date differences are GB={diff_gb.days}d, GL={diff_gl.days}d, BL={diff_bl.days}d."
                            )
                        )
                        matched_gateway_ids.add(g_tx.id)
                        matched_bank_ids.add(b_tx.id)
                        matched_ledger_ids.add(l_tx.id)
                else:
                    # Amount mismatch in three-way comparison
                    discrepancies.append(
                        DiscrepancyCase(
                            id=str(uuid.uuid4()),
                            transaction_gateway=g_tx,
                            transaction_bank=b_tx,
                            status=ReconciliationStatus.DISCREPANCY,
                            discrepancy_type=DiscrepancyType.PARTIAL_AMOUNT,
                            explanation=f"Amount mismatch: Gateway={g_tx.amount}, Bank={b_tx.amount}, Ledger={l_tx.amount}."
                        )
                    )
                    matched_gateway_ids.add(g_tx.id)
                    matched_bank_ids.add(b_tx.id)
                    matched_ledger_ids.add(l_tx.id)

            # 2-Way Match: Gateway + Bank, missing Ledger
            elif len(g_list) == 1 and len(b_list) == 1 and len(l_list) == 0:
                g_tx = g_list[0]
                b_tx = b_list[0]
                amounts_match = abs(g_tx.amount) == abs(b_tx.amount)
                
                exp = "Gateway-Bank match found, but missing counterpart in Ledger DB."
                if not amounts_match:
                    exp = f"Gateway-Bank reference match, but amounts differ (G={g_tx.amount}, B={b_tx.amount}) and missing Ledger counterpart."
                
                discrepancies.append(
                    DiscrepancyCase(
                        id=str(uuid.uuid4()),
                        transaction_gateway=g_tx,
                        transaction_bank=b_tx,
                        status=ReconciliationStatus.DISCREPANCY,
                        discrepancy_type=DiscrepancyType.PARTIAL_AMOUNT if not amounts_match else DiscrepancyType.MISSING_COUNTERPART,
                        explanation=exp
                    )
                )
                matched_gateway_ids.add(g_tx.id)
                matched_bank_ids.add(b_tx.id)

            # 2-Way Match: Gateway + Ledger, missing Bank
            elif len(g_list) == 1 and len(l_list) == 1 and len(b_list) == 0:
                g_tx = g_list[0]
                l_tx = l_list[0]
                amounts_match = abs(g_tx.amount) == abs(l_tx.amount)
                
                exp = f"Gateway-Ledger match found (Ledger ID: {l_tx.id}), but missing counterpart in Bank statement."
                if not amounts_match:
                    exp = f"Gateway-Ledger reference match, but amounts differ (G={g_tx.amount}, L={l_tx.amount}) and missing Bank counterpart."
                    
                discrepancies.append(
                    DiscrepancyCase(
                        id=str(uuid.uuid4()),
                        transaction_gateway=g_tx,
                        transaction_bank=None,
                        status=ReconciliationStatus.DISCREPANCY,
                        discrepancy_type=DiscrepancyType.PARTIAL_AMOUNT if not amounts_match else DiscrepancyType.MISSING_COUNTERPART,
                        explanation=exp
                    )
                )
                matched_gateway_ids.add(g_tx.id)
                matched_ledger_ids.add(l_tx.id)

            # 2-Way Match: Bank + Ledger, missing Gateway
            elif len(b_list) == 1 and len(l_list) == 1 and len(g_list) == 0:
                b_tx = b_list[0]
                l_tx = l_list[0]
                amounts_match = abs(b_tx.amount) == abs(l_tx.amount)
                
                exp = f"Bank-Ledger match found (Ledger ID: {l_tx.id}), but missing counterpart in Gateway."
                if not amounts_match:
                    exp = f"Bank-Ledger reference match, but amounts differ (B={b_tx.amount}, L={l_tx.amount}) and missing Gateway counterpart."
                    
                discrepancies.append(
                    DiscrepancyCase(
                        id=str(uuid.uuid4()),
                        transaction_gateway=None,
                        transaction_bank=b_tx,
                        status=ReconciliationStatus.DISCREPANCY,
                        discrepancy_type=DiscrepancyType.PARTIAL_AMOUNT if not amounts_match else DiscrepancyType.MISSING_COUNTERPART,
                        explanation=exp
                    )
                )
                matched_bank_ids.add(b_tx.id)
                matched_ledger_ids.add(l_tx.id)

        return matched_3way, discrepancies
