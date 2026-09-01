"""Contract tests for the Syroce PMS -> Quick-ID boundary."""

import asyncio
import os
import sys
from pathlib import Path

from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

os.environ.setdefault("JWT_SECRET", "unit-test-jwt-secret-not-for-production")

from auth import create_token, require_user_or_service  # noqa: E402
import llm_client  # noqa: E402
from ocr_providers import extract_with_provider  # noqa: E402


def _contract_app() -> FastAPI:
    app = FastAPI()

    @app.get("/protected")
    async def protected(principal=Depends(require_user_or_service)):
        return principal

    return app


def test_pms_service_key_authentication(monkeypatch):
    monkeypatch.setenv("QUICKID_SERVICE_KEY", "pms-contract-secret")
    client = TestClient(_contract_app())

    response = client.get(
        "/protected",
        headers={"X-Service-Key": "pms-contract-secret", "X-Acting-User": "desk@example.com"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "email": "desk@example.com",
        "role": "service",
        "auth_type": "service_key",
    }


def test_service_auth_fails_closed(monkeypatch):
    monkeypatch.delenv("QUICKID_SERVICE_KEY", raising=False)
    client = TestClient(_contract_app())

    assert client.get("/protected").status_code == 401
    assert client.get("/protected", headers={"X-Service-Key": "anything"}).status_code == 401


def test_user_jwt_still_supported(monkeypatch):
    monkeypatch.delenv("QUICKID_SERVICE_KEY", raising=False)
    client = TestClient(_contract_app())
    token = create_token({"email": "admin@example.com", "role": "admin"})

    response = client.get("/protected", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    assert response.json()["email"] == "admin@example.com"


def test_openai_request_key_is_forwarded_without_global_mutation(monkeypatch):
    captured = {}

    async def fake_chat(**kwargs):
        captured.update(kwargs)
        return {"document_count": 0, "documents": []}

    monkeypatch.setattr(llm_client, "chat_with_vision_json", fake_chat)
    before = os.environ.get("OPENAI_API_KEY")

    result = asyncio.run(
        extract_with_provider(
            "gpt-4o-mini",
            "aW1hZ2U=",
            provider_keys={"openai": "request-scoped-key"},
        )
    )

    assert result["success"] is True
    assert captured["api_key"] == "request-scoped-key"
    assert os.environ.get("OPENAI_API_KEY") == before
