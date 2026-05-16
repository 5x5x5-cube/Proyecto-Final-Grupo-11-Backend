import calendar
from datetime import date, datetime
from decimal import Decimal
from typing import List
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from ..schemas import (
    AvailablePeriod,
    MonthlyRevenueReport,
    MonthlyRevenueSummary,
    TransactionDetail,
)


class RevenueService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_monthly_revenue_report(
        self, hotel_id: UUID, month: int, year: int
    ) -> MonthlyRevenueReport:
        """
        Genera el reporte de ingresos mensuales para un hotel.
        Consulta directamente las tablas de bookings y payments.
        """
        # Obtener resumen
        summary = await self._calculate_summary(hotel_id, month, year)

        # Obtener transacciones detalladas
        transactions = await self._get_transactions(hotel_id, month, year)

        return MonthlyRevenueReport(summary=summary, transactions=transactions)

    async def _calculate_summary(
        self, hotel_id: UUID, month: int, year: int
    ) -> MonthlyRevenueSummary:
        """Calcula el resumen de ingresos del mes."""

        # Query para obtener estadísticas de bookings
        query = text(
            """
            SELECT
                COUNT(*) as total_bookings,
                COUNT(*) FILTER (WHERE status = 'confirmed') as confirmed_bookings,
                COUNT(*) FILTER (WHERE status = 'cancelled') as cancelled_bookings,
                COUNT(*) FILTER (WHERE status = 'pending') as pending_bookings,
                COALESCE(SUM(total_price) FILTER (WHERE status = 'confirmed'), 0) as gross_revenue,
                COALESCE(SUM(total_price) FILTER (WHERE status = 'cancelled'), 0) as cancellations_amount,
                COALESCE(currency, 'COP') as currency
            FROM bookings
            WHERE hotel_id = :hotel_id
                AND EXTRACT(MONTH FROM created_at) = :month
                AND EXTRACT(YEAR FROM created_at) = :year
            GROUP BY currency
        """
        )

        result = await self.db.execute(
            query, {"hotel_id": str(hotel_id), "month": month, "year": year}
        )
        row = result.fetchone()

        if not row:
            # No hay datos para este periodo
            return MonthlyRevenueSummary(
                hotel_id=hotel_id,
                month=month,
                year=year,
                gross_revenue=Decimal("0"),
                cancellations_amount=Decimal("0"),
                refunds_amount=Decimal("0"),
                net_revenue=Decimal("0"),
                total_bookings=0,
                confirmed_bookings=0,
                cancelled_bookings=0,
                pending_bookings=0,
            )

        # Query para obtener reembolsos desde payment_service
        refunds_query = text(
            """
            SELECT COALESCE(SUM(p.amount), 0) as refunds_amount
            FROM payments p
            JOIN bookings b ON b.payment_id = p.id
            WHERE b.hotel_id = :hotel_id
                AND p.status = 'refunded'
                AND EXTRACT(MONTH FROM p.created_at) = :month
                AND EXTRACT(YEAR FROM p.created_at) = :year
        """
        )

        refunds_result = await self.db.execute(
            refunds_query, {"hotel_id": str(hotel_id), "month": month, "year": year}
        )
        refunds_row = refunds_result.fetchone()
        refunds_amount = Decimal(str(refunds_row[0])) if refunds_row else Decimal("0")

        gross_revenue = Decimal(str(row.gross_revenue))
        cancellations_amount = Decimal(str(row.cancellations_amount))
        net_revenue = gross_revenue - cancellations_amount - refunds_amount

        return MonthlyRevenueSummary(
            hotel_id=hotel_id,
            month=month,
            year=year,
            gross_revenue=gross_revenue,
            cancellations_amount=cancellations_amount,
            refunds_amount=refunds_amount,
            net_revenue=net_revenue,
            total_bookings=row.total_bookings,
            confirmed_bookings=row.confirmed_bookings,
            cancelled_bookings=row.cancelled_bookings,
            pending_bookings=row.pending_bookings,
            currency=row.currency or "COP",
        )

    async def _get_transactions(
        self, hotel_id: UUID, month: int, year: int
    ) -> List[TransactionDetail]:
        """Obtiene el detalle de transacciones del mes."""

        query = text(
            """
            SELECT
                b.code as booking_code,
                b.id as booking_id,
                b.guest_name,
                b.check_in,
                b.check_out,
                (b.check_out - b.check_in) as nights,
                b.total_price as amount,
                b.currency,
                b.status,
                p.status as payment_status,
                b.created_at
            FROM bookings b
            LEFT JOIN payments p ON b.payment_id = p.id
            WHERE b.hotel_id = :hotel_id
                AND EXTRACT(MONTH FROM b.created_at) = :month
                AND EXTRACT(YEAR FROM b.created_at) = :year
            ORDER BY b.created_at DESC
        """
        )

        result = await self.db.execute(
            query, {"hotel_id": str(hotel_id), "month": month, "year": year}
        )
        rows = result.fetchall()

        transactions = []
        for row in rows:
            transactions.append(
                TransactionDetail(
                    booking_code=row.booking_code,
                    booking_id=row.booking_id,
                    guest_name=row.guest_name or "N/A",
                    room_name=None,  # TODO: Obtener de inventory_service si es necesario
                    check_in=row.check_in,
                    check_out=row.check_out,
                    nights=int(row.nights) if row.nights else 0,
                    amount=Decimal(str(row.amount)),
                    currency=row.currency,
                    status=row.status,
                    payment_status=row.payment_status,
                    created_at=row.created_at,
                )
            )

        return transactions

    async def get_available_periods(self, hotel_id: UUID) -> List[AvailablePeriod]:
        """
        Retorna los periodos (mes/año) que tienen datos disponibles para el hotel.
        """
        query = text(
            """
            SELECT
                EXTRACT(MONTH FROM created_at)::int as month,
                EXTRACT(YEAR FROM created_at)::int as year,
                COUNT(*) as booking_count
            FROM bookings
            WHERE hotel_id = :hotel_id
            GROUP BY month, year
            ORDER BY year DESC, month DESC
            LIMIT 24
        """
        )

        result = await self.db.execute(query, {"hotel_id": str(hotel_id)})
        rows = result.fetchall()

        periods = []
        for row in rows:
            month_name = calendar.month_name[row.month]
            label = f"{month_name} {row.year}"
            periods.append(
                AvailablePeriod(
                    month=row.month,
                    year=row.year,
                    label=label,
                    booking_count=row.booking_count,
                )
            )

        return periods
