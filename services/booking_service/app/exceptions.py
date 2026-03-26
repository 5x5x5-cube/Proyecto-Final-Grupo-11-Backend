class BookingNotFoundError(Exception):
    def __init__(self, booking_id: str):
        self.booking_id = booking_id
        super().__init__(f"Booking {booking_id} not found")


class InventoryServiceError(Exception):
    def __init__(self, message: str, status_code: int | None = None):
        self.status_code = status_code
        super().__init__(message)
