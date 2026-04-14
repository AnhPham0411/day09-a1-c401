# Báo Cáo Cá Nhân — Lab Day 09: Multi-Agent Orchestration

**Họ và tên:** Hoàng Tuấn Anh  
**Vai trò trong nhóm:** Data Finder — Retrieval Worker & Worker Contracts  
**Ngày nộp:** 14/04/2026  
**Độ dài yêu cầu:** 500–800 từ

---

## 1. Tôi phụ trách phần nào?

**Module/file tôi chịu trách nhiệm:**
- File chính: `workers/retrieval.py`, `contracts/worker_contracts.yaml`
- Functions tôi implement:
  - `_get_embedding_fn()` — khởi tạo embedding theo fallback chain 3 tầng (OpenAI → SentenceTransformers → random)
  - `_get_collection()` — kết nối ChromaDB, trả `None` thay vì raise khi collection chưa tồn tại
  - `_distance_to_score(cosine_distance)` — convert ChromaDB cosine distance sang similarity score, enforce clamp `[0.0, 1.0]`
  - `retrieve_dense(query, top_k)` — embed query, query ChromaDB, assemble ChunkDict list
  - `run(state)` — entry point được `graph.py` gọi, đọc/ghi `AgentState` theo contract

**Cách công việc của tôi kết nối với phần của thành viên khác:**

`retrieval_worker` là upstream dependency của cả `policy_tool_worker` (Người 3) và `synthesis_worker` (Người 4). Cả hai worker đó đọc `state['retrieved_chunks']` và `state['retrieved_sources']` mà tôi ghi vào. Ngoài ra, phần `retrieval_worker` trong `worker_contracts.yaml` định nghĩa `ChunkDict schema` và `LogEntry schema` — đây là "hợp đồng" cho phép Người 3 và 4 mock output của tôi và viết worker của họ song song mà không cần đợi tôi xong.

**Bằng chứng:**
- `workers/retrieval.py` dòng đầu: `Role: Data Finder — tìm bằng chứng từ kho tài liệu`
- `contracts/worker_contracts.yaml`: `updated_at: "2026-04-13"`, section `retrieval_worker` có đầy đủ constraints và `actual_implementation.status`

---

## 2. Tôi đã ra một quyết định kỹ thuật gì?

**Quyết định:** Tách logic convert distance → score thành một function riêng `_distance_to_score()`, thay vì inline công thức trong vòng lặp.

**Các lựa chọn thay thế:**
- Inline trực tiếp: `score = round(max(0.0, min(1.0, 1.0 - dist)), 4)` trong `retrieve_dense()` — đơn giản hơn nhưng logic quan trọng bị chôn vùi giữa boilerplate
- Để raw distance vào score luôn — nhanh viết nhất, nhưng vi phạm contract (contract yêu cầu score ∈ [0.0, 1.0], là *similarity* không phải distance)

**Lý do chọn function riêng:**

Contract khai báo rõ ràng: `score_formula: round(max(0.0, min(1.0, 1.0 - cosine_distance)), 4)`. Khi logic này bị inline, mọi người đọc code phải hiểu ngầm tại sao lại `1.0 - dist`. Tách ra thành `_distance_to_score()` với docstring giải thích `ChromaDB cosine distance = 1 - similarity` thì bất kỳ ai vào đọc cũng hiểu ngay. Quan trọng hơn, nếu sau này đổi sang L2 distance hay metric khác, chỉ cần sửa 1 chỗ thay vì hunt qua toàn bộ vòng lặp.

**Trade-off đã chấp nhận:** Thêm 1 function call overhead — hoàn toàn không đáng kể so với latency của ChromaDB query.

**Bằng chứng từ code:**

```python
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
```

Function này sau đó được gọi trong vòng lặp assemble chunks: `"score": _distance_to_score(dist)`. Kết quả: contract invariant B4 pass — `score ∈ [0.0, 1.0]` với mọi chunk.

---

## 3. Tôi đã sửa một lỗi gì?

**Lỗi:** `_get_embedding_fn()` ban đầu đặt SentenceTransformers là Priority 1, OpenAI là Priority 2 — dẫn đến dimension mismatch với ChromaDB index.

**Symptom:**

Khi chạy standalone test (TC-R01 đến TC-R05), tất cả queries đều trả về `[]` với log: `ChromaDB không sẵn sàng: Collection day09_docs not found` — mặc dù collection đã được build. Sau khi điều tra thêm, lỗi thực sự là: collection được build bằng OpenAI embedding (dim=1536), nhưng khi query, tôi dùng SentenceTransformers (dim=384) → ChromaDB từ chối query vì dimension không khớp.

**Root cause:**

Index `day09_docs` được build với `text-embedding-3-small` (1536 chiều). SentenceTransformers `all-MiniLM-L6-v2` cho ra vector 384 chiều. ChromaDB enforce dimension consistency — query vector phải cùng chiều với index vector.

**Cách sửa:**

Đảo thứ tự ưu tiên: OpenAI làm Priority 1 (khớp với index hiện có), SentenceTransformers làm Priority 2 với cảnh báo rõ ràng. Random fallback giữ nguyên dim=1536 để ít nhất không bị lỗi dimension khi test I/O contract:

```python
# Trước khi sửa:
# Priority 1: SentenceTransformers (dim=384) ← sai, không khớp index
# Priority 2: OpenAI (dim=1536)

# Sau khi sửa:
# Priority 1: OpenAI (dim=1536) ← khớp index đã build
# Priority 2: SentenceTransformers (dim=384) + warning "cần rebuild index"
# Priority 3: random (dim=1536) ← cùng dim để không crash, chỉ cho I/O test
```

**Bằng chứng trước/sau:**

```
# Trước: tất cả TC fail
[TC-R01] Không lấy được chunk nào — ChromaDB chưa sẵn sàng?
[TC-R02] Không lấy được chunk nào — ChromaDB chưa sẵn sàng?

# Sau: domain tests pass khi có OPENAI_API_KEY
[TC-R01]  3 chunks | sources: ['sla-p1-2026.pdf']
         Top chunk [score=0.8431]: SLA ticket P1 — thời gian phản hồi 15 phút...
[TC-R02]  3 chunks | sources: ['refund-v4.pdf']
         Top chunk [score=0.7912]: Flash Sale exception: hoàn tiền bằng store credit...
```

---

## 4. Tôi tự đánh giá đóng góp của mình

**Tôi làm tốt nhất ở điểm nào?**

Viết contract invariant tests trong `if __name__ == "__main__"`. Thay vì chỉ test "có kết quả không", tôi viết 5 tests (B1–B5) verify từng ràng buộc trong contract: log format, EMPTY_TASK guard, `workers_called` append, score range, và stateless property. Điều này cho phép Người 3 và 4 tin tưởng vào output của tôi mà không cần đọc implementation.

**Tôi làm chưa tốt hoặc còn yếu ở điểm nào?**

Contract ban đầu thiếu khai báo `infrastructure` section (embedding model, ChromaDB path, collection name). Khi Người 1 viết `graph.py` cần biết cách khởi tạo môi trường, họ phải vào đọc thẳng code `retrieval.py` thay vì đọc contract. Phát hiện ra muộn khi Người 1 hỏi `CHROMA_PATH` là gì.

**Nhóm phụ thuộc vào tôi ở đâu?**

`retrieved_chunks` là input bắt buộc của Synthesis Worker. Nếu tôi trả sai schema (thiếu field `source` hoặc `score` ngoài range), synthesis sẽ lỗi hoặc tạo citation sai. Đây là lý do tôi enforce contract invariants ngay trong `run()` thay vì để downstream worker tự xử lý.

**Phần tôi phụ thuộc vào thành viên khác:**

Phụ thuộc Người 1 để `AgentState` được khởi tạo với field `task` đúng format trước khi `run(state)` được gọi. Tôi giải quyết bằng EMPTY_TASK guard — nếu `task` rỗng, worker abstain sớm với `ERR_EMPTY_TASK` thay vì query ChromaDB với vector vô nghĩa.

---

## 5. Nếu có thêm 2 giờ, tôi sẽ làm gì?

Tôi sẽ thêm **hybrid retrieval** (dense + BM25 keyword) vào `retrieve_dense()`. Từ trace của câu `gq09` (multi-hop, 16 điểm), pipeline cần retrieve từ cả `sla-p1-2026.pdf` và `access-control-sop.md` trong 1 query — dense retrieval với top_k=3 đôi khi chỉ lấy từ 1 file vì cosine similarity thiên về semantic chung. BM25 bắt được exact token như `"Level 2"`, `"emergency override"`, `"P1 active"` — kết hợp với dense score sẽ tăng recall cho câu multi-hop mà không cần tăng top_k lên quá cao.

---
