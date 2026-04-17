"""Simulated gateway operations. In production, these would be SDK calls to the real gateway."""

from sqlalchemy.ext.asyncio import AsyncSession

from ..exceptions import InvalidTokenError
from ..models import PaymentMethodType, PaymentToken
from ..schemas import (
    TokenizeCardRequest,
    TokenizeRequest,
    TokenizeResponse,
    TokenizeTransferRequest,
    TokenizeWalletRequest,
)
from . import token_service


def _parse_tokenize_request(body: dict) -> TokenizeRequest:
    from pydantic import TypeAdapter

    adapter = TypeAdapter(TokenizeRequest)
    return adapter.validate_python(body)


async def tokenize(db: AsyncSession, body: dict) -> TokenizeResponse:
    """Tokenize any payment method. Simulates a gateway's tokenization API."""
    method = body.get("method", "credit_card")
    if method not in PaymentMethodType._value2member_map_:
        raise InvalidTokenError(f"Unsupported payment method: {method}")

    request = _parse_tokenize_request(body)

    if isinstance(request, TokenizeCardRequest):
        token = await token_service.create_card_token(
            db=db,
            method=request.method,
            card_number=request.card_number,
            card_holder=request.card_holder,
            expiry=request.expiry,
            cvv=request.cvv,
        )
    elif isinstance(request, TokenizeWalletRequest):
        token = await token_service.create_wallet_token(
            db=db,
            wallet_provider=request.wallet_provider,
            wallet_email=request.wallet_email,
        )
    elif isinstance(request, TokenizeTransferRequest):
        token = await token_service.create_transfer_token(
            db=db,
            bank_code=request.bank_code,
            account_number=request.account_number,
            account_holder=request.account_holder,
        )
    else:
        raise InvalidTokenError("Unsupported payment method")

    return TokenizeResponse(
        token=token.token,
        method=token.method,
        display_label=token.display_label,
        expires_at=token.expires_at,
        card_last4=token.method_data.get("last4"),
        card_brand=token.method_data.get("brand"),
        wallet_provider=token.method_data.get("provider"),
        bank_code=token.method_data.get("bankCode"),
    )
