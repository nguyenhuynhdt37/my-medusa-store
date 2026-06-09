class ChatbotServiceError(Exception):
    status_code = 500

    def __init__(self, message: str, *, status_code: int | None = None) -> None:
        super().__init__(message)
        if status_code is not None:
            self.status_code = status_code


class MedusaAPIError(ChatbotServiceError):
    pass


class MedusaTimeoutError(MedusaAPIError):
    status_code = 504


class GeminiAPIError(ChatbotServiceError):
    pass


class AuthenticationRequiredError(ChatbotServiceError):
    status_code = 401

    def __init__(self, message: str = "Customer authentication is required.") -> None:
        super().__init__(message, status_code=self.status_code)


class ProductNotFoundError(ChatbotServiceError):
    status_code = 404

    def __init__(self, message: str = "Product was not found.") -> None:
        super().__init__(message, status_code=self.status_code)


class MissingOrderCodeError(ChatbotServiceError):
    status_code = 400

    def __init__(self, message: str = "Order code is required.") -> None:
        super().__init__(message, status_code=self.status_code)


class OrderNotFoundError(ChatbotServiceError):
    status_code = 404

    def __init__(self, message: str = "Order was not found.") -> None:
        super().__init__(message, status_code=self.status_code)
