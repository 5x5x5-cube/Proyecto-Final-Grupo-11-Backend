# 🏨 Sistema de Búsqueda de Hoteles

Sistema completo de búsqueda de hoteles con sincronización en tiempo real vía SQS y Redis.

## 📋 Historia de Usuario Implementada

**Como viajero**  
Quiero buscar hospedajes por ciudad, fechas de entrada y salida y número de personas  
Para encontrar opciones que se ajusten a mi viaje.

## ✅ Criterios de Aceptación Cumplidos

### Búsqueda
- ✅ Permite ingresar ciudad de destino
- ✅ Permite seleccionar fecha de entrada y salida
- ✅ Permite indicar número de huéspedes

### Validaciones
- ✅ Fecha de salida posterior a fecha de entrada
- ✅ Fecha de entrada no anterior a fecha actual
- ✅ Número de huéspedes mayor que cero

### Resultados
- ✅ Muestra lista de hospedajes disponibles
- ✅ Solo muestra hoteles con habitaciones disponibles
- ✅ Cada resultado muestra:
  - Nombre del hotel
  - Ubicación (ciudad, país, dirección)
  - Calificación
  - Precio por noche (mínimo de habitaciones disponibles)
  - Servicios principales
  - Botón "Ver habitaciones"
- ✅ Mensaje cuando no hay resultados

## 🏗️ Arquitectura

```
Terceros/Admin → POST /hotels/webhook
    ↓
Inventory Service (PostgreSQL)
    ↓ Publica evento
AWS SQS (hotel-sync-queue)
    ↓ Consume
Search Worker
    ↓ Indexa
Redis (RediSearch)
    ↓ Consulta
Search Service API → Usuario
```

## 🚀 Endpoints

### Inventory Service (Puerto 8006)

#### Registrar Hotel (Webhook)
```http
POST /hotels/webhook
Content-Type: application/json

{
  "name": "Hotel Plaza",
  "description": "Hotel en el centro de la ciudad",
  "city": "Bogotá",
  "country": "Colombia",
  "address": "Calle 100 #15-20",
  "rating": 4.5
}
```

**Respuesta:**
```json
{
  "id": "uuid-del-hotel",
  "name": "Hotel Plaza",
  "description": "Hotel en el centro de la ciudad",
  "city": "Bogotá",
  "country": "Colombia",
  "address": "Calle 100 #15-20",
  "rating": 4.5
}
```

#### Listar Hoteles
```http
GET /hotels?skip=0&limit=100
```

#### Obtener Hotel
```http
GET /hotels/{hotel_id}
```

### Search Service (Puerto 8003)

#### Buscar Hoteles
```http
GET /search/hotels?city=Bogotá&check_in=2024-04-01&check_out=2024-04-05&guests=2&min_rating=4.0
```

**Parámetros:**
- `city` (opcional): Ciudad de destino
- `check_in` (opcional): Fecha de entrada (YYYY-MM-DD)
- `check_out` (opcional): Fecha de salida (YYYY-MM-DD)
- `guests` (opcional): Número de huéspedes
- `min_rating` (opcional): Calificación mínima (0-5)
- `page` (opcional): Número de página (default: 1)
- `page_size` (opcional): Resultados por página (default: 20, max: 100)

**Respuesta:**
```json
{
  "results": [
    {
      "id": "uuid-del-hotel",
      "name": "Hotel Plaza",
      "description": "Hotel en el centro de la ciudad",
      "city": "Bogotá",
      "country": "Colombia",
      "address": "Calle 100 #15-20",
      "rating": 4.5,
      "available_rooms_count": 5,
      "min_price": 150000
    }
  ],
  "total": 1,
  "page": 1,
  "page_size": 20,
  "total_pages": 1,
  "filters": {
    "city": "Bogotá",
    "check_in": "2024-04-01",
    "check_out": "2024-04-05",
    "guests": 2,
    "min_rating": 4.0
  }
}
```

#### Ver Habitaciones de un Hotel
```http
GET /search/hotels/{hotel_id}/rooms
```

**Respuesta:**
```json
{
  "hotel_id": "uuid-del-hotel",
  "rooms": [
    {
      "id": "uuid-habitacion",
      "hotel_id": "uuid-del-hotel",
      "room_type": "Standard",
      "room_number": "101",
      "capacity": 2,
      "price_per_night": 150000,
      "tax_rate": 0.19,
      "total_quantity": 1
    }
  ],
  "total": 1
}
```

## 🔄 Flujo de Sincronización

1. **Registro de Hotel:**
   - Admin/Tercero envía POST a `/hotels/webhook`
   - Inventory Service guarda en PostgreSQL
   - Publica evento `created` con `entity_type: hotel` a SQS

2. **Sincronización:**
   - Search Worker consume mensaje de SQS
   - Indexa hotel en Redis con RediSearch
   - Elimina mensaje de la cola

3. **Búsqueda:**
   - Usuario busca hoteles por ciudad/fechas/huéspedes
   - Search Service consulta Redis
   - Filtra hoteles con habitaciones disponibles
   - Retorna resultados ordenados

## 🧪 Ejemplos de Uso

### 1. Registrar un Hotel

```bash
curl -X POST http://localhost:8006/hotels/webhook \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Hotel Boutique Cartagena",
    "description": "Hotel colonial en el centro histórico",
    "city": "Cartagena",
    "country": "Colombia",
    "address": "Centro Histórico, Calle del Arsenal",
    "rating": 4.8
  }'
```

### 2. Buscar Hoteles por Ciudad

```bash
curl "http://localhost:8003/search/hotels?city=Cartagena"
```

### 3. Buscar con Fechas y Huéspedes

```bash
curl "http://localhost:8003/search/hotels?city=Cartagena&check_in=2024-04-15&check_out=2024-04-20&guests=2&min_rating=4.5"
```

### 4. Ver Habitaciones de un Hotel

```bash
curl "http://localhost:8003/search/hotels/{hotel_id}/rooms"
```

## ⚠️ Validaciones

### Fechas
```bash
# ❌ Error: Fecha de salida antes de entrada
GET /search/hotels?check_in=2024-04-10&check_out=2024-04-05
# Respuesta: 400 "Check-out date must be after check-in date"

# ❌ Error: Fecha en el pasado
GET /search/hotels?check_in=2023-01-01
# Respuesta: 400 "Check-in date cannot be in the past"
```

### Huéspedes
```bash
# ❌ Error: Huéspedes <= 0
GET /search/hotels?guests=0
# Respuesta: 400 "Number of guests must be greater than zero"
```

## 🐳 Docker Compose

```bash
# Levantar todos los servicios
docker-compose up -d postgres redis localstack inventory-service search-service search-worker

# Ver logs
docker-compose logs -f search-worker

# Verificar salud
curl http://localhost:8006/health  # Inventory
curl http://localhost:8003/health  # Search
```

## 🛠️ Stack Tecnológico

- **FastAPI** - Framework web async
- **PostgreSQL** - Base de datos inventory
- **Redis Stack** - Cache + RediSearch
- **AWS SQS** - Cola de mensajes (LocalStack)
- **SQLAlchemy** - ORM async
- **Pydantic** - Validación de datos
- **boto3** - SDK AWS

## 📊 Estructura de Datos

### Hotel (PostgreSQL + Redis)
```python
{
    "id": "uuid",
    "name": "string",
    "description": "string",
    "city": "string",
    "country": "string",
    "address": "string",
    "rating": float  # 0-5
}
```

### Room (PostgreSQL + Redis)
```python
{
    "id": "uuid",
    "hotel_id": "uuid",
    "room_type": "string",
    "room_number": "string",
    "capacity": int,
    "price_per_night": float,
    "tax_rate": float,
    "total_quantity": int
}
```

### Evento SQS
```python
{
    "event_id": "uuid",
    "event_type": "created|updated|deleted",
    "entity_type": "hotel|room",
    "timestamp": "ISO8601",
    "data": {
        "hotel": {...},  # o "room": {...}
        "previous_state": {...}  # solo en updated
    },
    "metadata": {
        "retry_count": 0,
        "correlation_id": "uuid",
        "source_service": "inventory-service"
    }
}
```

## 🧪 Tests

```bash
# Inventory Service
cd services/inventory_service
poetry install
poetry run pytest -v

# Search Service
cd services/search_service
poetry install
poetry run pytest -v
```

## 📝 Notas Importantes

1. **LocalStack**: Simula AWS SQS localmente en puerto 4566
2. **Redis Stack**: Incluye módulo RediSearch para búsquedas
3. **Worker**: Debe estar corriendo para sincronización automática
4. **Webhook**: Endpoint para que terceros registren hoteles
5. **Disponibilidad**: Filtrado por capacidad de habitaciones
