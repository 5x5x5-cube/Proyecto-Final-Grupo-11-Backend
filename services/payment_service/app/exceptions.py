class PaymentNotFoundError(Exception):
    def __init__(self, payment_id: str):
        self.payment_id = payment_id
        super().__init__(f"Payment {payment_id} not found")


class InvalidTokenError(Exception):
    def __init__(self, message: str = "Invalid payment token"):
        super().__init__(message)


class TokenExpiredError(Exception):
    def __init__(self, message: str = "Payment token has expired"):
        super().__init__(message)


class PaymentDeclinedError(Exception):
    def __init__(self, error_code: str, message: str = "Payment was declined"):
        self.error_code = error_code
        super().__init__(message)
