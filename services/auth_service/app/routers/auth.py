import uuid
from datetime import datetime, timedelta
from enum import Enum
from typing import Optional

import jwt
from fastapi import APIRouter, HTTPException
from passlib.context import CryptContext
from pydantic import BaseModel

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])

# Configuración JWT (en producción usar variables de entorno)
SECRET_KEY = "your-secret-key-change-in-production"  # nosec B105
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24  # 24 horas

# Hashing de contraseñas con bcrypt. Nunca guardamos la contraseña en plano.
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class Role(str, Enum):
    """Roles soportados por la plataforma.

    - ``traveler``: usuario viajero (app móvil / web pública).
    - ``hotel_admin``: administrador del portal de hoteles (HU3.1).
    """

    TRAVELER = "traveler"
    HOTEL_ADMIN = "hotel_admin"


# Base de datos en memoria (en producción usar PostgreSQL)
users_db: dict = {}


class RegisterRequest(BaseModel):
    email: str
    password: str
    name: str
    role: Optional[Role] = Role.TRAVELER


class LoginRequest(BaseModel):
    email: str
    password: str


class AuthResponse(BaseModel):
    access_token: str
    token_type: str
    user_id: str
    email: str
    name: str
    role: Role


def hash_password(plain: str) -> str:
    """Genera un hash bcrypt de la contraseña."""
    return pwd_context.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    """Verifica una contraseña contra su hash bcrypt."""
    return pwd_context.verify(plain, hashed)


def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def _seed_hotel_admin() -> None:
    """Crea un admin de hotel por defecto para desarrollo.

    Solo se ejecuta si el usuario no existe aún. En producción este seed se
    reemplaza por un alta controlada por el equipo comercial (fuera de alcance
    de HU3.1 — ver ticket técnico de MFA).
    """
    seed_email = "admin@hotel.com"
    if seed_email in users_db:
        return
    users_db[seed_email] = {
        "id": "hotel-admin-001",
        "email": seed_email,
        "password": hash_password("Admin123!"),  # nosec B106 -- dev seed only
        "name": "Admin Hotel",
        "role": Role.HOTEL_ADMIN,
        "created_at": datetime.utcnow(),
    }


# Ejecutar el seed al importar el módulo para que el admin esté disponible
# desde el primer request (útil en dev y en tests).
_seed_hotel_admin()


@router.post("/register", response_model=AuthResponse)
async def register(request: RegisterRequest):
    """Registrar un nuevo usuario"""
    # Verificar si el usuario ya existe
    if request.email in users_db:
        raise HTTPException(status_code=400, detail="Email already registered")

    # Crear nuevo usuario (contraseña hasheada con bcrypt)
    user_id = str(uuid.uuid4())
    role = request.role or Role.TRAVELER
    users_db[request.email] = {
        "id": user_id,
        "email": request.email,
        "password": hash_password(request.password),
        "name": request.name,
        "role": role,
        "created_at": datetime.utcnow(),
    }

    # Crear token (incluye rol para que el gateway / servicios puedan autorizar)
    access_token = create_access_token(
        data={"sub": user_id, "email": request.email, "role": role.value}
    )

    return AuthResponse(
        access_token=access_token,
        token_type="bearer",  # nosec B106
        user_id=user_id,
        email=request.email,
        name=request.name,
        role=role,
    )


@router.post("/login", response_model=AuthResponse)
async def login(request: LoginRequest):
    """Iniciar sesión"""
    # Verificar credenciales. Usamos un mensaje genérico tanto si el usuario no
    # existe como si la contraseña es incorrecta para evitar enumeración.
    user = users_db.get(request.email)
    if not user or not verify_password(request.password, user["password"]):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    role: Role = user["role"]

    # Crear token
    access_token = create_access_token(
        data={"sub": user["id"], "email": request.email, "role": role.value}
    )

    return AuthResponse(
        access_token=access_token,
        token_type="bearer",  # nosec B106
        user_id=user["id"],
        email=request.email,
        name=user["name"],
        role=role,
    )


@router.get("/me")
async def get_current_user(token: str):
    """Obtener información del usuario actual"""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email = payload.get("email")

        user = users_db.get(email)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        return {
            "user_id": user["id"],
            "email": user["email"],
            "name": user["name"],
            "role": user["role"].value,
        }
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Invalid token")


@router.get("/users/{user_id}")
async def get_user_by_id(user_id: str):
    """Internal endpoint: look up a user by ID (no JWT required)."""
    for user in users_db.values():
        if user["id"] == user_id:
            return {
                "user_id": user["id"],
                "email": user["email"],
                "name": user["name"],
                "role": user["role"].value,
            }
    raise HTTPException(status_code=404, detail="User not found")
