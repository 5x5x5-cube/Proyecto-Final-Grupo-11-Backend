import io
from datetime import datetime
from decimal import Decimal

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from ..schemas import MonthlyRevenueReport


class PDFGenerator:
    @staticmethod
    def generate_revenue_report(report: MonthlyRevenueReport, hotel_name: str = "Hotel") -> bytes:
        """Genera un PDF del reporte de ingresos mensuales."""
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=letter)
        story = []
        styles = getSampleStyleSheet()

        # Título
        title = Paragraph(
            f"<b>Reporte de Ingresos Mensuales</b><br/>{hotel_name}",
            styles["Title"],
        )
        story.append(title)
        story.append(Spacer(1, 0.2 * inch))

        # Periodo
        period_text = f"Periodo: {report.summary.month}/{report.summary.year}"
        period = Paragraph(period_text, styles["Normal"])
        story.append(period)
        story.append(Spacer(1, 0.3 * inch))

        # Resumen financiero
        summary_data = [
            ["Concepto", "Monto"],
            ["Ingresos Brutos", f"${report.summary.gross_revenue:,.2f} {report.summary.currency}"],
            [
                "Cancelaciones",
                f"-${report.summary.cancellations_amount:,.2f} {report.summary.currency}",
            ],
            ["Reembolsos", f"-${report.summary.refunds_amount:,.2f} {report.summary.currency}"],
            ["Ingreso Neto", f"${report.summary.net_revenue:,.2f} {report.summary.currency}"],
        ]

        summary_table = Table(summary_data, colWidths=[3 * inch, 2 * inch])
        summary_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.grey),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                    ("ALIGN", (0, 0), (-1, -1), "LEFT"),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, 0), 12),
                    ("BOTTOMPADDING", (0, 0), (-1, 0), 12),
                    ("BACKGROUND", (0, 1), (-1, -2), colors.beige),
                    ("BACKGROUND", (0, -1), (-1, -1), colors.lightgreen),
                    ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
                    ("GRID", (0, 0), (-1, -1), 1, colors.black),
                ]
            )
        )
        story.append(summary_table)
        story.append(Spacer(1, 0.3 * inch))

        # Estadísticas
        stats_text = f"""
        Total de Reservas: {report.summary.total_bookings}<br/>
        Confirmadas: {report.summary.confirmed_bookings}<br/>
        Canceladas: {report.summary.cancelled_bookings}<br/>
        Pendientes: {report.summary.pending_bookings}
        """
        stats = Paragraph(stats_text, styles["Normal"])
        story.append(stats)
        story.append(Spacer(1, 0.3 * inch))

        # Tabla de transacciones
        if report.transactions:
            trans_title = Paragraph("<b>Detalle de Transacciones</b>", styles["Heading2"])
            story.append(trans_title)
            story.append(Spacer(1, 0.1 * inch))

            trans_data = [["Código", "Huésped", "Check-in", "Noches", "Monto", "Estado"]]

            for tx in report.transactions:
                trans_data.append(
                    [
                        tx.booking_code,
                        tx.guest_name[:20],
                        tx.check_in.strftime("%d/%m/%Y"),
                        str(tx.nights),
                        f"${tx.amount:,.0f}",
                        tx.status,
                    ]
                )

            trans_table = Table(
                trans_data,
                colWidths=[1 * inch, 1.5 * inch, 1 * inch, 0.7 * inch, 1 * inch, 1 * inch],
            )
            trans_table.setStyle(
                TableStyle(
                    [
                        ("BACKGROUND", (0, 0), (-1, 0), colors.grey),
                        ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                        ("FONTSIZE", (0, 0), (-1, 0), 10),
                        ("BOTTOMPADDING", (0, 0), (-1, 0), 12),
                        ("BACKGROUND", (0, 1), (-1, -1), colors.beige),
                        ("GRID", (0, 0), (-1, -1), 1, colors.black),
                    ]
                )
            )
            story.append(trans_table)

        # Footer
        story.append(Spacer(1, 0.5 * inch))
        footer_text = f"Generado el {datetime.now().strftime('%d/%m/%Y %H:%M')}"
        footer = Paragraph(footer_text, styles["Normal"])
        story.append(footer)

        doc.build(story)
        buffer.seek(0)
        return buffer.getvalue()
