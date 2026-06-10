# Phân Tích & Ước Tính Chi Phí (Cost Estimation)

Tài liệu này cung cấp dự toán chi phí cơ bản để vận hành hệ thống **Medusa E-commerce & AI Chatbot** trên môi trường Production. Các con số mang tính chất ước tính dựa trên lưu lượng truy cập giả định (khoảng 10,000 phiên chat/tháng).

## 1. Cloud Hosting & Database (Infrastructure)

Mô hình triển khai đề xuất: **Docker Swarm** (Auto-scaling / High Availability)

| Dịch vụ | Cấu hình đề xuất | Chi phí ước tính (Tháng) |
|---|---|---|
| **App Server (VPS/EC2)** | 2x Node (2 vCPU, 4GB RAM) - Chạy Backend, Frontend, Chatbot Service | ~$40.00 |
| **PostgreSQL Database** | Managed DB (e.g. AWS RDS t3.micro hoặc DO Managed DB) | ~$15.00 |
| **Redis Cache** | Managed Redis (hoặc tự host trên EC2/Droplet nhỏ) | ~$10.00 |
| **Network/Bandwidth** | 100GB Outbound | ~$5.00 |
| **Tổng cộng** | | **~$70.00** |

> [!TIP]
> Để tối ưu trong giai đoạn đầu (MVP), có thể tự host toàn bộ DB & Redis trên 1 VPS duy nhất với cấu hình trung bình (4 vCPU, 8GB RAM). Khi đó chi phí sẽ giảm xuống chỉ còn khoảng **$20.00 - $40.00 / tháng**.

## 2. Dịch vụ Trí tuệ Nhân tạo (AI & NLP)

Lưu lượng dự kiến: 10,000 phiên chat/tháng (Mỗi phiên trung bình 5 tin nhắn = 50,000 requests).

| Dịch vụ | Đơn giá | Ước tính với 50,000 requests | Chi phí (Tháng) |
|---|---|---|---|
| **AWS Lex V2 (NLU)** | $0.00075 / text request | 50,000 * $0.00075 | $37.50 |
| **Google Gemini Flash 2.5** | $0.30/1M tokens (Input) <br> $2.50/1M tokens (Output) | ~10M tokens Input, ~2M tokens Output | ~$8.00 |
| **AWS Lambda** | $0.20/1M request + Duration cost | Miễn phí trong Free Tier | $0.00 |
| **Tổng cộng** | | | **~$45.50** |

## 3. Tổng Chi Phí (TCO) & Auto-Scaling

Tổng chi phí ước tính để vận hành trơn tru trong tháng đầu tiên: **~$115.50 / tháng**.

### Chiến lược Auto-Scaling & Tối ưu hóa (Optimization Strategy)
Hệ thống được cấu hình file `docker-compose.prod.yml` tích hợp **Docker Swarm / Compose V2** để có khả năng:
1. **Replicas & Load Balancing**: Dịch vụ `storefront` và `chatbot-service` được cấu hình chạy nhiều bản sao (`replicas: 2`), chịu tải gấp đôi so với dev.
2. **Resource Limits**: Giới hạn CPU (`cpus: '0.5'`) và RAM (`memory: 512M`) cho mỗi container tránh tình trạng OOM (Out Of Memory) sập chéo.
3. **Log Rotation**: Cấu hình `max-size: 10m` giúp log không bao giờ phình to làm đầy ổ cứng.

> [!IMPORTANT] 
> Điểm nhấn của dự án: Tích hợp hệ thống tracking chi phí tự động lưu vào Database (`ai_usage` table) thông qua migration `003_ai_cost_analytics.sql` giúp Admin theo dõi Real-time số tiền đang tiêu tốn cho AI, tránh tình trạng đội vốn (Billing Alert).
