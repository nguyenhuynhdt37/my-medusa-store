from app.services.messenger_service import generic_template_elements, messenger_plain_text


def test_generic_template_elements_from_products_payload():
    elements = generic_template_elements(
        {
            "products": [
                {
                    "title": "iPhone 17",
                    "url": "https://example.com/vn/products/iphone-17",
                    "image": "https://example.com/iphone-17.jpg",
                    "price_from": "22.990.000 VNĐ",
                    "discount": "Chưa có chương trình khuyến mãi",
                }
            ]
        }
    )

    assert elements == [
        {
            "title": "iPhone 17",
            "subtitle": "Giá từ 22.990.000 VNĐ\nƯu đãi: Chưa có chương trình khuyến mãi",
            "image_url": "https://example.com/iphone-17.jpg",
            "default_action": {
                "type": "web_url",
                "url": "https://example.com/vn/products/iphone-17",
                "webview_height_ratio": "tall",
            },
            "buttons": [
                {
                    "type": "web_url",
                    "url": "https://example.com/vn/products/iphone-17",
                    "title": "Xem chi tiết",
                    "webview_height_ratio": "tall",
                }
            ],
        }
    ]


def test_messenger_plain_text_strips_markdown_images_and_links():
    text = "### iPhone 17\n\n![iPhone 17](https://example.com/a.jpg)\n\n[Xem chi tiết](https://example.com/p)"

    assert messenger_plain_text(text) == "iPhone 17\nXem chi tiết"
