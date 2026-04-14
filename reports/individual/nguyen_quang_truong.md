# Báo Cáo Cá Nhân — Lab Day 09: Multi-Agent Orchestration

**Họ và tên:** Nguyễn Quang Trường  
**Vai trò trong nhóm:** Người 3 — Policy Enforcer (Policy Worker + MCP Client)  
**Ngày nộp:** 14/04/2026  
**Độ dài yêu cầu:** 500–800 từ

---

## 1. Tôi phụ trách phần nào?

**Module/file tôi chịu trách nhiệm:**
- File chính: `workers/policy_tool.py` — toàn bộ logic kiểm tra chính sách hoàn tiền, access control, và exception detection.
- Functions tôi implement: `analyze_policy()`, `_detect_refund_exceptions()`, `_check_temporal_scoping()`, `_check_refund_eligibility()`, `_detect_access_control_need()`, `_detect_p1_context()`, `_call_mcp_tool()`, `_discover_mcp_tools()`, và `run()`.
- Tôi cũng chỉnh sửa `graph.py` phần `policy_tool_worker_node()` để gọi real worker thay vì placeholder, và cập nhật `contracts/worker_contracts.yaml` status policy_tool_worker sang "done".

**Cách công việc của tôi kết nối với phần của thành viên khác:**

Policy worker nhận `retrieved_chunks` từ retrieval worker (Người 2) làm context đầu vào. Sau khi phân tích policy, kết quả `policy_result` (gồm `exceptions_found`, `eligibility`, `access_control`) được truyền sang synthesis worker (Người 4) để tổng hợp câu trả lời cuối. Tôi gọi MCP tools từ `mcp_server.py` (Người 5) qua hàm `_call_mcp_tool()` dùng `dispatch_tool()`. Trong graph flow, supervisor (Người 1) route tới policy worker khi task chứa keyword chính sách.

**Bằng chứng:** File `workers/policy_tool.py` có dòng `Owner: Người 3 — Policy Enforcer` ở docstring đầu file. Commit message: `feat(nguoi3): policy_tool worker + MCP client + edge cases`.

---

## 2. Tôi đã ra một quyết định kỹ thuật gì?

**Quyết định:** Tôi chọn dùng **rule-based exception detection** với severity levels thay vì gọi LLM để phân tích policy.

**Lý do:** Có 3 lựa chọn: (A) gọi LLM để đọc context và xác định exceptions, (B) rule-based thuần với keyword matching, hoặc (C) hybrid — rule-based cho exceptions cứng + LLM cho trường hợp mơ hồ. Tôi chọn phương án B vì:

1. **Tốc độ**: Rule-based chạy < 5ms, trong khi LLM call mất 800–2000ms. Với 10 câu grading questions cần chạy nhanh trước 18:00, latency thấp là ưu tiên.
2. **Deterministic**: Các ngoại lệ trong policy_refund_v4.txt rất rõ ràng (Flash Sale, digital product, activated product) — không cần LLM "suy luận". Rule-based cho kết quả 100% consistent across runs.
3. **Anti-hallucination**: Rule-based không bao giờ bịa thêm exception không có trong tài liệu, giúp tránh bị trừ điểm hallucination ở câu gq07.

**Trade-off đã chấp nhận:** Rule-based không xử lý tốt các câu hỏi diễn đạt bất thường (ví dụ: "tôi muốn trả lại hàng" thay vì "hoàn tiền"). Tuy nhiên, 15 test questions đều dùng từ khóa chuẩn nên trade-off này chấp nhận được.

**Bằng chứng từ trace/code:**

```python
# TEST 6 — Flash Sale vẫn chặn dù sản phẩm lỗi NXS + trong 7 ngày
# policy_applies: False
# exceptions: ['flash_sale_exception']
# → Rule-based detect chính xác exception blocking, không cần LLM

# TEST 7 — P1 2am + Level 2 emergency
# MCP tools called: ['check_access_permission', 'get_ticket_info']
# access_control.emergency_override: True
# → Rule-based trigger MCP call đúng, trả về kết quả đúng
```

---

## 3. Tôi đã sửa một lỗi gì?

**Lỗi:** Policy worker không phân biệt được trường hợp Flash Sale kết hợp với điều kiện hoàn tiền hợp lệ (lỗi nhà sản xuất + trong 7 ngày + chưa dùng).

**Symptom:** Ban đầu, hàm `analyze_policy()` phiên bản cũ chỉ kiểm tra exceptions và eligibility conditions một cách độc lập. Khi gặp câu gq10 ("Flash Sale + lỗi nhà sản xuất + 7 ngày — được hoàn tiền không?"), pipeline trả về `policy_applies: True` vì thấy 3 điều kiện Điều 2 đều thỏa mãn, nhưng bỏ qua ngoại lệ Flash Sale ở Điều 3.

**Root cause:** Logic ban đầu check eligibility conditions (Điều 2) trước và set `policy_applies = True` nếu thỏa, rồi mới check exceptions. Nhưng kết quả cuối chỉ dựa vào eligibility mà không override bằng exception result.

**Cách sửa:** Tôi thêm `severity: "blocking"` cho mỗi exception và thay đổi logic: exceptions kiểm tra trước, nếu có bất kỳ exception nào với `severity == "blocking"` thì `policy_applies = False` bất kể eligibility conditions. Theo đúng Điều 3 policy v4 — ngoại lệ override điều kiện.

**Bằng chứng trước/sau:**

```
# TRƯỚC (sai):
# Input: "Flash Sale + lỗi NXS + 7 ngày"
# Output: policy_applies = True  ← SAI, bỏ qua Flash Sale exception

# SAU (đúng):
# Input: "Flash Sale + lỗi NXS + 7 ngày"
# Output: policy_applies = False, exceptions = ['flash_sale_exception']  ← ĐÚNG
# TEST 6: ✅ PASS
```

---

## 4. Tôi tự đánh giá đóng góp của mình

**Tôi làm tốt nhất ở điểm nào?**

Phủ rộng edge cases: Tôi cover 9 scenarios khác nhau bao gồm cả câu gq09 (multi-hop P1 + Level 2 emergency) và gq10 (Flash Sale + valid conditions). Mỗi scenario đều có assertion test chạy tự động, giúp nhóm tự tin khi chạy grading questions.

**Tôi làm chưa tốt hoặc còn yếu ở điểm nào?**

Tôi chưa implement LLM-based analysis cho các trường hợp phức tạp hơn — chỉ dùng rule-based. Ngoài ra, temporal scoping (v3 vs v4) chỉ flag được vấn đề mà không giải quyết vì thiếu tài liệu v3.

**Nhóm phụ thuộc vào tôi ở đâu?**

Synthesis worker (Người 4) phụ thuộc vào `policy_result` output của tôi — đặc biệt trường `exceptions_found` và `access_control` để tổng hợp câu trả lời. Nếu policy worker không detect đúng exception, synthesis sẽ trả lời sai các câu policy.

**Phần tôi phụ thuộc vào thành viên khác:**

Tôi cần retrieval worker (Người 2) cung cấp `retrieved_chunks` làm context, và MCP server (Người 5) expose đúng các tools. Khi retrieval chưa có data (ChromaDB trống), tôi fallback bằng cách gọi MCP `search_kb`.

---

## 5. Nếu có thêm 2 giờ, tôi sẽ làm gì?

Tôi sẽ thêm **LLM-as-Judge cho confidence scoring** trong policy worker. Hiện tại confidence chỉ được tính ở synthesis worker dựa trên chunk scores. Nếu thêm 2 giờ, tôi sẽ implement hàm gọi LLM với prompt: "Given this policy context and exceptions, rate confidence 0-1 that the analysis is complete." Trace từ câu gq09 cho thấy confidence = 0.1 (vì synthesis lỗi API key), nhưng thực tế policy worker đã detect đúng cả `emergency_override: True` và `required_approvers`. Việc tính confidence ngay tại policy step sẽ giúp hệ thống biết khi nào cần trigger HITL trước khi đến synthesis, tránh lãng phí LLM call cho các câu mà policy đã đủ thông tin.

---


