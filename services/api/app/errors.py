"""Domain errors and how they become HTTP responses."""

from __future__ import annotations

from api import ErrorBody, ErrorCode
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

__all__ = ("ERROR_RESPONSES", "ApiError", "install_error_handlers")

_STATUS: dict[ErrorCode, int] = {
	ErrorCode.INVALID_REQUEST: 422,
	ErrorCode.UNAUTHORIZED: 401,
	ErrorCode.FORBIDDEN: 403,
	ErrorCode.NOT_FOUND: 404,
	ErrorCode.BLACKLISTED: 403,
	ErrorCode.INSUFFICIENT_FUNDS: 409,
	ErrorCode.SAME_ACCOUNT: 422,
	ErrorCode.INVALID_CHANNEL: 422,
	ErrorCode.INVALID_EMOJI: 422,
	ErrorCode.STARBOARD_LIMIT: 409,
	ErrorCode.STARBOARD_NAME_TAKEN: 409,
	ErrorCode.STARBOARD_TIER_TAKEN: 409,
	ErrorCode.SHOP_LIMIT: 409,
	ErrorCode.SHOP_ITEM_TAKEN: 409,
	ErrorCode.GIVEAWAY_LIMIT: 409,
	ErrorCode.ALERT_LIMIT: 409,
	ErrorCode.RATE_LIMITED: 429,
	ErrorCode.DISCORD_UNAVAILABLE: 502,
}

ERROR_RESPONSES: dict[int | str, dict[str, object]] = {
	"4XX": {"model": ErrorBody, "description": "The request failed. `code` says why."},
	"5XX": {"model": ErrorBody, "description": "The API or Discord failed."},
}
"""The error responses declared in the OpenAPI schema."""


class ApiError(Exception):
	"""A request failure, rendered as an `ErrorBody`.

	Args:
		code: Why the request failed. Decides the HTTP status.
		message: A human-readable detail. Defaults to the code in words.
		headers: Extra response headers, e.g. ``Retry-After``.
	"""

	def __init__(self, code: ErrorCode, message: str | None = None, headers: dict[str, str] | None = None) -> None:
		super().__init__(message or code.value)
		self.code = code
		self.message = message or code.value.replace("_", " ")
		self.headers = headers or {}

	@property
	def status(self) -> int:
		"""The HTTP status for the code."""
		return _STATUS[self.code]


def _body(code: ErrorCode, message: str, status: int, headers: dict[str, str] | None = None) -> JSONResponse:
	"""Build an `ErrorBody` response.

	Args:
		code: The error code.
		message: The error message.
		status: The HTTP status.
		headers: Extra response headers.

	Returns:
		The response.
	"""
	return JSONResponse(ErrorBody(code=code, message=message).model_dump(mode="json"), status, headers=headers)


def install_error_handlers(app: FastAPI) -> None:
	"""Render every error, including FastAPI's own, as an `ErrorBody`.

	Args:
		app: The app to install the handlers on.
	"""

	@app.exception_handler(ApiError)
	async def _api_error(_: Request, exc: ApiError) -> JSONResponse:
		"""Render an `ApiError`.

		Args:
			exc: The error.

		Returns:
			The error response, with ``WWW-Authenticate`` for ``unauthorized`` and the error's own headers.
		"""
		headers = {"WWW-Authenticate": "Bearer"} if exc.code is ErrorCode.UNAUTHORIZED else {}
		return _body(exc.code, exc.message, exc.status, headers | exc.headers or None)

	@app.exception_handler(RequestValidationError)
	async def _validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
		"""Render a request validation failure as ``invalid_request``.

		Args:
			exc: The validation error.

		Returns:
			The error response.
		"""
		details = "; ".join(f"{'.'.join(str(p) for p in e['loc'])}: {e['msg']}" for e in exc.errors())
		return _body(ErrorCode.INVALID_REQUEST, details or "invalid request", 422)

	@app.exception_handler(StarletteHTTPException)
	async def _http_error(_: Request, exc: StarletteHTTPException) -> JSONResponse:
		"""Render a Starlette HTTP error, such as an unknown route.

		Args:
			exc: The HTTP error.

		Returns:
			The error response.
		"""
		code = {401: ErrorCode.UNAUTHORIZED, 403: ErrorCode.FORBIDDEN, 404: ErrorCode.NOT_FOUND}.get(
			exc.status_code, ErrorCode.INVALID_REQUEST
		)
		return _body(code, str(exc.detail), exc.status_code)
