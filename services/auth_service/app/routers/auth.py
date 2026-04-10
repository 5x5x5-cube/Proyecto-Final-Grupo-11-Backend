import uuid
from datetime import datetime, timedelta

import jwt
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])

# Configuración JWT (en producción usar variables de entorno)
SECRET_KEY = "your-secret-key-change-in-production"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24  # 24 horas

# Base de datos en memoria (en producción usar PostgreSQL)
users_db = {}


class RegisterRequest(BaseModel):
    email: str
    password: str
    name: str


class LoginRequest(BaseModel):
    email: str
    password: str


class AuthResponse(BaseModel):
    access_token: str
    token_type: str
    user_id: str
    email: str
    name: str


def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


@router.post("/register", response_model=AuthResponse)
async def register(request: RegisterRequest):
    """Registrar un nuevo usuario"""
    # Verificar si el usuario ya existe
    if request.email in users_db:
        raise HTTPException(status_code=400, detail="Email already registered")

    # Crear nuevo usuario
    user_id = str(uuid.uuid4())
    users_db[request.email] = {
        "id": user_id,
        "email": request.email,
        "password": request.password,  # En producción: hashear con bcrypt
        "name": request.name,
        "created_at": datetime.utcnow(),
    }

    # Crear token
    access_token = create_access_token(data={"sub": user_id, "email": request.email})

    return AuthResponse(
        access_token=access_token,
        token_type="bearer",
        user_id=user_id,
        email=request.email,
        name=request.name,
    )


@router.post("/login", response_model=AuthResponse)
async def login(request: LoginRequest):
    """Iniciar sesión"""
    # Verificar credenciales
    user = users_db.get(request.email)
    if not user or user["password"] != request.password:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    # Crear token
    access_token = create_access_token(data={"sub": user["id"], "email": request.email})

    return AuthResponse(
        access_token=access_token,
        token_type="bearer",
        user_id=user["id"],
        email=request.email,
        name=user["name"],
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
        }
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Invalid token")
