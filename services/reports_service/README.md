# Reports Service

Servicio para generación de reportes financieros y analíticos para hoteles.

## Características

- **Reportes de Ingresos Mensuales**: Consulta ingresos brutos, cancelaciones, reembolsos e ingreso neto
- **Detalle de Transacciones**: Lista completa de reservas con su estado y monto
- **Exportación**: Descarga reportes en formato PDF o Excel
- **Periodos Disponibles**: Consulta qué meses tienen datos disponibles

## Endpoints Principales

### GET `/api/v1/reports/revenue/monthly`
Obtiene el reporte de ingresos mensuales.

**Headers:** `X-Hotel-Id` (UUID del hotel)  
**Params:** `month` (1-12), `year` (2020-2100)

### GET `/api/v1/reports/revenue/available-periods`
Lista los periodos con datos disponibles.

### GET `/api/v1/reports/revenue/download`
Descarga el reporte en PDF o Excel.

**Params:** `month`, `year`, `format` (pdf/excel)

## Configuración

```bash
DATABASE_URL=postgresql+asyncpg://user:pass@host:5432/bookings
```

## Development

```bash
poetry install
poetry run uvicorn app.main:app --reload --port 8005
poetry run pytest
```

## Base de Datos

Consulta directamente las tablas de `bookings` y `payments`. No crea tablas nuevas.
