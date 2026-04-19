"""HTTP client to submit payments to the simulated gateway for processing."""

import uuid
from dataclasses import dataclass

import httpx

from ..config import settings
from ..schemas import GatewayProcessRequest, GatewayProcessResponse


async def submit_to_gateway(
    payment_id: uuid.UUID,
    token: str,
    amount: float,
    currency: str,
    webhook_url: str,
) -> GatewayProcessResponse:
    """Submit a payment to the gateway. Returns immediately with status=pending."""
    request = GatewayProcessRequest(
        payment_id=str(payment_id),
        token=token,
        amount=amount,
        currency=currency,
        webhook_url=webhook_url,
    )

    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.post(
            f"{settings.gateway_url}/api/v1/gateway/process",
            json=request.model_dump(by_alias=True),
        )
        response.raise_for_status()

    return GatewayProcessResponse.model_validate(response.json())
