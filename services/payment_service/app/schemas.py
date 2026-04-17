import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel


class TokenizeRequest(BaseModel):
    card_number: str = Field(..., alias="cardNumber")
    card_holder: str = Field(..., alias="cardHolder")
    expiry: str = Field(..., alias="expiry", pattern=r"^\d{2}/\d{2}$")
    cvv: str = Field(..., alias="cvv")

    model_config = ConfigDict(populate_by_name=True, alias_generator=to_camel)


class TokenizeResponse(BaseModel):
    token: str
    card_last4: str = Field(..., alias="cardLast4")
    card_brand: str = Field(..., alias="cardBrand")
    expires_at: datetime = Field(..., alias="expiresAt")

    model_config = ConfigDict(populate_by_name=True, alias_generator=to_camel)


class InitiatePaymentRequest(BaseModel):
    token: str
    booking_id: uuid.UUID = Field(..., alias="bookingId")
    amount: float
    currency: str = "COP"
    method: str = "credit_card"

    model_config = ConfigDict(populate_by_name=True, alias_generator=to_camel)


class PaymentResponse(BaseModel):
    payment_id: uuid.UUID = Field(..., alias="paymentId")
    status: str
    booking_id: uuid.UUID | None = Field(None, alias="bookingId")
    booking_code: str | None = Field(None, alias="bookingCode")
    amount: float
    currency: str
    method: str
    card_last4: str | None = Field(None, alias="cardLast4")
    card_brand: str | None = Field(None, alias="cardBrand")
    transaction_id: str | None = Field(None, alias="transactionId")
    message: str | None = None
    created_at: datetime = Field(..., alias="createdAt")
    processed_at: datetime | None = Field(None, alias="processedAt")

    model_config = ConfigDict(populate_by_name=True, alias_generator=to_camel)
