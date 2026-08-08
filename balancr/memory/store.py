import os
import hashlib
from typing import List, Dict, Any, Optional
import chromadb
from chromadb.api.types import Documents, Embeddings
from balancr.canonical import DiscrepancyCase

class SimpleHashEmbeddingFunction:
    """
    100% offline, lightweight hashing-based embedding function.
    Eliminates downloading heavy models from Hugging Face during test/runs.
    """
    def __call__(self, input: Documents) -> Embeddings:
        embeddings = []
        for doc in input:
            words = doc.lower().split()
            vec = [0.0] * 128
            for w in words:
                h = int(hashlib.md5(w.encode('utf-8')).hexdigest(), 16)
                idx = h % 128
                vec[idx] += 1.0
            norm = sum(x**2 for x in vec)**0.5
            if norm > 0:
                vec = [x / norm for x in vec]
            embeddings.append(vec)
        return embeddings

class ReconciliationMemory:
    """
    Interface to local ChromaDB for persisting and querying resolved reconciliation cases.
    """
    def __init__(self, persist_dir: str = "./chroma_data"):
        self.client = chromadb.PersistentClient(path=persist_dir)
        self.collection = self.client.get_or_create_collection(
            name="resolved_discrepancies",
            embedding_function=SimpleHashEmbeddingFunction()
        )


    def add_resolved_case(self, case: DiscrepancyCase) -> None:
        """
        Indexes a resolved discrepancy case in ChromaDB.
        """
        g_ref = case.transaction_gateway.reference if case.transaction_gateway else "N/A"
        b_ref = case.transaction_bank.reference if case.transaction_bank else "N/A"
        
        # Build text document for embedding generation
        doc = (
            f"Case resolution description: {case.explanation}\n"
            f"Category: {case.discrepancy_type.value if case.discrepancy_type else 'UNKNOWN'}\n"
            f"Gateway Reference: {g_ref}\n"
            f"Bank Reference: {b_ref}"
        )
        
        # Build metadata for filtering and few-shot formatting
        metadata = {
            "discrepancy_type": case.discrepancy_type.value if case.discrepancy_type else "UNKNOWN",
            "explanation": case.explanation or "",
            "gateway_id": case.transaction_gateway.id if case.transaction_gateway else "N/A",
            "bank_id": case.transaction_bank.id if case.transaction_bank else "N/A",
        }
        
        self.collection.upsert(
            ids=[case.id],
            documents=[doc],
            metadatas=[metadata]
        )

    def find_similar_cases(self, query_text: str, n_results: int = 2) -> List[Dict[str, Any]]:
        """
        Retrieves similar cases from memory based on query similarity.
        """
        # If the collection is empty, return early
        if self.collection.count() == 0:
            return []

        results = self.collection.query(
            query_texts=[query_text],
            n_results=min(n_results, self.collection.count())
        )
        
        cases = []
        if results and "metadatas" in results and results["metadatas"]:
            for meta_list in results["metadatas"]:
                for m in meta_list:
                    cases.append(m)
        return cases

# Singleton instance reference
_memory_store: Optional[ReconciliationMemory] = None

def get_memory_store(persist_dir: str = "./chroma_data") -> ReconciliationMemory:
    """
    Retrieves the global ReconciliationMemory singleton instance.
    """
    global _memory_store
    if _memory_store is None:
        _memory_store = ReconciliationMemory(persist_dir)
    return _memory_store
