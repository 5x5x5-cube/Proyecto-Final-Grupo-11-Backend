from .availability import Availability
from .hold import Hold
from .hotel import Hotel
from .room import Room

Base = Hotel.metadata

__all__ = ["Hotel", "Room", "Availability", "Hold", "Base"]
