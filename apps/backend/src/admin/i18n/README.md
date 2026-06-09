# Admin Customizations Translations

Hệ thống i18n của project. Xem [I18N_README.md](./I18N_README.md) để biết chi tiết.

## Tóm tắt nhanh

### Custom translations cho Live Chat

Thêm key vào `src/admin/i18n/json/vi.json`, export trong `src/admin/i18n/index.ts`.

### Sử dụng trong component

```tsx
import { useTranslation } from "react-i18next"

const MyPage = () => {
  const { t } = useTranslation()
  return <Button>{t("common.save")}</Button>
}
```

### Bật tiếng Việt cho toàn bộ Dashboard

1. Settings → Store → Language → Tiếng Việt
2. Hoặc thêm file `src/admin/plugins/i18n-plugin.ts`

Xem [I18N_README.md](./I18N_README.md) để biết thêm chi tiết.
