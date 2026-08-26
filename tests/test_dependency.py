import pytest
from flask import request
from pytest_lazy_fixtures import lf

from fastapi_login import LoginManager


@pytest.fixture(scope="module", autouse=True)
def _register_all_routes(
    header_manager, cookie_manager, cookie_header_manager, scoped_manager
):
    # Flask locks route registration once the app has handled its first
    # request (Flask's @setupmethod guard). FastAPI/Starlette allowed routes
    # to be added dynamically after startup, so the original module-scoped
    # manager fixtures could register their routes lazily on first use. Under
    # Flask every route must be registered during module setup, before any
    # test issues a request. Depending on all four manager fixtures here
    # forces them to run (and register their routes) up front.
    yield


@pytest.fixture(scope="module")
def header_manager(app, secret, token_url, load_user_fn) -> LoginManager:
    instance = LoginManager(secret, token_url)
    instance.user_loader()(load_user_fn)

    @app.get("/private/header")
    @instance.login_required
    def private_header_route():
        return {"detail": "Success"}

    return instance


@pytest.fixture(scope="module")
def cookie_manager(app, secret, token_url, load_user_fn) -> LoginManager:
    instance = LoginManager(secret, token_url, use_cookie=True, use_header=False)
    instance.user_loader()(load_user_fn)

    @app.get("/private/cookie")
    @instance.login_required
    def private_cookie_route():
        return {"detail": "Success"}

    return instance


@pytest.fixture(scope="module")
def cookie_header_manager(app, secret, token_url, load_user_fn) -> LoginManager:
    instance = LoginManager(secret, token_url, use_cookie=True)
    instance.user_loader()(load_user_fn)

    @app.get("/private/both")
    @instance.login_required
    def private_route():
        return {"detail": "Success"}

    @app.get("/private/optional")
    def optional_user_route():
        user = instance.optional()
        invalid = request.args.get("invalid", 0, type=int)
        if user is None and invalid == 1:
            return {"detail": "Success"}
        elif user is not None and invalid == 0:
            return {"detail": "Success"}
        else:
            return {"detail": "Error"}

    return instance


@pytest.fixture(scope="module")
def scoped_manager(app, secret, token_url, load_user_fn) -> LoginManager:
    instance = LoginManager(secret, token_url)
    instance.user_loader()(load_user_fn)

    @app.get("/private/scoped")
    @instance.login_required(scopes=["read"])
    def private_scoped_route():
        return {"detail": "Success"}

    return instance


def test_header_dependency(client, header_manager, default_data):
    token = header_manager.create_access_token(data=default_data)
    resp = client.get(
        "/private/header", headers={"Authorization": f"Bearer {token}"}
    )

    assert resp.status_code == 200
    assert resp.get_json()["detail"] == "Success"


def test_cookie_dependency(client, cookie_manager, default_data):
    token = cookie_manager.create_access_token(data=default_data)
    client.set_cookie(cookie_manager.cookie_name, token)
    resp = client.get("/private/cookie")
    client.delete_cookie(cookie_manager.cookie_name)

    assert resp.status_code == 200
    assert resp.get_json()["detail"] == "Success"


def test_cookie_header_fallback(client, cookie_header_manager, default_data):
    token = cookie_header_manager.create_access_token(data=default_data)
    client.delete_cookie(cookie_header_manager.cookie_name)
    resp = client.get(
        "/private/both", headers={"Authorization": f"Bearer {token}"}
    )

    # even tough no valid access cookie is present,
    # as use_header is enabled the request is valid
    assert resp.status_code == 200
    assert resp.get_json()["detail"] == "Success"


def test_scoped_dependency(client, scoped_manager, default_data):
    token = scoped_manager.create_access_token(data=default_data, scopes=["read"])
    resp = client.get(
        "/private/scoped", headers={"Authorization": f"Bearer {token}"}
    )

    assert resp.status_code == 200
    assert resp.get_json()["detail"] == "Success"


def test_scoped_dependency_raises(client, scoped_manager, default_data):
    token = scoped_manager.create_access_token(data=default_data)
    resp = client.get(
        "/private/scoped", headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 400


@pytest.mark.parametrize(
    "data, is_invalid",
    [(lf("default_data"), 0), (lf("invalid_data"), 1)],
)
def test_optional_dependency(client, cookie_header_manager, data, is_invalid):
    token = cookie_header_manager.create_access_token(data=data)
    resp = client.get(
        "/private/optional",
        headers={"Authorization": f"Bearer {token}"},
        query_string={"invalid": is_invalid},
    )

    assert resp.status_code == 200
    assert resp.get_json()["detail"] == "Success"
