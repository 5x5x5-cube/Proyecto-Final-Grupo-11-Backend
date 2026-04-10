from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_register_user():
    """Test user registration"""
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
