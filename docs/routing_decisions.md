# Routing Decisions Log — Lab Day 09

**Nhóm:** Nhóm AICB-P1 Demo  
**Ngày:** 14/04/2026

> **Hướng dẫn:** Ghi lại ít nhất **3 quyết định routing** thực tế từ trace của nhóm.
> Không ghi giả định — phải từ trace thật (`artifacts/traces/`).
> 
> Mỗi entry phải có: task đầu vào → worker được chọn → route_reason → kết quả thực tế.

---

## Routing Decision #1

**Task đầu vào:**
> SLA xử lý ticket P1 là bao lâu?

**Worker được chọn:** `retrieval_worker`
**Route reason (từ trace):** `task chứa keyword tra cứu (SLA, ticket) -> chọn retrieval`
**MCP tools được gọi:** Chưa gọi (placeholder)
**Workers called sequence:** `['retrieval_worker', 'synthesis_worker']`

**Kết quả thực tế:**
- final_answer (ngắn): [PLACEHOLDER] Câu trả lời được tổng hợp từ 1 chunks.
- confidence: 0.75
- Correct routing? Yes

**Nhận xét:**
Từ khóa "SLA" và "P1" hoạt động chính xác trong luồng routing đầu tiên, đưa query về trực tiếp kho retrieval mà không cần qua tool kiểm tra chính sách.

---

## Routing Decision #2

**Task đầu vào:**
> Khách hàng Flash Sale yêu cầu hoàn tiền vì sản phẩm lỗi — được không?

**Worker được chọn:** `policy_tool_worker`
**Route reason (từ trace):** `task chứa keyword chính sách/cấp quyền -> chọn policy tool | bật cờ risk_high (cẩn trọng)`
**MCP tools được gọi:** Chưa gọi (placeholder)
**Workers called sequence:** `['policy_tool_worker', 'retrieval_worker', 'synthesis_worker']`

**Kết quả thực tế:**
- final_answer (ngắn): [PLACEHOLDER] Câu trả lời được tổng hợp từ 1 chunks.
- confidence: 0.75
- Correct routing? Yes

**Nhận xét:**
Hệ thống bắt chính xác từ khóa "hoàn tiền" để rẽ nhánh qua `policy_tool_worker`. Ngoài ra, từ khóa "lỗi" cũng kích hoạt cờ `risk_high` đúng như thiết kế dành cho các case Flash Sale hoàn tiền.

---

## Routing Decision #3

**Task đầu vào:**
> Cần cấp quyền Level 3 để khắc phục P1 khẩn cấp. Quy trình là gì?

**Worker được chọn:** `policy_tool_worker`
**Route reason (từ trace):** `task chứa keyword chính sách/cấp quyền -> chọn policy tool | bật cờ risk_high (cẩn trọng)`
**MCP tools được gọi:** Chưa gọi (placeholder)
**Workers called sequence:** `['policy_tool_worker', 'retrieval_worker', 'synthesis_worker']`

**Kết quả thực tế:**
- final_answer (ngắn): [PLACEHOLDER] Câu trả lời được tổng hợp từ 1 chunks.
- confidence: 0.75
- Correct routing? Yes

**Nhận xét:**
Một câu hỏi multi-hop mang tính chất "khẩn cấp" và liên quan đến "cấp quyền Level 3". Supervisor đưa về `policy_tool_worker` để duyệt chính sách cấp quyền là hợp lý. Đồng thời cờ rủi ro cao cũng tung lên vì "khẩn cấp".

---

## Tổng kết

### Routing Distribution (mẫu tạm từ 3 run)

| Worker | Số câu được route | % tổng |
|--------|------------------|--------|
| retrieval_worker | 1 | 33.3% |
| policy_tool_worker | 2 | 66.7% |
| human_review | 0 | 0% |

### Routing Accuracy

- Câu route đúng: 3 / 3
- Câu route sai (đã sửa bằng cách nào?): 0
- Câu trigger HITL: 0

### Lesson Learned về Routing

> Quyết định kỹ thuật quan trọng nhất nhóm đưa ra về routing logic là gì?  

1. **Từ khóa có độ ưu tiên kết hợp Risk flag**: Việc tách riêng các keyword nguy hiểm (`khẩn cấp`, `lỗi`) bằng một biến Risk Flag riêng giúp chúng ta không bị over-ride route chính nhưng vẫn log lại được mức độ rủi ro để truyền cho human review nếu sau này có human in the loop (HITL).
2. **Ưu tiên logic cấp quyền & policy hơn retrieval thường**: Khi câu hỏi vừa có cấp quyền vừa gọi P1, luồng ưu tiên bẻ qua Policy Check trước, sau đó Policy Worker mới trigger Retrieval.

### Route Reason Quality

> Nhìn lại các `route_reason` trong trace — chúng có đủ thông tin để debug không?  

Trong trace, `route_reason` được lưu với định dạng `[Lý do route chính] | [Cờ cảnh báo phụ]`, nên rất rõ ràng và dễ dàng debug (ví dụ: `task chứa keyword chính sách/cấp quyền -> chọn policy tool | bật cờ risk_high (cẩn trọng)`). Đây là một cải tiến nhỏ mà rất hữu hiệu trong lúc grading.
