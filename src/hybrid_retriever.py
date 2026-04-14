import os
from typing import List, Dict, Any
import chromadb
from sentence_transformers import SentenceTransformer
from rank_bm25 import BM25Okapi

from src.data_processor import load_and_process_all_docs

class HybridRetriever:
    def __init__(self, db_path: str = "./chroma_db", collection_name: str = "day09_hybrid"):
        # Load embedding model
        self.encoder = SentenceTransformer("all-MiniLM-L6-v2")
        
        # Init ChromaDB
        self.chroma_client = chromadb.PersistentClient(path=db_path)
        self.collection = self.chroma_client.get_or_create_collection(collection_name)
        
        # Prepare docs for BM25 and Chroma
        docs = load_and_process_all_docs()
        
        self.doc_store = {}
        self.domain_indices = {"IT": [], "HR": [], "CS": []}
        bm25_corpus = []
        
        # Check if collection is empty
        needs_indexing = self.collection.count() == 0
        
        vector_ids = []
        vector_embeddings = []
        vector_metadatas = []
        vector_documents = []
        
        for i, doc in enumerate(docs):
            doc_id = f"doc_{i}"
            self.doc_store[doc_id] = doc
            domain = doc.metadata.get("domain", "IT")
            if domain in self.domain_indices:
                self.domain_indices[domain].append(doc_id)
                
            # Tokens for BM25
            tokenized_content = doc.page_content.lower().split()
            bm25_corpus.append(tokenized_content)
            
            if needs_indexing:
                vector_ids.append(doc_id)
                vector_metadatas.append(doc.metadata)
                vector_documents.append(doc.page_content)
                
        # Fit BM25
        if bm25_corpus:
            self.bm25 = BM25Okapi(bm25_corpus)
        else:
            self.bm25 = None
            
        if needs_indexing and vector_documents:
            print("Generating embeddings for vector store...")
            embeddings = self.encoder.encode(vector_documents).tolist()
            self.collection.add(
                ids=vector_ids,
                embeddings=embeddings,
                metadatas=vector_metadatas,
                documents=vector_documents
            )
            print("Vector store indexing complete.")
            
    def _rrf_score(self, rank: int, k: int = 60) -> float:
        return 1.0 / (k + rank)

    def search(self, query: str, domain: str, top_k: int = 3) -> List[Dict[str, Any]]:
        # Dense Search
        query_emb = self.encoder.encode([query]).tolist()
        chroma_res = self.collection.query(
            query_embeddings=query_emb,
            n_results=top_k * 2, 
            where={"domain": domain}
        )
        
        dense_results = {}
        if chroma_res["ids"] and chroma_res["ids"][0]:
            for rank, doc_id in enumerate(chroma_res["ids"][0]):
                dense_results[doc_id] = rank + 1
                
        # Sparse Search (BM25)
        sparse_results = {}
        if self.bm25:
            tokenized_query = query.lower().split()
            doc_scores = self.bm25.get_scores(tokenized_query)
            
            domain_doc_ids = self.domain_indices.get(domain, [])
            
            filtered_scores = []
            for doc_id in domain_doc_ids:
                idx = int(doc_id.split('_')[1])
                filtered_scores.append((doc_id, doc_scores[idx]))
                
            filtered_scores.sort(key=lambda x: x[1], reverse=True)
            for rank, (doc_id, score) in enumerate(filtered_scores[:top_k * 2]):
                if score > 0: 
                    sparse_results[doc_id] = rank + 1
                    
        # Fusion RRF
        fused_scores = {}
        all_candidate_ids = set(list(dense_results.keys()) + list(sparse_results.keys()))
        
        for doc_id in all_candidate_ids:
            score = 0.0
            if doc_id in dense_results:
                score += self._rrf_score(dense_results[doc_id])
            if doc_id in sparse_results:
                score += self._rrf_score(sparse_results[doc_id])
            fused_scores[doc_id] = score
            
        sorted_results = sorted(fused_scores.items(), key=lambda x: x[1], reverse=True)
        
        final_docs = []
        for doc_id, score in sorted_results[:top_k]:
            doc_obj = self.doc_store[doc_id]
            final_docs.append({
                "content": doc_obj.page_content,
                "metadata": doc_obj.metadata,
                "score": score
            })
            
        return final_docs

if __name__ == "__main__":
    retriever = HybridRetriever()
    print("--- Test IT Domain Query ---")
    res_it = retriever.search("SLA ticket P1 là bao lâu?", "IT")
    for r in res_it:
        print(f">> [Score: {r['score']:.4f}] {r['metadata']['source_file']} | {r['metadata'].get('section_name', '')}")
        print(f"Content: {r['content'][:80]}...\n")
        
    print("--- Test HR Domain Query ---")
    res_hr = retriever.search("Xin nghỉ phép thai sản như thế nào?", "HR")
    for r in res_hr:
        print(f">> [Score: {r['score']:.4f}] {r['metadata']['source_file']} | {r['metadata'].get('section_name', '')}")
        print(f"Content: {r['content'][:80]}...\n")
