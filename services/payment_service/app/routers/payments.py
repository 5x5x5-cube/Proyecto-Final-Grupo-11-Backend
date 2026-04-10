from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import uuid
from datetime import datetime
from typing import Optional

router = APIRouter(prefix="/api/v1/payments", tags=["payments"])

# Base de datos en memoria para pagos
payments_db = {}


class PaymentInitiateRequest(BaseModel):
    booking_id: str
    amount: float
    currency: str = "USD"
    payment_method: str


class PaymentResponse(BaseModel):
    payment_id: str
    booking_id: str
    amount: float
    currency: str
    status: str
    payment_method: str
    created_at: str
    payment_url: Optional[str] = None


@router.post("/initiate", response_model=PaymentResponse)
async def initiate_payment(request: PaymentInitiateRequest):
    """Iniciar un pago"""
    payment_id = str(uuid.uuid4())
    
    payment = {
        "payment_id": payment_id,
        "booking_id": request.booking_id,
        "amount": request.amount,
        "currency": request.currency,
        "status": "pending",
        "payment_method": request.payment_method,
        "created_at": datetime.utcnow().isoformat(),
        "payment_url": f"https://payment-gateway.example.com/pay/{payment_id}"
    }
    
    payments_db[payment_id] = payment
    
    return PaymentResponse(**payment)


@router.get("/{payment_id}", response_model=PaymentResponse)
async def get_payment(payment_id: str):
    """Obtener estado de un pago"""
    payment = payments_db.get(payment_id)
    if not payment:
        raise HTTPException(status_code=404, detail="Payment not found")
    
    return PaymentResponse(**payment)


@router.post("/{payment_id}/confirm")
async def confirm_payment(payment_id: str):
    """Confirmar un pago"""
    payment = payments_db.get(payment_id)
    if not payment:
        raise HTTPException(status_code=404, detail="Payment not found")
    
    payment["status"] = "completed"
    payment["completed_at"] = datetime.utcnow().isoformat()
    
    return {"message": "Payment confirmed", "payment_id": payment_id, "status": "completed"}


@router.post("/{payment_id}/cancel")
async def cancel_payment(payment_id: str):
    """Cancelar un pago"""
    payment = payments_db.get(payment_id)
    if not payment:
        raise HTTPException(status_code=404, detail="Payment not found")
    
    payment["status"] = "cancelled"
    payment["cancelled_at"] = datetime.utcnow().isoformat()
    
    return {"message": "Payment cancelled", "payment_id": payment_id, "status": "cancelled"}
