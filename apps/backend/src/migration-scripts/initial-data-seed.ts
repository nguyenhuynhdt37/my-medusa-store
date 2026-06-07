import { MedusaContainer } from "@medusajs/framework";
import {
  ContainerRegistrationKeys,
  ModuleRegistrationName,
  Modules,
  ProductStatus,
} from "@medusajs/framework/utils";
import {
  createApiKeysWorkflow,
  createCollectionsWorkflow,
  createInventoryLevelsWorkflow,
  createProductCategoriesWorkflow,
  createProductsWorkflow,
  createRegionsWorkflow,
  createSalesChannelsWorkflow,
  createShippingOptionsWorkflow,
  createStockLocationsWorkflow,
  createStoresWorkflow,
  createTaxRegionsWorkflow,
  linkSalesChannelsToApiKeyWorkflow,
  linkSalesChannelsToStockLocationWorkflow,
} from "@medusajs/medusa/core-flows";

type PhoneSeedProduct = {
  title: string;
  handle: string;
  brand: "Apple" | "Samsung" | "Google" | "Xiaomi" | "OPPO" | "vivo" | "Nothing" | "OnePlus";
  category: "iPhone" | "Android" | "Foldable" | "Accessories";
  basePrice: number;
  colors: string[];
  storage: string[];
  description: string;
  weight?: number;
  metadata?: Record<string, unknown>;
};

const productImageUrls: Record<string, string> = {
  "iphone-11": "https://fdn2.gsmarena.com/vv/pics/apple/apple-iphone-11-1.jpg",
  "iphone-12": "https://fdn2.gsmarena.com/vv/pics/apple/apple-iphone-12-r1.jpg",
  "iphone-13": "https://fdn2.gsmarena.com/vv/pics/apple/apple-iphone-13-01.jpg",
  "iphone-14": "https://fdn2.gsmarena.com/vv/pics/apple/apple-iphone-14-1.jpg",
  "iphone-15": "https://fdn2.gsmarena.com/vv/pics/apple/apple-iphone-15-1.jpg",
  "iphone-16": "https://fdn2.gsmarena.com/vv/pics/apple/apple-iphone-16-1.jpg",
  "iphone-17": "https://fdn2.gsmarena.com/vv/pics/apple/apple-iphone-17-1.jpg",
  "iphone-air": "https://fdn2.gsmarena.com/vv/pics/apple/apple-iphone-air-1.jpg",
  "iphone-17-pro": "https://fdn2.gsmarena.com/vv/pics/apple/apple-iphone-17-pro-1.jpg",
  "iphone-17-pro-max": "https://fdn2.gsmarena.com/vv/pics/apple/apple-iphone-17-pro-max-1.jpg",
  "samsung-galaxy-s26-ultra": "https://fdn2.gsmarena.com/vv/pics/samsung/samsung-galaxy-s26-ultra-1.jpg",
  "samsung-galaxy-s26-plus": "https://fdn2.gsmarena.com/vv/pics/samsung/samsung-galaxy-s26-plus-1.jpg",
  "samsung-galaxy-z-fold7": "https://fdn2.gsmarena.com/vv/pics/samsung/samsung-galaxy-z-fold7-1.jpg",
  "samsung-galaxy-z-flip7": "https://fdn2.gsmarena.com/vv/pics/samsung/samsung-galaxy-z-flip7-1.jpg",
  "google-pixel-10-pro-xl": "https://commons.wikimedia.org/wiki/Special:Redirect/file/Pixel%2010%20Pro%20XL%20back%20%28Obsidian%29.svg",
  "xiaomi-15-ultra": "https://commons.wikimedia.org/wiki/Special:Redirect/file/Xiaomi_15_Ultra.jpg",
  "oppo-find-x8-pro": "https://www.oppo.com/content/dam/oppo/common/mkt/v2-2/find-x8-series-en/find-x8-pro/products/932-720.png",
  "vivo-x200-pro": "https://fdn2.gsmarena.com/vv/pics/vivo/vivo-x200-pro-1.jpg",
  "nothing-phone-3": "https://cdn.shopify.com/s/files/1/0585/2479/5086/files/0000s_0011_Phone-3-white.png?v=1753757231",
  "oneplus-13": "https://fdn2.gsmarena.com/vv/pics/oneplus/oneplus-13-1.jpg",
};

const productImageUrl = (handle: string) => productImageUrls[handle];

const price = (amount: number) => [
  {
    amount,
    currency_code: "vnd",
  },
  {
    amount: Math.round(amount / 25000),
    currency_code: "usd",
  },
];

const phoneVariants = (product: PhoneSeedProduct) =>
  product.storage.flatMap((storage, storageIndex) =>
    product.colors.map((color, colorIndex) => {
      const extra = storageIndex * 2500000 + colorIndex * 100000;
      return {
        title: `${storage} / ${color}`,
        sku: `${product.handle}-${storage}-${color}`
          .toUpperCase()
          .replace(/[^A-Z0-9]+/g, "-")
          .replace(/-$/g, ""),
        options: {
          Storage: storage,
          Color: color,
        },
        prices: price(product.basePrice + extra),
      };
    })
  );

const phones: PhoneSeedProduct[] = [
  {
    title: "iPhone 11",
    handle: "iphone-11",
    brand: "Apple",
    category: "iPhone",
    basePrice: 6990000,
    colors: ["Black", "White", "Purple"],
    storage: ["64GB", "128GB"],
    description: "iPhone gia tot cho nguoi dung can iOS on dinh, camera kep va Face ID.",
    metadata: { best_seller: true, release_year: 2019 },
  },
  {
    title: "iPhone 12",
    handle: "iphone-12",
    brand: "Apple",
    category: "iPhone",
    basePrice: 8490000,
    colors: ["Black", "White", "Blue"],
    storage: ["64GB", "128GB"],
    description: "iPhone 5G dau tien voi man hinh OLED, MagSafe va thiet ke canh phang.",
    metadata: { release_year: 2020 },
  },
  {
    title: "iPhone 13",
    handle: "iphone-13",
    brand: "Apple",
    category: "iPhone",
    basePrice: 10490000,
    colors: ["Midnight", "Starlight", "Pink"],
    storage: ["128GB", "256GB"],
    description: "iPhone can bang giua hieu nang, pin va camera cho nhu cau pho thong.",
    metadata: { best_seller: true, release_year: 2021 },
  },
  {
    title: "iPhone 14",
    handle: "iphone-14",
    brand: "Apple",
    category: "iPhone",
    basePrice: 12990000,
    colors: ["Midnight", "Blue", "Purple"],
    storage: ["128GB", "256GB"],
    description: "iPhone co Crash Detection, camera low-light tot hon va pin ben.",
    metadata: { release_year: 2022 },
  },
  {
    title: "iPhone 15",
    handle: "iphone-15",
    brand: "Apple",
    category: "iPhone",
    basePrice: 15990000,
    colors: ["Black", "Blue", "Pink"],
    storage: ["128GB", "256GB"],
    description: "iPhone USB-C voi Dynamic Island, camera 48MP va thiet ke nhom kinh.",
    metadata: { best_seller: true, release_year: 2023 },
  },
  {
    title: "iPhone 16",
    handle: "iphone-16",
    brand: "Apple",
    category: "iPhone",
    basePrice: 19990000,
    colors: ["Black", "White", "Ultramarine"],
    storage: ["128GB", "256GB"],
    description: "iPhone the he moi voi chip A18, Camera Control va Apple Intelligence.",
    metadata: { release_year: 2024 },
  },
  {
    title: "iPhone 17",
    handle: "iphone-17",
    brand: "Apple",
    category: "iPhone",
    basePrice: 22990000,
    colors: ["Black", "Lavender", "Sage"],
    storage: ["256GB", "512GB"],
    description: "iPhone 17 voi chip A19, man hinh sang va camera Fusion 48MP.",
    metadata: { latest: true, release_year: 2025 },
  },
  {
    title: "iPhone Air",
    handle: "iphone-air",
    brand: "Apple",
    category: "iPhone",
    basePrice: 27990000,
    colors: ["Space Black", "Cloud White", "Light Gold"],
    storage: ["256GB", "512GB"],
    description: "iPhone sieu mong trong lineup 2025, hop voi nguoi thich may nhe va cao cap.",
    metadata: { latest: true, release_year: 2025 },
  },
  {
    title: "iPhone 17 Pro",
    handle: "iphone-17-pro",
    brand: "Apple",
    category: "iPhone",
    basePrice: 30990000,
    colors: ["Deep Blue", "Silver", "Cosmic Orange"],
    storage: ["256GB", "512GB", "1TB"],
    description: "iPhone Pro cho quay chup, gaming va tac vu nang voi chip A19 Pro.",
    metadata: { latest: true, release_year: 2025 },
  },
  {
    title: "iPhone 17 Pro Max",
    handle: "iphone-17-pro-max",
    brand: "Apple",
    category: "iPhone",
    basePrice: 34990000,
    colors: ["Deep Blue", "Silver", "Cosmic Orange"],
    storage: ["256GB", "512GB", "1TB"],
    description: "Mau iPhone cao cap nhat voi man hinh lon, pin lau va camera tot nhat cua Apple.",
    metadata: { latest: true, flagship: true, release_year: 2025 },
  },
  {
    title: "Samsung Galaxy S26 Ultra",
    handle: "samsung-galaxy-s26-ultra",
    brand: "Samsung",
    category: "Android",
    basePrice: 32990000,
    colors: ["Titanium Black", "Titanium Silver", "Titanium Blue"],
    storage: ["256GB", "512GB", "1TB"],
    description: "Flagship Android voi Galaxy AI, camera zoom manh va but S Pen.",
    metadata: { latest: true, flagship: true, release_year: 2026 },
  },
  {
    title: "Samsung Galaxy S26 Plus",
    handle: "samsung-galaxy-s26-plus",
    brand: "Samsung",
    category: "Android",
    basePrice: 25990000,
    colors: ["Black", "Silver", "Mint"],
    storage: ["256GB", "512GB"],
    description: "Galaxy man hinh lon, pin tot va hieu nang cao cho nguoi dung Android.",
    metadata: { latest: true, release_year: 2026 },
  },
  {
    title: "Samsung Galaxy Z Fold7",
    handle: "samsung-galaxy-z-fold7",
    brand: "Samsung",
    category: "Foldable",
    basePrice: 41990000,
    colors: ["Phantom Black", "Icy Blue"],
    storage: ["256GB", "512GB", "1TB"],
    description: "Dien thoai gap dang tablet cho lam viec, da nhiem va giai tri man hinh lon.",
    metadata: { latest: true, flagship: true, release_year: 2025 },
  },
  {
    title: "Samsung Galaxy Z Flip7",
    handle: "samsung-galaxy-z-flip7",
    brand: "Samsung",
    category: "Foldable",
    basePrice: 24990000,
    colors: ["Graphite", "Blue", "Coral Red"],
    storage: ["256GB", "512GB"],
    description: "Dien thoai gap gon, man hinh phu tien loi va phong cach tre trung.",
    metadata: { latest: true, release_year: 2025 },
  },
  {
    title: "Google Pixel 10 Pro XL",
    handle: "google-pixel-10-pro-xl",
    brand: "Google",
    category: "Android",
    basePrice: 28990000,
    colors: ["Obsidian", "Porcelain", "Bay"],
    storage: ["256GB", "512GB"],
    description: "Pixel cao cap voi Android thuan, AI cua Google va camera xu ly anh manh.",
    metadata: { latest: true, flagship: true, release_year: 2025 },
  },
  {
    title: "Xiaomi 15 Ultra",
    handle: "xiaomi-15-ultra",
    brand: "Xiaomi",
    category: "Android",
    basePrice: 26990000,
    colors: ["Black", "White", "Silver Chrome"],
    storage: ["256GB", "512GB"],
    description: "Flagship camera cua Xiaomi, man hinh dep va sac nhanh.",
    metadata: { flagship: true, release_year: 2025 },
  },
  {
    title: "OPPO Find X8 Pro",
    handle: "oppo-find-x8-pro",
    brand: "OPPO",
    category: "Android",
    basePrice: 22990000,
    colors: ["Space Black", "Pearl White"],
    storage: ["256GB", "512GB"],
    description: "Dien thoai OPPO cao cap voi camera Hasselblad, pin lon va sac nhanh.",
    metadata: { release_year: 2024 },
  },
  {
    title: "vivo X200 Pro",
    handle: "vivo-x200-pro",
    brand: "vivo",
    category: "Android",
    basePrice: 23990000,
    colors: ["Titanium Grey", "Carbon Black"],
    storage: ["256GB", "512GB"],
    description: "Flagship vivo tap trung chup chan dung, zoom va hieu nang cao.",
    metadata: { release_year: 2024 },
  },
  {
    title: "Nothing Phone 3",
    handle: "nothing-phone-3",
    brand: "Nothing",
    category: "Android",
    basePrice: 17990000,
    colors: ["Black", "White"],
    storage: ["256GB", "512GB"],
    description: "Android thiet ke trong suot, giao dien toi gian va den Glyph dac trung.",
    metadata: { latest: true, release_year: 2025 },
  },
  {
    title: "OnePlus 13",
    handle: "oneplus-13",
    brand: "OnePlus",
    category: "Android",
    basePrice: 19990000,
    colors: ["Black Eclipse", "Arctic Dawn", "Midnight Ocean"],
    storage: ["256GB", "512GB"],
    description: "May Android hieu nang cao, OxygenOS muot va sac nhanh.",
    metadata: { best_seller: true, release_year: 2025 },
  },
];

export default async function initial_data_seed({
  container,
}: {
  container: MedusaContainer;
}) {
  const logger = container.resolve(ContainerRegistrationKeys.LOGGER);
  const link = container.resolve(ContainerRegistrationKeys.LINK);
  const query = container.resolve(ContainerRegistrationKeys.QUERY);
  const fulfillmentModuleService = container.resolve(
    ModuleRegistrationName.FULFILLMENT
  );

  const countries = ["vn"];

  logger.info("Seeding store data...");
  const {
    result: [defaultSalesChannel],
  } = await createSalesChannelsWorkflow(container).run({
    input: {
      salesChannelsData: [
        {
          name: "Default Sales Channel",
          description: "Created by Medusa",
        },
      ],
    },
  });

  const {
    result: [publishableApiKey],
  } = await createApiKeysWorkflow(container).run({
    input: {
      api_keys: [
        {
          title: "Default Publishable API Key",
          type: "publishable",
          created_by: "",
        },
      ],
    },
  });

  if (process.env.NEXT_PUBLIC_MEDUSA_PUBLISHABLE_KEY) {
    const pgConnection = container.resolve(ContainerRegistrationKeys.PG_CONNECTION);
    const token = process.env.NEXT_PUBLIC_MEDUSA_PUBLISHABLE_KEY;

    await pgConnection.raw(
      "UPDATE api_key SET token = ?, redacted = ? WHERE id = ?",
      [token, `${token.slice(0, 6)}***${token.slice(-3)}`, publishableApiKey.id]
    );
  }

  await linkSalesChannelsToApiKeyWorkflow(container).run({
    input: {
      id: publishableApiKey.id,
      add: [defaultSalesChannel.id],
    },
  });

  await createStoresWorkflow(container).run({
    input: {
      stores: [
        {
          name: "Ecomoi Phone Store",
          supported_currencies: [
            {
              currency_code: "vnd",
              is_default: true,
            },
            {
              currency_code: "usd",
              is_default: false,
            },
          ],
          default_sales_channel_id: defaultSalesChannel.id,
        },
      ],
    },
  });

  logger.info("Seeding region data...");
  const { result: regionResult } = await createRegionsWorkflow(container).run({
    input: {
      regions: [
        {
          name: "Vietnam Phone Market",
          currency_code: "vnd",
          countries,
          payment_providers: ["pp_system_default"],
        },
      ],
    },
  });
  const region = regionResult[0];
  logger.info("Finished seeding regions.");

  logger.info("Seeding tax regions...");
  await createTaxRegionsWorkflow(container).run({
    input: countries.map((country_code) => ({
      country_code,
      provider_id: "tp_system",
    })),
  });
  logger.info("Finished seeding tax regions.");

  logger.info("Seeding stock location data...");
  const { result: stockLocationResult } = await createStockLocationsWorkflow(
    container
  ).run({
    input: {
      locations: [
        {
          name: "Ecomoi Phone Warehouse",
          address: {
            city: "Ho Chi Minh City",
            country_code: "VN",
            address_1: "District 1",
          },
        },
      ],
    },
  });
  const stockLocation = stockLocationResult[0];

  await link.create({
    [Modules.STOCK_LOCATION]: {
      stock_location_id: stockLocation.id,
    },
    [Modules.FULFILLMENT]: {
      fulfillment_provider_id: "manual_manual",
    },
  });

  logger.info("Seeding fulfillment data...");
  const { data: shippingProfileResult } = await query.graph({
    entity: "shipping_profile",
    fields: ["id"],
  });
  const shippingProfile = shippingProfileResult[0];

  const fulfillmentSet = await fulfillmentModuleService.createFulfillmentSets({
    name: "Ecomoi phone delivery",
    type: "shipping",
    service_zones: [
      {
        name: "Supported countries",
        geo_zones: countries.map((country_code) => ({
          country_code,
          type: "country" as const,
        })),
      },
    ],
  });

  await link.create({
    [Modules.STOCK_LOCATION]: {
      stock_location_id: stockLocation.id,
    },
    [Modules.FULFILLMENT]: {
      fulfillment_set_id: fulfillmentSet.id,
    },
  });

  await createShippingOptionsWorkflow(container).run({
    input: [
      {
        name: "Giao hang tieu chuan",
        price_type: "flat",
        provider_id: "manual_manual",
        service_zone_id: fulfillmentSet.service_zones[0].id,
        shipping_profile_id: shippingProfile.id,
        type: {
          label: "Standard",
          description: "Giao hang 2-3 ngay.",
          code: "standard",
        },
        prices: [
          {
            currency_code: "vnd",
            amount: 50000,
          },
          {
            currency_code: "usd",
            amount: 2,
          },
          {
            region_id: region.id,
            amount: 50000,
          },
        ],
        rules: [
          {
            attribute: "enabled_in_store",
            value: "true",
            operator: "eq",
          },
          {
            attribute: "is_return",
            value: "false",
            operator: "eq",
          },
        ],
      },
      {
        name: "Giao nhanh trong ngay",
        price_type: "flat",
        provider_id: "manual_manual",
        service_zone_id: fulfillmentSet.service_zones[0].id,
        shipping_profile_id: shippingProfile.id,
        type: {
          label: "Express",
          description: "Giao nhanh trong 24 gio.",
          code: "express",
        },
        prices: [
          {
            currency_code: "vnd",
            amount: 120000,
          },
          {
            currency_code: "usd",
            amount: 5,
          },
          {
            region_id: region.id,
            amount: 120000,
          },
        ],
        rules: [
          {
            attribute: "enabled_in_store",
            value: "true",
            operator: "eq",
          },
          {
            attribute: "is_return",
            value: "false",
            operator: "eq",
          },
        ],
      },
    ],
  });
  logger.info("Finished seeding fulfillment data.");

  await linkSalesChannelsToStockLocationWorkflow(container).run({
    input: {
      id: stockLocation.id,
      add: [defaultSalesChannel.id],
    },
  });
  logger.info("Finished seeding stock location data.");

  logger.info("Seeding product data...");

  const { result: categoryResult } = await createProductCategoriesWorkflow(
    container
  ).run({
    input: {
      product_categories: [
        {
          name: "iPhone",
          handle: "iphone",
          is_active: true,
        },
        {
          name: "Android",
          handle: "android",
          is_active: true,
        },
        {
          name: "Foldable",
          handle: "foldable",
          is_active: true,
        },
        {
          name: "Accessories",
          handle: "accessories",
          is_active: true,
        },
      ],
    },
  });

  const { result: collectionResult } = await createCollectionsWorkflow(container).run({
    input: {
      collections: [
        { title: "Apple", handle: "apple" },
        { title: "Samsung", handle: "samsung" },
        { title: "Google", handle: "google" },
        { title: "Xiaomi", handle: "xiaomi" },
        { title: "OPPO", handle: "oppo" },
        { title: "vivo", handle: "vivo" },
        { title: "Nothing", handle: "nothing" },
        { title: "OnePlus", handle: "oneplus" },
      ],
    },
  });

  await createProductsWorkflow(container).run({
    input: {
      products: phones.map((phone, index) => ({
        title: phone.title,
        subtitle: `${phone.brand} smartphone`,
        category_ids: [
          categoryResult.find((category) => category.name === phone.category)!.id,
        ],
        collection_id: collectionResult.find(
          (collection) => collection.title === phone.brand
        )!.id,
        description: phone.description,
        handle: phone.handle,
        weight: phone.weight ?? 220,
        status: ProductStatus.PUBLISHED,
        shipping_profile_id: shippingProfile.id,
        thumbnail: productImageUrl(phone.handle),
        images: [
          {
            url: productImageUrl(phone.handle),
          },
        ],
        options: [
          {
            title: "Storage",
            values: phone.storage,
          },
          {
            title: "Color",
            values: phone.colors,
          },
        ],
        variants: phoneVariants(phone),
        sales_channels: [
          {
            id: defaultSalesChannel.id,
          },
        ],
        metadata: {
          brand: phone.brand,
          category: phone.category,
          ...phone.metadata,
        },
      })),
    },
  });
  logger.info("Finished seeding product data.");

  logger.info("Seeding inventory levels.");

  const { data: inventoryItems } = await query.graph({
    entity: "inventory_item",
    fields: ["id"],
  });

  await createInventoryLevelsWorkflow(container).run({
    input: {
      inventory_levels: inventoryItems.map((item) => ({
        location_id: stockLocation.id,
        stocked_quantity: 100,
        inventory_item_id: item.id,
      })),
    },
  });

  logger.info("Finished seeding inventory levels data.");
}
