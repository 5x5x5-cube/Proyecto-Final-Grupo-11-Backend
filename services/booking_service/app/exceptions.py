class BookingNotFoundError(Exception):
    def __init__(self, booking_id: str):
        self.booking_id = booking_id
        super().__init__(f"Booking {booking_id} not found")
