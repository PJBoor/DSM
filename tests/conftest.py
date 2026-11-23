import os
import tempfile

_tmp = tempfile.mkdtemp(prefix="holistic_test_")
os.environ["DATABASE_URL"] = f"sqlite:///{_tmp}/test.db"
os.environ["SECRET_KEY"] = "test-secret-key-0123456789abcdef0123456789abcd"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.database import Base, SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.models import User  # noqa: E402
from app.security import hash_password  # noqa: E402

Base.metadata.create_all(bind=engine)

PASSWORD = "Password123!"


@pytest.fixture(scope="session", autouse=True)
def seed_users():
    with SessionLocal() as db:
        if db.query(User).first() is None:
            db.add_all(
                [
                    User(email="admin@holistic.local", hashed_password=hash_password(PASSWORD), role="admin"),
                    User(email="strategist@holistic.local", hashed_password=hash_password(PASSWORD), role="strategist"),
                    User(email="contributor@holistic.local", hashed_password=hash_password(PASSWORD), role="contributor"),
                    User(email="reader@holistic.local", hashed_password=hash_password(PASSWORD), role="reader"),
                ]
            )
            db.commit()


@pytest.fixture(scope="session")
def client():
    with TestClient(app) as c:
        yield c


def _headers(client, email):
    r = client.post("/auth/token", data={"username": email, "password": PASSWORD})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.fixture(scope="session")
def admin(client):
    return _headers(client, "admin@holistic.local")


@pytest.fixture(scope="session")
def strategist(client):
    return _headers(client, "strategist@holistic.local")


@pytest.fixture(scope="session")
def contributor(client):
    return _headers(client, "contributor@holistic.local")


@pytest.fixture(scope="session")
def reader(client):
    return _headers(client, "reader@holistic.local")


@pytest.fixture()
def db_session():
    with SessionLocal() as db:
        yield db
