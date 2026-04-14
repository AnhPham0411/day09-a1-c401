"""
workers/retrieval.py — Retrieval Worker
Role: Data Finder — tìm bằng chứng từ kho tài liệu

Contract: contracts/worker_contracts.yaml → retrieval_worker
Test độc lập: python workers/retrieval.py

═══════════════════════════════════════════════════════════
INPUT  (đọc từ AgentState — chỉ những fields này):
    state['task']                    : str  — câu hỏi cần tìm evidence
    state.get('retrieval_top_k', 3)  : int  — số chunks muốn lấy

OUTPUT (ghi vào AgentState — chỉ những fields này):
    state['retrieved_chunks']        : list[ChunkDict]  — kết quả retrieval
    state['retrieved_sources']       : list[str]        — unique file names
    state['workers_called']          : append 'retrieval_worker'
    state['worker_io_logs']          : append 1 LogEntry
    state['history']                 : append 1 summary string

ChunkDict schema (theo contract):
    {
        "text"    : str,        — nội dung chunk
        "source"  : str,        — tên file, KHÔNG BAO GIỜ null (dùng 'unknown')
        "score"   : float,      — similarity [0.0, 1.0], 4 chữ số thập phân
        "metadata": dict,       — metadata từ ChromaDB, KHÔNG BAO GIỜ null (dùng {})
    }

LogEntry schema (theo contract):
    {
        "worker" : "retrieval_worker",
        "input"  : {"task": str, "top_k": int},
        "output" : {"chunks_count": int, "sources": list, "top_score": float|null}
                   | null  (nếu exception xảy ra trước khi có kết quả),
        "error"  : {"code": str, "reason": str}
                   | null  (nếu thành công),
    }
    Invariant: output và error KHÔNG BAO GIỜ đều là null cùng lúc.

Constraints bất biến (từ contract):
    1. retrieved_chunks KHÔNG chứa fake chunks — rỗng là hợp lệ
    2. score luôn trong [0.0, 1.0] — KHÔNG phải raw distance
    3. chunk['source'] KHÔNG BAO GIỜ null
    4. chunk['metadata'] KHÔNG BAO GIỜ null
    5. run() KHÔNG BAO GIỜ raise exception ra ngoài
    6. Stateless — không lưu gì giữa các lần gọi
═══════════════════════════════════════════════════════════
"""

import os
import sys

# Cho phép chạy độc lập từ thư mục gốc lab/
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# ─── Constants (phải khớp với infrastructure section trong contract YAML) ──────

WORKER_NAME     = "retrieval_worker"   # contract: retrieval_worker.name
DEFAULT_TOP_K   = 3                    # contract: retrieval_top_k.default
TOP_K_MIN       = 1                    # contract: retrieval_top_k.min
TOP_K_MAX       = 10                   # contract: retrieval_top_k.max
CHROMA_PATH     = os.path.join(os.path.dirname(__file__), "..", "chroma_db")
COLLECTION_NAME = "day09_docs"         # contract: infrastructure.vector_store.collection_name

# Error codes (contract: log_entry.error.code enum)
ERR_RETRIEVAL_FAILED  = "RETRIEVAL_FAILED"
ERR_EMPTY_TASK        = "EMPTY_TASK"
ERR_CHROMA_UNAVAILABLE = "CHROMA_UNAVAILABLE"

from dotenv import load_dotenv
load_dotenv()  # load .env từ thư mục gốc

# ─── Embedding (Priority 1→2→3 theo contract infrastructure.embedding) ────────
def _get_embedding_fn():
    """
    Thứ tự ưu tiên (theo contract infrastructure.embedding):
        Priority 1: openai/text-embedding-3-small (dim=1536) — khớp index hiện có
        Priority 2: sentence-transformers/all-MiniLM-L6-v2 (dim=384) — cần rebuild index
        Priority 3: random float[1536] seeded by hash(text) — CHỈ test I/O contract
    """
    # Priority 1 — OpenAI (khớp với index 1536 chiều đã build)
    try:
        from openai import OpenAI
        api_key = os.getenv("OPENAI_API_KEY", "")
        if api_key:
            client = OpenAI(api_key=api_key)
            print("[retrieval_worker] Embedding: openai/text-embedding-3-small (dim=1536) ✓")
            def _embed(text: str) -> list:
                resp = client.embeddings.create(
                    input=text,
                    model="text-embedding-3-small",
                )
                return resp.data[0].embedding
            return _embed
        else:
            print("⚠️  [retrieval_worker] OPENAI_API_KEY không có — thử Priority 2")
    except ImportError:
        print("⚠️  [retrieval_worker] openai chưa cài — thử Priority 2")

    # Priority 2 — sentence-transformers (dim=384 — KHÔNG khớp index hiện tại)
    try:
        from sentence_transformers import SentenceTransformer
        model = SentenceTransformer("all-MiniLM-L6-v2")
        print(
            "⚠️  [retrieval_worker] Embedding: sentence-transformers (dim=384)\n"
            "   CẢNH BÁO: Index hiện tại dim=1536 — query sẽ fail!\n"
            "   Để fix: rebuild index bằng sentence-transformers"
        )
        def _embed(text: str) -> list:
            return model.encode([text])[0].tolist()
        return _embed
    except ImportError:
        pass

    # Priority 3 — random fallback dim=1536 (khớp collection để không lỗi dimension)
    import random
    print(
        "⚠️  [retrieval_worker] WARNING: Dùng random embedding (Priority 3, dim=1536).\n"
        "   Kết quả retrieval sẽ vô nghĩa — chỉ dùng để test I/O contract."
    )
    def _embed(text: str) -> list:
        rng = random.Random(hash(text) % (2**32))
        return [rng.random() for _ in range(1536)]   # ← 1536 để khớp collection
    return _embed

# ─── ChromaDB Connection ───────────────────────────────────────────────────────

def _get_collection():
    """
    Kết nối ChromaDB, trả về collection hoặc None.

    Trả về None (không raise) khi:
    - chromadb chưa cài
    - chroma_db path chưa tồn tại
    - collection chưa được build

    Caller phải kiểm tra None trước khi dùng.
    """
    try:
        import chromadb
        client = chromadb.PersistentClient(path=CHROMA_PATH)
        collection = client.get_collection(COLLECTION_NAME)
        return collection
    except Exception as e:
        print(f"⚠️  [retrieval_worker] ChromaDB không sẵn sàng: {e}")
        print("   → Chạy: python index.py để build trước")
        return None


# ─── Score Conversion (contract: score_formula) ───────────────────────────────

def _distance_to_score(cosine_distance: float) -> float:
    """
    Convert ChromaDB cosine distance → similarity score.

    ChromaDB dùng cosine distance space: distance = 1 - similarity
    Contract: score = round(max(0.0, min(1.0, 1.0 - cosine_distance)), 4)

    Tại sao clamp về [0, 1]?
    - Lý thuyết: similarity ∈ [-1, 1], distance ∈ [0, 2]
    - Thực tế với normalized vectors: similarity ∈ [0, 1]
    - Clamp để đảm bảo contract dù có edge cases float precision
    """
    return round(max(0.0, min(1.0, 1.0 - cosine_distance)), 4)


# ─── Core Retrieval ────────────────────────────────────────────────────────────

def retrieve_dense(query: str, top_k: int = DEFAULT_TOP_K) -> list[dict]:
    """
    Dense retrieval: embed query → query ChromaDB → trả về top-k chunks.

    Args:
        query  : câu hỏi cần tìm evidence
        top_k  : số chunks tối đa (clamped về [TOP_K_MIN, TOP_K_MAX])

    Returns:
        list[ChunkDict] — sắp xếp giảm dần theo score.
        Trả về [] nếu ChromaDB chưa sẵn sàng hoặc query fail.
        KHÔNG BAO GIỜ trả fake chunks.

    Contract invariants được enforce ở đây:
        - source: dùng 'unknown' nếu metadata thiếu field 'source'
        - metadata: dùng {} nếu ChromaDB trả None
        - score: convert distance → similarity, clamp [0.0, 1.0]
        - sort: chunks[0] là chunk liên quan nhất
    """
    # Clamp top_k về range hợp lệ (theo contract)
    top_k = max(TOP_K_MIN, min(TOP_K_MAX, top_k))

    collection = _get_collection()
    if collection is None:
        return []  # contract: CHROMA_UNAVAILABLE → trả [] không fake

    try:
        embed_fn = _get_embedding_fn()
        query_embedding = embed_fn(query)

        n_results = min(top_k, collection.count() or 1)  # contract: chroma_config.n_results_formula
        results = collection.query(
            query_embeddings=[query_embedding],
            n_results=n_results,
            include=["documents", "distances", "metadatas"],  # contract: chroma_config.query_include
        )

        chunks = []
        for doc, dist, meta in zip(
            results["documents"][0],
            results["distances"][0],
            results["metadatas"][0],
        ):
            # Enforce contract invariants cho từng chunk
            chunks.append({
                "text"    : doc,
                "source"  : (meta or {}).get("source") or "unknown",  # KHÔNG BAO GIỜ null
                "score"   : _distance_to_score(dist),                  # [0.0, 1.0], 4 decimals
                "metadata": meta if meta is not None else {},          # KHÔNG BAO GIỜ null
            })

        # Contract: sắp xếp giảm dần theo score
        chunks.sort(key=lambda c: c["score"], reverse=True)
        return chunks

    except Exception as e:
        print(f"⚠️  [retrieval_worker] Query failed: {e}")
        return []


# ─── Worker Entry Point ────────────────────────────────────────────────────────

def run(state: dict) -> dict:
    """
    Entry point được graph.py gọi.

    Đọc state theo contract input section.
    Ghi state theo contract output section.
    KHÔNG BAO GIỜ raise exception ra ngoài.

    Args:
        state : AgentState dict (shared state toàn pipeline)

    Returns:
        state đã được update (cùng object, không phải copy mới)
    """
    # ── Đọc input (chỉ đọc fields được khai báo trong contract) ──────────────
    task  = state.get("task", "")
    top_k = state.get("retrieval_top_k", DEFAULT_TOP_K)

    # ── Initialize shared tracking fields nếu chưa có ────────────────────────
    # Contract: state_mutations.initializes_if_missing
    state.setdefault("workers_called", [])
    state.setdefault("history", [])
    state.setdefault("worker_io_logs", [])

    # Ghi tên worker vào tracking list
    state["workers_called"].append(WORKER_NAME)

    # ── Chuẩn bị log entry (sẽ fill output/error bên dưới) ───────────────────
    # Contract: log_entry phải có đủ 4 fields: worker, input, output, error
    log_entry = {
        "worker": WORKER_NAME,
        "input" : {"task": task, "top_k": top_k},
        "output": None,   # sẽ fill nếu thành công
        "error" : None,   # sẽ fill nếu có lỗi
    }

    # ── Guard: task rỗng → abstain sớm (contract: EMPTY_TASK) ────────────────
    if not task or not task.strip():
        log_entry["error"] = {
            "code"  : ERR_EMPTY_TASK,
            "reason": "task rỗng hoặc chỉ có whitespace",
        }
        state["retrieved_chunks"]  = []
        state["retrieved_sources"] = []
        state["history"].append(f"[{WORKER_NAME}] ABSTAIN: task rỗng")
        state["worker_io_logs"].append(log_entry)
        return state

    # ── Core retrieval ────────────────────────────────────────────────────────
    try:
        chunks = retrieve_dense(task, top_k=top_k)

        # Contract: retrieved_sources = unique list, giữ thứ tự xuất hiện
        sources = list(dict.fromkeys(c["source"] for c in chunks))

        # ── Ghi output fields (chỉ những fields được khai báo) ───────────────
        state["retrieved_chunks"]  = chunks
        state["retrieved_sources"] = sources

        # Fill log entry — success path
        # Contract: output != null khi thành công, error = null
        log_entry["output"] = {
            "chunks_count": len(chunks),
            "sources"     : sources,
            "top_score"   : chunks[0]["score"] if chunks else None,
        }

        state["history"].append(
            f"[{WORKER_NAME}] retrieved {len(chunks)} chunks "
            f"from {sources} "
            f"(top_score={log_entry['output']['top_score']})"
        )

    except Exception as e:
        # Contract: run() KHÔNG BAO GIỜ raise — mọi lỗi catch ở đây
        # Contract: Invariant: khi error != null thì output = null
        log_entry["error"] = {
            "code"  : ERR_RETRIEVAL_FAILED,
            "reason": str(e),
        }
        state["retrieved_chunks"]  = []
        state["retrieved_sources"] = []
        state["history"].append(f"[{WORKER_NAME}] ERROR ({ERR_RETRIEVAL_FAILED}): {e}")

    # ── Append log entry (luôn append, dù success hay error) ─────────────────
    state["worker_io_logs"].append(log_entry)
    return state


# ─── Standalone Test ───────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 60)
    print("  Retrieval Worker — Standalone Test")
    print("  Contract: contracts/worker_contracts.yaml → retrieval_worker")
    print("=" * 60)

    # Test cases từ contract (retrieval_worker.test_cases)
    TEST_CASES = [
    {"id": "TC-R01", "query": "SLA ticket P1 là bao lâu?",                 "expect": "sla-p1-2026.pdf"},
    {"id": "TC-R02", "query": "Điều kiện được hoàn tiền flash sale là gì?", "expect": "refund-v4.pdf"},
    {"id": "TC-R03", "query": "Ai phê duyệt cấp quyền Level 3?",            "expect": "access-control-sop.md"},
    {"id": "TC-R04", "query": "Nhân viên thử việc được làm remote không?",  "expect": "leave-policy-2026.pdf"},
    {"id": "TC-R05", "query": "Mật khẩu cần đổi sau bao nhiêu ngày?",       "expect": "helpdesk-faq.md"},
    ]

    print("\n── [A] Domain Test Cases (từ contract test_cases) ──────────────")
    for case in TEST_CASES:
        print(f"\n  [{case['id']}] Query: \"{case['query']}\"")
        result = run({"task": case["query"]})

        chunks  = result.get("retrieved_chunks", [])
        sources = result.get("retrieved_sources", [])

        if not chunks:
            print(f"   Không lấy được chunk nào — ChromaDB chưa sẵn sàng?")
            continue

        found  = any(case["expect"] in s for s in sources)
        status = "✅" if found else "⚠️ "
        print(f"  {status} {len(chunks)} chunks | sources: {sources}")
        print(f"     Top chunk [score={chunks[0]['score']:.4f}]: {chunks[0]['text'][:80]}...")
        if not found:
            print(f"  ⚠️  Expected '{case['expect']}' trong sources nhưng không thấy")

    # ── Contract Invariant Tests ──────────────────────────────────────────────
    print("\n── [B] Contract Invariant Tests ────────────────────────────────")

    # B1: worker_io_logs format
    s = run({"task": "test log format"})
    log = s["worker_io_logs"][-1]
    assert "worker" in log and log["worker"] == WORKER_NAME, " log thiếu field 'worker'"
    assert "input"  in log, " log thiếu field 'input'"
    assert "output" in log, " log thiếu field 'output'"
    assert "error"  in log, " log thiếu field 'error'"
    # Invariant: không được cả output lẫn error đều là null
    assert not (log["output"] is None and log["error"] is None), \
        " VIOLATED: output và error không được đều là null"
    print("  ✅ B1: worker_io_logs format hợp lệ")

    # B2: EMPTY_TASK guard
    s2 = run({"task": ""})
    assert s2["retrieved_chunks"] == [], " task rỗng phải trả chunks=[]"
    log2 = s2["worker_io_logs"][-1]
    assert log2["error"] is not None,            " task rỗng phải có error"
    assert log2["error"]["code"] == ERR_EMPTY_TASK, " error code sai"
    assert log2["output"] is None,               " task rỗng phải có output=null"
    print("  ✅ B2: EMPTY_TASK guard hoạt động đúng")

    # B3: workers_called được append
    s3 = run({"task": "test workers_called"})
    assert WORKER_NAME in s3["workers_called"], " workers_called thiếu worker name"
    print("  ✅ B3: workers_called append đúng")

    # B4: score trong [0.0, 1.0]
    s4 = run({"task": "SLA ticket P1"})
    for chunk in s4.get("retrieved_chunks", []):
        sc = chunk["score"]
        assert 0.0 <= sc <= 1.0, f" score={sc} ngoài range [0, 1]"
        assert chunk["source"] is not None, " source không được null"
        assert chunk["metadata"] is not None, " metadata không được null"
    print("  ✅ B4: score ∈ [0.0, 1.0], source/metadata không null")

    # B5: stateless — gọi 2 lần cùng input, kết quả phải giống nhau
    s5a = run({"task": "SLA P1"})
    s5b = run({"task": "SLA P1"})
    assert s5a["retrieved_sources"] == s5b["retrieved_sources"], \
        " Stateless violated: cùng input cho kết quả khác nhau"
    print("  ✅ B5: Stateless — cùng input cho cùng output")

    print(f"\n{'='*60}")
    print("  ✅ Retrieval Worker — tất cả tests passed")
    print(f"{'='*60}")