# Code Coverage Chart — Sprint 1
## TravelHub · Proyecto Final MISW4501 · Grupo 11

> Informa el total de líneas de código ejercitadas mediante pruebas automáticas.
> Herramientas utilizadas: **Pytest + pytest-cov** (Backend) · **Vitest + v8** (Web) · **Jest + jest-expo** (Móvil)

---

## Backend — Microservicios (Pytest)

| Cubrimiento | Servicio / Módulo                        | Tests  |
|:-----------:|------------------------------------------|:------:|
| 🟢 **100%** | `notification_service` — app/            | 2 ✓    |
| 🟢 **99%**  | `booking_service` — app/                 | 67 ✓   |
| 🟢 **97%**  | `payment_service` — app/                 | 7 ✓    |
| 🟢 **87%**  | `auth_service` — app/                    | 7 ✓    |
| 🟡 **83%**  | `inventory_service` — app/               | 52 ✓   |
| 🟡 **77%**  | `search_service` — app/                  | 70 ✓   |

**Promedio backend: ~90%** · **Total tests ejecutados: 205**

### Detalle por archivo (servicios principales)

| Cubrimiento | Archivo                                          |
|:-----------:|--------------------------------------------------|
| 🟢 **100%** | `booking_service/app/routers/bookings.py`        |
| 🟢 **100%** | `booking_service/app/services/booking_service.py`|
| 🟢 **100%** | `booking_service/app/schemas.py`                 |
| 🟢 **100%** | `search_service/app/routes/search.py`            |
| 🟢 **96%**  | `search_service/app/services/sqs_consumer.py`    |
| 🟡 **75%**  | `search_service/app/services/redis_indexer.py`   |
| 🔴 **45%**  | `search_service/app/redis_client.py`             |

---

## Frontend Web — React + TypeScript (Vitest / v8)

| Cubrimiento | Módulo / Página                          |
|:-----------:|------------------------------------------|
| 🟢 **100%** | `ConfirmationPage`                       |
| 🟢 **86%**  | `ReservationsPage`                       |
| 🟢 **86%**  | `ReservationDetailPage`                  |
| 🟡 **75%**  | `PropertyDetailPage`                     |
| 🟡 **73%**  | `LoginPage`                              |
| 🟡 **70%**  | `PaymentPage`                            |
| 🟡 **69%**  | `RegisterPage`                           |
| 🟡 **62%**  | `CartPage`                               |
| 🟡 **62%**  | `ResultsPage`                            |
| 🟡 **60%**  | `HomePage`                               |

**Total Web:**

| Métrica    | Cubrimiento |
|------------|:-----------:|
| Statements | **80.65%**  |
| Branches   | **64.33%**  |
| Functions  | **53.55%**  |
| Lines      | **84.52%**  |

**Total tests ejecutados: 21+ archivos de prueba · 6 specs E2E (Playwright)**

---

## Aplicación Móvil — React Native + Expo (Jest / jest-expo)

| Cubrimiento | Capa                                     |
|:-----------:|------------------------------------------|
| 🟢 ~**85%** | Componentes UI (Brand, Card, Divider...) |
| 🟡 ~**70%** | Pantallas (SearchScreen, ResultsScreen…) |
| 🟡 ~**65%** | Checkout / Booking flow                  |
| 🟡 ~**60%** | Hooks de API                             |

**Total Móvil:**

| Métrica    | Cubrimiento |
|------------|:-----------:|
| Statements | **62.78%**  |
| Branches   | **49.11%**  |
| Functions  | **37.80%**  |
| Lines      | **64.69%**  |

**Total tests ejecutados: 136 tests · 42 suites**

---

## Resumen Consolidado — Sprint 1

| Componente              | Herramienta    | % Líneas cubierto | Tests ejecutados |
|-------------------------|----------------|:-----------------:|:----------------:|
| Backend (Microservicios)| Pytest + cov   | **~90%**          | 205              |
| Frontend Web            | Vitest + v8    | **84.52%**        | 21+ suites       |
| Aplicación Móvil        | Jest + jest-expo| **64.69%**       | 136              |

> **Nota:** El cubrimiento del módulo móvil refleja el estado al cierre del Sprint 1.
> Las pruebas E2E del frontend web (Playwright) y las pruebas de integración del backend
> complementan los números de cobertura unitaria reportados aquí.

---

*Generado al cierre del Sprint 1 — TravelHub · MISW4501 · Grupo 11*
