"""
Gateway Unit Tests
==================
Tests auth, rate limiting, and route logic.

Run:
  pytest Tests.py -v
"""
import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, patch, MagicMock
from fastapi import HTTPException
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.Auth import hash_password, verify_password, create_access_token, create_refresh_token, decode_token, generate_api_key


# =============================================================================
# Auth unit tests (no database needed)
# =============================================================================

class TestPasswordHashing:
    def test_hash_and_verify(self):
        password = "testpassword123"
        hashed = hash_password(password)
        assert verify_password(password, hashed) is True

    def test_wrong_password(self):
        hashed = hash_password("correct_password")
        assert verify_password("wrong_password", hashed) is False

    def test_hash_is_different_each_time(self):
        h1 = hash_password("same_password")
        h2 = hash_password("same_password")
        assert h1 != h2


class TestJWT:
    def test_create_and_decode_access_token(self):
        token = create_access_token(user_id=456)
        payload = decode_token(token)
        assert payload["sub"] == 456
        assert payload["type"] == "access"

    def test_create_and_decode_refresh_token(self):
        token = create_refresh_token(user_id=456)
        payload = decode_token(token)
        assert payload["sub"] == 456
        assert payload["type"] == "refresh"

    def test_invalid_token(self):
        with pytest.raises(Exception):
            decode_token("invalid.token.here")

    def test_token_contains_expiry(self):
        token = create_access_token(user_id=1)
        payload = decode_token(token)
        assert "exp" in payload
        assert "iat" in payload


class TestAPIKey:
    def test_generate_api_key_format(self):
        key = generate_api_key()
        assert key.startswith("ask_")
        assert len(key) > 40

    def test_api_keys_are_unique(self):
        k1 = generate_api_key()
        k2 = generate_api_key()
        assert k1 != k2


# =============================================================================
# Route integration tests (mock database and Redis)
# =============================================================================

@pytest_asyncio.fixture
async def client():
    """Create test client with mocked database and Redis."""
    with patch("app.main.init_db", new_callable=AsyncMock), \
         patch("app.main.close_db", new_callable=AsyncMock), \
         patch("app.main.init_redis", new_callable=AsyncMock), \
         patch("app.main.close_redis", new_callable=AsyncMock):

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            yield ac


@pytest.mark.asyncio
class TestHealthEndpoints:
    async def test_health(self, client):
        resp = await client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["service"] == "gateway"

    async def test_root(self, client):
        resp = await client.get("/")
        assert resp.status_code == 200
        data = resp.json()
        assert data["service"] == "ASR Gateway"
        assert data["version"] == "1.0.0"


@pytest.mark.asyncio
class TestRegister:
    async def test_register_success(self, client):
        mock_user = {
            "id": 1,
            "email": "test@example.com",
            "api_key": "ask_abc123",
            "plan": "free",
            "quota_minutes": 60,
            "used_minutes": 0,
            "created_at": "2026-03-13T00:00:00",
        }

        with patch("app.Routes.get_user_by_email", new_callable=AsyncMock, return_value=None), \
             patch("app.Routes.create_user", new_callable=AsyncMock, return_value=mock_user):
            resp = await client.post("/api/auth/register", json={
                "email": "test@example.com",
                "password": "testpassword123",
            })
            assert resp.status_code == 200
            data = resp.json()
            assert data["email"] == "test@example.com"
            assert data["plan"] == "free"

    async def test_register_duplicate_email(self, client):
        existing_user = {"id": 1, "email": "test@example.com"}

        with patch("app.Routes.get_user_by_email", new_callable=AsyncMock, return_value=existing_user):
            resp = await client.post("/api/auth/register", json={
                "email": "test@example.com",
                "password": "testpassword123",
            })
            assert resp.status_code == 400
            assert "already registered" in resp.json()["detail"]

    async def test_register_short_password(self, client):
        with patch("app.Routes.get_user_by_email", new_callable=AsyncMock, return_value=None):
            resp = await client.post("/api/auth/register", json={
                "email": "test@example.com",
                "password": "short",
            })
            assert resp.status_code == 400
            assert "8 characters" in resp.json()["detail"]

    async def test_register_invalid_email(self, client):
        resp = await client.post("/api/auth/register", json={
            "email": "not-an-email",
            "password": "testpassword123",
        })
        assert resp.status_code == 422


@pytest.mark.asyncio
class TestLogin:
    async def test_login_success(self, client):
        mock_user = {
            "id": 1,
            "email": "test@example.com",
            "password_hash": hash_password("testpassword123"),
            "api_key": "ask_abc123",
            "plan": "free",
            "quota_minutes": 60,
            "used_minutes": 0,
            "is_active": True,
        }

        with patch("app.Routes.get_user_by_email", new_callable=AsyncMock, return_value=mock_user):
            resp = await client.post("/api/auth/login", json={
                "email": "test@example.com",
                "password": "testpassword123",
            })
            assert resp.status_code == 200
            data = resp.json()
            assert "access_token" in data
            assert "refresh_token" in data
            assert data["token_type"] == "bearer"

    async def test_login_wrong_password(self, client):
        mock_user = {
            "id": 1,
            "email": "test@example.com",
            "password_hash": hash_password("correct_password"),
        }

        with patch("app.Routes.get_user_by_email", new_callable=AsyncMock, return_value=mock_user):
            resp = await client.post("/api/auth/login", json={
                "email": "test@example.com",
                "password": "wrong_password",
            })
            assert resp.status_code == 401

    async def test_login_nonexistent_user(self, client):
        with patch("app.Routes.get_user_by_email", new_callable=AsyncMock, return_value=None):
            resp = await client.post("/api/auth/login", json={
                "email": "nobody@example.com",
                "password": "testpassword123",
            })
            assert resp.status_code == 401


@pytest.mark.asyncio
class TestAuthenticatedRoutes:
    def _auth_header(self, user_id=1):
        token = create_access_token(user_id)
        return {"Authorization": f"Bearer {token}"}

    async def test_me_with_valid_token(self, client):
        mock_user = {
            "id": 1,
            "email": "test@example.com",
            "api_key": "ask_abc123",
            "plan": "free",
            "quota_minutes": 60,
            "used_minutes": 0,
            "created_at": "2026-03-13T00:00:00",
            "updated_at": "2026-03-13T00:00:00",
            "password_hash": "xxx",
            "is_active": True,
        }

        with patch("app.Auth.get_user_by_id", new_callable=AsyncMock, return_value=mock_user):
            resp = await client.get("/api/auth/me", headers=self._auth_header())
            assert resp.status_code == 200
            data = resp.json()
            assert data["email"] == "test@example.com"

    async def test_me_without_token(self, client):
        resp = await client.get("/api/auth/me")
        assert resp.status_code == 401

    async def test_me_with_invalid_token(self, client):
        resp = await client.get("/api/auth/me", headers={
            "Authorization": "Bearer invalid.token.here"
        })
        assert resp.status_code == 401

    async def test_me_with_api_key(self, client):
        mock_user = {
            "id": 1,
            "email": "test@example.com",
            "api_key": "ask_abc123",
            "plan": "free",
            "quota_minutes": 60,
            "used_minutes": 0,
            "created_at": "2026-03-13T00:00:00",
            "updated_at": "2026-03-13T00:00:00",
            "password_hash": "xxx",
            "is_active": True,
        }

        with patch("app.Auth.get_user_by_api_key", new_callable=AsyncMock, return_value=mock_user):
            resp = await client.get("/api/auth/me", headers={
                "X-API-Key": "ask_abc123"
            })
            assert resp.status_code == 200


@pytest.mark.asyncio
class TestRefreshToken:
    async def test_refresh_success(self, client):
        refresh = create_refresh_token(user_id=1)
        resp = await client.post("/api/auth/refresh", json={
            "refresh_token": refresh,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        assert "refresh_token" in data

    async def test_refresh_with_access_token_fails(self, client):
        access = create_access_token(user_id=1)
        resp = await client.post("/api/auth/refresh", json={
            "refresh_token": access,
        })
        assert resp.status_code == 401


@pytest.mark.asyncio
class TestQuota:
    def _auth_header(self, user_id=1):
        token = create_access_token(user_id)
        return {"Authorization": f"Bearer {token}"}

    async def test_quota_check(self, client):
        mock_user = {
            "id": 1, "email": "test@example.com", "api_key": "ask_abc",
            "plan": "free", "quota_minutes": 60, "used_minutes": 10,
            "created_at": "2026-03-13T00:00:00", "updated_at": "2026-03-13T00:00:00",
            "password_hash": "xxx", "is_active": True,
        }
        mock_quota = {
            "has_quota": True, "remaining": 50, "quota": 60, "used": 10,
        }

        with patch("app.Auth.get_user_by_id", new_callable=AsyncMock, return_value=mock_user), \
             patch("app.Routes.check_quota", new_callable=AsyncMock, return_value=mock_quota):
            resp = await client.get("/api/auth/quota", headers=self._auth_header())
            assert resp.status_code == 200
            data = resp.json()
            assert data["has_quota"] is True
            assert data["remaining"] == 50


@pytest.mark.asyncio
class TestJobProxy:
    def _auth_header(self, user_id=1):
        token = create_access_token(user_id)
        return {"Authorization": f"Bearer {token}"}

    def _mock_user(self):
        return {
            "id": 1, "email": "test@example.com", "api_key": "ask_abc",
            "plan": "free", "quota_minutes": 60, "used_minutes": 10,
            "created_at": "2026-03-13T00:00:00", "updated_at": "2026-03-13T00:00:00",
            "password_hash": "xxx", "is_active": True,
        }

    async def test_create_job_proxies_to_orchestrator(self, client):
        mock_quota = {"has_quota": True, "remaining": 50, "quota": 60, "used": 10}
        mock_orchestrator_response = MagicMock()
        mock_orchestrator_response.status_code = 200
        mock_orchestrator_response.json.return_value = {
            "id": "j_123", "status": "queued", "user_id": 1,
        }

        with patch("app.Auth.get_user_by_id", new_callable=AsyncMock, return_value=self._mock_user()), \
             patch("app.Routes.check_quota", new_callable=AsyncMock, return_value=mock_quota), \
             patch("app.Routes.check_rate_limit", new_callable=AsyncMock), \
             patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=mock_orchestrator_response):
            resp = await client.post("/api/jobs", headers=self._auth_header(), json={
                "file_path": "s3://uploads/test.mp4",
                "dialect": "lebanese",
            })
            assert resp.status_code == 200
            assert resp.json()["id"] == "j_123"

    async def test_create_job_rejected_no_quota(self, client):
        mock_quota = {"has_quota": False, "remaining": 0, "quota": 60, "used": 60}

        with patch("app.Auth.get_user_by_id", new_callable=AsyncMock, return_value=self._mock_user()), \
             patch("app.Routes.check_quota", new_callable=AsyncMock, return_value=mock_quota), \
             patch("app.Routes.check_rate_limit", new_callable=AsyncMock):
            resp = await client.post("/api/jobs", headers=self._auth_header(), json={
                "file_path": "s3://uploads/test.mp4",
            })
            assert resp.status_code == 403
            assert "Quota exceeded" in resp.json()["detail"]

    async def test_get_job_proxies_to_orchestrator(self, client):
        mock_orchestrator_response = MagicMock()
        mock_orchestrator_response.status_code = 200
        mock_orchestrator_response.json.return_value = {
            "id": "j_123", "status": "transcribing", "progress": 45,
        }

        with patch("app.Auth.get_user_by_id", new_callable=AsyncMock, return_value=self._mock_user()), \
             patch("app.Routes.check_rate_limit", new_callable=AsyncMock), \
             patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=mock_orchestrator_response):
            resp = await client.get("/api/jobs/j_123", headers=self._auth_header())
            assert resp.status_code == 200
            assert resp.json()["status"] == "transcribing"

    async def test_orchestrator_unavailable(self, client):
        with patch("app.Auth.get_user_by_id", new_callable=AsyncMock, return_value=self._mock_user()), \
             patch("app.Routes.check_rate_limit", new_callable=AsyncMock), \
             patch("app.Routes._proxy_to_orchestrator", new_callable=AsyncMock, side_effect=HTTPException(status_code=503, detail="Orchestrator service unavailable")):
            resp = await client.get("/api/jobs/j_123", headers=self._auth_header())
            assert resp.status_code == 503
            assert "unavailable" in resp.json()["detail"]


@pytest.mark.asyncio
class TestRateLimiting:
    def _auth_header(self, user_id=1):
        token = create_access_token(user_id)
        return {"Authorization": f"Bearer {token}"}

    async def test_rate_limit_passes_when_redis_down(self, client):
        mock_user = {
            "id": 1, "email": "test@example.com", "api_key": "ask_abc",
            "plan": "free", "quota_minutes": 60, "used_minutes": 10,
            "created_at": "2026-03-13T00:00:00", "updated_at": "2026-03-13T00:00:00",
            "password_hash": "xxx", "is_active": True,
        }
        mock_quota = {"has_quota": True, "remaining": 50, "quota": 60, "used": 10}

        with patch("app.Auth.get_user_by_id", new_callable=AsyncMock, return_value=mock_user), \
             patch("app.Routes.check_quota", new_callable=AsyncMock, return_value=mock_quota), \
             patch("app.Rate_limiter.redis_client", None):
            resp = await client.get("/api/auth/quota", headers=self._auth_header())
            assert resp.status_code == 200