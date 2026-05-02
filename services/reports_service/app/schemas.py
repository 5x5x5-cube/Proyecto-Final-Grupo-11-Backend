from datetime import date, datetime
from decimal import Decimal
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class TransactionDetail(BaseModel):
    booking_code: str
    booking_id: UUID
    guest_name: str
    room_name: Optional[str] = None
    check_in: date
    check_out: date
    nights: int
    amount: Decimal
    currency: str
    status: str
    payment_status: Optional[str] = None
    created_at: datetime


class MonthlyRevenueSummary(BaseModel):
    hotel_id: UUID
    month: int = Field(ge=1, le=12)
    year: int
    gross_revenue: Decimal = Field(description="Total ingresos brutos")
    cancellations_amount: Decimal = Field(description="Monto de cancelaciones")
    refunds_amount: Decimal = Field(description="Monto de reembolsos")
    net_revenue: Decimal = Field(description="Ingreso neto (bruto - cancelaciones - reembolsos)")
    total_bookings: int
    confirmed_bookings: int
    cancelled_bookings: int
    pending_bookings: int
    currency: str = "COP"


class MonthlyRevenueReport(BaseModel):
    summary: MonthlyRevenueSummary
    transactions: List[TransactionDetail]


class AvailablePeriod(BaseModel):
    month: int
    year: int
    label: str
    booking_count: int


class AvailablePeriodsResponse(BaseModel):
    periods: List[AvailablePeriod]
