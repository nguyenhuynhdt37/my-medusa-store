# Lex V2 Intents for Ecomoi Phone Store

Bot locale: `English (United States) (en_US)` with Vietnamese utterances.

## Slot Types

### ProductName
Values:
- iPhone 11
- iPhone 12
- iPhone 13
- iPhone 14
- iPhone 15
- iPhone 16
- iPhone 17
- iPhone Air
- iPhone 17 Pro
- iPhone 17 Pro Max
- Samsung Galaxy S26 Ultra
- Samsung Galaxy S26 Plus
- Samsung Galaxy Z Fold7
- Samsung Galaxy Z Flip7
- Google Pixel 10 Pro XL
- Xiaomi 15 Ultra
- OPPO Find X8 Pro
- vivo X200 Pro
- Nothing Phone 3
- OnePlus 13

### BrandName
Values:
- Apple
- iPhone
- Samsung
- Google
- Xiaomi
- OPPO
- vivo
- Nothing
- OnePlus

### ProductNeed
Values:
- chụp ảnh
- quay video
- chơi game
- pin trâu
- giá rẻ
- cao cấp
- điện thoại gập
- AI
- màn hình lớn
- học sinh sinh viên

### BudgetRange
Values:
- dưới 10 triệu
- 10 đến 15 triệu
- 15 đến 20 triệu
- 20 đến 30 triệu
- trên 30 triệu

### PromoCode
Values:
- WELCOME10
- ANDROID15
- PHONE500K
- FREESHIP
- PREORDER17

## Intents

### GreetingIntent
Purpose: chào hỏi bot.

Slots:
- Không có slot

Sample utterances:
- xin chào
- hello
- hi
- chào shop
- bot ơi

Response:
Sẽ chọn ngẫu nhiên một trong các câu chào:
- `Xin chào! Mình là Medusan, trợ lý ảo của shop. Mình có thể giúp gì cho bạn hôm nay?`
- `Chào bạn, mình là Medusan. Bạn đang cần tìm điện thoại hay kiểm tra đơn hàng ạ?`
- `Medusan xin chào! Bạn cần hỗ trợ tư vấn sản phẩm hay hỏi về khuyến mãi không?`
- `Hi bạn, mình là trợ lý Medusan. Mình có thể hỗ trợ bạn tra giá, kiểm tra tồn kho hoặc trạng thái đơn hàng nhé!`

### ProductSearchIntent
Purpose: tìm sản phẩm theo tên, hãng, nhu cầu, hoặc ngân sách.

Slots:
- `product_name`: ProductName
  Required: No
  Prompt: để trống
- `brand`: BrandName
  Required: No
  Prompt: để trống
- `need`: ProductNeed
  Required: No
  Prompt: để trống
- `budget`: BudgetRange
  Required: No
  Prompt: để trống

Sample utterances:
- tìm {product_name}
- cửa hàng có {product_name} không
- cho tôi xem {product_name}
- có điện thoại {brand} không
- tôi muốn mua điện thoại {brand}
- gợi ý điện thoại để {need}
- có máy nào {need} không
- tìm điện thoại tầm {budget}
- điện thoại {brand} tầm {budget}
- cho xem các mẫu mới nhất
- có điện thoại gập nào không

Response:
`Mình sẽ tìm các sản phẩm phù hợp cho bạn.`

### ProductPriceIntent
Purpose: hỏi giá sản phẩm.

Slots:
- `product_name`: ProductName
  Required: Yes
  Prompt: Bạn muốn hỏi giá mẫu điện thoại nào? Ví dụ: iPhone 17 Pro Max.
- `brand`: BrandName
  Required: No
  Prompt: để trống

Sample utterances:
- {product_name} giá bao nhiêu
- giá {product_name}
- báo giá {product_name}
- {brand} có giá bao nhiêu
- điện thoại {brand} rẻ nhất bao nhiêu
- {product_name} bản 256GB giá nhiêu
- cho tôi biết giá của {product_name}

Response:
`Mình sẽ kiểm tra giá hiện tại của sản phẩm.`

### ProductRecommendationIntent
Purpose: tư vấn sản phẩm theo nhu cầu.

Slots:
- `need`: ProductNeed
  Required: No
  Prompt: để trống
- `budget`: BudgetRange
  Required: No
  Prompt: để trống
- `brand`: BrandName
  Required: No
  Prompt: để trống

Sample utterances:
- tư vấn cho tôi điện thoại {need}
- nên mua máy nào để {need}
- tôi cần điện thoại {need}
- tầm {budget} nên mua máy nào
- điện thoại nào đáng mua nhất
- máy nào bán chạy nhất
- gợi ý điện thoại {brand}
- tôi thích {brand} nên mua mẫu nào
- máy nào pin tốt
- máy nào chụp ảnh đẹp

Response:
`Mình sẽ gợi ý vài mẫu phù hợp với nhu cầu của bạn.`

### PromotionIntent
Purpose: hỏi mã giảm giá và khuyến mãi.

Slots:
- `promo_code`: PromoCode
  Required: No
  Prompt: để trống
- `product_name`: ProductName
  Required: No
  Prompt: để trống
- `brand`: BrandName
  Required: No
  Prompt: để trống

Sample utterances:
- có mã giảm giá không
- shop có khuyến mãi gì
- mã {promo_code} dùng được không
- {product_name} có giảm giá không
- mua {brand} có mã gì
- mã FREESHIP còn dùng được không
- mã nào giảm nhiều nhất
- cho tôi voucher hiện có
- PREORDER17 là mã gì
- ANDROID15 áp dụng cho máy nào

Response:
`Các mã hiện có gồm WELCOME10, ANDROID15, PHONE500K, FREESHIP và PREORDER17.`

### InventoryIntent
Purpose: hỏi tồn kho.

Slots:
- `product_name`: ProductName
  Required: Yes
  Prompt: Bạn muốn kiểm tra tồn kho mẫu điện thoại nào?

Sample utterances:
- {product_name} còn hàng không
- còn {product_name} không
- {product_name} có sẵn không
- bản 512GB của {product_name} còn không
- màu đen của {product_name} còn hàng không
- shop còn máy này không

Response:
`Mình sẽ kiểm tra tồn kho theo phiên bản và màu sắc.`

### ProductCompareIntent
Purpose: so sánh hai sản phẩm.

Slots:
- `product_a`: ProductName
  Required: Yes
  Prompt: Bạn muốn so sánh sản phẩm thứ nhất là gì?
- `product_b`: ProductName
  Required: Yes
  Prompt: Bạn muốn so sánh với sản phẩm nào?

Sample utterances:
- so sánh {product_a} và {product_b}
- {product_a} với {product_b} máy nào tốt hơn
- nên mua {product_a} hay {product_b}
- khác nhau giữa {product_a} và {product_b}
- {product_a} hơn {product_b} điểm nào

Response:
`Mình sẽ so sánh nhanh giá, hiệu năng, camera, pin và nhu cầu sử dụng.`

### OrderStatusIntent
Purpose: hỏi trạng thái đơn hàng.

Slots:
- `order_id`: AMAZON.AlphaNumeric
  Required: Yes
  Prompt: Bạn cho mình mã đơn hàng cần kiểm tra nhé.

Sample utterances:
- kiểm tra đơn hàng {order_id}
- đơn {order_id} tới đâu rồi
- trạng thái đơn hàng của tôi
- tôi muốn xem đơn hàng
- đơn hàng đã giao chưa
- tra cứu đơn hàng {order_id}

Response:
`Mình sẽ kiểm tra trạng thái đơn hàng cho bạn.`

### ShippingPolicyIntent
Purpose: hỏi giao hàng.

Slots:
- Không có slot

Sample utterances:
- shop giao hàng mất bao lâu
- phí ship bao nhiêu
- có giao nhanh không
- có miễn phí vận chuyển không
- giao trong ngày được không
- shop giao tới tỉnh không
- chính sách vận chuyển thế nào

Response:
`Chính sách giao hàng của shop:
- Giao hàng tiêu chuẩn: 2-3 ngày, phí 50.000 VNĐ.
- Giao nhanh: trong ngày hoặc trong 24 giờ, phí 120.000 VNĐ.
- Mã FREESHIP có thể miễn hoặc giảm phí vận chuyển nếu đơn đủ điều kiện.
- Shop hỗ trợ giao hàng toàn quốc cho các sản phẩm demo.`

### WarrantyPolicyIntent
Purpose: hỏi bảo hành, đổi trả.

Slots:
- `product_name`: ProductName
  Required: No
  Prompt: để trống

Sample utterances:
- {product_name} bảo hành bao lâu
- chính sách bảo hành thế nào
- có đổi trả không
- máy lỗi có được đổi không
- bảo hành chính hãng không
- mua điện thoại có bảo hành không

Response:
`Các điện thoại demo đang được bảo hành 12 tháng.
Chính sách đổi trả:
- Hỗ trợ đổi trả trong 7 ngày nếu máy lỗi, giao sai màu/phiên bản, hoặc hư hỏng khi vận chuyển.
- Máy còn nguyên seal có thể được xem xét đổi trả theo điều kiện của shop.
- Khi bảo hành hoặc đổi trả cần thông tin đơn hàng/hóa đơn.`

### HumanHandoffIntent
Purpose: chuyển tư vấn viên.

Slots:
- Không có slot

Sample utterances:
- gặp nhân viên
- cho tôi gặp tư vấn viên
- nói chuyện với người thật
- tôi cần hỗ trợ trực tiếp
- gọi nhân viên giúp tôi
- chuyển cho sale

Response:
`Mình sẽ chuyển yêu cầu của bạn cho tư vấn viên.`

### FallbackIntent
Purpose: fallback khi không hiểu.

Sample utterances:
- không có
- hỏi cái khác
- tôi không rõ

Response:
`Mình chưa hiểu rõ ý bạn. Bạn có thể hỏi giá sản phẩm, mã giảm giá, tồn kho hoặc nhờ mình tư vấn điện thoại.`

## Notes

- `ProductSearchIntent` là intent, không phải slot type.
- Trong sample utterance dùng slot name, ví dụ `{product_name}`, không dùng `{ProductName}`.
- Các intent search/recommendation/promotion nên để slot không required để bot linh hoạt.
- Chỉ bật Required khi bắt buộc cần dữ liệu cụ thể, ví dụ hỏi giá cần `product_name`, so sánh cần `product_a` và `product_b`.

## Fulfillment Mapping

- `GreetingIntent` -> call chatbot fulfillment and answer with default greeting.
- `ProductSearchIntent` -> call `/store/products` with query, brand, tags, or category.
- `ProductPriceIntent` -> call `/store/products`, read variants and calculated prices.
- `ProductRecommendationIntent` -> rank products by metadata `sold_count`, `rating`, `promo_hint`, and tags.
- `PromotionIntent` -> list active promotions or query by code.
- `InventoryIntent` -> read variant inventory.
- `ProductCompareIntent` -> fetch both products and compare metadata/specs.
- `OrderStatusIntent` -> query order by ID.
- `ShippingPolicyIntent` -> call chatbot fulfillment and answer from demo shipping policy.
- `WarrantyPolicyIntent` -> call chatbot fulfillment and answer from product metadata + demo return policy.

## Lex V2 Fulfillment Endpoint

Use this endpoint when connecting Lex V2 through an HTTP/API Gateway adapter:

`POST /lexv2/webhook`

Expected Lex V2 event fields:
- `sessionState.intent.name`: intent name, for example `ShippingPolicyIntent`
- `sessionState.intent.slots`: Lex slots, for example `product_name`
- `inputTranscript`: user text

The service returns a Lex V2 response with:
- `sessionState.dialogAction.type`: `Close`
- `sessionState.intent.state`: `Fulfilled`
- `messages[0].contentType`: `PlainText`
