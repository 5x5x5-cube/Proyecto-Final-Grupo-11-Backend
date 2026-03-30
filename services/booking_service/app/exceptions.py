class BookingNotFoundError(Exception):
    def __init__(self, booking_id: str):
        self.booking_id = booking_id
        super().__init__(f"Booking {booking_id} not found")


class BookingAlreadyProcessedError(Exception):
    def __init__(self, booking_id: str, current_status: str):
        self.booking_id = booking_id
        self.current_status = current_status
        super().__init__(
            f"Booking {booking_id} has already been processed (status={current_status})"
        )
