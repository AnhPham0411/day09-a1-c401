# Báo Cáo Nhóm — Lab Day 09: Multi-Agent Orchestration

**Tên nhóm:** a1-c401
**Thành viên:**
| Tên | Vai trò | Email |
|-----|---------|-------|
| Phạm Tuấn Anh | Supervisor Owner | bintuananh2003@gmail.com |
| Thành viên 2 | Worker Owner (Retrieval) | tv2@example.com |
| Thành viên 3 | Worker Owner (Policy) | tv3@example.com |
| Thành viên 4 | Synthesis Owner | tv4@example.com |
| Thành viên 5 | MCP Owner | tv5@example.com |
| Thành viên 6 | Trace & Docs Owner | tv6@example.com |

**Ngày nộp:** 14/04/2026  
**Repo:** `AnhPham0411/day09-a1-c401`  
**Độ dài khuyến nghị:** 600–1000 từ

---

## 1. Kiến trúc nhóm đã xây dựng

**Hệ thống tổng quan:**
Nhóm sử dụng kiến trúc **Supervisor-Worker** dạng Graph thay vì pipeline nguyên khối. Supervisor đóng vai trò nhận đầu vào (`AgentState`), phân loại bài toán, và đẩy sang 1 trong 3 worker cụ thể: `retrieval_worker` (tìm kiếm cơ bản), `policy_tool_worker` (tính toán chính sách qua MCP), hoặc nhánh `human_review` (nếu bắt được rủi ro cấp thiết). Kết quả cuối cùng luôn hội tụ về `synthesis_worker` để xuất câu trả lời chống Hallucination (cấm bịa đặt).

**Routing logic cốt lõi:**
Supervisor dùng **Keyword matching kèm theo Risk Flag**. Cụ thể: 
- Quét các keyword ưu tiên cao liên quan đến chính sách ("hoàn tiền", "cấp quyền", "level 2").
- Tách riêng việc quét Risk flag ("khẩn cấp", "lỗi", "p1 + không phản hồi"). 
Sự kết hợp này cho phép hệ thống route chính xác đến Policy Branch kể cả khi câu hỏi vừa chứa keyword của policy nhưng mang thêm tính chất Khẩn cấp (Risk High).

**MCP tools đã tích hợp:**
- `search_kb`: Dùng để tra cứu ChromaDB trực tiếp dựa trên vector similarity thay vì hard-code đường dẫn docs.
- `get_ticket_info`: Mock API dùng để lấy trạng thái SLA của thẻ Ticket P1.

---

## 2. Quyết định kỹ thuật quan trọng nhất

**Quyết định:** Tách biến `risk_high` (Cờ rủi ro) ra khỏi logic chuyển hướng rẽ nhánh chính (`route`).

**Bối cảnh vấn đề:**
Rất nhiều câu hỏi đánh lừa (multi-hop case) khi người dùng vừa đưa ra ngữ cảnh "Sự cố P1 lúc 2am" (Nên ưu tiên tra cứu SLA) nhưng lại có câu hỏi hệ lụy "vậy có được hoàn tiền không?" (Nên ưu tiên Policy). Nếu chỉ dùng logic if-else ưu tiên từ khóa 1-1, pipeline sẽ chuyển sai nhánh và đánh rơi context.

**Các phương án đã cân nhắc:**

| Phương án | Ưu điểm | Nhược điểm |
|-----------|---------|-----------|
| Router dùng LLM Classifier | Tuyệt đối chính xác vì LLM hiểu ngữ nghĩa. | Latency cao, tốn token mỗi lúc bẻ nhánh, khó trace rõ rệt bằng code. |
| Keyword matching dạng tuyến tính | Nhanh, độ trễ (~0ms), dễ debug. | Sai số lớn với câu hỏi kết hợp (multi-hop), ghi đè nhánh xử lý. |
| **Keyword kết hợp Risk Flag** | Vừa nhanh (0ms), vừa bảo lưu được phân loại rủi ro cho các Worker phía sau xử lý độc lập. | Cần phải test bộ keyword đủ bao quát các exception. |

**Phương án đã chọn và lý do:**
Nhóm ưu tiên **Keyword kết hợp Risk Flag**. Lý do: Trong môi trường Customer Service, tốc độ điều phối phải đạt mức thời gian thực. Bằng cách thiết lập state có dạng dict, cờ rủi ro `risk_high: True` được bảo lưu và ngầm chuyển theo data xuống cho các Worker bên dưới để chúng quyết định thay đổi phong cách trả lời cho thận trọng, mà không phá đi luồng Routing chính.

**Bằng chứng từ trace/code:**
```json
{
  "supervisor_route": "policy_tool_worker",
  "route_reason": "task chứa keyword chính sách/cấp quyền -> chọn policy tool | bật cờ risk_high (cẩn trọng)",
  "workers_called": ["policy_tool_worker", "retrieval_worker", "synthesis_worker"],
  "risk_high": true,
  "needs_tool": true
}
```

---

## 3. Kết quả grading questions (CHỜ CHẠY LÚC 17:00)

> ⚠️ Báo cáo: Phần này đang được để trống. Nhóm sẽ chỉ được phép cập nhật sau 17:00 khi có file `grading_questions.json`.

**Tổng điểm raw ước tính:** [TODO] / 96

**Câu pipeline xử lý tốt nhất:**
- ID: [TODO] — Lý do tốt: [TODO]

**Câu pipeline fail hoặc partial:**
- ID: [TODO] — Fail ở đâu: [TODO]
  Root cause: [TODO]

**Câu gq07 (abstain):** Nhóm xử lý thế nào?
- [TODO] (Dự kiến: Nhờ vào lệnh prompt cứng tại `workers/synthesis.py`, model sẽ trả lời "Abstain" và bỏ qua chứ không hallucinate)

**Câu gq09 (multi-hop khó nhất):** Trace ghi được 2 workers không? Kết quả thế nào?
- [TODO]

---

## 4. So sánh Day 08 vs Day 09 (CHỜ DATA LÚC 17:00)

**Metric thay đổi rõ nhất (có số liệu):**
- [TODO] (Kỳ vọng: Debuggability tăng mạnh vì nhóm có thể biết lỗi nằm ở Retrieval, Policy hay Synthesis thông qua JSON trace).

**Điều nhóm bất ngờ nhất khi chuyển từ single sang multi-agent:**
- [TODO] (Kỳ vọng: Tổng latency có thể chậm hơn Day 08 một chút do phải luân chuyển State giữa nhiều node, nhưng Accuracy với các case phức tạp lại tăng mạnh).

**Trường hợp multi-agent KHÔNG giúp ích hoặc làm chậm hệ thống:**
- [TODO]

---

## 5. Phân công và đánh giá nhóm

**Phân công thực tế:** (Theo khung Task.md)
| Thành viên | Phần đã làm | Theo Sprint |
|------------|-------------|--------|
| Tuan Anh | Khởi tạo repo, Role 1 (Graph.py Flow Master), Quyết định routing & state | Sprint 1 & Github Base |
| Thành viên 2 | Tích hợp ChromaDB và viết chức năng Retrieval | Sprint 2 |
| Thành viên 3 | Bắt policy các edge cases | Sprint 2 |
| Thành viên 4 | Prompt engineering cho `synthesis.py` bắt Abstain | Sprint 2 |
| Thành viên 5 | Viết MCP Server API mockup | Sprint 3 |
| Thành viên 6 | Viết tool benchmark trace JsonL đợi 17:00 | Sprint 4 |

**Điều nhóm làm tốt:**
- Phân chia source code rất tách bạch ngay từ đầu. File ai người nấy sửa, không bị conflict (đụng độ code) trên nhánh Git. Logic state `AgentState` được làm rất chắc giúp việc giao tiếp liên module không bị sập.

**Điều nhóm làm chưa tốt hoặc gặp vấn đề về phối hợp:**
- Mất thời gian tranh luận cách định dạng dữ liệu truyền cho `worker_contracts.yaml`. 
- Gặp lỗi crash `UnicodeEncodeError` ban đầu khi cố in log ra termial Windows.

**Nếu làm lại, nhóm sẽ thay đổi gì trong cách tổ chức?**
- Áp dụng Test-Driven Development. Lẽ ra nhóm nên tự đẻ ra 1 bộ Mini-Test Question ngay từ phút mở máy thay vì code mò và chờ đề bài cung cấp 15 test câu hỏi public.

---

## 6. Nếu có thêm 1 ngày, nhóm sẽ làm gì?
1. Nâng cấp bộ Routing thành Semantic Router chạy bằng Embedding Cosine Similarity thay vì Regex String Matching thô sơ.
2. Nâng cấp Server MCP từ Class Mock python lên HTTP MCP thật giao tiếp qua Rest API, cho phép Scale Up số lượng Tool độc lập với luồng Code Python.
