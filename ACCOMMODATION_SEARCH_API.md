# API de Búsqueda de Alojamientos

Documentación completa de los servicios de Inventory y Search para el sistema de búsqueda de alojamientos.

## 📋 Tabla de Contenidos

- [Arquitectura](#arquitectura)
- [Inventory Service](#inventory-service)
- [Search Service](#search-service)
- [Flujo de Datos](#flujo-de-datos)
- [Ejemplos de Uso](#ejemplos-de-uso)

---

## 🏗️ Arquitectura

```
Terceros → Inventory Service → SQS → Search Service → Redis
                ↓                         ↓
            PostgreSQL              API de Búsqueda
```

### Componentes

1. **Inventory Service** (Puerto 8006)
   - Recibe alojamientos vía webhook
   - Almacena en PostgreSQL
   - Publica eventos a SQS

2. **Search Service** (Puerto 8003)
   - Consume eventos de SQS
   - Indexa en Redis (RediSearch)
   - Expone API de búsqueda

3. **Search Worker**
   - Worker dedicado para procesar cola SQS
   - Indexación asíncrona en Redis

---

## 📦 Inventory Service

### Base URL
```
http://localhost:8006
```

### Endpoints

#### 1. Recibir Alojamiento (Webhook)

```http
POST /webhooks/accommodation
Content-Type: application/json
```

**Request Body:**
```json
{
  "external_id": "airbnb-12345",
  "provider": "airbnb",
  "title": "Hermoso Apartamento en Madrid Centro",
  "description": "Apartamento moderno con vistas increíbles",
  "accommodation_type": "apartment",
  "location": {
    "city": "Madrid",
    "country": "Spain",
    "address": "Calle Gran Vía 123",
    "postal_code": "28013",
    "coordinates": {
      "lat": 40.4168,
      "lon": -3.7038
    }
  },
  "pricing": {
    "base_price": 120.0,
    "currency": "USD",
    "cleaning_fee": 30.0,
    "service_fee": 15.0
  },
  "capacity": {
    "max_guests": 4,
    "bedrooms": 2,
    "beds": 2,
    "bathrooms": 1.5
  },
  "rating": {
    "average": 4.8,
    "count": 156
  },
  "popularity": {
    "views_count": 1200,
    "bookings_count": 45,
    "favorites_count": 89
  },
  "amenities": ["wifi", "kitchen", "air_conditioning", "tv"],
  "images": [
    {
      "url": "https://example.com/image1.jpg",
      "is_primary": true,
      "order": 0
    }
  ],
  "availability": {
    "is_available": true,
    "minimum_nights": 2
  },
  "policies": {
    "cancellation_policy": "flexible",
    "check_in_time": "15:00",
    "check_out_time": "11:00"
  }
}
```

**Response (202 Accepted):**
```json
{
  "message": "Accommodation received and queued for processing",
  "accommodation_id": "550e8400-e29b-41d4-a716-446655440000",
  "external_id": "airbnb-12345"
}
```

#### 2. Listar Alojamientos

```http
GET /accommodations?page=0&limit=20&provider=airbnb&status=active
```

**Response:**
```json
[
  {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "external_id": "airbnb-12345",
    "title": "Hermoso Apartamento en Madrid Centro",
    "accommodation_type": "apartment",
    "pricing": { "total_price": 165.0 },
    "rating": { "average": 4.8 },
    "status": "active"
  }
]
```

#### 3. Obtener Alojamiento

```http
GET /accommodations/{accommodation_id}
```

#### 4. Actualizar Alojamiento

```http
PUT /accommodations/{accommodation_id}
Content-Type: application/json
```

#### 5. Actualizar Popularidad

```http
PATCH /accommodations/{accommodation_id}/popularity
Content-Type: application/json

{
  "views": 10,
  "bookings": 1,
  "favorites": 2
}
```

#### 6. Eliminar Alojamiento

```http
DELETE /accommodations/{accommodation_id}
```

---

## 🔍 Search Service

### Base URL
```
http://localhost:8003
```

### Endpoints

#### 1. Búsqueda con Filtros

```http
GET /search?city=Madrid&min_price=50&max_price=200&accommodation_type=apartment&min_rating=4.0&sort_by=price&sort_order=asc&page=1&page_size=20
```

**Parámetros de Query:**

| Parámetro | Tipo | Descripción | Ejemplo |
|-----------|------|-------------|---------|
| `city` | string | Filtrar por ciudad | `Madrid` |
| `min_price` | float | Precio mínimo | `50` |
| `max_price` | float | Precio máximo | `200` |
| `accommodation_type` | string[] | Tipo de alojamiento (múltiple) | `apartment`, `house` |
| `min_rating` | float | Calificación mínima (0-5) | `4.0` |
| `min_guests` | int | Capacidad mínima de huéspedes | `2` |
| `amenities` | string[] | Amenidades requeridas (múltiple) | `wifi`, `pool` |
| `sort_by` | string | Campo de ordenamiento | `price`, `rating`, `popularity` |
| `sort_order` | string | Dirección de ordenamiento | `asc`, `desc` |
| `page` | int | Número de página | `1` |
| `page_size` | int | Resultados por página (max 100) | `20` |

**Response:**
```json
{
  "results": [
    {
      "id": "550e8400-e29b-41d4-a716-446655440000",
      "title": "Hermoso Apartamento en Madrid Centro",
      "accommodation_type": "apartment",
      "location": {
        "city": "Madrid",
        "country": "Spain"
      },
      "pricing": {
        "total_price": 165.0,
        "currency": "USD"
      },
      "rating": {
        "average": 4.8,
        "count": 156
      },
      "popularity": {
        "popularity_score": 562.0
      },
      "amenities": ["wifi", "kitchen", "air_conditioning"],
      "images": [...]
    }
  ],
  "total": 45,
  "page": 1,
  "page_size": 20,
  "total_pages": 3,
  "filters_applied": {
    "city": "Madrid",
    "min_price": 50,
    "max_price": 200,
    "types": ["apartment"],
    "min_rating": 4.0
  },
  "sort": {
    "by": "price",
    "order": "asc"
  }
}
```

#### 2. Sugerencias de Búsqueda

```http
GET /search/suggestions?q=Mad&limit=10
```

**Response:**
```json
{
  "cities": ["Madrid", "Madeira"],
  "accommodations": [
    {
      "id": "...",
      "title": "Apartamento en Madrid",
      "city": "Madrid",
      "price": 120.0
    }
  ]
}
```

#### 3. Limpiar Filtros

```http
DELETE /search/filters
```

**Response:**
```json
{
  "message": "Filters cleared",
  "info": "Call GET /search without parameters to see all results"
}
```

#### 4. Obtener Alojamiento desde Cache

```http
GET /accommodations/{accommodation_id}
```

---

## 🔄 Flujo de Datos

### 1. Recepción de Alojamiento

```
Tercero → POST /webhooks/accommodation → Inventory Service
                                              ↓
                                        PostgreSQL
                                              ↓
                                         SQS Queue
```

### 2. Indexación

```
SQS Queue → Search Worker → Redis Indexer → RediSearch
```

### 3. Búsqueda

```
Cliente → GET /search → Search Service → RediSearch → Resultados
```

---

## Ejemplos de Uso

### Caso 1: Buscar Apartamentos en Madrid

```bash
curl "http://localhost:8003/search?city=Madrid&accommodation_type=apartment&min_rating=4.0&sort_by=price&sort_order=asc"
```

### Caso 2: Filtrar por Rango de Precio

```bash
curl "http://localhost:8003/search?min_price=50&max_price=150&sort_by=rating&sort_order=desc"
```

### Caso 3: Buscar con Amenidades Específicas

```bash
curl "http://localhost:8003/search?amenities=wifi&amenities=pool&amenities=parking"
```

### Caso 4: Filtros Múltiples Combinados

```bash
curl "http://localhost:8003/search?city=Barcelona&accommodation_type=apartment&accommodation_type=house&min_price=80&max_price=200&min_rating=4.5&min_guests=4&amenities=wifi&amenities=kitchen&sort_by=popularity&sort_order=desc&page=1&page_size=10"
```

### Caso 5: Ordenar por Popularidad

```bash
curl "http://localhost:8003/search?city=Madrid&sort_by=popularity&sort_order=desc"
```

### Caso 6: Enviar Alojamiento desde Tercero

```bash
curl -X POST http://localhost:8006/webhooks/accommodation \
  -H "Content-Type: application/json" \
  -d '{
    "external_id": "booking-67890",
    "provider": "booking",
    "title": "Hotel Boutique en Barcelona",
    "description": "Hotel de lujo en el corazón de Barcelona",
    "accommodation_type": "hotel",
    "location": {
      "city": "Barcelona",
      "country": "Spain",
      "address": "Passeig de Gràcia 100",
      "postal_code": "08008",
      "coordinates": {"lat": 41.3874, "lon": 2.1686}
    },
    "pricing": {
      "base_price": 200.0,
      "currency": "USD",
      "cleaning_fee": 0,
      "service_fee": 20.0
    },
    "capacity": {
      "max_guests": 2,
      "bedrooms": 1,
      "beds": 1,
      "bathrooms": 1
    },
    "rating": {"average": 4.9, "count": 234},
    "popularity": {
      "views_count": 5000,
      "bookings_count": 120,
      "favorites_count": 200
    },
    "amenities": ["wifi", "breakfast", "gym", "spa"],
    "images": [
      {"url": "https://example.com/hotel1.jpg", "is_primary": true, "order": 0}
    ],
    "availability": {"is_available": true, "minimum_nights": 1},
    "policies": {
      "cancellation_policy": "moderate",
      "check_in_time": "14:00",
      "check_out_time": "12:00"
    }
  }'
```

---

## Inicio Rápido

### 1. Levantar Servicios

```bash
docker-compose up -d
```

### 2. Verificar Salud de Servicios

```bash
# Inventory Service
curl http://localhost:8006/health

# Search Service
curl http://localhost:8003/health
```

### 3. Enviar Alojamiento de Prueba

```bash
curl -X POST http://localhost:8006/webhooks/accommodation \
  -H "Content-Type: application/json" \
  -d @examples/sample-accommodation.json
```

### 4. Buscar Alojamientos

```bash
curl "http://localhost:8003/search?page=1&page_size=10"
```

---

## Testing

### Test de Integración Completo

```bash
# 1. Enviar alojamiento
ACCOMMODATION_ID=$(curl -X POST http://localhost:8006/webhooks/accommodation \
  -H "Content-Type: application/json" \
  -d '{"external_id":"test-123", ...}' | jq -r '.accommodation_id')

# 2. Esperar indexación (5-10 segundos)
sleep 10

# 3. Buscar alojamiento
curl "http://localhost:8003/search?city=Madrid"

# 4. Obtener desde cache
curl "http://localhost:8003/accommodations/$ACCOMMODATION_ID"
```

---



