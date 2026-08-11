---
name: reconciliation-engine
description: Technical design details for 2-way and 3-way matching engine using canonical models.
---

# Reconciliation Engine

Use this skill to maintain, optimize, or extend the core deterministic matching logic in Balancr.

## Key Models (`balancr.canonical`)
- `CanonicalTransaction`: Standardized format for all records. Key attributes: `id`, `amount`, `currency`, `date` (datetime), `reference`, `source`.
- `DiscrepancyCase`: Case created when reconciliation fails deterministically. Contains `transaction_gateway`, `transaction_bank`, `status`, `discrepancy_type`, `explanation`.
- `ReconciliationStatus`: `MATCHED`, `DISCREPANCY`, `UNMATCHED`.
- `DiscrepancyType`: `DUPLICATE`, `TIMING_MISMATCH`, `PARTIAL_AMOUNT`, `MISSING_COUNTERPART`, `UNKNOWN`.

## Reconciliation Matching Engine (`balancr.matching.engine`)
- **2-Way Match (`reconcile`)**: Group by reference. Perfect matches (within exact date tolerance of 1 day) are paired. Timing mismatches within 3 days are recorded as timing discrepancies. Other mismatches (amount, duplicates, orphans) generate discrepancy cases.
- **3-Way Match (`reconcile_3way`)**: Compares Gateway, Bank, and Ledger. Finds 1-1-1 matches, 2-way partial matches (missing Ledger, Bank, or Gateway), and duplicates/orphans.

## Coding Best Practices
- Keep all code comments, docstrings, variable names, and error logs in **English**.
- Do not modify financial matching algorithms without updating both `tests/test_matching.py` and the golden evaluation suite.
