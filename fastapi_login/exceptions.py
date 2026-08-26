import json
from http import HTTPStatus
from typing import Dict, Optional

from werkzeug.exceptions import HTTPException
from werkzeug.wrappers import Response

# Reference: https://datatracker.ietf.org/doc/html/rfc6749#section-5.2


class HTTPExceptionJSON(HTTPException):
    """
    A werkzeug ``HTTPException`` that renders a JSON body ``{"detail": ...}``.

    It carries a status code, a ``detail`` message and optional headers
    (e.g. ``WWW-Authenticate``). Flask turns any raised
    ``werkzeug.exceptions.HTTPException`` into a response by calling
    :meth:`get_response`.
    """

    def __init__(
        self,
        status_code: int,
        detail: str,
        headers: Optional[Dict[str, str]] = None,
    ):
        super().__init__(description=detail)
        self.code = int(status_code)
        self.detail = detail
        self.extra_headers = headers or {}

    def get_response(self, environ=None, scope=None) -> Response:
        response = Response(
            json.dumps({"detail": self.detail}),
            status=self.code,
            content_type="application/json",
        )
        for key, value in self.extra_headers.items():
            response.headers[key] = value
        return response


InvalidCredentialsException = HTTPExceptionJSON(
    status_code=HTTPStatus.UNAUTHORIZED,
    detail="Invalid credentials",
    headers={"WWW-Authenticate": "Bearer"},
)

InsufficientScopeException = HTTPExceptionJSON(
    status_code=HTTPStatus.BAD_REQUEST,
    detail="Insufficient scope",
    headers={"WWW-Authenticate": "Bearer"},
)
