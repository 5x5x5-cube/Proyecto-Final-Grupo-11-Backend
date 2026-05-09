"""Thin HTTP client for the payment_service refund endpoint (HU4.3)."""

from __future__ import annotations

import uuid

import httpx

from ..config import settings


class PaymentServiceError(Exception):
    """Raised when the payment_service returns a non-success status for a refund."""

    def __init__(self, message: str, status_code: int | None = None):
        self.status_code = status_code
        super().__init__(message)


async def request_refund(
    payment_id: uuid.UUID,
    amount: float,
    reason: str | None = None,
    timeout: float = 5.0,
) -> dict:
    """POST /api/v1/payments/{payment_id}/refund.

    Booking_service computes the refund amount based on the cancellation
    policy and calls this client. The endpoint itself is policy-agnostic.

    On success returns the JSON body of the response. On any non-200 raises
    `PaymentServiceError` so the caller can decide whether to mark the
    cancellation refund as failed (booking is still cancelled).
    """
    body: dict = {"amount": amount}
    if reason is not None:
        body["reason"] = reason

    async with httpx.AsyncClient(base_url=settings.payment_service_url, timeout=timeout) as client:
        response = await client.post(
            f"/api/v1/payments/{payment_id}/refund",
            json=body,
        )

    if response.status_code == 200:
        return response.json()

    raise PaymentServiceError(
        f"Refund failed (status={response.status_code})",
        status_code=response.status_code,
    )
