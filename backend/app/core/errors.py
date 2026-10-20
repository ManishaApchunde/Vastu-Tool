"""Uniform, user-facing error model. Every error returns {"error": {code, message, hint}}."""
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException


class AppError(Exception):
    def __init__(self, code: str, message: str, status_code: int = 400, hint: str | None = None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code
        self.hint = hint


class NotFound(AppError):
    def __init__(self, what: str = "Resource"):
        super().__init__("not_found", f"{what} not found.", 404)


class Conflict(AppError):
    def __init__(self, code: str, message: str, hint: str | None = None):
        super().__init__(code, message, 409, hint)


def _body(code: str, message: str, hint: str | None = None, details=None) -> dict:
    err = {"code": code, "message": message}
    if hint:
        err["hint"] = hint
    if details is not None:
        err["details"] = details
    return {"error": err}


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _app_error(_: Request, exc: AppError):
        return JSONResponse(_body(exc.code, exc.message, exc.hint), status_code=exc.status_code)

    @app.exception_handler(RequestValidationError)
    async def _validation(_: Request, exc: RequestValidationError):
        details = [
            {"field": ".".join(str(p) for p in e.get("loc", [])[1:]), "message": e.get("msg")}
            for e in exc.errors()
        ]
        return JSONResponse(
            _body("invalid_input", "Some fields are missing or invalid.", details=details), status_code=422
        )

    @app.exception_handler(StarletteHTTPException)
    async def _http(_: Request, exc: StarletteHTTPException):
        code = {401: "unauthorized", 403: "forbidden", 404: "not_found", 405: "method_not_allowed"}.get(
            exc.status_code, "http_error"
        )
        return JSONResponse(_body(code, str(exc.detail)), status_code=exc.status_code)
