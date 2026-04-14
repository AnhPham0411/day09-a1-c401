"""
workers/retrieval.py — Retrieval Worker
Người 2 (Data Finder) — Sprint 2

Nhiệm vụ:
    Nhận câu hỏi (task) từ AgentState, embed nó, query ChromaDB,
    trả về top-k chunks làm bằng chứng cho các worker sau dùng.

Input (từ AgentState):
    - task          : câu hỏi cần tìm evidence
    - retrieval_top_k: số chunks muốn lấy (mặc định 3)

Output (ghi vào AgentState):
    - retrieved_chunks  : list[{"text", "source", "score", "metadata"}]
    - retrieved_sources : list[str] — tên file nguồn (unique)
    - worker_io_logs    : append 1 log entry

Contract: contracts/worker_contracts.yaml → retrieval_worker section
Test độc lập: python workers/retrieval.py
"""

import os
import sys

# Cho phép chạy độc lập từ thư mục gốc lab/
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# ─── Constants ─────────────────────────────────────────────────────────────────
WORKER_NAME    = "retrieval_worker"
DEFAULT_TOP_K  = 3
CHROMA_PATH    = os.path.join(os.path.dirname(__file__), "..", "chroma_db")
COLLECTION_NAME = "day09_docs"


# ─── Embedding ─────────────────────────────────────────────────────────────────

def _get_embedding_fn():
    """
    Trả về hàm embed(text) -> list[float].

    Thứ tự ưu tiên:
    1. SentenceTransformers (offline, không cần API key) — khuyến nghị cho lab
    2. OpenAI text-embedding-3-small (cần OPENAI_API_KEY trong .env)
    3. Random fallback (CHỈ cho test khi không có gì khác)

    Lý do dùng SentenceTransformers làm mặc định:
    - Không phụ thuộc API key → lab chạy được offline
    - all-MiniLM-L6-v2: nhỏ (80MB), đủ chính xác cho retrieval tiếng Việt
    - Cosine similarity với ChromaDB hoạt động tốt
    """
    # Option A: SentenceTransformers (offline)
    try:
        from sentence_transformers import SentenceTransformer
        _model = SentenceTransformer("all-MiniLM-L6-v2")
        def _embed_st(text: str) -> list:
            return _model.encode([text])[0].tolist()
        return _embed_st
    except ImportError:
        pass

    # Option B: OpenAI (cần API key)
    try:
        from openai import OpenAI
        _api_key = os.getenv("OPENAI_API_KEY", "")
        if _api_key:
            _client = OpenAI(api_key=_api_key)
            def _embed_oai(text: str) -> list:
                resp = _client.embeddings.create(
                    input=text, model="text-embedding-3-small"
                )
                return resp.data[0].embedding
            return _embed_oai
    except ImportError:
        pass

    # Fallback: random (test only — kết quả retrieval sẽ ngẫu nhiên)
    import random
    print("⚠️  [retrieval_worker] WARNING: Dùng random embedding. "
          "Cài sentence-transformers để dùng thật: pip install sentence-transformers")
    def _embed_rand(text: str) -> list:
        random.seed(hash(text) % 2**32)  # seed theo text để nhất quán trong 1 run
        return [random.random() for _ in range(384)]
    return _embed_rand


# ─── ChromaDB Connection ────────────────────────────────────────────────────────

def _get_collection():
    """
    Kết nối ChromaDB và trả về collection day09_docs.

    Nếu collection chưa tồn tại: in cảnh báo và trả về empty collection.
    → Chạy scripts/build_index.py trước để build index.
    """
    try:
        import chromadb
        client = chromadb.PersistentClient(path=CHROMA_PATH)
        collection = client.get_collection(COLLECTION_NAME)
        return collection
    except Exception as e:
        # Collection chưa có hoặc path sai
        print(f"⚠️  [retrieval_worker] ChromaDB không sẵn sàng: {e}")
        print(f"   → Chạy: python scripts/build_index.py")
        return None


# ─── Core Retrieval Logic ───────────────────────────────────────────────────────

def retrieve_dense(query: str, top_k: int = DEFAULT_TOP_K) -> list[dict]:
    """
    Dense retrieval: embed query → cosine similarity search trong ChromaDB.

    Args:
        query : câu hỏi cần tìm evidence
        top_k : số chunks tối đa muốn lấy

    Returns:
        list of dict, mỗi dict gồm:
            - text     : nội dung chunk
            - source   : tên file tài liệu gốc (e.g. "sla_p1_2026.txt")
            - score    : cosine similarity [0.0, 1.0], càng cao càng liên quan
            - metadata : dict thông tin phụ từ ChromaDB

    Contract: nếu không tìm thấy → trả về [] (không bao giờ trả fake chunks)
    """
    embed_fn   = _get_embedding_fn()
    collection = _get_collection()

    # Nếu ChromaDB chưa ready → abstain (trả empty, không hallucinate)
    if collection is None:
        return []

    try:
        query_embedding = embed_fn(query)

        results = collection.query(
            query_embeddings=[query_embedding],
            n_results=min(top_k, collection.count() or 1),
            include=["documents", "distances", "metadatas"],
        )

        chunks = []
        for doc, dist, meta in zip(
            results["documents"][0],
            results["distances"][0],
            results["metadatas"][0],
        ):
            # ChromaDB cosine space: distance = 1 - similarity
            # → similarity = 1 - distance, clamped [0, 1]
            score = round(max(0.0, min(1.0, 1.0 - dist)), 4)

            chunks.append({
                "text"    : doc,
                "source"  : meta.get("source", "unknown"),
                "score"   : score,
                "metadata": meta,
            })

        # Sắp xếp giảm dần theo score (thường đã sorted, nhưng đảm bảo)
        chunks.sort(key=lambda x: x["score"], reverse=True)
        return chunks

    except Exception as e:
        print(f"⚠️  [retrieval_worker] Query failed: {e}")
        return []


# ─── Worker Entry Point ─────────────────────────────────────────────────────────

def run(state: dict) -> dict:
    """
    Entry point được graph.py gọi.

    Đọc state["task"], chạy retrieve_dense(), ghi kết quả vào state.
    Không raise exception ra ngoài — mọi lỗi đều được catch và ghi vào log.

    Args:
        state : AgentState dict (shared state của toàn pipeline)

    Returns:
        state đã được update với:
            - retrieved_chunks  : list of chunk dicts
            - retrieved_sources : list of unique source filenames
            - worker_io_logs    : thêm 1 entry log của worker này
    """
    task  = state.get("task", "")
    top_k = state.get("retrieval_top_k", DEFAULT_TOP_K)

    # Khởi tạo các fields nếu chưa có
    state.setdefault("workers_called", [])
    state.setdefault("history", [])
    state.setdefault("worker_io_logs", [])

    state["workers_called"].append(WORKER_NAME)

    # Chuẩn bị log entry (sẽ fill output/error bên dưới)
    log_entry = {
        "worker" : WORKER_NAME,
        "input"  : {"task": task, "top_k": top_k},
        "output" : None,
        "error"  : None,
    }

    try:
        chunks  = retrieve_dense(task, top_k=top_k)
        sources = list(dict.fromkeys(c["source"] for c in chunks))  # unique, giữ thứ tự

        state["retrieved_chunks"]  = chunks
        state["retrieved_sources"] = sources

        log_entry["output"] = {
            "chunks_count": len(chunks),
            "sources"     : sources,
            "top_score"   : chunks[0]["score"] if chunks else None,
        }

        state["history"].append(
            f"[{WORKER_NAME}] retrieved {len(chunks)} chunks "
            f"from {sources} (top_score={log_entry['output']['top_score']})"
        )

    except Exception as e:
        error_msg = str(e)
        log_entry["error"] = {"code": "RETRIEVAL_FAILED", "reason": error_msg}
        state["retrieved_chunks"]  = []
        state["retrieved_sources"] = []
        state["history"].append(f"[{WORKER_NAME}] ERROR: {error_msg}")

    state["worker_io_logs"].append(log_entry)
    return state


# ─── Standalone Test ────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 55)
    print("  Retrieval Worker — Standalone Test (Người 2)")
    print("=" * 55)

    test_cases = [
        {
            "query": "SLA ticket P1 là bao lâu?",
            "expect_source": "sla_p1_2026.txt",
        },
        {
            "query": "Điều kiện được hoàn tiền flash sale là gì?",
            "expect_source": "policy_refund_v4.txt",
        },
        {
            "query": "Ai phê duyệt cấp quyền Level 3?",
            "expect_source": "access_control_sop.txt",
        },
        {
            "query": "Nhân viên thử việc được làm remote không?",
            "expect_source": "hr_leave_policy.txt",
        },
        {
            "query": "Mật khẩu cần đổi sau bao nhiêu ngày?",
            "expect_source": "it_helpdesk_faq.txt",
        },
    ]

    all_pass = True
    for i, case in enumerate(test_cases, 1):
        print(f"\n[Test {i}] Query: \"{case['query']}\"")
        result = run({"task": case["query"]})

        chunks  = result.get("retrieved_chunks", [])
        sources = result.get("retrieved_sources", [])

        if not chunks:
            print(f"  ❌ Không lấy được chunk nào!")
            all_pass = False
            continue

        # Kiểm tra source mong đợi có trong kết quả không
        found = any(case["expect_source"] in s for s in sources)
        status = "✅" if found else "⚠️ "

        print(f"  {status} Retrieved {len(chunks)} chunks | sources: {sources}")
        print(f"     Top chunk [{chunks[0]['score']:.3f}]: {chunks[0]['text'][:80]}...")

        if not found:
            print(f"  ⚠️  Expected '{case['expect_source']}' trong sources nhưng không thấy.")

    print(f"\n{'='*55}")

    # Kiểm tra worker_io_logs format
    sample_state = run({"task": "test io log format"})
    log = sample_state["worker_io_logs"][-1]
    assert "worker" in log and log["worker"] == WORKER_NAME, "Log thiếu field 'worker'"
    assert "input" in log, "Log thiếu field 'input'"
    assert "output" in log, "Log thiếu field 'output'"
    assert "error" in log, "Log thiếu field 'error'"
    print("  ✅ worker_io_logs format hợp lệ theo contract")

    print(f"\n✅  Retrieval Worker test done.")