from unittest.mock import Mock

import pytest
from flask import jsonify, redirect

from fastapi_login import LoginManager
from fastapi_login.exceptions import InvalidCredentialsException


@pytest.fixture
def exception_manager(
    app, secret, token_url, load_user_fn, auth_exception, scope_exception
) -> LoginManager:
    # ``app`` is module scoped while this fixture is function scoped, so the
    # body runs once per test. Flask (unlike Starlette) refuses to register the
    # same endpoint twice, so register the routes/handlers a single time per app
    # and reuse the manager on subsequent invocations. The configuration is
    # identical across invocations, so the cached instance is equivalent.
    existing = getattr(app, "_exception_manager", None)
    if existing is not None:
        return existing

    instance = LoginManager(
        secret,
        token_url,
        not_authenticated_exception=auth_exception,
        out_of_scope_exception=scope_exception,
    )
    instance.user_loader()(load_user_fn)

    # exception handling setup

    @app.errorhandler(auth_exception)
    def redirect_on_auth_exc(exc):
        return redirect("/redirect")

    @app.errorhandler(scope_exception)
    def redirect_on_scope_exc(exc):
        return jsonify(
            {"error": "invalid_scope", "error_description": "scope exception"}
        )

    # routes
    # Should raise the custom exception when encountering
    # a non-authenticated user and redirect
    @app.get("/private/exception")
    @instance.login_required
    def raise_exception():
        return {"detail": "error"}

    @app.get("/redirect")
    def redirect_view():
        return {"detail": "Redirected"}

    @app.get("/scope")
    @instance.login_required(scopes=["write"])
    def scope():
        raise NotImplementedError

    app._exception_manager = instance
    return instance


def test_out_of_scope_exception(exception_manager, client, default_data):
    token = exception_manager.create_access_token(data=default_data, scopes=["read"])
    resp = client.get("/scope", headers={"Authorization": f"Bearer {token}"})
    assert resp.get_json()["error"] == "invalid_scope"


def test_exception_call_cookie_error_user_header_false(clean_manager):
    # setup clean_manager
    clean_manager.use_cookie = True
    clean_manager.use_header = False
    response = Mock(cookies={})
    with pytest.raises(
        Exception
    ) as exc_info:  # HTTPExceptions cannot be used with pytest.raises
        clean_manager(response)

    assert exc_info.value is InvalidCredentialsException


def test_exception_call_raises_no_token_auto_error_off(clean_manager):
    clean_manager.auto_error = False
    # set headers so the framework internals dont raise an error
    response = Mock(headers={"abc": "abc"})
    with pytest.raises(
        Exception
    ) as exc_info:  # HTTPExceptions cannot be used with pytest.raises
        clean_manager(response)

    assert exc_info.value is InvalidCredentialsException


def test_exception_handling(exception_manager, client, invalid_data):
    invalid_token = exception_manager.create_access_token(
        data={"sub": invalid_data["username"]}
    )
    resp = client.get(
        "/private/exception",
        headers={"Authorization": f"Bearer {invalid_token}"},
        follow_redirects=True,
    )
    assert resp.get_json()["detail"] == "Redirected"


def test_exception_handling_with_no_token(
    exception_manager, client, invalid_data
):
    # Set use cookie true for this test to check all possible ways to raise an error
    exception_manager.use_cookie = True
    resp = client.get("/private/exception", follow_redirects=True)
    assert resp.get_json()["detail"] == "Redirected"


def test_exception_changes_no_sub(exception_manager, auth_exception):
    no_sub_token = exception_manager.create_access_token(data={"id": "something"})
    with pytest.raises(auth_exception):
        exception_manager.get_current_user(no_sub_token)


def test_exception_changes_invalid_token(exception_manager, auth_exception):
    invalid_jwt_token = (
        "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.aGVsb"
        "G8gd29ybGQ.SIr03zM64awWRdPrAM_61QWsZchAtgDV"
        "3pphfHPPWkI"
    )  # this token is taken from pyjwt (https://github.com/jpadilla/pyjwt/blob/master/tests/test_api_jwt.py#L82)
    with pytest.raises(auth_exception):
        exception_manager.get_current_user(invalid_jwt_token)


def test_exception_changes_user_is_none(
    exception_manager, auth_exception, invalid_data
):
    invalid_user_token = exception_manager.create_access_token(
        data={"sub": invalid_data["username"]}
    )
    with pytest.raises(auth_exception):
        exception_manager.get_current_user(invalid_user_token)
