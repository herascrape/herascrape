from typing import Optional

import pytest

from herascrape._errors import (
    JSON,
    AuthenticationError,
    BadRequestError,
    ForbiddenError,
    HerascrapeAPIError,
    HerascrapeError,
    HerascrapeTransportError,
    InternalError,
    InvalidCursorError,
    InvalidParameterError,
    NotFoundError,
    PrivateAccountError,
    ProfileNotFoundError,
    RateLimitError,
    ServerError,
    ServiceUnavailableError,
    UpstreamError,
    ValidationError,
    error_from_response,
)


def _map(
    *,
    status_code: int,
    error_code: Optional[str] = None,
    detail: JSON = "",
    request_id: Optional[str] = None,
    retry_after: Optional[float] = None,
) -> HerascrapeAPIError:
    return error_from_response(
        status_code=status_code,
        error_code=error_code,
        detail=detail,
        request_id=request_id,
        retry_after=retry_after,
    )


def test_maps_private_account():
    e = _map(
        status_code=403,
        error_code="private_account",
        detail="x",
        request_id="r1",
    )
    assert isinstance(e, PrivateAccountError) and e.request_id == "r1"


def test_profile_not_found_is_notfound_subclass():
    assert issubclass(ProfileNotFoundError, NotFoundError)


def test_invalid_cursor_maps():
    assert isinstance(
        _map(status_code=400, error_code="invalid_cursor"), InvalidCursorError
    )


def test_rate_limit_carries_retry_after():
    e = _map(status_code=429, error_code="too_many_requests", retry_after=4.0)
    assert isinstance(e, RateLimitError) and e.retry_after == 4.0


def test_validation_dict_detail_exposes_errors():
    e = _map(
        status_code=422,
        error_code="unprocessable_entity",
        detail={"message": "bad", "errors": {"query": "required"}},
    )
    assert isinstance(e, ValidationError) and e.field_errors == {
        "query": "required"
    }


def test_validation_string_detail_no_crash():
    e = _map(
        status_code=422,
        error_code="unprocessable_entity",
        detail="Invalid request data",
    )
    assert isinstance(e, ValidationError) and e.field_errors is None


def test_validation_dict_detail_without_errors_key():
    e = _map(
        status_code=422,
        error_code="unprocessable_entity",
        detail={"message": "bad"},
    )
    assert isinstance(e, ValidationError) and e.field_errors is None


def test_validation_non_dict_errors_value_is_ignored():
    e = _map(
        status_code=422,
        error_code="unprocessable_entity",
        detail={"errors": ["query"]},
    )
    assert isinstance(e, ValidationError) and e.field_errors is None


def test_unknown_code_falls_back():
    e = _map(status_code=418, detail=None)
    assert type(e) is HerascrapeAPIError and e.status_code == 418


def test_5xx_mapping():
    e = _map(status_code=503, error_code="upstream_unavailable")
    assert isinstance(e, ServiceUnavailableError)


@pytest.mark.parametrize(
    ("status_code", "error_code", "expected"),
    [
        (400, "bad_request", BadRequestError),
        (400, "invalid_cursor", InvalidCursorError),
        (400, "invalid_parameter", InvalidParameterError),
        (401, "unauthorized", AuthenticationError),
        (403, "forbidden", ForbiddenError),
        (403, "private_account", PrivateAccountError),
        (404, "not_found", NotFoundError),
        (404, "profile_not_found", ProfileNotFoundError),
        (422, "unprocessable_entity", ValidationError),
        (429, "too_many_requests", RateLimitError),
        (500, "internal_error", InternalError),
        (502, "upstream_error", UpstreamError),
        (503, "upstream_unavailable", ServiceUnavailableError),
    ],
)
def test_catalog_maps_to_exact_class(
    status_code: int, error_code: str, expected: type[HerascrapeAPIError]
):
    assert (
        type(_map(status_code=status_code, error_code=error_code)) is expected
    )


@pytest.mark.parametrize(
    ("status_code", "expected"),
    [
        (400, BadRequestError),
        (401, AuthenticationError),
        (403, ForbiddenError),
        (404, NotFoundError),
        (422, ValidationError),
        (429, RateLimitError),
        (500, ServerError),
        (504, ServerError),
    ],
)
def test_unknown_code_falls_back_by_status(
    status_code: int, expected: type[HerascrapeAPIError]
):
    assert (
        type(_map(status_code=status_code, error_code="something_new"))
        is expected
    )


def test_code_under_wrong_status_falls_back_by_status():
    assert (
        type(_map(status_code=404, error_code="private_account"))
        is NotFoundError
    )


def test_hierarchy_roots():
    assert issubclass(HerascrapeAPIError, HerascrapeError)
    assert issubclass(HerascrapeTransportError, HerascrapeError)
    assert not issubclass(HerascrapeTransportError, HerascrapeAPIError)


def test_bad_request_family_shares_parent():
    assert issubclass(InvalidCursorError, BadRequestError)
    assert issubclass(InvalidParameterError, BadRequestError)


def test_server_family_shares_parent():
    assert issubclass(InternalError, ServerError)
    assert issubclass(UpstreamError, ServerError)
    assert issubclass(ServiceUnavailableError, ServerError)


def test_attributes_and_message():
    e = _map(
        status_code=404,
        error_code="profile_not_found",
        detail={"message": "No such user"},
        request_id="r2",
    )
    assert (e.status_code, e.error_code, e.detail, e.request_id) == (
        404,
        "profile_not_found",
        {"message": "No such user"},
        "r2",
    )
    assert str(e) == "404 profile_not_found: No such user"


def test_message_without_code_or_detail():
    assert str(_map(status_code=418, detail=None)) == "418"
