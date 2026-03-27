import uuid
from datetime import date

from app.schemas import (
    CreateHoldRequest,
    ErrorResponse,
    HoldCheckResponse,
)


def test_create_hold_request_from_camel_case():
    data = {
        "roomId": str(uuid.uuid4()),
        "userId": str(uuid.uuid4()),
        "checkIn": "2026-04-01",
        "checkOut": "2026-04-05",
    }
    req = CreateHoldRequest(**data)
    assert isinstance(req.room_id, uuid.UUID)
    assert isinstance(req.check_in, date)
    assert req.check_out == date(2026, 4, 5)


def test_create_hold_request_from_snake_case():
    req = CreateHoldRequest(
        room_id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        check_in=date(2026, 4, 1),
        check_out=date(2026, 4, 5),
    )
    assert isinstance(req.room_id, uuid.UUID)


def test_hold_check_response_not_held():
    resp = HoldCheckResponse(held=False, holder_id=None, hold_id=None)
    assert resp.held is False
    assert resp.holder_id is None


def test_hold_check_response_held():
    hid = uuid.uuid4()
    uid = uuid.uuid4()
    resp = HoldCheckResponse(held=True, holder_id=uid, hold_id=hid)
    assert resp.held is True
    assert resp.holder_id == uid


def test_error_response():
    err = ErrorResponse(code="ROOM_HELD", message="Room is being processed")
    assert err.code == "ROOM_HELD"
    assert err.details is None


def test_error_response_with_details():
    err = ErrorResponse(
        code="ROOM_UNAVAILABLE",
        message="No availability",
        details=[{"dates": ["2026-04-01"]}],
    )
    assert len(err.details) == 1
