class ChatbotServiceError(Exception):
    pass


class ProductNotFoundError(ChatbotServiceError):
    pass


class OrderNotFoundError(ChatbotServiceError):
    pass


class MissingOrderCodeError(ChatbotServiceError):
    pass


class AuthenticationRequiredError(ChatbotServiceError):
    pass


class MedusaTimeoutError(ChatbotServiceError):
    pass


class GeminiAPIError(ChatbotServiceError):
    pass


class MedusaAPIError(ChatbotServiceError):
    def __init__(self, message: str, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code
