import logging

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse


logger = logging.getLogger(__name__)


class DomainException(Exception):
    status_code: int = 500
    code: str = "internal_error"

    def __init__(self, message: str, **details):
        super().__init__(message)
        self.message = message
        self.details = details


class InvalidCredentials(DomainException):
    status_code = 401
    code = "invalid_credentials"

    def __init__(self):
        super().__init__("Invalid email or password")


class InvalidToken(DomainException):
    status_code = 401
    code = "invalid_token"

    def __init__(self, reason: str = "Invalid token"):
        super().__init__(reason)


class TokenExpired(DomainException):
    status_code = 401
    code = "token_expired"

    def __init__(self):
        super().__init__("Token expired")


class MissingAuth(DomainException):
    status_code = 401
    code = "missing_auth"

    def __init__(self):
        super().__init__("Missing authentication")


class UserNotFound(DomainException):
    status_code = 404
    code = "user_not_found"

    def __init__(self, user_id):
        super().__init__(f"User {user_id} not found", user_id=user_id)


class EmailAlreadyExists(DomainException):
    status_code = 409
    code = "email_already_exists"

    def __init__(self, email: str):
        super().__init__(f"Email {email} already registered", email=email)


class QuotaExceeded(DomainException):
    status_code = 403
    code = "quota_exceeded"


class RateLimited(DomainException):
    status_code = 429
    code = "rate_limited"

    def __init__(self, retry_after: int):
        super().__init__(
            f"Rate limit exceeded. Try again in {retry_after} seconds.",
            retry_after=retry_after,
        )
        self.retry_after = retry_after


async def domain_exception_handler(request: Request, exc: DomainException) -> JSONResponse:
    headers = {}
    if isinstance(exc, RateLimited):
        headers["Retry-After"] = str(exc.retry_after)
    return JSONResponse(
        status_code=exc.status_code,
        headers=headers,
        content={
            "error": {
                "code": exc.code,
                "message": exc.message,
                "details": exc.details,
            }
        },
    )


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled exception", exc_info=exc)
    return JSONResponse(
        status_code=500,
        content={
            "error": {
                "code": "internal_error",
                "message": "An unexpected error occurred.",
                "details": {},
            }
        },
    )


def register_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(DomainException, domain_exception_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)