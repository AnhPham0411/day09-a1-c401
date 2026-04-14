# System Architecture — Lab Day 09

**Nhóm:** a1-c401  
**Ngày:** 14/04/2026  
**Version:** 1.0

---

## 1. Tổng quan kiến trúc

> Mô tả ngắn hệ thống của nhóm: chọn pattern gì, gồm những thành phần nào.

**Pattern đã chọn:** Supervisor-Worker  
**Lý do chọn pattern này (thay vì single agent):**

Hệ thống hỗ trợ IT Helpdesk nội bộ xử lý các câu hỏi về SLA, policy hoàn tiền, và kiểm soát quyền truy cập. Supervisor-Worker được chọn vì mỗi loại query đòi hỏi logic xử lý khác nhau: truy vấn knowledge base (retrieval), kiểm tra chính sách và gọi external tool (policy_tool), hoặc yêu cầu con người xét duyệt khi rủi ro cao (human review). Việc tách thành từng worker chuyên biệt giúp dễ test độc lập, dễ thêm capability mới mà không cần sửa toàn bộ hệ thống, và tạo audit trail rõ ràng qua `route_reason` trong mỗi trace.

---

## 2. Sơ đồ Pipeline

> Vẽ sơ đồ pipeline dưới dạng text, Mermaid diagram, hoặc ASCII art.
> Yêu cầu tối thiểu: thể hiện rõ luồng từ input → supervisor → workers → output.

**Ví dụ (ASCII art):**
```
User Request
     │
     ▼
┌──────────────┐
│  Supervisor  │  ← route_reason, risk_high, needs_tool
└──────┬───────┘
       │
   [route_decision]
       │
  ┌────┴────────────────────┐
  │                         │
  ▼                         ▼
Retrieval Worker     Policy Tool Worker
  (evidence)           (policy check + MCP)
  │                         │
  └─────────┬───────────────┘
            │
            ▼
      Synthesis Worker
        (answer + cite)
            │
            ▼
         Output
```

**Sơ đồ thực tế của nhóm:**

```
User Request (task str)
       │
       ▼
┌─────────────────────────────────────────┐
│            Supervisor Node              │
│  - Phân tích keyword trong task         │
│  - Gán: supervisor_route, route_reason  │
│  - Gán cờ: risk_high, needs_tool        │
└──────────────────┬──────────────────────┘
                   │ [route_decision]
        ┌──────────┼──────────────────┐
        │          │                  │
        ▼          ▼                  ▼
 human_review  policy_tool_worker  retrieval_worker
     │              │                  │
     │    (multi-hop: chạy retrieval   │
     │     trước, rồi policy_tool)     │
     │              │                  │
     └──────┬───────┘                  │
            │          ┌───────────────┘
            ▼          ▼
     ┌───────────────────────┐
     │   Retrieval Worker    │
     │  - Dense search       │
     │    ChromaDB (top-k=3) │
     │  - Ghi retrieved_     │
     │    chunks & sources   │
     └──────────┬────────────┘
                │
     ┌──────────▼────────────┐
     │ Policy Tool Worker    │    ←── (nếu route = policy_tool)
     │  - Rule-based check   │
     │  - Gọi MCP tools:     │
     │    • search_kb        │
     │    • check_access_    │
     │      permission       │
     │    • get_ticket_info  │
     └──────────┬────────────┘
                │
     ┌──────────▼────────────┐
     │   Synthesis Worker    │
     │  - Gọi LLM            │
     │    (gpt-4o-mini)      │
     │  - Grounded answer    │
     │    với citation       │
     │  - Tính confidence    │
     └──────────┬────────────┘
                │
                ▼
   AgentState với final_answer,
   sources, confidence, trace
```

---

## 3. Vai trò từng thành phần

### Supervisor (`graph.py`)

| Thuộc tính | Mô tả |
|-----------|-------|
| **Nhiệm vụ** | Phân tích câu hỏi đầu vào, phân loại intent, quyết định route sang worker phù hợp |
| **Input** | `task` (câu hỏi từ user) từ AgentState |
| **Output** | `supervisor_route`, `route_reason`, `risk_high`, `needs_tool` |
| **Routing logic** | Keyword matching: policy_keywords → `policy_tool_worker`; retrieval_keywords / "p1" → `retrieval_worker`; risk_high + "err-" → `human_review`; default fallback → `retrieval_worker` |
| **HITL condition** | `risk_high=True` AND task chứa mã lỗi "err-" không rõ → route sang `human_review`. Trong lab, auto-approve và tiếp tục sang retrieval |

### Retrieval Worker (`workers/retrieval.py`)

| Thuộc tính | Mô tả |
|-----------|-------|
| **Nhiệm vụ** | Tìm evidence từ ChromaDB — dense retrieval dựa trên semantic similarity của câu hỏi |
| **Embedding model** | Priority 1: `openai/text-embedding-3-small` (dim=1536); Priority 2: `sentence-transformers/all-MiniLM-L6-v2` (dim=384); Priority 3: random float[1536] fallback (chỉ test I/O) |
| **Top-k** | Mặc định 3 (clamped vào [1, 10]); score được convert từ cosine distance: `score = round(max(0, min(1, 1 - dist)), 4)` |
| **Stateless?** | Yes — không lưu state giữa các lần gọi; cùng input luôn cho cùng output |

### Policy Tool Worker (`workers/policy_tool.py`)

| Thuộc tính | Mô tả |
|-----------|-------|
| **Nhiệm vụ** | Kiểm tra chính sách hoàn tiền (refund_policy_v4), phát hiện exception, temporal scoping, và kiểm tra quyền truy cập; gọi MCP tools để bổ sung context |
| **MCP tools gọi** | `search_kb` (khi chưa có chunks), `check_access_permission` (khi phát hiện yêu cầu Level 1/2/3), `get_ticket_info` (khi phát hiện ngữ cảnh P1) |
| **Exception cases xử lý** | Flash Sale exception (blocking), Digital product/license key exception (blocking), Activated product exception (blocking), Temporal scoping (đơn trước 01/02/2026 → áp dụng policy v3, kết quả uncertain), Store credit 110% |

### Synthesis Worker (`workers/synthesis.py`)

| Thuộc tính | Mô tả |
|-----------|-------|
| **LLM model** | `gpt-4o-mini` (OpenAI, Priority 1); fallback `gemini-2.5-flash` (Google Generative AI) |
| **Temperature** | 0.1 — low temperature để đảm bảo câu trả lời grounded, ít sáng tạo |
| **Grounding strategy** | Chỉ dùng thông tin trong `<CONTEXT>` (retrieved_chunks + policy exceptions); mỗi câu quan trọng phải có citation `[tên_file]`; nếu thiếu context → abstain hoàn toàn |
| **Abstain condition** | Không có chunks retrieval nào (độ tin cậy 0.1); hoặc LLM tự nhận "Không tìm thấy thông tin này trong tài liệu nội bộ" (confidence 0.3) |

### MCP Server (`mcp_server.py`)

| Tool | Input | Output |
|------|-------|--------|
| `search_kb` | `query: str`, `top_k: int = 3` | `chunks: list`, `sources: list`, `total_found: int` |
| `get_ticket_info` | `ticket_id: str` | `ticket_id`, `priority`, `status`, `assignee`, `sla_deadline`, `escalated`, `notifications_sent` |
| `check_access_permission` | `access_level: int (1/2/3)`, `requester_role: str`, `is_emergency: bool` | `can_grant: bool`, `required_approvers: list`, `emergency_override: bool`, `notes: list` |
| `create_ticket` | `priority: str (P1-P4)`, `title: str`, `description: str` | `ticket_id`, `url`, `created_at` (MOCK — không tạo thật) |

---

## 4. Shared State Schema

> Liệt kê các fields trong AgentState và ý nghĩa của từng field.

| Field | Type | Mô tả | Ai đọc/ghi |
|-------|------|-------|-----------| 
| `task` | `str` | Câu hỏi đầu vào từ user | supervisor đọc |
| `supervisor_route` | `str` | Worker được chọn (`retrieval_worker` / `policy_tool_worker` / `human_review`) | supervisor ghi, graph đọc |
| `route_reason` | `str` | Lý do route (audit trail) | supervisor ghi |
| `risk_high` | `bool` | True nếu task chứa keyword khẩn cấp hoặc mã lỗi không rõ | supervisor ghi |
| `needs_tool` | `bool` | True nếu policy_tool_worker cần gọi MCP tools | supervisor ghi, policy_tool đọc |
| `hitl_triggered` | `bool` | True nếu đã qua human_review_node | human_review ghi |
| `retrieved_chunks` | `list[ChunkDict]` | Evidence từ retrieval — mỗi chunk có `text`, `source`, `score`, `metadata` | retrieval_worker ghi, synthesis/policy_tool đọc |
| `retrieved_sources` | `list[str]` | Danh sách tên file nguồn (unique, giữ thứ tự) | retrieval_worker ghi |
| `policy_result` | `dict` | Kết quả phân tích policy: `policy_applies`, `exceptions_found`, `eligibility`, `access_control`, `ticket_context` | policy_tool_worker ghi, synthesis đọc |
| `mcp_tools_used` | `list` | Danh sách các MCP tool call đã thực hiện (log đầy đủ input/output/error) | policy_tool_worker ghi |
| `final_answer` | `str` | Câu trả lời cuối có citation | synthesis ghi |
| `sources` | `list[str]` | Sources được cite trong câu trả lời | synthesis ghi |
| `confidence` | `float` | Mức tin cậy (0.0–1.0), tính từ avg retrieval score trừ exception/citation penalty | synthesis ghi |
| `history` | `list[str]` | Lịch sử log từng bước (supervisor, workers, graph) — dùng để debug | tất cả components append |
| `workers_called` | `list[str]` | Danh sách tên worker đã được gọi theo thứ tự | mỗi worker self-append |
| `worker_io_logs` | `list[LogEntry]` | Chi tiết input/output/error của từng worker call | mỗi worker append |
| `latency_ms` | `Optional[int]` | Tổng thời gian xử lý (ms) | graph ghi sau khi hoàn thành |
| `run_id` | `str` | ID định danh run (format: `run_YYYYMMDD_HHMMSS`) | khởi tạo bởi `make_initial_state()` |
| `timestamp` | `str` | Thời điểm hoàn thành (ISO format) | graph ghi |

---

## 5. Lý do chọn Supervisor-Worker so với Single Agent (Day 08)

| Tiêu chí | Single Agent (Day 08) | Supervisor-Worker (Day 09) |
|----------|----------------------|--------------------------|
| Debug khi sai | Khó — không rõ lỗi ở đâu | Dễ hơn — test từng worker độc lập |
| Thêm capability mới | Phải sửa toàn prompt | Thêm worker/MCP tool riêng |
| Routing visibility | Không có | Có `route_reason` trong trace |
| Xử lý multi-policy | Một prompt ôm toàn bộ rule → dễ nhầm | Policy worker chuyên biệt, tách biệt refund / access control |
| Gọi external tool | Hard-code trong 1 agent | MCP dispatch layer dùng chung, workers gọi theo nhu cầu |
| Human-in-the-loop | Không có cơ chế rõ ràng | `human_review_node` với flag `hitl_triggered`, dễ mở rộng |

**Quan sát thực tế từ lab:**

- **Multi-hop routing** hoạt động hiệu quả: câu hỏi policy_tool_worker tự động chạy retrieval trước để có context, rồi mới phân tích policy — kết quả tốt hơn khi làm trong 1 bước duy nhất.
- **Stateless workers** giúp test cực dễ: có thể gọi `workers/retrieval.py` độc lập mà không cần khởi động cả pipeline.
- **`route_reason`** trong trace giúp nhanh chóng phát hiện khi supervisor route sai (ví dụ: query về SLA bị nhầm sang policy vì có từ "policy" trong câu hỏi).

---

## 6. Giới hạn và điểm cần cải tiến

> Nhóm mô tả những điểm hạn chế của kiến trúc hiện tại.

1. **Supervisor routing dựa trên keyword cứng:** Logic `if keyword in task` dễ route sai khi câu hỏi phức tạp hoặc dùng từ đồng nghĩa (VD: "trả hàng" thay vì "hoàn tiền"). Cải tiến: dùng LLM-based intent classification hoặc embedding similarity cho routing.

2. **HITL chỉ là placeholder, không có cơ chế thật:** Hiện tại `human_review_node` tự động approve — không thực sự pause pipeline để chờ người dùng xác nhận. Cần implement `interrupt_before` của LangGraph hoặc webhook/queue pattern để tích hợp thật sự.

3. **ChromaDB single-collection, không có sparse retrieval:** Toàn bộ tài liệu trong một collection, chỉ dùng dense search (cosine similarity). Thiếu hybrid retrieval (BM25 + dense) khiến kết quả kém với query chứa số/mã ticket cụ thể (VD: "IT-1234", "ERR-502") — keyword exact match không được ưu tiên.
