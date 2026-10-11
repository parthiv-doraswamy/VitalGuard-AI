"""Helpers for exercising authenticated demo API endpoints in tests."""
import os


def authenticate_test_client(client) -> str:
    os.environ["VITALGUARD_AUTH_USERNAME"] = "demo-operator"
    os.environ["VITALGUARD_AUTH_PASSWORD"] = "a-long-demo-password"
    os.environ["VITALGUARD_AUTH_SECRET"] = "test-only-secret-that-is-at-least-32-chars"
    response = client.post("/api/v1/auth/login", json={
        "username": "demo-operator",
        "password": "a-long-demo-password",
    })
    assert response.status_code == 200, response.text
    token = response.json()["access_token"]
    client.headers.update({"Authorization": f"Bearer {token}"})
    return token
