#!/bin/bash

# Script para configurar entorno de desarrollo

set -e

echo "🚀 Configurando entorno de desarrollo..."

# Verificar que Poetry está instalado
if ! command -v poetry &> /dev/null; then
    echo "❌ Poetry no está instalado. Instalando..."
    curl -sSL https://install.python-poetry.org | python3 -
    export PATH="$HOME/.local/bin:$PATH"
fi

# Verificar que Docker está instalado
if ! command -v docker &> /dev/null; then
    echo "❌ Docker no está instalado. Por favor instala Docker primero."
    exit 1
fi

# Verificar que Docker Compose está instalado
if ! command -v docker-compose &> /dev/null; then
    echo "❌ Docker Compose no está instalado. Por favor instala Docker Compose primero."
    exit 1
fi

echo "✅ Dependencias del sistema verificadas"

# Instalar dependencias de cada servicio
echo "📦 Instalando dependencias de los servicios..."
for dir in services/*/; do
    service=$(basename "$dir")
    echo "  - Instalando $service..."
    cd "$dir"
    poetry install --no-interaction
    cd ../..
done

echo "✅ Dependencias instaladas"

# Crear archivo .env si no existe
if [ ! -f .env ]; then
    echo "📝 Creando archivo .env..."
    cat > .env << EOF
# Database
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/proyectofinal

# Redis
REDIS_URL=redis://localhost:6379

# AWS (para desarrollo local, usar localstack)
AWS_REGION=us-east-1
AWS_ACCESS_KEY_ID=test
AWS_SECRET_ACCESS_KEY=test

# Environment
ENVIRONMENT=development
EOF
    echo "✅ Archivo .env creado"
fi

echo ""
echo "✅ Entorno de desarrollo configurado correctamente!"
echo ""
echo "Próximos pasos:"
echo "  1. Levantar servicios: make docker-up"
echo "  2. Ver logs: docker-compose logs -f"
echo "  3. Ejecutar tests: make test"
echo "  4. Formatear código: make format"
echo ""
