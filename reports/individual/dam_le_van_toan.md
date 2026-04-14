# Báo Cáo Cá Nhân — Lab Day 09: Multi-Agent Orchestration

**Họ và tên:** Đàm Lê Văn Toàn  
**Vai trò trong nhóm:** Trace & Docs Owner  
**Ngày nộp:** 14/04/2026  
**Độ dài yêu cầu:** 500–800 từ

---

## 1. Tôi phụ trách phần nào? (100–150 từ)

**Module/file tôi chịu trách nhiệm:**
- File chính: `eval_trace.py` — implement toàn bộ logic thu thập trace, xuất `artifacts/grading_run.jsonl` và `artifacts/eval_report.json` sau khi chạy 10 grading questions. (Do trước 18:00 các module khác chưa hoàn thành nên chưa có commit)
- Bộ tài liệu: `docs/single_vs_multi_comparison.md`, `docs/system_architecture.md` — tổng hợp số liệu thực tế từ cả Day 08 và Day 09 để viết đánh giá so sánh.
- Hỗ trợ fix lỗi merge conflict tại `graph.py` (commit `73163b1`, 18:01 ngày 14/04/2026).
- Commit `grading_questions.json` vào repo để kích hoạt pipeline test (commit `38101e2`, 17:34 ngày 14/04/2026).

**Cách công việc của tôi kết nối với phần của thành viên khác:**  
Tôi nhận `AgentState` output từ `graph.py` (Phạm Tuấn Anh) và các workers (`retrieval_worker`, `policy_tool_worker`, `synthesis_worker`), thu thập các trường `route_reason`, `workers_called`, `confidence`, `latency_ms` rồi ghi vào JSONL để cả nhóm debug sau mỗi câu query.

**Bằng chứng (commit hash):**
- `38101e2` — `add grading_questions` (17:34, trước deadline 18:00)
- `73163b1` — `edit graph` (18:01, sau deadline — không tính vào điểm code nhưng là fix merge conflict cần thiết)
- Output: `artifacts/eval_report.json` (`"generated_at": "2026-04-14T17:33:24.364713"`)

---

## 2. Tôi đã ra một quyết định kỹ thuật gì? (150–200 từ)

**Quyết định:** Commit `grading_questions.json` vào repo lúc 17:34 để kích hoạt pipeline test, thay vì chờ đến sau deadline. Đồng thời nhận nhiệm vụ resolve merge conflict trong `graph.py` do các thành viên khác code riêng rẽ và chưa kịp tổng hợp.

**Bối cảnh:**  
Lúc 17:30 đề bài public 10 câu grading questions. Các thành viên khác trong nhóm còn đang hoàn thiện worker. Nếu không có `grading_questions.json` trong repo thì `eval_trace.py` không có input để chạy. Quyết định push file này sớm (17:34) giúp pipeline có thể được test ngay, output `grading_run.jsonl` được sinh ra trước 18:00.

**Lý do chọn cách này thay vì chờ:**  
Luật chỉ tính `artifacts/grading_run.jsonl` nếu commit trước 18:00 (xem SCORING.md). Nếu chờ đủ mọi thứ hoàn chỉnh thì có nguy cơ commit trễ và mất điểm toàn bộ phần grading questions.

**Trade-off đã chấp nhận:**  
Docs và report phải viết sau 18:00 với thông tin trace thu thập được, không có thời gian review thoải mái. Ngoài ra commit fix `graph.py` ở 18:01 — đúng 1 phút sau deadline — không được tính vào điểm code, nhưng cần thiết để pipeline chạy được sau 18:00 phục vụ việc viết report.

**Bằng chứng từ trace/code:**
```json
{
  "generated_at": "2026-04-14T17:33:24.364713",
  "day09_multi_agent": {
    "total_traces": 33,
    "avg_confidence": 0.455,
    "avg_latency_ms": 4498
  }
}
```

---

## 3. Tôi đã sửa một lỗi gì? (150–200 từ)

**Lỗi:** Merge conflict markers chưa được resolve trong `graph.py` sau khi merge PR của nhiều thành viên.

**Symptom (pipeline làm gì sai?):**  
Khi chạy `eval_trace.py`, Python báo `SyntaxError` ngay lập tức do file `graph.py` chứa các ký tự merge conflict (`<<<<<<< HEAD`, `=======`, `>>>>>>>`) ở phần khai báo import workers và docstring của `policy_tool_worker_node`. Pipeline crash hoàn toàn, không generate được bất kỳ trace nào.

**Root cause (lỗi nằm ở đâu):**  
Nằm ở `graph.py`, cụ thể tại block import workers (quanh dòng 177) và docstring của `policy_tool_worker_node`. Khi PR của Nguyễn Quang Trường (Policy Worker, branch `03d841b`) được merge vào, Git sinh conflict giữa phần TODO comment của branch cũ và phần import thật của branch mới. Conflict markers được giữ nguyên thay vì được resolve trước khi push.

**Cách sửa (commit `73163b1`):**  
Mở `graph.py`, xóa toàn bộ conflict markers, giữ lại phiên bản đúng:
```python
# Trước (có conflict markers — SyntaxError):
<<<<<<< HEAD
from workers.retrieval import run as retrieval_run
from workers.policy_tool import run as policy_tool_run
from workers.synthesis import run as synthesis_run
=======
# TODO Sprint 2: Uncomment sau khi implement workers
from workers.policy_tool import run as policy_tool_run
>>>>>>> 03d841b (Policy Enforcer (Policy + MCP Client))

# Sau (đã clean):
from workers.retrieval import run as retrieval_run
from workers.policy_tool import run as policy_tool_run
from workers.synthesis import run as synthesis_run
```

**Bằng chứng trước/sau:**
> Trước: `SyntaxError: invalid syntax` tại dòng `<<<<<<< HEAD` trong `graph.py`  
> Sau: Pipeline pass thành công, `grading_run.jsonl` được generate với đủ 10 câu, confidence trung bình 0.534

---

## 4. Tôi tự đánh giá đóng góp của mình (100–150 từ)

**Tôi làm tốt nhất ở điểm nào?**  
Làm tốt nhất ở khâu giải quyết bottleneck cuối: resolve merge conflict kịp thời giúp pipeline chạy được, và commit `grading_questions.json` đúng timing để output `grading_run.jsonl` có mặt trong repo trước 18:00. Nếu không có 2 hành động này, nhóm sẽ không có điểm grading questions.

**Tôi làm chưa tốt hoặc còn yếu ở điểm nào?**  
Tốc độ viết docs còn chậm. Vì phải chờ pipeline chạy xong mới có số liệu thực tế để điền, toàn bộ docs (`single_vs_multi_comparison.md`, `system_architecture.md`) phải viết sau 18:00 — đây là rủi ro không cần thiết nếu setup template docs sớm hơn từ Sprint 1. Tuy nhiên theo SCORING.md, docs commit sau 18:00 vẫn không được tính điểm nếu file đó thuộc loại deadline 18:00 (`docs/*.md`).

**Nhóm phụ thuộc vào tôi ở đâu?**  
Nếu tôi không resolve conflict ở `graph.py` kịp lúc, không ai trong nhóm chạy được pipeline để lấy kết quả. Cả phần grading questions và trace artifacts đều bị block.

**Phần tôi phụ thuộc vào thành viên khác:**  
Tôi cần các workers (`retrieval.py`, `policy_tool.py`, `synthesis.py`) hoàn thành trước mới có thể hook `eval_trace.py` vào đúng điểm và collect trace đầy đủ. Sự chậm trễ của các worker đẩy thời gian viết docs sang sau 18:00.

---

## 5. Nếu có thêm 2 giờ, tôi sẽ làm gì? (50–100 từ)

Tôi sẽ build dashboard log tự động thay cho file JSON thô. Qua trace của `gq09` (`latency_ms: 4337`) và `gq01` (`latency_ms: 5765`), tôi thấy latency biến động lớn: gq07 chỉ 2003ms (câu abstain nhanh vì không đủ chunk) trong khi gq01 mất 5765ms (multi-step với nhiều source). Gắn visualization như LangSmith hay Prometheus sẽ cho thấy node nào đang làm delay toàn bộ response — thông tin này giúp tối ưu routing thay vì phải đọc thủ công từng dòng JSONL.
