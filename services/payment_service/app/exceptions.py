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


class PaymentNotRefundableError(Exception):
    """Raised when a payment cannot be refunded (wrong status or already refunded)."""

    def __init__(self, current_status: str):
        self.current_status = current_status
        super().__init__(f"Payment cannot be refunded — current status: {current_status}")


class RefundAmountInvalidError(Exception):
    """Raised when a requested refund amount is invalid (<= 0 or > original amount)."""

    def __init__(self, message: str):
        super().__init__(message)
