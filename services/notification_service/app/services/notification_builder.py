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
    check_out = booking_data.get("check_out", "")

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
