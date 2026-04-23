import jwt
from fastapi.testclient import TestClient

from app.main import app
from app.routers.auth import ALGORITHM, SECRET_KEY

client = TestClient(app)


def test_register_user():
    """Test user registration defaults to traveler role"""
    response = client.post(
        "/api/v1/auth/register",
        json={"email": "test@example.com", "password": "password123", "name": "Test User"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert data["email"] == "test@example.com"
    assert data["name"] == "Test User"
    assert data["role"] == "traveler"
    assert "user_id" in data


def test_register_duplicate_email():
    """Test registration with duplicate email"""
    # First registration
    client.post(
        "/api/v1/auth/register",
        json={"email": "duplicate@example.com", "password": "pass123", "name": "User One"},
    )

    # Try to register again with same email
    response = client.post(
        "/api/v1/auth/register",
        json={"email": "duplicate@example.com", "password": "pass456", "name": "User Two"},
    )
    assert response.status_code == 400
    assert "already registered" in response.json()["detail"].lower()


def test_login_success():
    """Test successful login"""
    # Register a user
    client.post(
        "/api/v1/auth/register",
        json={"email": "login@example.com", "password": "mypassword", "name": "Login User"},
    )

    # Login
    response = client.post(
        "/api/v1/auth/login", json={"email": "login@example.com", "password": "mypassword"}
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert data["email"] == "login@example.com"
    assert data["role"] == "traveler"


def test_login_invalid_credentials():
    """Test login with invalid credentials"""
    response = client.post(
        "/api/v1/auth/login", json={"email": "nonexistent@example.com", "password": "wrongpass"}
    )
    assert response.status_code == 401
    assert "invalid credentials" in response.json()["detail"].lower()


def test_login_wrong_password():
    """Test login with wrong password"""
    # Register a user
    client.post(
        "/api/v1/auth/register",
        json={"email": "wrongpass@example.com", "password": "correctpass", "name": "User"},
    )

    # Try to login with wrong password
    response = client.post(
        "/api/v1/auth/login", json={"email": "wrongpass@example.com", "password": "wrongpass"}
    )
    assert response.status_code == 401


def test_get_user_by_id():
    """Test internal user lookup by ID"""
    # Register a user first
    reg = client.post(
        "/api/v1/auth/register",
        json={"email": "lookup@example.com", "password": "pass123", "name": "Lookup User"},
    )
    user_id = reg.json()["user_id"]

    # Look up by ID
    response = client.get(f"/api/v1/auth/users/{user_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Lookup User"
    assert data["email"] == "lookup@example.com"
    assert data["user_id"] == user_id
    assert data["role"] == "traveler"


def test_get_user_by_id_not_found():
    """Test user lookup with non-existent ID"""
    response = client.get("/api/v1/auth/users/non-existent-id")
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# HU3.1 — Hotel admin support
# ---------------------------------------------------------------------------


def test_register_hotel_admin_role():
    """Registering a user with role=hotel_admin returns that role."""
    response = client.post(
        "/api/v1/auth/register",
        json={
            "email": "newadmin@hotel.com",
            "password": "StrongPass1!",
            "name": "New Hotel Admin",
            "role": "hotel_admin",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["role"] == "hotel_admin"


def test_seed_hotel_admin_can_login():
    """The dev-seed hotel admin (admin@hotel.com / Admin123!) exists at startup."""
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "admin@hotel.com", "password": "Admin123!"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["email"] == "admin@hotel.com"
    assert data["role"] == "hotel_admin"
    assert data["user_id"] == "hotel-admin-001"


def test_login_jwt_contains_role():
    """The access token payload includes the role so services can authorize."""
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "admin@hotel.com", "password": "Admin123!"},
    )
    assert response.status_code == 200
    token = response.json()["access_token"]
    payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    assert payload["role"] == "hotel_admin"
    assert payload["email"] == "admin@hotel.com"


def test_password_is_hashed_not_stored_plain():
    """Passwords must be stored as bcrypt hashes, never in plain text."""
    from app.routers.auth import users_db

    client.post(
        "/api/v1/auth/register",
        json={"email": "hashcheck@example.com", "password": "MySecret123", "name": "Hash Check"},
    )
    stored = users_db["hashcheck@example.com"]["password"]
    assert stored != "MySecret123"
    # bcrypt hashes start with $2b$ / $2a$
    assert stored.startswith("$2")
