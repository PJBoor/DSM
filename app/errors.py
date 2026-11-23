from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from .i18n import normalize_locale, t


class AppError(Exception):
    def __init__(self, code: str, status_code: int = 400, **params):
        super().__init__(code)
        self.code = code
        self.status_code = status_code
        self.params = params


def _error_response(request: Request, status_code: int, code: str, **params) -> JSONResponse:
    locale = normalize_locale(request.headers.get("accept-language"))
    return JSONResponse(
        status_code=status_code,
        content={"error": {"code": code, "message": t(code, locale, **params)}},
    )


def register_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
        return _error_response(request, exc.status_code, exc.code, **exc.params)

    @app.exception_handler(RequestValidationError)
    async def validation_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
        return _error_response(request, 422, "error.validation")

    @app.exception_handler(StarletteHTTPException)
    async def http_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        code_map = {401: "error.unauthorized", 403: "error.forbidden", 404: "error.not_found"}
        code = code_map.get(exc.status_code, "error.not_found")
        params = {"resource": "", "id": ""} if code == "error.not_found" else {}
        return _error_response(request, exc.status_code, code, **params)
