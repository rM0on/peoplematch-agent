from typing import Any, Optional

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.logging import get_logger
from app.middleware.request_id import get_request_id
from app.schemas.common import ApiError, ApiResponse
from app.exceptions import DomainError


logger = get_logger("api.errors")


def _error_response(
    request: Request,
    *,
    status_code: int,
    code: str,
    message: str,
    details: Optional[Any] = None,
) -> JSONResponse:
    request_id = get_request_id(request)
    payload = ApiResponse[Any](
        success=False,
        data=None,
        error=ApiError(code=code, message=message, details=details),
        request_id=request_id,
    )
    return JSONResponse(
        status_code=status_code,
        content=jsonable_encoder(payload),
        headers={"X-Request-ID": request_id},
    )


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(DomainError)
    async def handle_domain_exception(
        request: Request,
        exception: DomainError,
    ) -> JSONResponse:
        return _error_response(
            request,
            status_code=exception.status_code,
            code=exception.code,
            message=str(exception),
        )

    @app.exception_handler(StarletteHTTPException)
    async def handle_http_exception(
        request: Request,
        exception: StarletteHTTPException,
    ) -> JSONResponse:
        code = "not_found" if exception.status_code == 404 else "http_error"
        return _error_response(
            request,
            status_code=exception.status_code,
            code=code,
            message=str(exception.detail),
        )

    @app.exception_handler(RequestValidationError)
    async def handle_validation_exception(
        request: Request,
        exception: RequestValidationError,
    ) -> JSONResponse:
        safe_details = [
            {key: value for key, value in error.items() if key not in {"input", "ctx"}}
            for error in exception.errors()
        ]
        return _error_response(
            request,
            status_code=422,
            code="validation_error",
            message="Request validation failed",
            details=jsonable_encoder(safe_details),
        )

    @app.exception_handler(Exception)
    async def handle_unexpected_exception(
        request: Request,
        exception: Exception,
    ) -> JSONResponse:
        logger.exception(
            "Unhandled application exception",
            extra={"request_id": get_request_id(request)},
        )
        return _error_response(
            request,
            status_code=500,
            code="internal_error",
            message="Internal server error",
        )
