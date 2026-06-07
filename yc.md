# AI Customer Support Chatbot for E-commerce (MedusaJS)

## Project Overview

Build an intelligent customer support chatbot integrated into an e-commerce website.

The chatbot can:

* Understand natural language
* Answer product-related questions
* Check order status
* Recommend products using AI
* Escalate to human support when needed

---

# System Architecture

```text
+------------------+
|      User        |
+--------+---------+
         |
         v
+------------------+
| Dialogflow CX    |
| Intent Detection |
+--------+---------+
         |
         v
+------------------+
| FastAPI Webhook  |
| Chatbot Service  |
+--------+---------+
         |
         +-------------------+
         |                   |
         v                   v
+----------------+   +----------------+
|   MedusaJS     |   |     Gemini     |
| E-commerce API |   | Recommendation |
+-------+--------+   +--------+-------+
        |                    |
        +----------+---------+
                   |
                   v
          +------------------+
          | PostgreSQL       |
          | Products/Orders  |
          +------------------+
```

---

# Technology Stack

## Frontend

* Next.js Storefront
* Medusa Storefront UI

## AI Layer

* Dialogflow CX
* Google Gemini API

## Backend

* FastAPI Microservice

## E-commerce Backend

* MedusaJS v2

## Database

* PostgreSQL

## Deployment

* Docker
* Docker Compose
* AWS EC2

---

# Intent Design

## Greeting

Examples:

* Xin chào
* Chào shop
* Hello
* Hi

Response:

```text
Xin chào. Tôi có thể hỗ trợ tra cứu đơn hàng và tư vấn sản phẩm cho bạn.
```

---

## ProductPrice

Examples:

* Giá áo hoodie bao nhiêu?
* Áo polo giá bao nhiêu?
* Quần jogger giá bao nhiêu?

Flow:

```text
User
↓
Dialogflow Intent
↓
FastAPI
↓
Medusa Product API
↓
Get Product Price
↓
Return Response
```

Response Example:

```text
Áo hoodie hiện có giá 299.000 VNĐ.
```

---

## OrderTracking

Examples:

* Đơn hàng ORD-1001 ở đâu?
* Kiểm tra đơn hàng ORD-1001
* Tra cứu vận đơn

Flow:

```text
User
↓
Dialogflow Intent
↓
FastAPI
↓
Medusa Order API
↓
Get Order Status
↓
Return Response
```

Response Example:

```text
Đơn hàng ORD-1001 hiện đang được giao.
```

---

## HumanHandover

Examples:

* Tôi muốn gặp nhân viên
* Kết nối hỗ trợ

Response:

```text
Xin vui lòng liên hệ nhân viên hỗ trợ qua hotline hoặc email hỗ trợ khách hàng.
```

---

## ProductRecommendation (AI Feature)

Examples:

* Tôi cần áo mặc mùa đông dưới 500k
* Gợi ý sản phẩm cho nam
* Tôi thích phong cách streetwear

Flow:

```text
User
↓
Dialogflow Intent
↓
FastAPI
↓
Medusa Product Catalog
↓
Gemini Analysis
↓
AI Recommendation
↓
Response
```

Response Example:

```text
Dựa trên nhu cầu của bạn, tôi đề xuất:

- Áo Hoodie Basic Black
- Oversized Sweatshirt Grey
- Streetwear Bomber Jacket
```

---

# FastAPI Responsibilities

## Webhook Endpoint

```http
POST /webhook
```

Responsibilities:

* Receive Dialogflow CX requests
* Parse intent and parameters
* Query Medusa APIs
* Call Gemini when required
* Return Dialogflow CX response format

---

# Medusa Integration

## Product APIs

```http
GET /store/products
GET /store/products/{id}
```

Use Cases:

* Product search
* Price lookup
* Product information

---

## Order APIs

```http
GET /admin/orders
```

Use Cases:

* Order tracking
* Order details
* Customer support

---

# Docker Deployment

Services:

```yaml
services:
  postgres:
  medusa:
  chatbot-service:
```

---

# AWS Deployment

Infrastructure:

```text
AWS EC2
│
├── PostgreSQL
├── MedusaJS
├── FastAPI Chatbot
└── Docker Compose
```

Benefits:

* Cloud deployment
* Easy scaling
* Simplified management
* Low cost

---

# Evaluation Criteria Mapping

## Architecture (3 points)

✓ Dialogflow CX

✓ FastAPI Microservice

✓ MedusaJS

✓ PostgreSQL

✓ AWS

✓ Docker

---

## Implementation & Demo (4 points)

✓ Greeting Intent

✓ Product Price Query

✓ Order Tracking

✓ Human Handover

✓ AI Recommendation

---

## Optimization & Cost (1 point)

✓ Docker Containerization

✓ AWS EC2 Deployment

✓ Cost Estimation

---

## Report & Presentation (2 points)

✓ Architecture Diagram

✓ Deployment Diagram

✓ System Flow

✓ Demo Video

---

# Expected Demo Scenario

### Scenario 1

User:

```text
Giá áo hoodie bao nhiêu?
```

Bot:

```text
Áo hoodie hiện có giá 299.000 VNĐ.
```

---

### Scenario 2

User:

```text
Đơn hàng ORD-1001 ở đâu?
```

Bot:

```text
Đơn hàng ORD-1001 hiện đang được giao.
```

---

### Scenario 3

User:

```text
Tôi cần áo mặc mùa đông dưới 500k.
```

Bot:

```text
Dựa trên nhu cầu của bạn, tôi đề xuất:

- Hoodie Basic Black
- Oversized Sweatshirt Grey
- Streetwear Bomber Jacket
```

---

### Scenario 4

User:

```text
Tôi muốn gặp nhân viên hỗ trợ.
```

Bot:

```text
Xin vui lòng liên hệ nhân viên hỗ trợ qua hotline hoặc email hỗ trợ khách hàng.
```
