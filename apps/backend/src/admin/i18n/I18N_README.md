# Hệ thống Quốc tế hóa (i18n) - Medusa Admin

## Tổng quan

Dự án đã triển khai hệ thống i18n hoàn chỉnh cho Medusa Admin, đảm bảo toàn bộ giao diện hiển thị bằng tiếng Việt.

## Cấu trúc

```
apps/
├── backend/src/admin/
│   └── i18n/
│       ├── index.ts          # Export resources cho Medusa Dashboard
│       ├── json/
│       │   └── vi.json       # Translation keys cho tiếng Việt
│       └── README.md         # Hướng dẫn của Medusa
│
└── storefront/src/modules/chatbot/
    └── i18n/
        └── index.ts          # Hệ thống i18n độc lập cho storefront
```

## Medusa Dashboard (Admin)

### Nguồn dịch sẵn

Medusa Dashboard v2.15.3 đã có sẵn **3051 dòng** translation cho tiếng Việt tại:

```
node_modules/@medusajs/dashboard/src/i18n/translations/vi.json
```

Bao gồm dịch cho: Dashboard, Orders, Products, Customers, Inventory, Promotions, Price Lists, Settings, User Management, Auth, Notifications, và hơn 30 ngôn ngữ khác.

### Custom Translations

File `i18n/json/vi.json` chứa translations riêng cho module **Live Chat**:

| Key | Mô tả |
|-----|--------|
| `chat.routeLabel` | Tên route trong sidebar |
| `chat.sidebar.*` | Text trong sidebar (tiêu đề, placeholder, badges) |
| `chat.stats.*` | Thống kê AI |
| `chat.status.*` | Trạng thái hội thoại (Bot, Chờ NV, Đang hỗ trợ, Đã đóng) |
| `chat.header.*` | Header panel chat |
| `chat.actions.*` | Các nút hành động |
| `chat.messages.*` | Tin nhắn trạng thái, placeholder |
| `chat.sender.*` | Nhãn người gửi |
| `chat.empty.*` | Empty state |
| `chat.error.*` | Thông báo lỗi |
| `chat.success.*` | Thông báo thành công |
| `chat.notifications.*` | Notification settings |
| `common.*` | Common actions (Lưu, Hủy, Xóa...) |

### Cách sử dụng trong Admin Routes/Widgets

```tsx
import { useTranslation } from "react-i18next"
import { defineRouteConfig } from "@medusajs/admin-sdk"

const MyPage = () => {
  const { t } = useTranslation()

  return (
    <div>
      <Heading>{t("chat.routeLabel")}</Heading>
      <Button>{t("common.save")}</Button>
    </div>
  )
}

export const config = defineRouteConfig({
  label: "chat.routeLabel",
  translationNs: "chat",
})
```

## Storefront Chatbot

Storefront chatbot sử dụng hệ thống i18n độc lập tại `modules/chatbot/i18n/index.ts`.

### Cách sử dụng

```tsx
import { t, formatPresence } from "../../i18n"

// Translation đơn giản
const title = t("chat.header.title")

// Translation với tham số
const message = t("chat.presence.minutesAgo", { count: 5 })

// Format thời gian tương đối
const lastSeen = formatPresence(isoString)
```

### Thêm translation mới

Mở file `modules/chatbot/i18n/index.ts` và thêm vào object `translations`:

```ts
const translations = {
  chat: {
    // ... existing keys
    newSection: {
      greeting: "Xin chào!",
      farewell: "Tạm biệt!",
    },
  },
}
```

## Dashboard - Bật Tiếng Việt

### Cách 1: Settings (Recommended)

1. Mở Medusa Admin Dashboard
2. Đi đến **Settings** → **Store**
3. Tìm phần **Language** hoặc **Locale**
4. Chọn **Tiếng Việt**
5. Dashboard sẽ reload với giao diện tiếng Việt

### Cách 2: Cookie (Default cho tất cả users)

Nếu muốn Vietnamese là mặc định cho mọi user, set cookie `lng=vi`:

```ts
// apps/backend/src/admin/plugins/i18n-plugin.ts
// (Đã có sẵn trong cấu trúc project)
```

## Thêm ngôn ngữ mới

### Backend Admin

1. Tạo file `apps/backend/src/admin/i18n/json/{code}.json`
2. Thêm vào `apps/backend/src/admin/i18n/index.ts`:

```ts
import en from "./json/en.json"
import vi from "./json/vi.json"
import fr from "./json/fr.json"

export default {
  en: { translation: en },
  vi: { translation: vi },
  fr: { translation: fr }, // ← Thêm ngôn ngữ mới
}
```

### Storefront

Thêm vào `translations` object trong `modules/chatbot/i18n/index.ts`:

```ts
const translations = {
  vi: { chat: { ... } },
  fr: { chat: { ... } }, // ← Thêm ngôn ngữ mới
}
```

## Danh sách Languages có sẵn

Medusa Dashboard hỗ trợ sẵn:

| Code | Ngôn ngữ |
|------|----------|
| `en` | English |
| `vi` | Tiếng Việt |
| `de` | Deutsch |
| `fr` | Français |
| `es` | Español |
| `it` | Italiano |
| `ptBR` | Português (Brasil) |
| `ptPT` | Português (Portugal) |
| `nl` | Nederlands |
| `pl` | Polski |
| `ru` | Русский |
| `uk` | Українська |
| `th` | ไทย |
| `tr` | Türkçe |
| `ar` | العربية |
| `zhCN` | 简体中文 |
| `zhTW` | 繁體中文 |
| `ja` | 日本語 |
| `ko` | 한국어 |
| `id` | Bahasa Indonesia |
| `ro` | Română |
| `hu` | Magyar |
| `cs` | Čeština |
| `hr` | Hrvatski |
| `bg` | Български |
| `mk` | Македонски |
| `mn` | Монгол |
| `lt` | Lietuviškai |
| `bs` | Bosanski |
| `he` | עברית |
| `fa` | فارسی |

## Migration Checklist

### Đối với component mới

- [ ] Import `useTranslation` từ `react-i18next`
- [ ] Gọi `const { t } = useTranslation()`
- [ ] Thay text hardcoded bằng `t("namespace.key")`
- [ ] Thêm translation key vào file `vi.json`

### Ví dụ

**Sai:**
```tsx
<Button>Save</Button>
<Heading level="h1">Live Chat</Heading>
```

**Đúng:**
```tsx
<Button>{t("common.save")}</Button>
<Heading level="h1">{t("chat.routeLabel")}</Heading>
```

## Tài liệu tham khảo

- [Medusa Admin Translations](https://docs.medusajs.com/learn/fundamentals/admin/translations)
- [React i18next](https://react.i18next.com/)
- [Medusa Languages PR](https://github.com/medusajs/medusa/pull/12042)
