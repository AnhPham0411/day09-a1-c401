# Individual Report - Role 1 (Supervisor & Graph)

**Thông tin:**
- Họ và tên: [Điền tên của bạn]
- Vai trò thực thụ: Tech Lead / Team Lead
- Role Lab: Flow Master (Supervisor & Graph)

## 1. Phần phụ trách kỹ thuật
Dự án ngày 09 yêu cầu chuyển đổi cấu trúc pipeline từ dạng monolith sang dạng hệ phân tán Supervisor-Worker. Tại role của mình, tôi là người thiết kế và thi công trực tiếp **Module Trái Tim Hệ Thống** tại file `graph.py`. Cụ thể:
- Tôi thiết kế biến giao tiếp tổng `AgentState`, quy chuẩn hóa tất cả các biến vào ra giữa các Agent (bao gồm biến rủi ro `risk_high` và `route_reason` để lưu vết đồ thị).
- Tôi code hàm `supervisor_node()` đóng vai trò làm điều phối viên (Orchestrator). Hàm này bắt và phân loại Intent của User bằng Keyword matching nâng cao, từ đó ra quyết định Rẽ nhánh (Routing) chính xác dựa trên từng case.

**(Bằng chứng Code Contribution):** Tất cả các commit init core flow, bao gồm file `graph.py` và kiến trúc routing logic, có thông tin tài khoản của tôi.

## 2. Quyết định kỹ thuật: Tính năng Cờ Cảnh Báo Phụ (Risk Flag)
Thay vì sử dụng thuật toán gộp và bẻ nhánh tuyến tính kiểu 1-về-1, tôi quyết định áp dụng một quyết định kiến trúc: **Tách riêng Cờ rủi ro (Risk flag) khỏi đường dẫn logic (Logic path)**.
- **Vấn đề:** Có những câu hỏi phải gọi Policy Worker (ví dụ: hoàn tiền) nhưng đồng thời lại khẩn cấp, dễ mang rủi ro kiện tụng (P1 phản hồi chậm). Nếu code tuyến tính if/else thì rất dễ ghi đè lẫn nhau (dù khẩn cấp nhưng lọt vào ngách nhánh xử lý thông thường).
- **Quyết định:** Tôi viết logic để luôn phân tích từ khoá `emergency`, `err-` thành một cờ biến thái độc lập `risk_high = True`, rồi mới đưa qua nhánh xử lý Policy (ví dụ: `task chứa keyword chính sách/cấp quyền -> chọn policy tool | bật cờ risk_high`).
- **Minh chứng Trace:** Khi log trace của truy vấn `"Khách hàng Flash Sale yêu cầu hoàn tiền vì sản phẩm lỗi — được không?"`, trace của đồ thị in rõ `route_reason: task chứa keyword chính sách/cấp quyền -> chọn policy tool | bật cờ risk_high (cẩn trọng)`. Quyết định này giúp Human Verification dễ dàng xen vào lúc sau để review riêng các ca nhạy cảm.

## 3. Quá trình khắc phục lỗi (Troubleshoot/Debug)
**Lỗi gặp phải:** String encoding crash trên console Windows trong quá trình test chạy Unit Test. 
- **Mô tả:** Khi invoke Terminal chạy thử script `graph.py` để in log trace ra màn hình, Python terminal sập ngay lập tức vì Unicode Encode Error do ký tự thiết kế giao diện (`>` và các dấu tiếng Việt UTF-8) đụng độ với bảng mã cp1252 mặc định của Windows (`'charmap' codec can't encode character...`).
- **Cách khắc phục:** 
    1. Chủ động ép toàn bộ script loại bỏ ký tự không phổ thông khỏi console (`▶` đổi thành `>`).
    2. Đè biến môi trường local bằng PowerShell `$env:PYTHONUTF8=1` để ép chuẩn giao tiếp output về UTF-8 trước khi Python runtime kịp boot.
- **Kết quả:** Pipeline Supervisor hoạt động hoàn hảo, gen json trace mượt mà ra log file `run_20260414_144943.json` và log console đã đọc được rõ các log tiếng việt của mình.

## 4. Tự đánh giá
- **Làm tốt:** Dựng framework nhanh chóng và không ai phải đợi lâu để ghép nối. Phân nhánh đồ thị gọn gàng, log vết mạch lạc - đây là nền móng để 30 điểm bài test lúc 17h diễn ra trơn tru.
- **Yếu điểm:** Code logic routing ban đầu dùng keyword matching (Heuristic) nên chưa đủ Dynamic Mềm dẻo như cách giải NLP bằng Classifier prompt.
- **Phụ thuộc nhóm:** Supervisor rỗng tuếch nếu Retrieval và Policy Worker không trả về context như kỳ vọng trong state dictionary.

## 5. Nếu có thêm 2h để phát triển cải tiến
Tôi sẽ đập bỏ mô hình Regex/Keyword tĩnh hiện tại để **Áp dụng "LLM Router Node" (Semantic Router)** có tích hợp Json Schema. Khi truy xuất route từ file `eval_trace`, tôi thấy có vài câu hỏi đánh đố dùng Hidden Context, việc dùng keyword sẽ bị Fail Silent bắt route sai, và chỉ có Prompt Re-ranking của LLM Router mới xử lý triệt để Routing Accuracy lên 100%.
