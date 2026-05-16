from typing import Any, Dict


def build_booking_notification(booking_data: Dict[str, Any], status: str) -> Dict[str, str]:
    """
    Build notification title and body based on booking status.

    Args:
        booking_data: Dictionary with booking information
        status: New booking status ('confirmed', 'rejected', 'cancelled')

    Returns:
        Dictionary with 'title', 'body', and 'type'
    """
    hotel_name = booking_data.get("hotel_name", "Hotel")
    check_in = booking_data.get("check_in", "")

    # Format dates if available
    check_in_formatted = check_in[:10] if check_in else ""  # YYYY-MM-DD

    if status == "confirmed":
        return {
            "title": "¡Reserva confirmada!",
            "body": f"Tu reserva en {hotel_name} ha sido confirmada. Check-in: {check_in_formatted}",
            "type": "booking_confirmed",
        }
    elif status == "rejected":
        return {
            "title": "Reserva no disponible",
            "body": f"Tu reserva en {hotel_name} no pudo ser confirmada. Revisa los detalles.",
            "type": "booking_rejected",
        }
    elif status == "cancelled":
        return {
            "title": "Reserva cancelada",
            "body": f"Tu reserva en {hotel_name} ha sido cancelada.",
            "type": "booking_cancelled",
        }
    else:
        return {
            "title": "Actualización de reserva",
            "body": f"Tu reserva en {hotel_name} ha sido actualizada.",
            "type": "booking_updated",
        }


def build_cancellation_refund_notification(booking_data: Dict[str, Any]) -> Dict[str, str]:
    """Build the push payload for a booking.cancelled event (HU4.3 CA5).

    The wording branches on ``refund_status`` so the user gets a clear signal:
    - processed: refund issued, includes amount and ETA
    - failed:    booking cancelled but refund needs ops attention
    - no_refund: cancellation outside the refund window (policy)
    """
    refund_status = booking_data.get("refund_status", "no_refund")
    refund_amount = booking_data.get("refund_amount", "0")
    currency = booking_data.get("currency", "COP")

    if refund_status == "processed":
        return {
            "title": "Reembolso en camino",
            "body": (
                f"Tu reserva fue cancelada. Reembolsamos {currency} {refund_amount}; "
                "veras el dinero en 5 a 10 dias habiles."
            ),
            "type": "booking_cancelled_refund_processed",
        }

    if refund_status == "failed":
        return {
            "title": "Reserva cancelada",
            "body": (
                "Tu reserva fue cancelada. Hay un inconveniente con el reembolso; "
                "te contactaremos en las proximas horas."
            ),
            "type": "booking_cancelled_refund_failed",
        }

    # no_refund (or unknown — defaults to the safest message)
    return {
        "title": "Reserva cancelada",
        "body": (
            "Tu reserva fue cancelada. La politica no aplica reembolso por la "
            "fecha de cancelacion."
        ),
        "type": "booking_cancelled_no_refund",
    }


# ── Fraud alerts (HU4.7) ──


_FRAUD_TYPE_LABELS: Dict[str, str] = {
    "duplicate": "Transaccion duplicada",
    "velocity": "Velocidad sospechosa",
    "threed_secure_failed": "Fallos consecutivos de 3D Secure",
}


def build_fraud_alert_email(alert_data: Dict[str, Any]) -> Dict[str, str]:
    """Build a minimal HTML email for a fraud_detected event (HU4.7 CA5).

    Targets the system admin (no per-user routing here): subject + HTML body
    summarising what the rules engine flagged so the admin can decide via
    the /fraud-alerts/{id}/review endpoint.
    """
    alert_type = alert_data.get("alert_type", "unknown")
    label = _FRAUD_TYPE_LABELS.get(alert_type, alert_type)
    amount = alert_data.get("amount", 0)
    currency = alert_data.get("currency", "COP")
    payment_id = alert_data.get("payment_id", "")
    user_id = alert_data.get("user_id", "")
    alert_id = alert_data.get("alert_id", "")
    triggered = alert_data.get("triggered_reason", "")
    severity = alert_data.get("severity", "high")

    subject = f"[TravelHub] Alerta de fraude: {label}"
    html = f"""<!doctype html>
<html><body style="font-family:Arial,sans-serif;color:#222;">
  <h2 style="color:#b00020;margin:0 0 8px 0;">Alerta de fraude detectada</h2>
  <p><strong>Tipo:</strong> {label} ({alert_type})</p>
  <p><strong>Severidad:</strong> {severity}</p>
  <p><strong>Motivo:</strong> {triggered}</p>
  <hr style="border:none;border-top:1px solid #ccc;margin:16px 0;">
  <p><strong>Pago bloqueado:</strong> {payment_id}</p>
  <p><strong>Viajero:</strong> {user_id}</p>
  <p><strong>Monto:</strong> {currency} {amount}</p>
  <p><strong>Alert ID:</strong> {alert_id}</p>
  <hr style="border:none;border-top:1px solid #ccc;margin:16px 0;">
  <p style="font-size:13px;color:#555;">
    Reviewa esta alerta con
    <code>POST /api/v1/payments/fraud-alerts/{alert_id}/review</code>.
  </p>
</body></html>
"""
    return {"subject": subject, "html": html, "type": "email_fraud_alert"}
