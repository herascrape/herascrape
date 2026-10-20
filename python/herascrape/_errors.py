from collections.abc import Callable
from typing import Optional, TypeVar, Union

JSON = Union[str, int, float, bool, None, list["JSON"], dict[str, "JSON"]]


def _summary(
    *, status_code: int, error_code: Optional[str], detail: JSON
) -> str:
    message = detail.get("message") if isinstance(detail, dict) else detail
    head = f"{status_code} {error_code}" if error_code else str(status_code)
    return (
        f"{head}: {message}" if isinstance(message, str) and message else head
    )


_E = TypeVar("_E", bound="HerascrapeAPIError")


def _rebuild(
    error_class: type[_E], args: tuple[object, ...], state: dict[str, object]
) -> _E:
    error = error_class.__new__(error_class, *args)
    error.__dict__.update(state)
    return error


class HerascrapeError(Exception):
    """Base class for every error raised by this client."""


class HerascrapeTransportError(HerascrapeError):
    """No HTTP response was received (connection failure or timeout)."""


class HerascrapeAPIError(HerascrapeError):
    """The API answered with an error status."""

    def __init__(
        self,
        *,
        status_code: int,
        error_code: Optional[str] = None,
        detail: JSON = None,
        request_id: Optional[str] = None,
    ) -> None:
        super().__init__(
            _summary(
                status_code=status_code, error_code=error_code, detail=detail
            )
        )
        self.status_code = status_code
        self.error_code = error_code
        self.detail = detail
        self.request_id = request_id

    def __reduce__(
        self,
    ) -> tuple[Callable[..., "HerascrapeAPIError"], tuple[object, ...]]:
        """Skip the keyword-only `__init__` so pickle and copy work."""
        return _rebuild, (type(self), self.args, self.__dict__)


class BadRequestError(HerascrapeAPIError):
    """400: the request was malformed."""


class InvalidCursorError(BadRequestError):
    """400 invalid_cursor: the pagination cursor is not valid here."""


class InvalidParameterError(BadRequestError):
    """400 invalid_parameter: a query parameter has an unacceptable value."""


class AuthenticationError(HerascrapeAPIError):
    """401: the API key is missing or invalid."""


class ForbiddenError(HerascrapeAPIError):
    """403: the request is not allowed."""


class PrivateAccountError(ForbiddenError):
    """403 private_account: the profile is private."""


class NotFoundError(HerascrapeAPIError):
    """404: the resource does not exist."""


class ProfileNotFoundError(NotFoundError):
    """404 profile_not_found: no such profile."""


class ValidationError(HerascrapeAPIError):
    """422: the request failed validation."""

    @property
    def field_errors(self) -> Optional[dict[str, str]]:
        """Per-field messages from `detail["errors"]`, if the API sent them."""
        if not isinstance(self.detail, dict):
            return None
        errors = self.detail.get("errors")
        if not isinstance(errors, dict):
            return None
        return {field: str(message) for field, message in errors.items()}


class RateLimitError(HerascrapeAPIError):
    """429: too many requests."""

    def __init__(
        self,
        *,
        status_code: int,
        error_code: Optional[str] = None,
        detail: JSON = None,
        request_id: Optional[str] = None,
        retry_after: Optional[float] = None,
    ) -> None:
        super().__init__(
            status_code=status_code,
            error_code=error_code,
            detail=detail,
            request_id=request_id,
        )
        self.retry_after = retry_after


class ServerError(HerascrapeAPIError):
    """5xx: the API failed to process a valid request."""


class InternalError(ServerError):
    """500 internal_error."""


class UpstreamError(ServerError):
    """502 upstream_error: the upstream returned an error."""


class ServiceUnavailableError(ServerError):
    """503 upstream_unavailable: the upstream is temporarily unavailable."""


_BY_CODE: dict[tuple[int, str], type[HerascrapeAPIError]] = {
    (400, "bad_request"): BadRequestError,
    (400, "invalid_cursor"): InvalidCursorError,
    (400, "invalid_parameter"): InvalidParameterError,
    (401, "unauthorized"): AuthenticationError,
    (403, "forbidden"): ForbiddenError,
    (403, "private_account"): PrivateAccountError,
    (404, "not_found"): NotFoundError,
    (404, "profile_not_found"): ProfileNotFoundError,
    (422, "unprocessable_entity"): ValidationError,
    (429, "too_many_requests"): RateLimitError,
    (500, "internal_error"): InternalError,
    (502, "upstream_error"): UpstreamError,
    (503, "upstream_unavailable"): ServiceUnavailableError,
}

_BY_STATUS: dict[int, type[HerascrapeAPIError]] = {
    400: BadRequestError,
    401: AuthenticationError,
    403: ForbiddenError,
    404: NotFoundError,
    422: ValidationError,
    429: RateLimitError,
    500: InternalError,
    502: UpstreamError,
    503: ServiceUnavailableError,
}


def _error_class(
    *, status_code: int, error_code: Optional[str]
) -> type[HerascrapeAPIError]:
    if error_code is not None and (status_code, error_code) in _BY_CODE:
        return _BY_CODE[(status_code, error_code)]
    if status_code in _BY_STATUS:
        return _BY_STATUS[status_code]
    return ServerError if status_code >= 500 else HerascrapeAPIError


def error_from_response(
    *,
    status_code: int,
    error_code: Optional[str],
    detail: JSON,
    request_id: Optional[str],
    retry_after: Optional[float],
) -> HerascrapeAPIError:
    """Map an error response to its exception, falling back by status."""
    error_class = _error_class(status_code=status_code, error_code=error_code)
    if issubclass(error_class, RateLimitError):
        return error_class(
            status_code=status_code,
            error_code=error_code,
            detail=detail,
            request_id=request_id,
            retry_after=retry_after,
        )
    return error_class(
        status_code=status_code,
        error_code=error_code,
        detail=detail,
        request_id=request_id,
    )
