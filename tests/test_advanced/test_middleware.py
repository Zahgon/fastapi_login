import pytest
from flask import g

from fastapi_login import LoginManager
from fastapi_login.exceptions import InvalidCredentialsException


@pytest.fixture(scope="module")
def middleware_manager(app, token_url, load_user_fn):
    instance = LoginManager("secret", "/auth/token")
    instance.user_loader()(load_user_fn)
    instance.attach_middleware(app)

    @app.get("/private/request")
    def private_request_route():
        user = g.user
        if user is None:
            raise InvalidCredentialsException
        else:
            return {"detail": "Success"}

    return instance


def test_middleware_unauthorized(middleware_manager, client):
    resp = client.get("/private/request")

    assert resp.status_code == 401
    assert resp.get_json()["detail"] == InvalidCredentialsException.detail


def test_middleware_authorized(middleware_manager, client, default_data):
    token = middleware_manager.create_access_token(data=default_data)
    resp = client.get(
        "/private/request", headers={"Authorization": f"Bearer {token}"}
    )

    assert resp.status_code == 200
    assert resp.get_json()["detail"] == "Success"
