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
