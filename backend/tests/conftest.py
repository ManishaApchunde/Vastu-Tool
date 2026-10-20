import os
import tempfile

_tmp = tempfile.mkdtemp(prefix="vastu-test-")
os.environ.update({
    "ENVIRONMENT": "test", "DATABASE_URL": f"sqlite:///{_tmp}/test.db", "LOCAL_STORAGE_DIR": f"{_tmp}/storage",
    "AI_PROVIDER": "mock", "JOB_MODE": "inline", "AUTO_SEED": "true", "SECRET_KEY": "test-secret",
    "VIDEO_TTS": "silent",
})

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402


@pytest.fixture(scope="session")
def client():
    with TestClient(app) as c:
        yield c


def _register(client, email):
    r = client.post("/auth/register", json={"email": email, "password": "password123", "full_name": "T"})
    assert r.status_code == 201, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.fixture
def auth(client):
    import uuid

    return _register(client, f"u{uuid.uuid4().hex[:8]}@example.com")


@pytest.fixture
def other_auth(client):
    import uuid

    return _register(client, f"o{uuid.uuid4().hex[:8]}@example.com")
