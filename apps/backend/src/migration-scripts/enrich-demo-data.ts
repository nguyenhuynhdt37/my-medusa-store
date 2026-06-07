import { MedusaContainer } from "@medusajs/framework";
import { ContainerRegistrationKeys } from "@medusajs/framework/utils";
import {
  createCustomerAddressesWorkflow,
  createCustomersWorkflow,
  createPromotionsWorkflow,
} from "@medusajs/medusa/core-flows";

const productTypes = [
  { id: "ptype_demo_budget_phone", value: "Budget phone" },
  { id: "ptype_demo_midrange_phone", value: "Midrange phone" },
  { id: "ptype_demo_flagship_phone", value: "Flagship phone" },
  { id: "ptype_demo_foldable_phone", value: "Foldable phone" },
];

const productTags = [
  { id: "ptag_demo_latest", value: "latest" },
  { id: "ptag_demo_best_seller", value: "best-seller" },
  { id: "ptag_demo_camera", value: "camera-phone" },
  { id: "ptag_demo_gaming", value: "gaming" },
  { id: "ptag_demo_ai", value: "ai-phone" },
  { id: "ptag_demo_discount", value: "discount" },
  { id: "ptag_demo_premium", value: "premium" },
];

const productContext: Record<
  string,
  {
    type_id: string;
    tags: string[];
    metadata: Record<string, unknown>;
  }
> = {
  "iphone-11": {
    type_id: "ptype_demo_budget_phone",
    tags: ["ptag_demo_discount", "ptag_demo_best_seller"],
    metadata: {
      warranty_months: 12,
      condition: "new-sealed",
      audience: "nguoi dung iOS gia tot",
      display: "6.1 inch Liquid Retina",
      camera: "dual 12MP",
      battery: "all-day battery",
      promo_hint: "WELCOME10",
      sold_count: 168,
      rating: 4.6,
    },
  },
  "iphone-12": {
    type_id: "ptype_demo_midrange_phone",
    tags: ["ptag_demo_discount"],
    metadata: {
      warranty_months: 12,
      display: "6.1 inch OLED",
      camera: "dual 12MP",
      network: "5G",
      promo_hint: "PHONE500K",
      sold_count: 121,
      rating: 4.6,
    },
  },
  "iphone-13": {
    type_id: "ptype_demo_midrange_phone",
    tags: ["ptag_demo_best_seller", "ptag_demo_discount"],
    metadata: {
      warranty_months: 12,
      display: "6.1 inch OLED",
      camera: "dual 12MP cinematic mode",
      battery: "pin tot trong tam gia",
      promo_hint: "WELCOME10",
      sold_count: 265,
      rating: 4.8,
    },
  },
  "iphone-14": {
    type_id: "ptype_demo_midrange_phone",
    tags: ["ptag_demo_discount"],
    metadata: {
      warranty_months: 12,
      display: "6.1 inch Super Retina XDR",
      camera: "dual 12MP low-light",
      safety: "Crash Detection",
      promo_hint: "PHONE500K",
      sold_count: 143,
      rating: 4.7,
    },
  },
  "iphone-15": {
    type_id: "ptype_demo_midrange_phone",
    tags: ["ptag_demo_best_seller", "ptag_demo_camera"],
    metadata: {
      warranty_months: 12,
      display: "6.1 inch Dynamic Island",
      camera: "48MP main camera",
      connector: "USB-C",
      promo_hint: "WELCOME10",
      sold_count: 388,
      rating: 4.9,
    },
  },
  "iphone-16": {
    type_id: "ptype_demo_flagship_phone",
    tags: ["ptag_demo_ai", "ptag_demo_camera"],
    metadata: {
      warranty_months: 12,
      chip: "A18",
      camera: "Camera Control",
      ai_features: "Apple Intelligence ready",
      promo_hint: "PHONE500K",
      sold_count: 214,
      rating: 4.8,
    },
  },
  "iphone-17": {
    type_id: "ptype_demo_flagship_phone",
    tags: ["ptag_demo_latest", "ptag_demo_ai", "ptag_demo_premium"],
    metadata: {
      warranty_months: 12,
      chip: "A19",
      camera: "48MP Fusion",
      campaign: "2026 Tet phone upgrade",
      promo_hint: "PREORDER17",
      sold_count: 92,
      rating: 4.9,
    },
  },
  "iphone-air": {
    type_id: "ptype_demo_flagship_phone",
    tags: ["ptag_demo_latest", "ptag_demo_premium"],
    metadata: {
      warranty_months: 12,
      design: "thin-light",
      audience: "nguoi thich may mong nhe",
      promo_hint: "PREORDER17",
      sold_count: 64,
      rating: 4.7,
    },
  },
  "iphone-17-pro": {
    type_id: "ptype_demo_flagship_phone",
    tags: ["ptag_demo_latest", "ptag_demo_camera", "ptag_demo_premium"],
    metadata: {
      warranty_months: 12,
      chip: "A19 Pro",
      camera: "pro camera system",
      use_case: "quay chup, gaming, creator",
      promo_hint: "PREORDER17",
      sold_count: 117,
      rating: 4.9,
    },
  },
  "iphone-17-pro-max": {
    type_id: "ptype_demo_flagship_phone",
    tags: ["ptag_demo_latest", "ptag_demo_camera", "ptag_demo_premium"],
    metadata: {
      warranty_months: 12,
      chip: "A19 Pro",
      camera: "best iPhone camera",
      battery: "pin lau nhat dong iPhone",
      promo_hint: "PREORDER17",
      sold_count: 156,
      rating: 5,
    },
  },
  "samsung-galaxy-s26-ultra": {
    type_id: "ptype_demo_flagship_phone",
    tags: ["ptag_demo_latest", "ptag_demo_camera", "ptag_demo_ai", "ptag_demo_premium"],
    metadata: {
      warranty_months: 12,
      ai_features: "Galaxy AI",
      camera: "Ultra zoom camera",
      stylus: "S Pen",
      promo_hint: "ANDROID15",
      sold_count: 203,
      rating: 4.9,
    },
  },
  "samsung-galaxy-s26-plus": {
    type_id: "ptype_demo_flagship_phone",
    tags: ["ptag_demo_latest", "ptag_demo_ai"],
    metadata: {
      warranty_months: 12,
      ai_features: "Galaxy AI",
      display: "large AMOLED",
      promo_hint: "ANDROID15",
      sold_count: 139,
      rating: 4.8,
    },
  },
  "samsung-galaxy-z-fold7": {
    type_id: "ptype_demo_foldable_phone",
    tags: ["ptag_demo_latest", "ptag_demo_premium", "ptag_demo_ai"],
    metadata: {
      warranty_months: 12,
      form_factor: "foldable tablet style",
      use_case: "multitasking, work, entertainment",
      promo_hint: "ANDROID15",
      sold_count: 58,
      rating: 4.7,
    },
  },
  "samsung-galaxy-z-flip7": {
    type_id: "ptype_demo_foldable_phone",
    tags: ["ptag_demo_latest", "ptag_demo_premium"],
    metadata: {
      warranty_months: 12,
      form_factor: "compact flip",
      audience: "nguoi thich may gap gon",
      promo_hint: "ANDROID15",
      sold_count: 86,
      rating: 4.7,
    },
  },
  "google-pixel-10-pro-xl": {
    type_id: "ptype_demo_flagship_phone",
    tags: ["ptag_demo_latest", "ptag_demo_camera", "ptag_demo_ai"],
    metadata: {
      warranty_months: 12,
      software: "Android thuan",
      ai_features: "Google AI camera tools",
      promo_hint: "ANDROID15",
      sold_count: 77,
      rating: 4.8,
    },
  },
  "xiaomi-15-ultra": {
    type_id: "ptype_demo_flagship_phone",
    tags: ["ptag_demo_camera", "ptag_demo_gaming", "ptag_demo_premium"],
    metadata: {
      warranty_months: 12,
      camera: "Ultra camera flagship",
      charging: "fast charging",
      promo_hint: "ANDROID15",
      sold_count: 132,
      rating: 4.8,
    },
  },
  "oppo-find-x8-pro": {
    type_id: "ptype_demo_flagship_phone",
    tags: ["ptag_demo_camera", "ptag_demo_discount"],
    metadata: {
      warranty_months: 12,
      camera: "Hasselblad tuned camera",
      battery: "large battery",
      promo_hint: "ANDROID15",
      sold_count: 94,
      rating: 4.7,
    },
  },
  "vivo-x200-pro": {
    type_id: "ptype_demo_flagship_phone",
    tags: ["ptag_demo_camera"],
    metadata: {
      warranty_months: 12,
      camera: "portrait and zoom focus",
      audience: "nguoi thich chup chan dung",
      promo_hint: "ANDROID15",
      sold_count: 83,
      rating: 4.7,
    },
  },
  "nothing-phone-3": {
    type_id: "ptype_demo_midrange_phone",
    tags: ["ptag_demo_latest", "ptag_demo_discount"],
    metadata: {
      warranty_months: 12,
      design: "transparent glyph design",
      software: "clean Android UI",
      promo_hint: "WELCOME10",
      sold_count: 69,
      rating: 4.6,
    },
  },
  "oneplus-13": {
    type_id: "ptype_demo_flagship_phone",
    tags: ["ptag_demo_best_seller", "ptag_demo_gaming"],
    metadata: {
      warranty_months: 12,
      performance: "flagship Android performance",
      charging: "fast charging",
      promo_hint: "ANDROID15",
      sold_count: 171,
      rating: 4.8,
    },
  },
};

const promotions = [
  {
    code: "WELCOME10",
    type: "standard",
    status: "active",
    application_method: {
      type: "percentage",
      target_type: "items",
      allocation: "across",
      value: 10,
      currency_code: "vnd",
    },
  },
  {
    code: "ANDROID15",
    type: "standard",
    status: "active",
    application_method: {
      type: "percentage",
      target_type: "items",
      allocation: "across",
      value: 15,
      currency_code: "vnd",
    },
  },
  {
    code: "PHONE500K",
    type: "standard",
    status: "active",
    application_method: {
      type: "fixed",
      target_type: "order",
      value: 500000,
      currency_code: "vnd",
    },
  },
  {
    code: "FREESHIP",
    type: "standard",
    status: "active",
    application_method: {
      type: "fixed",
      target_type: "shipping_methods",
      allocation: "each",
      value: 120000,
      max_quantity: 1,
      currency_code: "vnd",
    },
  },
  {
    code: "PREORDER17",
    type: "standard",
    status: "active",
    application_method: {
      type: "fixed",
      target_type: "items",
      allocation: "across",
      value: 1000000,
      currency_code: "vnd",
    },
  },
];

const customers = [
  {
    email: "minh.nguyen@example.com",
    first_name: "Minh",
    last_name: "Nguyen",
    phone: "+84901234567",
    metadata: { segment: "vip", preferred_brand: "Apple", total_orders: 3 },
  },
  {
    email: "lan.tran@example.com",
    first_name: "Lan",
    last_name: "Tran",
    phone: "+84909876543",
    metadata: { segment: "student", preferred_brand: "Samsung", total_orders: 1 },
  },
  {
    email: "huy.pham@example.com",
    first_name: "Huy",
    last_name: "Pham",
    phone: "+84911222333",
    metadata: { segment: "creator", preferred_brand: "Xiaomi", total_orders: 2 },
  },
];

const returnReasons = [
  {
    id: "rr_demo_defective_phone",
    value: "defective_phone",
    label: "May loi ky thuat",
    description: "San pham loi phan cung hoac phan mem trong thoi gian doi tra.",
  },
  {
    id: "rr_demo_wrong_variant",
    value: "wrong_variant",
    label: "Sai phien ban hoac mau sac",
    description: "San pham giao khac dung luong, mau sac, hoac model da dat.",
  },
  {
    id: "rr_demo_shipping_damage",
    value: "shipping_damage",
    label: "Hu hong khi van chuyen",
    description: "Hop hoac san pham bi hu hong trong qua trinh giao hang.",
  },
  {
    id: "rr_demo_unopened_change",
    value: "unopened_change",
    label: "Doi tra may chua kich hoat",
    description: "Ho tro doi tra may con nguyen seal theo dieu kien cua shop.",
  },
];

const storePolicyMetadata = {
  shipping_policy: {
    standard: "Giao hang tieu chuan 2-3 ngay, phi 50.000 VND.",
    express: "Giao nhanh trong ngay hoac trong 24 gio, phi 120.000 VND.",
    free_shipping_code: "FREESHIP",
    coverage: "Ho tro giao hang toan quoc cho cac san pham demo.",
  },
  warranty_policy: {
    default_months: 12,
    scope: "Bao hanh chinh hang 12 thang cho dien thoai demo.",
    requirement: "Can giu hoa don hoac thong tin don hang de bao hanh.",
  },
  return_policy: {
    window_days: 7,
    condition: "Ho tro doi tra trong 7 ngay neu may loi, giao sai mau/phien ban, hoac hu hong khi van chuyen.",
    unopened: "May con nguyen seal co the duoc xem xet doi tra theo dieu kien cua shop.",
  },
};

export default async function enrich_demo_data({
  container,
}: {
  container: MedusaContainer;
}) {
  const logger = container.resolve(ContainerRegistrationKeys.LOGGER);
  const pgConnection = container.resolve(ContainerRegistrationKeys.PG_CONNECTION);

  logger.info("Enriching demo product tags, types, and metadata...");

  for (const type of productTypes) {
    await pgConnection.raw(
      `
      INSERT INTO product_type (id, value, metadata)
      SELECT ?, ?, '{}'::json
      WHERE NOT EXISTS (
        SELECT 1 FROM product_type WHERE value = ? AND deleted_at IS NULL
      )
      `,
      [type.id, type.value, type.value]
    );
  }

  for (const tag of productTags) {
    await pgConnection.raw(
      `
      INSERT INTO product_tag (id, value, metadata)
      SELECT ?, ?, '{}'::jsonb
      WHERE NOT EXISTS (
        SELECT 1 FROM product_tag WHERE value = ? AND deleted_at IS NULL
      )
      `,
      [tag.id, tag.value, tag.value]
    );
  }

  for (const [handle, context] of Object.entries(productContext)) {
    await pgConnection.raw(
      `
      UPDATE product
      SET
        type_id = ?,
        metadata = COALESCE(metadata, '{}'::jsonb) || ?::jsonb,
        updated_at = now()
      WHERE handle = ?
        AND deleted_at IS NULL
      `,
      [context.type_id, JSON.stringify(context.metadata), handle]
    );

    for (const tagId of context.tags) {
      await pgConnection.raw(
        `
        INSERT INTO product_tags (product_id, product_tag_id)
        SELECT p.id, ?
        FROM product p
        WHERE p.handle = ?
          AND p.deleted_at IS NULL
        ON CONFLICT DO NOTHING
        `,
        [tagId, handle]
      );
    }
  }

  logger.info("Enriching demo promotions...");
  const existingPromotions = await pgConnection.raw(
    "SELECT code FROM promotion WHERE deleted_at IS NULL"
  );
  const existingPromotionCodes = new Set(
    existingPromotions.rows.map((promotion: { code: string }) => promotion.code)
  );
  const promotionsToCreate = promotions.filter(
    (promotion) => !existingPromotionCodes.has(promotion.code)
  );

  if (promotionsToCreate.length) {
    await createPromotionsWorkflow(container).run({
      input: {
        promotionsData: promotionsToCreate,
      },
    });
  }

  logger.info("Enriching demo customers...");
  const existingCustomers = await pgConnection.raw(
    "SELECT email FROM customer WHERE deleted_at IS NULL"
  );
  const existingCustomerEmails = new Set(
    existingCustomers.rows.map((customer: { email: string }) => customer.email)
  );
  const customersToCreate = customers.filter(
    (customer) => !existingCustomerEmails.has(customer.email)
  );

  if (customersToCreate.length) {
    const { result: createdCustomers } = await createCustomersWorkflow(container).run({
      input: {
        customersData: customersToCreate,
      },
    });

    await createCustomerAddressesWorkflow(container).run({
      input: {
        addresses: createdCustomers.map((customer, index) => ({
          customer_id: customer.id,
          first_name: customer.first_name,
          last_name: customer.last_name,
          phone: customer.phone,
          address_1:
            index === 0
              ? "72 Le Thanh Ton"
              : index === 1
              ? "12 Nguyen Hue"
              : "45 Vo Van Tan",
          city: "Ho Chi Minh City",
          province: "Ho Chi Minh",
          country_code: "vn",
          postal_code: "700000",
          is_default_shipping: true,
          is_default_billing: true,
          metadata: {
            address_label: "Demo shipping address",
          },
        })),
      },
    });
  }

  logger.info("Enriching demo shipping, warranty, and return policies...");
  await pgConnection.raw(
    `
    UPDATE store
    SET
      metadata = COALESCE(metadata, '{}'::jsonb) || ?::jsonb,
      updated_at = now()
    WHERE deleted_at IS NULL
    `,
    [JSON.stringify(storePolicyMetadata)]
  );

  for (const reason of returnReasons) {
    await pgConnection.raw(
      `
      INSERT INTO return_reason (id, value, label, description, metadata)
      SELECT ?, ?, ?, ?, '{}'::jsonb
      WHERE NOT EXISTS (
        SELECT 1 FROM return_reason WHERE value = ? AND deleted_at IS NULL
      )
      `,
      [reason.id, reason.value, reason.label, reason.description, reason.value]
    );
  }

  logger.info("Finished enriching demo data.");
}
