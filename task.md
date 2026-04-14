# Lab Day 09: Master Checklist (Nhóm 6 người)

Cấu trúc này đã được review chéo với `SCORING.md` và `README.md` để đảm bảo: **Mỗi người có 1 file python** (không ai bị 0 điểm đóng góp) và **phủ 100%** Deliverables.

## [ ] Người 1: Flow Master (Supervisor & Graph)
- `[ ]` Code: Khởi tạo file `graph.py` và định nghĩa `AgentState`.
- `[ ]` Code: Viết hàm `supervisor_node()` và `route_decision()`.
- `[ ]` Code: Đảm bảo Supervisor log đúng biến `supervisor_route` và `route_reason` vào kết quả đầu ra.
- `[ ]` Doc: Viết file `docs/routing_decisions.md` (Ghi nhận 3 quyết định routing thực tế).
- `[ ]` Đánh giá: Thử nghiệm độc lập xem graph route có đến đúng các nhánh dự kiến (ví dụ: route đến human review nếu lỗi, policy vs retrieval).
- `[ ]` Report: Viết báo cáo cá nhân `reports/individual/nguoi1.md` tập trung vào logic routing.

## [ ] Người 2: Data Finder (Retrieval & Contracts)
- `[ ]` Code: Code chức năng `workers/retrieval.py` nhận state và query ChromaDB.
- `[ ]` Môi trường: Thử dùng script python (trong file `.md`) khởi tạo ChromaDB với 5 docs đã mô phỏng.
- `[ ]` Config: Viết file `contracts/worker_contracts.yaml` quy định chuẩn Input/Output cho toàn bộ các thư mục Worker.
- `[ ]` Đánh giá: Test `retrieval.py` độc lập không qua graph.
- `[ ]` Report: Viết báo cáo cá nhân `reports/individual/nguoi2.md` nói về schema trong contract và logic truy vấn tài liệu.

## [ ] Người 3: Policy Enforcer (Policy + MCP Client)
- `[ ]` Code: Code nhánh `workers/policy_tool.py` xử lý dữ liệu và check các điều khoản.
- `[ ]` Đánh giá: Chạy test độc lập focus bắt các exception case đặc biệt: Sale/ Digital Product, P1 khẩn.
- `[ ]` Code: Thêm client để tương tác trực tiếp lên file `mcp_server.py`.
- `[ ]` Doc: Viết phần Policy Worker trong báo cáo nhóm `reports/group_report.md`.
- `[ ]` Report: Viết báo cáo cá nhân `reports/individual/nguoi3.md` nói về các edge-cases và test case liên quan.

## [ ] Người 4: Truth Synthesizer (Synthesis)
- `[ ]` Code: Khởi tạo module `workers/synthesis.py` tổng hợp source từ Retrieval và kết quả Policy.
- `[ ]` Code: Chỉnh prompt gắt gao - "chỉ dùng context, không ảo giác, Abstain nếu không tìm thấy thông tin" (để lấy điểm câu cấm gq07).
- `[ ]` Bonus (+1): Thêm tính toán `confidence` dựa trên format dữ liệu.
- `[ ]` Doc: Phụ trách format và chốt lại báo cáo nhóm `reports/group_report.md`.
- `[ ]` Report: Viết báo cáo cá nhân `reports/individual/nguoi4.md` tập trung vào prompt grounding và chống hallucination.

## [ ] Người 5: External Connector (MCP Server)
- `[ ]` Code: Xây dựng tool server ở file `mcp_server.py` với tối thiểu 2 mock tools: `search_kb`, `get_ticket_info`.
- `[ ]` Bonus (+2): Nâng cấp tools thành HTTP MCP thật (Thay vì hàm mock python thông thường).
- `[ ]` Doc: Sở hữu và viết sơ đồ `docs/system_architecture.md` (Có lưu ý flow MCP).
- `[ ]` Report: Viết báo cáo cá nhân `reports/individual/nguoi5.md` tập trung vào thiết kế chuẩn MCP giao tiếp.

## [ ] Người 6: QA & Tracker (Eval Trace)
- `[ ]` Code: Xây dựng tools `eval_trace.py` để invoke tự động graph cho 15 câu hỏi. 
- `[ ]` Trace: Viết script gen log file JSONL vào file `artifacts/grading_run.jsonl`.
- `[ ]` Doc: Viết file so sánh `docs/single_vs_multi_comparison.md`.
- `[ ]` Nhiệm vụ 17:00: Khi đề bài public (grading_questions.json), Người 6 là người ấn nút chạy benchmark và nộp.
- `[ ]` Report: Viết báo cáo cá nhân `reports/individual/nguoi6.md` tập trung vào phân tích trace log và so sánh metrics.

---
## [ ] Bước chuẩn bị ngay lập tức (Team)
- `[ ]` Chạy `pip install -r requirements.txt`.
- `[ ]` Sao chép `.env.example` sang `.env` và nhập API key (LLM).
- `[ ]` Khởi chạy dữ liệu ChromaDB ban đầu.
- `[ ]` Tạo sẵn 6 file `reports/individual/[ten_thanh_vien].md` và push nháp để đánh dấu sở hữu.
