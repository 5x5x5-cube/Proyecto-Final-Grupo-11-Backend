# Auth Service

Authentication and Authorization microservice.

## Endpoints

- `GET /health` - Health check endpoint
- `GET /` - Service information
- `POST /api/v1/auth/register` - Register a new user (field `role` opcional: `traveler` | `hotel_admin`)
- `POST /api/v1/auth/login` - Login, devuelve JWT con el rol incluido en el payload
- `GET /api/v1/auth/me?token=...` - Devuelve datos del usuario actual
- `GET /api/v1/auth/users/{user_id}` - Lookup interno por id

## Roles

El servicio soporta dos roles:

- `traveler` — viajero (app móvil y web pública). Es el valor por defecto al registrar.
- `hotel_admin` — administrador del portal de hoteles (HU3.1).

Las contraseñas se almacenan con hash **bcrypt** (vía `passlib`). El JWT incluye el rol
para que el gateway y los demás servicios puedan autorizar rutas sin tener que consultar
al auth service en cada request.

## Seed de desarrollo

Al arrancar el servicio se crea automáticamente un admin de hotel para desarrollo local
y pruebas manuales:

| Email              | Password     | Role          |
|--------------------|--------------|---------------|
| `admin@hotel.com`  | `Admin123!`  | `hotel_admin` |

> En producción este seed se reemplaza por un alta controlada por el equipo comercial.
> MFA, rate limiting y audit logs quedan fuera del alcance de HU3.1 y se gestionan en
> tickets técnicos separados.

## Development

```bash
# Install dependencies
poetry install

# Run service
poetry run uvicorn app.main:app --reload --port 8001

# Run tests
poetry run pytest

# Format code
poetry run black .
poetry run isort .

# Lint
poetry run flake8 .
```
