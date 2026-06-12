# Huong dan chay local

Tai lieu nay dung cho cac ban trong team can chay du moi truong Medusa Backend, Storefront va Chatbot/WebSocket service.

## 1. Yeu cau cai san

- Node.js >= 20
- pnpm 10.x
- Docker Desktop
- Python 3.10+ neu chay `chatbot-service` thu cong
- File credential neu dung Dialogflow/Google: `google-credentials.json`
- API key neu dung Gemini: `GEMINI_API_KEY`

Kiem tra nhanh:

```bash
node -v
pnpm -v
docker -v
python3 --version
```

## 2. Port mac dinh

| Service | URL |
|---|---|
| Storefront | http://localhost:8000 |
| Medusa Backend/Admin | http://localhost:9000 |
| Chatbot service | http://localhost:8080 |
| Realtime WebSocket | ws://localhost:9001 |

Live Chat dang dung WebSocket truc tiep o:

```txt
ws://localhost:9001/ws/chat/:conversationId
ws://localhost:9001/ws/chat/admin
```

## 3. Chay nhanh bang Docker Compose

Day la cach nen dung cho team vi da gom Postgres, Redis, Backend, Storefront, Chatbot service.

### 3.1 Tao file `.env`

Cap nhat file `.env` duy nhat tai root repo voi cac bien can thiet:

```env
NEXT_PUBLIC_BASE_URL=https://store.itup.id.vn
NEXT_PUBLIC_MEDUSA_BACKEND_URL=https://admin.itup.id.vn
NEXT_PUBLIC_CHAT_WS_URL=wss://admin.itup.id.vn
VITE_CHAT_WS_URL=wss://admin.itup.id.vn
MEDUSA_BACKEND_URL=http://backend:9000
MEDUSA_INTERNAL_URL=http://backend:9000
MEDUSA_BASE_URL=http://backend:9000
STOREFRONT_INTERNAL_URL=http://storefront:8000
STOREFRONT_BASE_URL=https://store.itup.id.vn
CHATBOT_SERVICE_URL=http://chatbot-service:8080/webhook
CHAT_REALTIME_URL=http://realtime:9001
CHAT_REALTIME_PORT=9001
GEMINI_API_KEY=your_gemini_api_key
GEMINI_MODEL=gemini-2.5-flash
GEMINI_ENABLED=true
```

Neu dung Google/Dialogflow, dat file service account tai:

```txt
google-credentials.json
```

Khong commit file credential len git.

### 3.2 Start tat ca service

```bash
make dev
```

Lan dau se hoi lau vi container backend/storefront cai dependencies va migrate DB.

### 3.3 Mo trinh duyet

- Storefront: http://localhost:8000/vn
- Admin: http://localhost:9000/app
- Chatbot service health/API: http://localhost:8080

### 3.4 Stop service

```bash
make dev-down
```

Neu muon xoa sach volume DB/cache:

```bash
docker compose down -v
```

Chi dung `-v` khi chap nhan mat data local.

## 4. Chay thu cong tung service

Dung cach nay khi can debug rieng frontend/backend/python service.

### 4.1 Cai dependencies

Tu root repo:

```bash
corepack enable
pnpm install --frozen-lockfile
```

### 4.2 Chay Postgres va Redis

Co the dung Docker Compose chi cho DB/cache:

```bash
docker compose up postgres redis
```

### 4.3 Backend

Kiem tra `apps/backend/.env`. Toi thieu can:

```env
DATABASE_URL=postgres://postgres:postgres@localhost:5432/ecomoi
REDIS_URL=redis://localhost:6379
JWT_SECRET=supersecret
COOKIE_SECRET=supersecret
STORE_CORS=http://localhost:8000
ADMIN_CORS=http://localhost:9000,http://localhost:5173
AUTH_CORS=http://localhost:9000,http://localhost:5173,http://localhost:8000
```

Chay migrate va dev:

```bash
pnpm --filter @dtc/backend exec medusa db:migrate --execute-safe-links
pnpm backend:dev
```

Backend/Admin se chay o:

```txt
http://localhost:9000
```

### 4.4 Storefront

Kiem tra `apps/storefront/.env.local`. Toi thieu can:

```env
MEDUSA_BACKEND_URL=http://localhost:9000
NEXT_PUBLIC_MEDUSA_BACKEND_URL=http://localhost:9000
NEXT_PUBLIC_MEDUSA_PUBLISHABLE_KEY=pk_...
NEXT_PUBLIC_DEFAULT_REGION=vn
NEXT_PUBLIC_BASE_URL=http://localhost:8000
CHATBOT_SERVICE_URL=http://localhost:8080/webhook
```

Chay:

```bash
pnpm storefront:dev
```

Storefront se chay o:

```txt
http://localhost:8000
```

### 4.5 Chatbot service

```bash
cd chatbot-service
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Cap nhat `chatbot-service/.env`:

```env
MEDUSA_BASE_URL=http://localhost:9000
MEDUSA_PUBLISHABLE_API_KEY=pk_...
MEDUSA_REGION_COUNTRY_CODE=vn
STOREFRONT_BASE_URL=http://localhost:8000
STOREFRONT_COUNTRY_CODE=vn
GEMINI_API_KEY=your_gemini_api_key
GEMINI_ENABLED=true
```

Chay service:

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8080 --reload
```

## 5. Seed data

Neu DB moi hoan toan, chay seed backend:

```bash
pnpm backend:seed
```

Neu can bo du lieu demo/context them:

```bash
cd apps/backend
pnpm run seed:context
```

## 6. Kiem tra Live Chat

### 6.1 Storefront customer

1. Mo http://localhost:8000/vn
2. Mo widget chat goc phai.
3. Gui tin nhan.
4. Kiem tra:
   - Tin nhan Bot co label `Tro ly Medusan`.
   - Tin nhan Admin co label `NV Ho tro`.
   - Badge trang thai doi theo flow.
   - Typing indicator chi hien khi co WebSocket `typing.start`.

### 6.2 Admin

1. Mo http://localhost:9000/app
2. Vao Live Chat.
3. Flow can test:
   - `WAITING_ADMIN` -> bam `Tiep nhan ho tro` -> `IN_PROGRESS`
   - Admin go tin nhan -> customer thay `Nhan vien dang nhap...`
   - Customer go tin nhan -> admin thay `Khach dang nhap...`
   - Admin bam `Giao lai cho Bot` -> customer thay system message va quay ve AI
   - Customer bam `Ket thuc ho tro` -> quay ve `BOT_HANDLED`

## 7. Lenh verify truoc khi push

```bash
pnpm --filter @dtc/backend build
pnpm --filter @dtc/storefront build
python3 -m py_compile chatbot-service/app/api/websocket.py
```

Lint storefront hien co mot so loi cu ngoai live chat. Neu chay:

```bash
pnpm --filter @dtc/storefront lint
```

co the fail o cac file nhu `cart.ts`, `add-address.tsx`, `chat-notifications.ts`, `language-select`.

## 8. Loi thuong gap

### Port da bi chiem

Kiem tra process:

```bash
lsof -i :8000
lsof -i :9000
lsof -i :8080
```

### WebSocket khong connect

Kiem tra chatbot service co chay khong:

```bash
curl http://localhost:8080
```

Kiem tra browser console xem co loi:

```txt
WebSocket connection to ws://localhost:8080/ws/chat/... failed
```

### Chat luu duoc tin nhan nhung Admin khong thay realtime

Kiem tra backend goi broadcast sang chatbot service duoc khong. Log backend se co:

```txt
websocket broadcast completed
```

Neu chay Docker, backend goi service bang:

```txt
http://chatbot-service:8080/api/broadcast
```

Neu chay thu cong, can dam bao route/backend dang cau hinh dung host hoac sua endpoint broadcast tu container hostname sang localhost khi can debug local.

### DB bi lech migration

Thu migrate lai:

```bash
pnpm --filter @dtc/backend exec medusa db:migrate --execute-safe-links
```

Neu local DB rac va co the xoa:

```bash
docker compose down -v
docker compose up --build
```
