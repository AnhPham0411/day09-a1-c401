# Báo Cáo Cá Nhân — Lab Day 09: Multi-Agent Orchestration

**Họ và tên:** Vũ Lê Hoàng 
**Vai trò trong nhóm:** Synthesis Owner 
**Ngày nộp:** 14/4/2026  
**Độ dài yêu cầu:** 500–800 từ

---

> **Lưu ý quan trọng:**
> - Viết ở ngôi **"tôi"**, gắn với chi tiết thật của phần bạn làm
> - Phải có **bằng chứng cụ thể**: tên file, đoạn code, kết quả trace, hoặc commit
> - Nội dung phân tích phải khác hoàn toàn với các thành viên trong nhóm
> - Deadline: Được commit **sau 18:00** (xem SCORING.md)
> - Lưu file với tên: `reports/individual/[ten_ban].md` (VD: `nguyen_van_a.md`)

---

## [ ] Người 4: Truth Synthesizer (Synthesis)
- `[ ]` Code: Khởi tạo module `workers/synthesis.py` tổng hợp source từ Retrieval và kết quả Policy.
- `[ ]` Code: Chỉnh prompt gắt gao - "chỉ dùng context, không ảo giác, Abstain nếu không tìm thấy thông tin" (để lấy điểm câu cấm gq07).
- `[ ]` Bonus (+1): Thêm tính toán `confidence` dựa trên format dữ liệu.
- `[ ]` Doc: Phụ trách format và chốt lại báo cáo nhóm `reports/group_report.md`.
- `[ ]` Report: Viết báo cáo cá nhân `reports/individual/nguoi4.md` tập trung vào prompt grounding và chống hallucination.

## 1. Tôi phụ trách phần nào? (100–150 từ)

Tôi phụ trách phần khởi tạo module `workers/synthesis.py` tổng hợp source từ Retrieval và kết quả Policy.

**Module/file tôi chịu trách nhiệm:**
- File chính: `synthesis.py`
- Functions tôi implement: `synthesize`; `calculate_confidence`; `_extract_sources_from_answer`, `_safe_generate`

**Cách công việc của tôi kết nối với phần của thành viên khác:**

Phần code của tôi kết nối synthesis vào graph.py

**Bằng chứng (commit hash, file có comment tên bạn, v.v.):**

file: `synthesis.py` và các function đã được implement và chỉnh sửa ở trong đó

---

## 2. Tôi đã ra một quyết định kỹ thuật gì? (150–200 từ)

> Chọn **1 quyết định** bạn trực tiếp đề xuất hoặc implement trong phần mình phụ trách.
> Giải thích:
> - Quyết định là gì?
> - Các lựa chọn thay thế là gì?
> - Tại sao bạn chọn cách này?
> - Bằng chứng từ code/trace cho thấy quyết định này có effect gì?

**Quyết định:** Tôi đã quyết định sử dụng prompt gắt gao để ngăn model bị hallucinate và thêm nhiều guardrails để chống prompt injection và jailbreak. Tôi cũng đã chỉnh sửa thêm sao cho llm đọc hiểu context tốt hơn.

**Ví dụ:**
> "Tôi chọn dùng keyword-based routing trong supervisor_node thay vì gọi LLM để classify.
>  Lý do: keyword routing nhanh hơn (~5ms vs ~800ms) và đủ chính xác cho 5 categories.
>  Bằng chứng: trace gq01 route_reason='task contains P1 SLA keyword', latency=45ms."

**Lý do:**

Lý do tôi chọn cách này là vì nó làm cho hệ thống agents của tôi an toàn hơn và đảm bảo hệ thống hoạt động đúng như những gì tôi muốn đó là chatbot helfdesk trả lời đúng, đưa ra dẫn chứng và không bịa đặt thông tin.

**Trade-off đã chấp nhận:**

Trade-off đã chấp nhận là tốn nhiều tài nguyên hơn để xử lý và tốn nhiều thời gian hơn để xử lý.

**Bằng chứng từ trace/code:**

```
[PASTE ĐOẠN CODE HOẶC TRACE RELEVANT VÀO ĐÂY]
```

---

## 3. Tôi đã sửa một lỗi gì? (150–200 từ)

> Mô tả 1 bug thực tế bạn gặp và sửa được trong lab hôm nay.
> Phải có: mô tả lỗi, symptom, root cause, cách sửa, và bằng chứng trước/sau.

**Lỗi:** Lỗi không tìm thấy thông tin trong tài liệu nội bộ.

**Symptom (pipeline làm gì sai?):**

Khi tôi test với câu hỏi "What is the P1 SLA for email support?", pipeline trả về "Không tìm thấy thông tin này trong tài liệu nội bộ." mặc dù trong tài liệu có thông tin về P1 SLA.

**Root cause (lỗi nằm ở đâu — indexing, routing, contract, worker logic?):**

Lỗi nằm ở phần synthesis worker, cụ thể là ở prompt của synthesis worker. Prompt của synthesis worker không đủ gắt để ngăn model bị hallucinate và không có guardrails để chống prompt injection và jailbreak.

**Cách sửa:**

Tôi đã chỉnh sửa lại prompt của synthesis worker để ngăn model bị hallucinate và có guardrails để chống prompt injection và jailbreak. Ngoài ra tôi còn chỉnh sửa thêm sao cho llm đọc hiểu context tốt hơn.

**Bằng chứng trước/sau:**
> Dán trace/log/output trước khi sửa và sau khi sửa.



---

## 4. Tôi tự đánh giá đóng góp của mình (100–150 từ)

> Trả lời trung thực — không phải để khen ngợi bản thân.

**Tôi làm tốt nhất ở điểm nào?**

Tôi làm tốt nhất ở việc chỉnh sửa prompt của synthesis worker để ngăn model bị hallucinate và có guardrails để chống prompt injection và jailbreak. Ngoài ra tôi còn chỉnh sửa thêm sao cho llm đọc hiểu context tốt hơn.

**Tôi làm chưa tốt hoặc còn yếu ở điểm nào?**

Tôi còn quá phụ thuộc vào llm và chưa tối ưu được prompt để giảm thiểu chi phí và thời gian xử lý.

**Nhóm phụ thuộc vào tôi ở đâu?** _(Phần nào của hệ thống bị block nếu tôi chưa xong?)_

Nhóm phụ thuộc vào tôi ở việc hoàn thành tool synthesis để có thể trả lời câu hỏi của người dùng.

**Phần tôi phụ thuộc vào thành viên khác:** _(Tôi cần gì từ ai để tiếp tục được?)_

Tôi phụ thuộc vào thành viên khác ở việc hoàn thành tool retrieval và policy để có thể trả lời câu hỏi của người dùng.

---

## 5. Nếu có thêm 2 giờ, tôi sẽ làm gì? (50–100 từ)

> Nêu **đúng 1 cải tiến** với lý do có bằng chứng từ trace hoặc scorecard.
> Không phải "làm tốt hơn chung chung" — phải là:
> *"Tôi sẽ thử X vì trace của câu gq___ cho thấy Y."*

Tôi sẽ thử nghiệm những prompt khác nhau để tối ưu được chi phí và thời gian xử lý. Ngoài ra tôi sẽ thử nghiệm với các model llm khác nhau để xem ngoài OpenAI ra thì có llm nào tốt hơn với công việc này không

---

*Lưu file này với tên: `reports/individual/[ten_ban].md`*  
*Ví dụ: `reports/individual/nguyen_van_a.md`*
