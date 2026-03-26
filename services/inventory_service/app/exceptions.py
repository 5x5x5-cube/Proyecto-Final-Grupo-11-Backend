class RoomNotFoundError(Exception):
    def __init__(self, room_id: str):
        self.room_id = room_id
        super().__init__(f"Room {room_id} not found")


class RoomUnavailableError(Exception):
    def __init__(self, room_id: str, dates: list[str] | None = None):
        self.room_id = room_id
        self.dates = dates or []
        super().__init__(f"Room {room_id} not available for requested dates")


class RoomHeldError(Exception):
    def __init__(self, room_id: str, holder_id: str | None = None):
        self.room_id = room_id
        self.holder_id = holder_id
        super().__init__(f"Room {room_id} is currently held by another user")


class HoldNotFoundError(Exception):
    def __init__(self, hold_id: str):
        self.hold_id = hold_id
        super().__init__(f"Hold {hold_id} not found")
