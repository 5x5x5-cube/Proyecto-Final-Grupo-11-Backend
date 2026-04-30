# Notification Service — Arquitectura

## Descripcion General

El notification_service es responsable de enviar notificaciones a los viajeros de TravelHub. Soporta dos canales:

- **Push notifications** (Expo Push) — enviadas a dispositivos moviles registrados
- **Email** (SMTP) — enviado al correo electronico del viajero

El servicio consume eventos de una cola SQS (`notification-queue`) que recibe mensajes del topic SNS `command-update`. No expone logica de negocio propia — reacciona a eventos publicados por otros servicios.

## Flujo de Eventos

```
                         SNS topic: command-update
                                   |
                    +--------------+--------------+
                    |                             |
          entity_type=booking              entity_type=payment
          event_type=booking_created       (reservado para futuro uso)
          event_type=booking_status_updated
                    |
                    v
            SQS: notification-queue
                    |
                    v
            notification_service
            (SQS consumer thread)
                    |
        +-----------+-----------+
        |                       |
  booking_created         booking_status_updated
        |                       |
  Email SMTP              Push Notification
  (confirmacion           (Expo Push API)
   de pago)
```

## Eventos Procesados

### `booking_created`

**Origen**: booking_service (despues de crear una reserva a partir de un pago aprobado)

**Payload** (evento lean — solo IDs):
```json
{
  "event_type": "booking_created",
  "entity_type": "booking",
  "data": {
    "booking": {
      "id": "<booking_uuid>",
      "user_id": "<user_uuid>",
      "payment_id": "<payment_uuid>"
    }
  }
}
```

**Accion**: Envia un email de confirmacion de pago al viajero.

**Enriquecimiento de datos**: El evento solo contiene IDs. El servicio consulta los datos completos via HTTP:

| Servicio | Endpoint | Datos obtenidos |
|----------|----------|-----------------|
| auth_service | `GET /api/v1/auth/users/{user_id}` | Email, nombre del viajero |
| booking_service | `GET /api/v1/bookings/{booking_id}` | Codigo de reserva, hotel, habitacion, fechas, huespedes, precios |
| payment_service | `GET /api/v1/payments/{payment_id}` | Metodo de pago (ej. "Visa 4242"), ID de transaccion |

Este patron permite agregar nuevos tipos de notificacion sin modificar los eventos ni los servicios fuente.

### `booking_status_updated`

**Origen**: booking_service (cuando el hotel confirma o rechaza una reserva)

**Payload**:
```json
{
  "event_type": "booking_status_updated",
  "entity_type": "booking",
  "data": {
    "booking": {
      "id": "<booking_uuid>",
      "user_id": "<user_uuid>",
      "status": "confirmed|rejected|cancelled",
      "hotel_name": "Hotel Caribe Plaza",
      "check_in": "2026-06-01",
      "check_out": "2026-06-05"
    }
  }
}
```

**Accion**: Envia una push notification al dispositivo movil del viajero via Expo Push API.

## Estructura del Servicio

```
notification_service/
├── alembic/                          # Migraciones de base de datos
│   ├── env.py
│   └── versions/
│       └── 001_create_notification_tables.py
├── app/
│   ├── config.py                     # Configuracion (DB, SQS, SMTP, URLs de servicios)
│   ├── database.py                   # Engine y session factory de SQLAlchemy
│   ├── main.py                       # FastAPI app + hilo SQS consumer
│   ├── models.py                     # PushToken, NotificationHistory (ORM)
│   ├── routers/
│   │   └── notifications.py          # API REST (registro de tokens, historial)
│   ├── services/
│   │   ├── data_enrichment.py        # Cliente HTTP para consultar servicios hermanos
│   │   ├── email_builder.py          # Construccion de email HTML con Jinja2
│   │   ├── email_service.py          # Envio SMTP asincrono (aiosmtplib)
│   │   ├── expo_push.py              # Envio de push notifications via Expo
│   │   ├── notification_builder.py   # Templates de texto para push notifications
│   │   └── sqs_consumer.py           # Consumer SQS + dispatcher de eventos
│   └── templates/
│       └── payment_confirmation.html # Template HTML del email de confirmacion
├── tests/
│   ├── test_email_builder.py
│   ├── test_email_service.py
│   ├── test_main.py
│   └── test_sqs_consumer.py
├── alembic.ini
├── Dockerfile
├── entrypoint.sh                     # Ejecuta migraciones y luego uvicorn
└── pyproject.toml
```

## Idempotencia

Los mensajes SQS pueden entregarse mas de una vez (reintentos por visibilidad timeout, errores transitorios). Para evitar emails duplicados:

1. Antes de enviar un email, se consulta `notification_history` buscando un registro con `notification_type = 'email_payment_confirmation'` y `extra_data->>'payment_id' = <id>`
2. Si ya existe un registro, se omite el envio
3. Al enviar (o fallar), se guarda un registro en `notification_history` con el resultado

## Modelo de Datos

### `push_tokens`

Almacena tokens de dispositivos registrados para push notifications.

| Columna | Tipo | Descripcion |
|---------|------|-------------|
| id | UUID PK | |
| user_id | UUID | ID del viajero |
| expo_push_token | VARCHAR(255) | Token del dispositivo |
| device_id | VARCHAR(255) UNIQUE | ID unico del dispositivo |
| platform | VARCHAR(10) | `ios` o `android` |

### `notification_history`

Registro de todas las notificaciones enviadas (email y push).

| Columna | Tipo | Descripcion |
|---------|------|-------------|
| id | UUID PK | |
| user_id | UUID | ID del viajero |
| booking_id | UUID | ID de la reserva |
| notification_type | VARCHAR(50) | `email_payment_confirmation`, `booking_confirmed`, etc. |
| title | VARCHAR(255) | Asunto del email o titulo del push |
| body | TEXT | Contenido resumido |
| delivered | BOOLEAN | Si se entrego exitosamente |
| error_message | TEXT | Mensaje de error si fallo |
| extra_data | JSONB | Datos adicionales (`payment_id`, `booking_code`, `email`) |

## Variables de Entorno

| Variable | Descripcion | Valor por defecto |
|----------|-------------|-------------------|
| `DATABASE_URL` | Conexion PostgreSQL | `postgresql+asyncpg://...localhost.../travelhub` |
| `SQS_QUEUE_URL` | URL de la cola SQS | `http://localhost:4566/.../notification-queue` |
| `SMTP_HOST` | Host del servidor SMTP | `localhost` |
| `SMTP_PORT` | Puerto SMTP | `1025` |
| `SMTP_USERNAME` | Usuario SMTP (vacio para Mailpit) | `""` |
| `SMTP_PASSWORD` | Password SMTP | `""` |
| `SMTP_USE_TLS` | Usar TLS | `false` |
| `SMTP_FROM_EMAIL` | Remitente del email | `noreply@travelhub.com` |
| `AUTH_SERVICE_URL` | URL del auth service | `http://localhost:8011` |
| `BOOKING_SERVICE_URL` | URL del booking service | `http://localhost:8002` |
| `PAYMENT_SERVICE_URL` | URL del payment service | `http://localhost:8009` |
| `INVENTORY_SERVICE_URL` | URL del inventory service | `http://localhost:8006` |
| `EXPO_ACCESS_TOKEN` | Token de acceso para Expo Push (opcional) | — |

## Email en Desarrollo vs Produccion

| Entorno | SMTP Host | Comportamiento |
|---------|-----------|----------------|
| Local (docker-compose) | `mailpit:1025` | Emails capturados en Mailpit UI (http://localhost:8025) |
| K8s staging | `mailpit:1025` | Emails capturados en Mailpit (`kubectl port-forward svc/mailpit 8025:8025`) |
| Produccion | AWS SES SMTP | Emails entregados a buzones reales |

Para pasar a produccion, solo se cambian las variables de entorno SMTP — no se requieren cambios en codigo.
