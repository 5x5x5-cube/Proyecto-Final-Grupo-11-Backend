# 🚀 Quick Start - Sistema de Búsqueda de Alojamientos

Guía rápida para poner en marcha el sistema de búsqueda de alojamientos.

## 📦 Servicios Implementados

### 1. **Inventory Service** (Puerto 8006)
- Recibe alojamientos de terceros vía webhook
- Almacena en PostgreSQL
- Publica eventos a AWS SQS

### 2. **Search Service** (Puerto 8003)
- API de búsqueda con filtros múltiples
- Indexación en Redis con RediSearch
- Ordenamiento por precio, rating, popularidad

### 3. **Search Worker**
- Worker que consume eventos de SQS
- Indexa alojamientos en Redis automáticamente

## 🏃 Inicio Rápido

### 1. Levantar todos los servicios

```bash
docker-compose up -d postgres redis localstack inventory-service search-service search-worker
```

### 2. Verificar que los servicios están corriendo

```bash
# Inventory Service
curl http://localhost:8006/health

# Search Service
curl http://localhost:8003/health

# Redis (debe mostrar PONG)
docker exec -it <redis-container> redis-cli ping
```

### 3. Enviar un alojamiento de prueba

```bash
curl -X POST http://localhost:8006/webhooks/accommodation \
  -H "Content-Type: application/json" \
  -d '{
    "external_id": "test-001",
    "provider": "airbnb",
    "title": "Apartamento Moderno en Madrid",
    "description": "Hermoso apartamento en el centro de Madrid",
    "accommodation_type": "apartment",
    "location": {
      "city": "Madrid",
      "country": "Spain",
      "address": "Gran Vía 123",
      "postal_code": "28013",
      "coordinates": {"lat": 40.4168, "lon": -3.7038}
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
      {"url": "https://example.com/image1.jpg", "is_primary": true, "order": 0}
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
  }'
```

### 4. Esperar indexación (5-10 segundos)

El worker procesará el mensaje de SQS y lo indexará en Redis.

```bash
# Ver logs del worker
docker-compose logs -f search-worker
```

### 5. Buscar alojamientos

```bash
# Búsqueda simple
curl "http://localhost:8003/search"

# Buscar por ciudad
curl "http://localhost:8003/search?city=Madrid"

# Filtrar por precio
curl "http://localhost:8003/search?min_price=50&max_price=200"

# Filtros múltiples
curl "http://localhost:8003/search?city=Madrid&accommodation_type=apartment&min_rating=4.0&sort_by=price&sort_order=asc"
```

## 📊 Ejemplos de Filtros

### Filtrar por Rango de Precio

```bash
curl "http://localhost:8003/search?min_price=50&max_price=150"
```

### Filtrar por Tipo de Alojamiento

```bash
curl "http://localhost:8003/search?accommodation_type=apartment&accommodation_type=house"
```

### Filtrar por Calificación Mínima

```bash
curl "http://localhost:8003/search?min_rating=4.5"
```

### Filtros Combinados

```bash
curl "http://localhost:8003/search?city=Barcelona&min_price=80&max_price=200&accommodation_type=apartment&min_rating=4.5&amenities=wifi&amenities=pool&sort_by=popularity&sort_order=desc"
```

## 🔄 Ordenamiento

### Por Precio (Menor a Mayor)

```bash
curl "http://localhost:8003/search?sort_by=price&sort_order=asc"
```

### Por Precio (Mayor a Menor)

```bash
curl "http://localhost:8003/search?sort_by=price&sort_order=desc"
```

### Por Calificación

```bash
curl "http://localhost:8003/search?sort_by=rating&sort_order=desc"
```

### Por Popularidad

```bash
curl "http://localhost:8003/search?sort_by=popularity&sort_order=desc"
```

## 🧪 Verificar el Flujo Completo

```bash
# 1. Enviar alojamiento
RESPONSE=$(curl -s -X POST http://localhost:8006/webhooks/accommodation \
  -H "Content-Type: application/json" \
  -d @examples/sample-accommodation.json)

# 2. Extraer ID
ACCOMMODATION_ID=$(echo $RESPONSE | jq -r '.accommodation_id')
echo "Accommodation ID: $ACCOMMODATION_ID"

# 3. Esperar indexación
sleep 10

# 4. Buscar
curl "http://localhost:8003/search?city=Madrid"

# 5. Obtener desde cache
curl "http://localhost:8003/accommodations/$ACCOMMODATION_ID"
```

## 🔍 Debugging

### Ver mensajes en SQS

```bash
docker exec -it <localstack-container> bash
awslocal sqs receive-message \
  --queue-url http://localhost:4566/000000000000/accommodation-sync-queue
```

### Ver índice de Redis

```bash
docker exec -it <redis-container> redis-cli

# Ver información del índice
FT.INFO idx:accommodations

# Buscar todos los alojamientos
FT.SEARCH idx:accommodations "*"

# Contar documentos
FT.SEARCH idx:accommodations "*" LIMIT 0 0
```

### Ver logs de servicios

```bash
# Inventory Service
docker-compose logs -f inventory-service

# Search Service
docker-compose logs -f search-service

# Search Worker
docker-compose logs -f search-worker
```

## 📝 Notas Importantes

1. **LocalStack**: Simula AWS SQS localmente. En producción, usar AWS SQS real.

2. **Redis Stack**: Incluye RediSearch module para búsquedas avanzadas.

3. **Worker**: Debe estar corriendo para que los alojamientos se indexen automáticamente.

4. **Filtros**: Todos los filtros se aplican con lógica AND. Los tipos y amenidades permiten múltiples valores (OR entre ellos).

5. **Paginación**: Por defecto muestra 20 resultados por página. Máximo 100.

## 🎯 Criterios de Aceptación Cumplidos

✅ Filtrar por rango de precio (mínimo y máximo)  
✅ Filtrar por tipo de alojamiento  
✅ Filtrar por calificación mínima  
✅ Aplicar múltiples filtros simultáneamente  
✅ Mostrar solo hospedajes que cumplan filtros  
✅ Limpiar filtros (endpoint DELETE /search/filters)  
✅ Ordenar por precio (menor a mayor / mayor a menor)  
✅ Ordenar por popularidad  
✅ Ordenar por calificación  
✅ Actualizar resultados al cambiar ordenamiento  
✅ Mantener filtros al cambiar ordenamiento  
✅ Mostrar criterio de ordenamiento seleccionado  

## 📚 Documentación Completa

Ver `ACCOMMODATION_SEARCH_API.md` para documentación detallada de la API.
