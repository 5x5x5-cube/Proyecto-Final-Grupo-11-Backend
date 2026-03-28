"""
Configuración de pytest para el search-service.

El cliente de Redis se inicializa como singleton a nivel de módulo en redis_client.py,
lo que significa que intenta conectarse a Redis en el momento de la importación.
Este conftest parchea redis.from_url ANTES de que pytest importe los módulos de test,
permitiendo ejecutar los tests sin necesidad de tener Redis corriendo localmente.
"""

from unittest.mock import MagicMock, patch

# Iniciamos el patch antes de la importación de cualquier módulo de la app.
# pytest_configure es el hook más temprano disponible en pytest.
_redis_patcher = patch("redis.from_url")
_mock_redis_instance = MagicMock()


def pytest_configure(config):
    """Parchea redis.from_url antes de la recolección de tests."""
    mock_from_url = _redis_patcher.start()
    mock_from_url.return_value = _mock_redis_instance

    # Simulamos que los índices ya existen para que _ensure_indexes no falle
    # (el código solo captura redis.ResponseError, así que retornamos exitosamente)
    _mock_redis_instance.ft.return_value.info.return_value = {"index_name": "test"}
    _mock_redis_instance.ping.return_value = True


def pytest_unconfigure(config):
    """Detiene el patch al terminar la sesión de tests."""
    _redis_patcher.stop()
