import uuid
from datetime import datetime
from typing import Annotated, Literal, TypedDict, Union

from pydantic import BaseModel, ConfigDict, Discriminator, Field, Tag
from pydantic.alias_generators import to_camel

# ── Typed dicts for method_data JSON column ──


class CardMethodData(TypedDict):
    last4: str
    brand: str
    holder: str
    numberHash: str
    expiryMonth: int
    expiryYear: int


class WalletMethodData(TypedDict):
    provider: str
    email: str


class TransferMethodData(TypedDict):
    bankCode: str
    accountLast4: str
    holder: str


MethodData = CardMethodData | WalletMethodData | TransferMethodData


# ── Tokenize: typed per payment method ──


class TokenizeCardRequest(BaseModel):
    method: Literal["credit_card", "debit_card"]
    card_number: str = Field(..., alias="cardNumber")
    card_holder: str = Field(..., alias="cardHolder")
    expiry: str = Field(..., alias="expiry", pattern=r"^\d{2}/\d{2}$")
    cvv: str = Field(..., alias="cvv")

    model_config = ConfigDict(populate_by_name=True, alias_generator=to_camel)


class TokenizeWalletRequest(BaseModel):
    method: Literal["digital_wallet"]
    wallet_provider: str = Field(..., alias="walletProvider")
    wallet_email: str = Field(..., alias="walletEmail")

    model_config = ConfigDict(populate_by_name=True, alias_generator=to_camel)


class TokenizeTransferRequest(BaseModel):
    method: Literal["transfer"]
    bank_code: str = Field(..., alias="bankCode")
    account_number: str = Field(..., alias="accountNumber")
    account_holder: str = Field(..., alias="accountHolder")

    model_config = ConfigDict(populate_by_name=True, alias_generator=to_camel)


def _get_tokenize_discriminator(v: dict) -> str:
    method = v.get("method", "credit_card")
    if method in ("credit_card", "debit_card"):
        return "card"
    return method


TokenizeRequest = Annotated[
    Union[
        Annotated[TokenizeCardRequest, Tag("card")],
        Annotated[TokenizeWalletRequest, Tag("digital_wallet")],
        Annotated[TokenizeTransferRequest, Tag("transfer")],
    ],
    Discriminator(_get_tokenize_discriminator),
]


class TokenizeResponse(BaseModel):
    token: str
    method: str
    display_label: str = Field(..., alias="displayLabel")
    expires_at: datetime = Field(..., alias="expiresAt")
    # Card-specific (optional)
    card_last4: str | None = Field(None, alias="cardLast4")
    card_brand: str | None = Field(None, alias="cardBrand")
    # Wallet-specific (optional)
    wallet_provider: str | None = Field(None, alias="walletProvider")
    # Transfer-specific (optional)
    bank_code: str | None = Field(None, alias="bankCode")

    model_config = ConfigDict(populate_by_name=True, alias_generator=to_camel)


# ── Initiate & Response ──


class InitiatePaymentRequest(BaseModel):
    token: str
    cart_id: uuid.UUID = Field(..., alias="cartId")
    method: str = "credit_card"

    model_config = ConfigDict(populate_by_name=True, alias_generator=to_camel)


# ── Cart data (mirrors cart_service response for inter-service communication) ──


class CartPriceBreakdown(BaseModel):
    price_per_night: str = Field(..., alias="pricePerNight")
    nights: int
    subtotal: str
    vat: str
    tourism_tax: str = Field("0", alias="tourismTax")
    service_fee: str = Field("0", alias="serviceFee")
    total: str
    currency: str = "COP"

    model_config = ConfigDict(populate_by_name=True, alias_generator=to_camel)


class CartData(BaseModel):
    id: str
    user_id: str = Field(..., alias="userId")
    room_id: str = Field(..., alias="roomId")
    hotel_id: str = Field(..., alias="hotelId")
    check_in: str = Field(..., alias="checkIn")
    check_out: str = Field(..., alias="checkOut")
    guests: int
    hold_id: str = Field(..., alias="holdId")
    hotel_name: str = Field("", alias="hotelName")
    room_name: str = Field("", alias="roomName")
    price_breakdown: CartPriceBreakdown = Field(..., alias="priceBreakdown")

    model_config = ConfigDict(populate_by_name=True, alias_generator=to_camel)


# ── SQS Event Payloads ──


class PaymentConfirmedEvent(BaseModel):
    payment_id: str = Field(..., alias="paymentId")
    user_id: str = Field(..., alias="userId")
    amount: float
    currency: str
    transaction_id: str = Field(..., alias="transactionId")
    cart: CartData

    model_config = ConfigDict(populate_by_name=True, alias_generator=to_camel)


class PaymentDeclinedEvent(BaseModel):
    payment_id: str = Field(..., alias="paymentId")
    user_id: str = Field(..., alias="userId")
    amount: float
    currency: str
    error_code: str | None = Field(None, alias="errorCode")

    model_config = ConfigDict(populate_by_name=True, alias_generator=to_camel)


# ── Response ──


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
