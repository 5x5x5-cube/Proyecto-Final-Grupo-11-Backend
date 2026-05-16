# Guía de Despliegue - Reports Service

## 📦 Archivos Creados (Nuevos)

### Backend:
- `app/config.py` - Configuración
- `app/schemas.py` - Modelos Pydantic
- `app/database.py` - Conexión DB
- `app/services/revenue_service.py` - Lógica de negocio
- `app/services/pdf_generator.py` - Generador PDF
- `app/services/excel_generator.py` - Generador Excel
- `app/routers/revenue.py` - Endpoints REST
- `tests/test_revenue.py` - Tests
- `.env.example` - Ejemplo configuración

### Frontend:
- `src/hotels/components/MonthYearPicker.tsx` - Selector de periodo

### Archivos Modificados:
- `app/main.py` - Agregado router
- `pyproject.toml` - Agregadas dependencias
- `src/api/hooks/useReports.ts` - Nuevos hooks con X-Hotel-Id

## 🚀 Pasos para Desplegar

### 1. Instalar Dependencias

```bash
cd services/reports_service
poetry install
```

### 2. Configurar Variables de Entorno

Crear archivo `.env`:

```bash
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/travelhub
```

### 3. Ejecutar Localmente (Desarrollo)

```bash
poetry run uvicorn app.main:app --reload --port 8005
```

Verificar: http://localhost:8005/health

### 4. Build Docker Image

```bash
cd services/reports_service
docker build -t reports-service:latest .
```

### 5. Deploy a Kubernetes

**Ya está configurado en:**
- `kubernetes/deployments/reports-service.yaml` ✅
- `kubernetes/deployments/gateway-service.yaml` (línea 35-36) ✅
- `kubernetes/dev/secrets.yaml` (línea 73-76) ✅
- `kubernetes/shared-config.yaml` (línea 26) ✅

**Aplicar cambios:**

```bash
# Si usas AWS ECR
aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin 735566955557.dkr.ecr.us-east-1.amazonaws.com

# Build y push
docker build -t 735566955557.dkr.ecr.us-east-1.amazonaws.com/proyecto-final-dev-reports-service:latest .
docker push 735566955557.dkr.ecr.us-east-1.amazonaws.com/proyecto-final-dev-reports-service:latest

# Deploy
kubectl apply -f kubernetes/dev/secrets.yaml
kubectl apply -f kubernetes/deployments/reports-service.yaml
kubectl apply -f kubernetes/deployments/gateway-service.yaml

# Verificar
kubectl get pods | grep reports-service
kubectl logs -f deployment/reports-service
```

## 🧪 Probar el Servicio

### 1. Health Check

```bash
curl http://localhost:8005/health
```

### 2. Obtener Periodos Disponibles

```bash
curl -H "X-Hotel-Id: <HOTEL_UUID>" \
  http://localhost:8005/api/v1/reports/revenue/available-periods
```

### 3. Obtener Reporte Mensual

```bash
curl -H "X-Hotel-Id: <HOTEL_UUID>" \
  "http://localhost:8005/api/v1/reports/revenue/monthly?month=1&year=2026"
```

### 4. Descargar PDF

```bash
curl -H "X-Hotel-Id: <HOTEL_UUID>" \
  "http://localhost:8005/api/v1/reports/revenue/download?month=1&year=2026&format=pdf" \
  --output reporte.pdf
```

### 5. Descargar Excel

```bash
curl -H "X-Hotel-Id: <HOTEL_UUID>" \
  "http://localhost:8005/api/v1/reports/revenue/download?month=1&year=2026&format=excel" \
  --output reporte.xlsx
```

## 🌐 Probar desde el Frontend

### 1. Asegúrate de tener datos de prueba

Necesitas tener reservas en la base de datos para el hotel que vas a consultar.

### 2. Login como Hotel Admin

```
URL: http://localhost:5173/hotels/login
```

### 3. Navegar a Reportes

```
URL: http://localhost:5173/hotels/reportes
```

### 4. Seleccionar Periodo

El dropdown mostrará solo los meses que tienen datos disponibles.

### 5. Ver Reporte

Debería mostrar:
- Ingresos brutos
- Cancelaciones
- Reembolsos
- Ingreso neto
- Tabla de transacciones

### 6. Descargar

Botones "Descargar PDF" y "Descargar Excel" deberían funcionar.

## 🔍 Troubleshooting

### Error: "X-Hotel-Id header is required"

**Causa:** No se está enviando el header  
**Solución:** Verificar que `hotelId` esté en localStorage

```javascript
localStorage.getItem('auth_hotel_id')
```

### Error: "Hotel ID not found in session"

**Causa:** La sesión del hotel no tiene hotelId  
**Solución:** Hacer login nuevamente como hotel admin

### Error: "Database connection failed"

**Causa:** DATABASE_URL incorrecta  
**Solución:** Verificar que apunte a la misma DB de booking_service

### No se muestran datos

**Causa:** No hay reservas para ese hotel/mes  
**Solución:** Crear reservas de prueba o seleccionar otro periodo

## 📊 Estructura de Datos

### Tablas Consultadas:

**bookings:**
- id, code, hotel_id, user_id
- guest_name, check_in, check_out
- total_price, currency, status
- created_at

**payments:**
- id, amount, status
- created_at

### Cálculos:

- **Ingresos Brutos** = SUM(total_price) WHERE status='confirmed'
- **Cancelaciones** = SUM(total_price) WHERE status='cancelled'
- **Reembolsos** = SUM(amount) FROM payments WHERE status='refunded'
- **Ingreso Neto** = Brutos - Cancelaciones - Reembolsos

## 🔒 Seguridad

- ✅ Requiere header `X-Hotel-Id`
- ✅ Solo retorna datos del hotel especificado
- ✅ Gateway valida que sea `hotel_admin`
- ✅ Validación de parámetros (mes 1-12, año 2020-2100)

## 📝 Próximos Pasos

1. ✅ Backend implementado
2. ✅ Gateway configurado
3. ✅ Kubernetes configurado
4. ⏳ Actualizar ReportsPage.tsx para usar datos reales
5. ⏳ Agregar selector de periodo
6. ⏳ Implementar descarga de archivos
7. ⏳ Tests E2E

## 🆘 Soporte

Si encuentras problemas:

1. Verificar logs del servicio: `kubectl logs -f deployment/reports-service`
2. Verificar logs del gateway: `kubectl logs -f deployment/gateway-service`
3. Verificar que la DB tenga datos
4. Verificar que el hotelId sea correcto
