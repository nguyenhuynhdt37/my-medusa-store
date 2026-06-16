# Hướng dẫn Khởi tạo Môi trường mới (Bootstrap Guide)

Tài liệu này hướng dẫn cách triển khai hạ tầng và tích hợp Amazon Lex V2 từ đầu (clean setup).

---

## 1. Tại sao không thể tạo Lex Bot trước?

Trong AWS, mối quan hệ giữa **Amazon Lex V2** và **AWS Lambda** hoạt động như sau:
1. Lex Bot nhận diện ý định của người dùng (Intents).
2. Lex Bot cần gửi dữ liệu sang một **hàm Lambda cụ thể (Fulfillment Hook)** để xử lý nghiệp vụ (tra cứu thông tin, tạo giỏ hàng,...).
3. Do đó, cấu hình của Lex Bot bắt buộc phải chứa **ARN (Amazon Resource Name) chính xác** của hàm Lambda đó.

Nếu chạy script tạo Lex Bot trước khi chạy Terraform:
* Hàm Lambda chưa tồn tại trên AWS $\rightarrow$ Không có ARN để liên kết.
* Script `./scripts/import_lex_bot.sh` sẽ không thể tìm thấy ARN từ Terraform State và báo lỗi dừng chương trình.

**Vì vậy, Lambda bắt buộc phải được tạo trước thông qua Terraform.**

---

## 2. Quy trình 4 bước khởi tạo (Bootstrap Workflow)

### Bước 1: Khởi chạy Terraform lần đầu (Tạo hạ tầng nền)
Đảm bảo bạn đã điền các biến cơ bản trong `terraform.tfvars` (tạm thời điền `managed_lex_bot_id` bằng một giá trị giả lập có 10 ký tự viết hoa/số như `"EMPTYBOTID"`). Sau đó chạy:
```bash
terraform apply -auto-approve
```
* **Kết quả mong đợi**: Terraform tạo xong VPC, EC2, IAM, EIP và hàm Lambda `chatbot-lambda`.
* *Lưu ý*: Tiến trình này ở cuối sẽ báo lỗi ở block `terraform_data.lex_bot_deployment` vì `"EMPTYBOTID"` chưa tồn tại thực tế trên AWS. Điều này hoàn toàn bình thường, các hạ tầng cơ bản đã được tạo xong.

### Bước 2: Tạo Lex Bot mới trên AWS
Chạy script triển khai bot bằng cờ `--allow-create` để cấp quyền tạo mới:
```bash
./scripts/import_lex_bot.sh --allow-create
```
* **Kết quả mong đợi**: Script sẽ tự động lấy Lambda ARN đã tạo ở Bước 1, nén cấu hình JSON trong thư mục `infra/lex`, tạo mới Bot trên AWS, build locale và liên kết với Lambda.
* Khi kết thúc, script sẽ tự động ghi đè ID của Bot mới tạo vào biến `managed_lex_bot_id` trong file [terraform.tfvars](file:///Users/huynh/codes/project_dtdm/my-medusa-store/infra/terraform.tfvars) cho bạn.

### Bước 3: Chạy Terraform lần hai để hoàn tất
Chạy lại lệnh apply để Terraform đồng bộ ID bot thật vào biến môi trường của EC2 và kích hoạt Docker Compose:
```bash
terraform apply -auto-approve
```
* **Kết quả mong đợi**: Hệ thống chạy mượt mà không lỗi. Các container Docker trên EC2 tự động khởi chạy và kết nối trực tiếp với Lex Bot qua Lambda.

---

## 3. Lưu ý khi dọn dẹp (Terraform Destroy)
* Khi chạy `terraform destroy`, Lex Bot trên AWS **sẽ không bị xóa** (để giữ nguyên ID tránh việc cấu hình lại mệt mỏi cho lần sau).
* Nếu thực sự muốn xóa sạch Lex Bot trên AWS, hãy đăng nhập vào AWS Console và xóa thủ công Bot mang ID tương ứng.
