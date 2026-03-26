class CartNotFoundError(Exception):
    def __init__(self, user_id: str):
        self.user_id = user_id
        super().__init__(f"Cart not found for user {user_id}")


class CartExpiredError(Exception):
    def __init__(self, user_id: str):
        self.user_id = user_id
        super().__init__(f"Cart expired for user {user_id}")


class RoomUnavailableError(Exception):
    def __init__(self, message: str = "Room is unavailable"):
        super().__init__(message)


class InventoryServiceError(Exception):
    def __init__(self, message: str, status_code: int | None = None):
        self.status_code = status_code
        super().__init__(message)
