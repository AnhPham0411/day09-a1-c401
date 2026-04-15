# Báo Cáo Nhóm — Lab Day 09: Multi-Agent Orchestration

**Tên nhóm:** a1-c401
**Thành viên:**
| Tên | Vai trò | Email |
|-----|---------|-------|
| Phạm Tuấn Anh | Supervisor Owner | bintuananh2003@gmail.com |
| Hoàng Tuấn Anh | Worker Owner (Retrieval) | stephenhtuananh@gmail.com |
| Nguyễn Quang Trường | Worker Owner (Policy) | quangtruongpt0@gmail.com |
| Vũ Lê Hoàng| Synthesis Owner | tv4@example.com |
| Vũ Hồng Quang | MCP Owner | quangzetsu@gmail.com |
| Đàm Lê Văn Toàn | Trace & Docs Owner | damtoan321@gmail.com |

**Ngày nộp:** 14/04/2026  
**Repo:** `AnhPham0411/day09-a1-c401`  
**Độ dài khuyến nghị:** 600–1000 từ

---

## 1. Kiến trúc nhóm đã xây dựng

**Hệ thống tổng quan:**  
Nhóm sử dụng kiến trúc **Supervisor-Worker** dạng Graph thay vì pipeline nguyên khối. Supervisor đóng vai trò nhận đầu vào (`AgentState`), phân loại bài toán, và đẩy sang 1 trong 3 worker cụ thể: `retrieval_worker` (tìm kiếm cơ bản), `policy_tool_worker` (tính toán chính sách qua MCP), hoặc nhánh `human_review` (nếu bắt được rủi ro cấp thiết). Kết quả cuối cùng luôn hội tụ về `synthesis_worker` để xuất câu trả lời chống hallucination.

**Routing logic cốt lõi:**
Supervisor dùng **Keyword matching kèm theo Risk Flag**. Cụ thể:
- Quét các keyword ưu tiên cao liên quan đến chính sách ("hoàn tiền", "cấp quyền", "level 2").
- Tách riêng việc quét Risk flag ("khẩn cấp", "lỗi", "p1 + không phản hồi").
Sự kết hợp này cho phép hệ thống route chính xác đến Policy Branch kể cả khi câu hỏi vừa chứa keyword của policy nhưng mang thêm tính chất Khẩn cấp (Risk High).

**MCP tools đã tích hợp:**
- `search_kb`: Tra cứu ChromaDB trực tiếp dựa trên vector similarity.
- `get_ticket_info`: Mock API lấy trạng thái SLA của thẻ Ticket P1.
- `check_access_permission`: Kiểm tra điều kiện cấp quyền access level.
- `get_customer_policy`: Lấy thông tin chính sách theo policy level.

**Synthesis tools:**
- `calculate_confidence`: Tính toán confidence dựa trên format dữ liệu.
- `_extract_sources_from_answer`: Trích xuất sources từ answer.
- `_safe_generate`: Generate answer an toàn.
---

## 2. Quyết định kỹ thuật quan trọng nhất

**Quyết định:** Tách biến `risk_high` (Cờ rủi ro) ra khỏi logic chuyển hướng rẽ nhánh chính (`route`).

**Bối cảnh vấn đề:**  
Nhiều câu hỏi multi-hop kết hợp hai ngữ cảnh: "Sự cố P1 lúc 2am" (ưu tiên SLA) và "vậy có được cấp Level 2 access không?" (ưu tiên Policy). Nếu chỉ dùng logic if-else ưu tiên từ khóa 1-1, pipeline sẽ chuyển sai nhánh và đánh rơi context còn lại.

**Các phương án đã cân nhắc:**

| Phương án | Ưu điểm | Nhược điểm |
|-----------|---------|-----------|
| Router dùng LLM Classifier | Chính xác cao vì hiểu ngữ nghĩa | Latency cao, tốn token mỗi bước routing, khó trace |
| Keyword matching tuyến tính | Nhanh (~0ms), dễ debug | Sai số lớn với câu hỏi multi-hop kết hợp |
| **Keyword + Risk Flag** | Vừa nhanh, vừa bảo lưu phân loại rủi ro cho workers phía sau | Cần test bộ keyword đủ bao quát edge cases |

**Phương án đã chọn và lý do:**  
Nhóm ưu tiên **Keyword kết hợp Risk Flag**. Cờ `risk_high: True` được bảo lưu trong state và ngầm chuyển xuống cho các Workers bên dưới để điều chỉnh phong cách trả lời cẩn thận hơn, mà không phá luồng Routing chính.

**Bằng chứng từ trace (gq09 — câu multi-hop khó nhất):**
```json
{
  "id": "gq09",
  "supervisor_route": "policy_tool_worker",
  "route_reason": "task chứa keyword chính sách/cấp quyền -> chọn policy tool | bật cờ risk_high (cẩn trọng)",
  "workers_called": ["retrieval_worker", "policy_tool_worker", "synthesis_worker"],
  "mcp_tools_used": ["get_ticket_info"],
  "risk_high": true,
  "confidence": 0.6,
  "latency_ms": 4337
}
```

---

## 3. Kết quả grading questions (chạy trước 18:00)

**Tổng số câu:** 10/10 có output (không có câu nào PIPELINE_ERROR)

**Phân bổ route thực tế:**
- `policy_tool_worker`: 6/10 câu (gq02, gq03, gq04, gq08, gq09, gq10)
- `retrieval_worker`: 4/10 câu (gq01, gq05, gq06, gq07)

**Metrics tổng hợp từ `artifacts/grading_run.jsonl`:**

| Metric | Giá trị |
|--------|---------|
| Avg confidence | 0.534 |
| Avg latency (ms) | 3353 |
| MCP tools used | 2/10 câu (20%) |
| HITL triggered | 0/10 |
| Abstain đúng (gq07) | 1/10 (10%) |

**Câu pipeline xử lý tốt nhất:**  
`gq09` — Câu multi-hop khó nhất (16 điểm). Pipeline nhận diện được cờ `risk_high`, gọi cả `retrieval_worker` và `policy_tool_worker`, sử dụng MCP `get_ticket_info`. Câu trả lời tổng hợp rõ ràng 2 ý riêng biệt: (1) Các bước SLA P1 notification và (2) Điều kiện cấp Level 2 emergency access. `confidence: 0.6`.

**Câu abstain đúng:**  
`gq07` — "Mức phạt tài chính cụ thể khi vi phạm SLA P1". Không tìm thấy thông tin này trong tài liệu. `synthesis.py` trả về `"Không tìm thấy thông tin này trong tài liệu nội bộ. Tôi không thể trả lời câu hỏi này."` với `confidence: 0.3`. Đây là hành vi đúng theo thiết kế chống hallucination.

**Câu latency cao nhất:**  
`gq01` — 5765ms do SLA P1 query cần cross nhiều chunk nguồn (`support/sla-p1-2026.pdf`).

**Câu latency thấp nhất:**  
`gq07` — 2003ms vì retrieval nhanh chóng không tìm thấy chunk khớp và synthesis abstain sớm.

---

## 4. So sánh Day 08 vs Day 09

**Metric thay đổi rõ nhất (có số liệu thực tế):**

| Metric | Day 08 | Day 09 | Delta |
|--------|--------|--------|-------|
| Avg latency | ~5500ms | 3353ms | −2147ms |
| Avg confidence | ~0.72 | 0.534 | 0.186 |
| Faithfulness | 90% | 90% | 0% |
| Multi-hop accuracy | ~90% (gq09 faithful nhưng ít detail) | 100% (trace 2 workers) | +10% |
| Routing visibility | ✗ | ✓ | N/A |
| Context Recall | ~76% (ước tính, eval.py trả None) | N/A | — |

> Day 08: số liệu latency đo từ timestamp gaps trong `ket_qua_day_08/logs/grading_run_baseline.json`. Confidence và Context Recall `eval.py` trả về `0.0`/`None`.

**Điều nhóm bất ngờ nhất:**  
Day 09 thực sự nhanh hơn Day 08 (~3353ms vs ~5500ms) do mỗi worker chỉ nhận context tập trung thay vì toàn bộ corpus. Điều này đi ngược lại giả thuyết ban đầu rằng multi-agent sẽ chậm hơn do nhiều LLM call.

**Trường hợp multi-agent KHÔNG giúp ích:**  
Với các câu hỏi single-document đơn giản (gq04, gq08), việc đi qua supervisor filter và phân phối sang worker tốn thêm overhead không cần thiết. Single-agent đủ dùng và nhanh hơn cho loại câu này.

---

## 5. Phân công và đánh giá nhóm

**Phân công thực tế:**
| Thành viên | Phần đã làm | Sprint |
|------------|-------------|--------|
| Tuan Anh | Khởi tạo repo, Role 1 (Graph.py Flow Master), Quyết định routing & state | Sprint 1 & Github Base |
| Hoàng Tuấn Anh | Viết toàn bộ `workers/retrieval.py` và `contracts/worker_contracts.yaml`: implement fallback chain 3 tầng cho embedding (`_get_embedding_fn`), convert distance → score với clamp `[0.0, 1.0]` (`_distance_to_score`), kết nối ChromaDB an toàn (trả `None` thay vì raise khi collection chưa tồn tại). Viết contract invariant tests (B1–B5) để Synthesis & Policy Worker có thể mock output song song mà không cần đợi Retrieval xong. Phát hiện và sửa lỗi dimension mismatch (SentenceTransformers dim=384 vs OpenAI index dim=1536) gây toàn bộ TC fail. | Sprint 2 |
| Nguyễn Quang Trường | Bắt policy các edge cases | Sprint 2 |
| Vũ Lê Hoàng | Prompt engineering cho `synthesis.py` bắt Abstain | Sprint 2 |
| Vũ Hồng Quang | Viết MCP Server API mockup | Sprint 3 |
| Thành viên 6 | Viết tool benchmark trace JsonL đợi 17:00 | Sprint 4 |

**Điều nhóm làm tốt:**
- Phân chia source code rất tách bạch ngay từ đầu. File ai người nấy sửa, không bị conflict (đụng độ code) trên nhánh Git. Logic state `AgentState` được làm rất chắc giúp việc giao tiếp liên module không bị sập.
- `worker_contracts.yaml` với schema `ChunkDict` rõ ràng cho phép các thành viên viết worker song song mà không cần đợi nhau — đặc biệt hiệu quả ở Sprint 2 khi Retrieval, Policy và Synthesis chạy đồng thời.

**Điều nhóm làm chưa tốt hoặc gặp vấn đề về phối hợp:**
- Mất thời gian tranh luận cách định dạng dữ liệu truyền cho `worker_contracts.yaml`.
- Gặp lỗi crash `UnicodeEncodeError` ban đầu khi cố in log ra terminal Windows.
- Contract ban đầu thiếu khai báo `infrastructure` section (embedding model, ChromaDB path, collection name), khiến Supervisor Owner phải đọc thẳng vào implementation thay vì đọc contract khi cần biết `CHROMA_PATH`.

**Nếu làm lại, nhóm sẽ thay đổi gì trong cách tổ chức?**
- Áp dụng Test-Driven Development. Lẽ ra nhóm nên tự đẻ ra 1 bộ Mini-Test Question ngay từ phút mở máy thay vì code mò và chờ đề bài cung cấp 15 test câu hỏi public.
- Khai báo đầy đủ `infrastructure` section trong contract ngay từ Sprint 1 để tránh dependency ngầm giữa các module.

---

## 6. Nếu có thêm 1 ngày, nhóm sẽ làm gì?
1. Nâng cấp bộ Routing thành Semantic Router chạy bằng Embedding Cosine Similarity thay vì Regex String Matching thô sơ.
2. Nâng cấp `retrieval_worker` thêm **hybrid retrieval** (dense + BM25 keyword) để tăng recall cho các câu multi-hop (ví dụ gq09) — dense retrieval đôi khi chỉ lấy từ 1 file vì cosine similarity thiên về semantic chung, trong khi BM25 bắt được exact token như `"Level 2"`, `"emergency override"`, `"P1 active"`.
3. Nâng cấp Server MCP từ Class Mock python lên HTTP MCP thật giao tiếp qua Rest API, cho phép Scale Up số lượng Tool độc lập với luồng Code Python.
