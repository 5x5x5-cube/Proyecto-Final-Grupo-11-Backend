# Guía de Contribución

Gracias por tu interés en contribuir al proyecto. Esta guía te ayudará a empezar.

## Configuración del Entorno de Desarrollo

1. **Clonar el repositorio**
```bash
git clone https://github.com/tu-org/Proyecto-Final-Grupo-11-Backend.git
cd Proyecto-Final-Grupo-11-Backend
```

2. **Ejecutar script de setup**
```bash
chmod +x scripts/setup-dev.sh
./scripts/setup-dev.sh
```

3. **Levantar servicios localmente**
```bash
make docker-up
```

## Flujo de Trabajo

### 1. Crear una Rama

```bash
git checkout -b feature/nombre-de-la-funcionalidad
# o
git checkout -b fix/nombre-del-bug
```

### 2. Hacer Cambios

- Escribe código limpio y bien documentado
- Sigue las convenciones de estilo de Python (PEP 8)
- Agrega tests para nuevas funcionalidades
- Actualiza la documentación si es necesario

### 3. Formatear y Validar

```bash
# Formatear código
make format

# Ejecutar linting
make lint

# Ejecutar tests
make test
```

### 4. Commit

Usa mensajes de commit descriptivos siguiendo [Conventional Commits](https://www.conventionalcommits.org/):

```bash
git add .
git commit -m "feat: agregar endpoint de búsqueda avanzada"
# o
git commit -m "fix: corregir error en validación de datos"
```

Tipos de commit:
- `feat`: Nueva funcionalidad
- `fix`: Corrección de bug
- `docs`: Cambios en documentación
- `style`: Cambios de formato (no afectan el código)
- `refactor`: Refactorización de código
- `test`: Agregar o modificar tests
- `chore`: Tareas de mantenimiento

### 5. Push y Pull Request

```bash
git push origin feature/nombre-de-la-funcionalidad
```

Luego crea un Pull Request en GitHub con:
- Título descriptivo
- Descripción detallada de los cambios
- Referencias a issues relacionados
- Screenshots si aplica

## Estándares de Código

### Python

- **Formateo**: Black con line-length=100
- **Imports**: isort con profile=black
- **Linting**: Flake8
- **Type hints**: Usar type hints cuando sea posible
- **Docstrings**: Usar docstrings para funciones y clases

Ejemplo:
```python
from typing import Optional

def get_user(user_id: int) -> Optional[dict]:
    """
    Obtiene un usuario por su ID.
    
    Args:
        user_id: ID del usuario a buscar
        
    Returns:
        Diccionario con datos del usuario o None si no existe
    """
    # implementación
    pass
```

### Tests

- Usar pytest
- Nombrar tests con `test_` prefix
- Organizar tests en el directorio `tests/`
- Aim for >80% code coverage

Ejemplo:
```python
def test_get_user_success():
    """Test que verifica obtención exitosa de usuario"""
    user = get_user(1)
    assert user is not None
    assert user["id"] == 1

def test_get_user_not_found():
    """Test que verifica manejo de usuario no encontrado"""
    user = get_user(999)
    assert user is None
```

### Estructura de un Servicio

```
service_name/
├── app/
│   ├── __init__.py
│   ├── main.py           # FastAPI app
│   ├── models.py         # Modelos de datos
│   ├── schemas.py        # Pydantic schemas
│   ├── routes/           # Endpoints
│   │   ├── __init__.py
│   │   └── users.py
│   ├── services/         # Lógica de negocio
│   │   ├── __init__.py
│   │   └── user_service.py
│   └── database.py       # Configuración de DB
├── tests/
│   ├── __init__.py
│   ├── test_main.py
│   └── test_routes/
├── pyproject.toml
├── Dockerfile
└── README.md
```

## Revisión de Código

Los Pull Requests deben:
- Pasar todos los tests de CI
- Tener al menos una aprobación
- No tener conflictos con main
- Cumplir con los estándares de código

## Reportar Bugs

Usa el template de issues de GitHub e incluye:
- Descripción clara del problema
- Pasos para reproducir
- Comportamiento esperado vs actual
- Logs o screenshots relevantes
- Versión del servicio afectado

## Solicitar Funcionalidades

Usa el template de feature request e incluye:
- Descripción de la funcionalidad
- Caso de uso
- Beneficios esperados
- Posible implementación (opcional)

## Preguntas

Si tienes preguntas, puedes:
- Abrir un issue de tipo "Question"
- Contactar al equipo en [email]
- Revisar la documentación en `/docs`

## Licencia

Al contribuir, aceptas que tus contribuciones se licenciarán bajo la misma licencia del proyecto.
