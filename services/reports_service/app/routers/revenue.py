from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..schemas import AvailablePeriodsResponse, MonthlyRevenueReport
from ..services.excel_generator import ExcelGenerator
from ..services.pdf_generator import PDFGenerator
from ..services.revenue_service import RevenueService

router = APIRouter(prefix="/api/v1/reports/revenue", tags=["revenue-reports"])


def get_hotel_id(request: Request) -> UUID:
    """Extract and validate the X-Hotel-Id header."""
    raw = request.headers.get("X-Hotel-Id")
    if not raw:
        raise HTTPException(status_code=401, detail="X-Hotel-Id header is required")
    try:
        return UUID(raw)
    except ValueError:
        raise HTTPException(status_code=401, detail="X-Hotel-Id header is not a valid UUID")


@router.get("/monthly", response_model=MonthlyRevenueReport)
async def get_monthly_revenue(
    month: int = Query(..., ge=1, le=12, description="Mes (1-12)"),
    year: int = Query(..., ge=2020, le=2100, description="Año"),
    hotel_id: UUID = Depends(get_hotel_id),
    db: AsyncSession = Depends(get_db),
):
    """
    Obtiene el reporte de ingresos mensuales para un hotel.

    **Requiere header X-Hotel-Id** con el UUID del hotel.

    Retorna:
    - Resumen financiero (ingresos brutos, cancelaciones, reembolsos, ingreso neto)
    - Detalle de todas las transacciones del mes
    - Estadísticas de reservas
    """
    service = RevenueService(db)

    try:
        report = await service.get_monthly_revenue_report(hotel_id, month, year)
        return report
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generating report: {str(e)}")


@router.get("/available-periods", response_model=AvailablePeriodsResponse)
async def get_available_periods(
    hotel_id: UUID = Depends(get_hotel_id),
    db: AsyncSession = Depends(get_db),
):
    """
    Retorna la lista de periodos (mes/año) que tienen datos disponibles.

    **Requiere header X-Hotel-Id** con el UUID del hotel.

    Útil para poblar el selector de periodo en el frontend.
    """
    service = RevenueService(db)

    try:
        periods = await service.get_available_periods(hotel_id)
        return AvailablePeriodsResponse(periods=periods)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching periods: {str(e)}")


@router.get("/download")
async def download_revenue_report(
    month: int = Query(..., ge=1, le=12, description="Mes (1-12)"),
    year: int = Query(..., ge=2020, le=2100, description="Año"),
    format: Literal["pdf", "excel"] = Query(..., description="Formato del archivo"),
    hotel_id: UUID = Depends(get_hotel_id),
    db: AsyncSession = Depends(get_db),
):
    """
    Descarga el reporte de ingresos en formato PDF o Excel.

    **Requiere header X-Hotel-Id** con el UUID del hotel.

    Formatos disponibles:
    - `pdf`: Documento PDF con resumen y tabla de transacciones
    - `excel`: Archivo Excel con dos hojas (Resumen y Transacciones)
    """
    service = RevenueService(db)

    try:
        # Obtener datos del reporte
        report = await service.get_monthly_revenue_report(hotel_id, month, year)

        # TODO: Obtener nombre del hotel desde inventory_service
        hotel_name = f"Hotel {hotel_id}"

        # Generar archivo según formato
        if format == "pdf":
            file_content = PDFGenerator.generate_revenue_report(report, hotel_name)
            media_type = "application/pdf"
            filename = f"reporte_ingresos_{month}_{year}.pdf"
        else:  # excel
            file_content = ExcelGenerator.generate_revenue_report(report, hotel_name)
            media_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            filename = f"reporte_ingresos_{month}_{year}.xlsx"

        # Retornar archivo
        return StreamingResponse(
            iter([file_content]),
            media_type=media_type,
            headers={"Content-Disposition": f"attachment; filename={filename}"},
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generating file: {str(e)}")
