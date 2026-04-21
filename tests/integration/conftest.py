"""
System-wide integration tests — conftest.

Requires services to be running. By default targets local Docker Compose.
Override via environment variables to point to any deployed environment:

    GATEWAY_URL=https://gateway.dev.example.com pytest tests/integration/
"""

import os
import subprocess
import time

import httpx
import pytest

GATEWAY_URL = os.environ.get("GATEWAY_URL", "http://localhost:8090")
INVENTORY_URL = os.environ.get("INVENTORY_URL", "http://localhost:8006")
SEARCH_URL = os.environ.get("SEARCH_URL", "http://localhost:8003")
BOOKING_URL = os.environ.get("BOOKING_URL", "http://localhost:8002")
CART_URL = os.environ.get("CART_URL", "http://localhost:8004")
DATABASE_URL = os.environ.get(
    "DATABASE_URL", "postgresql+asyncpg://postgres:postgres@localhost:5432/travelhub"
)

DEFAULT_USER_ID = "c1000000-0000-0000-0000-000000000001"
ALT_USER_ID = "c2000000-0000-0000-0000-000000000002"

# Seed data IDs
HOTEL_CARIBE_ID = "a1000000-0000-0000-0000-000000000001"
HOTEL_BOGOTA_ID = "a1000000-0000-0000-0000-000000000002"
HOTEL_MEDELLIN_ID = "a1000000-0000-0000-0000-000000000003"
ROOM_STANDARD_CARIBE_ID = "b1000000-0000-0000-0000-000000000001"
ROOM_DELUXE_CARIBE_ID = "b1000000-0000-0000-0000-000000000002"
ROOM_STANDARD_BOGOTA_ID = "b1000000-0000-0000-0000-000000000004"
ROOM_CABIN_MEDELLIN_ID = "b1000000-0000-0000-0000-000000000006"


@pytest.fixture(scope="session")
def http():
    """Shared httpx client for the whole test session."""
    with httpx.Client(timeout=30) as client:
        yield client


@pytest.fixture(scope="session", autouse=True)
def wait_for_services(http):
    """Block until all core services are healthy."""
    services = {
        "gateway": f"{GATEWAY_URL}/health",
        "inventory": f"{INVENTORY_URL}/health",
        "booking": f"{BOOKING_URL}/health",
        "cart": f"{CART_URL}/health",
        "search": f"{SEARCH_URL}/health",
    }
    max_wait = 120
    start = time.time()
    pending = set(services.keys())

    while pending and (time.time() - start) < max_wait:
        for name in list(pending):
            try:
                r = http.get(services[name])
                if r.status_code == 200:
                    pending.discard(name)
            except httpx.ConnectError:
                pass
        if pending:
            time.sleep(2)

    if pending:
        pytest.exit(f"Services not ready after {max_wait}s: {pending}", returncode=1)


@pytest.fixture(scope="session", autouse=True)
def seed_database(wait_for_services):
    """Run the inventory seed script if DB is empty (local/Docker only)."""
    if os.environ.get("SKIP_SEED"):
        return

    inventory_dir = os.path.join(
        os.path.dirname(__file__), "..", "..", "services", "inventory_service"
    )
    inventory_dir = os.path.abspath(inventory_dir)

    if not os.path.isdir(inventory_dir):
        print(f"Seed skipped: {inventory_dir} not found (running against remote?)")
        return

    result = subprocess.run(
        [
            "poetry",
            "run",
            "python",
            "-c",
            (
                "import asyncio; "
                "from scripts.seed import seed; "
                f"asyncio.run(seed('{DATABASE_URL}'))"
            ),
        ],
        capture_output=True,
        text=True,
        cwd=inventory_dir,
    )
    print(result.stdout)
    if result.returncode != 0:
        print(f"Seed stderr: {result.stderr}")


@pytest.fixture(scope="session", autouse=True)
def cleanup_test_data(http, seed_database):
    """Run tests, then clean up bookings/carts/holds created during the session."""
    yield  # tests run here

    # Clean up cart (best-effort, may already be deleted)
    for user_id in (DEFAULT_USER_ID, ALT_USER_ID):
        http.delete(f"{CART_URL}/api/v1/cart", headers=user_headers(user_id))

    # Clean up bookings and holds via DB if DATABASE_URL is accessible
    if os.environ.get("SKIP_CLEANUP"):
        return

    sync_url = DATABASE_URL.replace("+asyncpg", "").replace("postgresql://", "postgresql://")
    try:
        import psycopg2

        conn = psycopg2.connect(sync_url)
        conn.autocommit = True
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM bookings WHERE user_id IN (%s, %s)",
                (DEFAULT_USER_ID, ALT_USER_ID),
            )
            cur.execute(
                "DELETE FROM carts WHERE user_id IN (%s, %s)",
                (DEFAULT_USER_ID, ALT_USER_ID),
            )
            cur.execute(
                "DELETE FROM holds WHERE user_id IN (%s, %s)",
                (DEFAULT_USER_ID, ALT_USER_ID),
            )
            print("Cleanup: deleted test bookings, carts, and holds for test users")
        conn.close()
    except ImportError:
        print("Cleanup skipped: psycopg2 not installed (install with: pip install psycopg2-binary)")
    except Exception as e:
        print(f"Cleanup warning: {e}")


def user_headers(user_id=DEFAULT_USER_ID):
    return {"X-User-Id": user_id}
