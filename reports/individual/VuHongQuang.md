# Individual Report - Role 1 (Supervisor & Graph)

**Thông tin:**
- Họ và tên: Vũ Hồng Quang
- Vai trò thực thụ: External Connector
- Role Lab: MCP Server

## 1. Phần phụ trách kỹ thuật
Dự án ngày 09 yêu cầu chuyển đổi cấu trúc pipeline từ dạng monolith sang dạng hệ phân tán Supervisor-Worker. Tôi là người triển khai MCP cho hệ thống, là chuẩn giúp agent giao tiếp với tool bên ngoài hiệu quả hơn. Hiện tại MCP server của hệ thống chỉ là mock, ta cần Tool worker gọi được external capability. Cụ thể:
- Tôi thiết triển khai tool_search_kb(query, top_k), get_ticket_info(ticket_id).
- Nâng cấp tools thành HTTP MCP thật (Thay vì hàm mock python thông thường).

**(Bằng chứng Code Contribution):** Commit ở file `mcp.py` có thông tin tài khoản của tôi.

## 2. Quyết định kỹ thuật: embedding
Tôi sử dụng mô hình ngôn ngữ lớn của Open AI để embedding câu hỏi thay vì sentence-transformers (all-MiniLM-L6-v2), sau đó dùng embedding này để tìm kiếm trong chromaDB. ban đầu, tôi sử dụng sentence-transformers (all-MiniLM-L6-v2) vì nó rẻ và tôi nghĩ là đủ để đáp ứng yêu cầu, nhưng vì quy định chung của nhóm nên tôi sử dụng Open AI. Có lợi là sẽ chính xác hơn nhưng đánh đổi là sẽ tốn kém hơn.

## 3. Quá trình khắc phục lỗi (Troubleshoot/Debug)
**Lỗi gặp phải:** lỗi classic của ChromaDB và embedding mismatch
- **Mô tả:** Khi emnedding bằng sentence-transformers (all-MiniLM-L6-v2) thì kết quả cho ra embedding 384 chiều nhưng csdl của chúng tôi yêu cầu embedding 1536 chiều
- **Cách khắc phục:** 
    Dùng OpenAI embedding (text-embedding-3-small) để embedding query của user

## 4. Tự đánh giá
- **Làm tốt:** triển khai được MCP http server
- **Yếu điểm:** Chưa làm nhanh
- **Phụ thuộc nhóm:** MCP không phụ thuộc và các thành phần khác của hệ thống

## 5. Nếu có thêm 2h để phát triển cải tiến
Tôi sẽ triển khai thêm nhiều tool hơn và thêm các error handling chi tiết.
