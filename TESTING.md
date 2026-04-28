# Guía de Pruebas — TravelHub

## URLs del Entorno

| Recurso | URL |
|---------|-----|
| **Web (Frontend)** | https://dycn6bg2u03a2.cloudfront.net |
| **API (Backend)** | https://dycn6bg2u03a2.cloudfront.net/api/v1 |
| **Portal Hoteles** | https://dycn6bg2u03a2.cloudfront.net/hotel/login |

---

## Usuarios de Prueba

### Viajero (Traveler)

| Campo | Valor |
|-------|-------|
| Email | `traveler@test.com` |
| Contraseña | `Test1234` |
| Rol | `traveler` |
| Login en | `/login` |

### Administrador de Hotel

| Campo | Valor |
|-------|-------|
| Email | `admin@hotel.com` |
| Contraseña | `Admin123!` |
| Rol | `hotel_admin` |
| Hotel asignado | Hotel Caribe Plaza (Cartagena, Colombia) |
| Login en | `/hotel/login` |

> Cualquier usuario nuevo se puede registrar desde `/register`. Los usuarios de hotel se crean con `role: hotel_admin` via API.

---

## Tarjetas de Prueba (Pagos)

El sistema usa un gateway de pagos simulado. Las siguientes tarjetas tienen comportamientos especiales:

### Pago Exitoso

| Campo | Valor |
|-------|-------|
| Número | `4242 4242 4242 4242` |
| Titular | Cualquier nombre |
| Expiración | Cualquier fecha futura (ej. `12/28`) |
| CVV | Cualquier 3 dígitos (ej. `123`) |
| Resultado | **Aprobado** ✅ |
| Marca | Visa |

### Pago Rechazado (Fondos Insuficientes)

| Campo | Valor |
|-------|-------|
| Número | `4000 0000 0000 0002` |
| Titular | Cualquier nombre |
| Expiración | Cualquier fecha futura |
| CVV | Cualquier 3 dígitos |
| Resultado | **Rechazado** ❌ — `insufficient_funds` |

### Pago Rechazado (Tarjeta Expirada)

| Campo | Valor |
|-------|-------|
| Número | `4000 0000 0000 0069` |
| Titular | Cualquier nombre |
| Expiración | Cualquier fecha futura |
| CVV | Cualquier 3 dígitos |
| Resultado | **Rechazado** ❌ — `expired_card` |

> **Nota**: La expiración de la tarjeta se valida al tokenizar. Si se ingresa una fecha pasada (ej. `01/20`), el tokenizador rechaza la tarjeta con error "Card has expired", independientemente del número.

---

## Otros Métodos de Pago

### Billetera Digital (PayPal, Nequi, etc.)

| Campo | Valor |
|-------|-------|
| Método | `digital_wallet` |
| Proveedor | `paypal`, `nequi`, `daviplata` |
| Email | Cualquier email válido |
| Resultado | **Aprobado** ✅ |

### Transferencia Bancaria

| Campo | Valor |
|-------|-------|
| Método | `transfer` |
| Código de banco | `007` (Bancolombia), `001` (Bogotá), etc. |
| Número de cuenta | Cualquier número |
| Titular | Cualquier nombre |
| Resultado | **Aprobado** ✅ |

---

## Hoteles Disponibles

| Hotel | Ciudad | Habitaciones | Precio desde |
|-------|--------|-------------|-------------|
| Hotel Caribe Plaza | Cartagena | Standard (COP 250.000), Deluxe (COP 450.000), Suite (COP 850.000) |COP 250.000/noche |
| Bogota Grand Hotel | Bogotá | Standard, Deluxe | COP 180.000/noche |
| Medellin Eco Resort | Medellín | Cabin, Villa | COP 200.000/noche |

---

## Flujos de Prueba

### 1. Reserva completa (viajero)

1. Ir a https://dycn6bg2u03a2.cloudfront.net
2. Buscar destino (ej. "Cartagena") con fechas futuras
3. Seleccionar hotel → ver habitaciones
4. Click "Reservar ahora" → redirige a login si no está autenticado
5. Login con `traveler@test.com` / `Test1234`
6. Revisar carrito → continuar al pago
7. Ingresar tarjeta `4242 4242 4242 4242`, exp `12/28`, CVV `123`
8. Pagar → confirmación con código de reserva
9. Ver en "Mis reservas" → estado: Pendiente

### 2. Confirmación de reserva (admin hotel)

1. Ir a https://dycn6bg2u03a2.cloudfront.net/hotel/login
2. Login con `admin@hotel.com` / `Admin123!`
3. Ver listado de reservas del hotel
4. Seleccionar una reserva pendiente
5. Click "Confirmar" → estado cambia a Confirmado
6. El viajero ve el estado actualizado en su panel

### 3. Pago rechazado

1. Seguir el flujo de reserva hasta el paso de pago
2. Ingresar tarjeta `4000 0000 0000 0002`, exp `12/28`, CVV `123`
3. El pago es rechazado → se muestra error
4. El usuario puede reintentar con otra tarjeta

### 4. QR de Check-in (móvil)

1. Tener una reserva **confirmada** con check-in dentro de ±3 días
2. En la app móvil, ir al detalle de la reserva
3. Click "Mostrar QR" → se genera un código QR con JWT firmado
4. Si la reserva no está confirmada o el check-in está fuera del rango, se muestra un mensaje de error

---

## API — Endpoints Principales

### Públicos (sin autenticación)

```
GET  /api/v1/search/destinations
GET  /api/v1/search/hotels?city=Cartagena&check_in=2026-05-01&check_out=2026-05-03&guests=2
GET  /api/v1/search/hotels/{hotel_id}
GET  /api/v1/search/hotels/{hotel_id}/rooms?checkIn=2026-05-01
GET  /api/v1/inventory/hotels
GET  /api/v1/inventory/rooms?hotel_id={hotel_id}
POST /api/v1/auth/register
POST /api/v1/auth/login
GET  /api/v1/payments/exchange-rates
```

### Protegidos (requieren `Authorization: Bearer <token>`)

```
PUT    /api/v1/cart                          — Crear/actualizar carrito
GET    /api/v1/cart                          — Ver carrito actual
POST   /api/v1/gateway/tokenize             — Tokenizar método de pago
POST   /api/v1/payments/initiate            — Iniciar pago
GET    /api/v1/payments/{id}                — Consultar estado del pago
GET    /api/v1/bookings                     — Listar reservas del usuario
GET    /api/v1/bookings/{id}                — Detalle de reserva
GET    /api/v1/bookings/{id}/qr             — QR de check-in
POST   /api/v1/bookings/{id}/cancel         — Cancelar reserva
```

### Admin Hotel (requieren token de `hotel_admin`)

```
GET    /api/v1/bookings/hotel               — Listar reservas del hotel
GET    /api/v1/bookings/hotel/{id}          — Detalle de reserva
POST   /api/v1/bookings/hotel/{id}/status   — Confirmar/rechazar reserva
GET    /api/v1/inventory/tariffs            — Listar tarifas
POST   /api/v1/inventory/tariffs            — Crear tarifa
PUT    /api/v1/inventory/tariffs/{id}       — Editar tarifa
DELETE /api/v1/inventory/tariffs/{id}       — Eliminar tarifa
```
