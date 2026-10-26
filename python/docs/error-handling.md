---
myst:
  html_meta:
    description: "The herascrape Python client exception hierarchy: typed errors per HTTP status and error code, request ids, field errors, and what to catch."
---

# Error handling

Every exception the client raises inherits from
{class}`~herascrape.HerascrapeError`, so one `except` clause can be the
backstop. Below it the tree splits in two: a response arrived with an error
status, or no response arrived at all.

```text
HerascrapeError
├── HerascrapeTransportError      no response: connection failure or timeout
└── HerascrapeAPIError            an error status, with status_code/error_code
    ├── BadRequestError                  400
    │   ├── InvalidCursorError           400 invalid_cursor
    │   └── InvalidParameterError        400 invalid_parameter
    ├── AuthenticationError              401
    ├── ForbiddenError                   403
    │   └── PrivateAccountError          403 private_account
    ├── NotFoundError                    404
    │   └── ProfileNotFoundError         404 profile_not_found
    ├── ValidationError                  422
    ├── RateLimitError                   429
    └── ServerError                      5xx
        ├── InternalError                500
        ├── UpstreamError                502
        └── ServiceUnavailableError      503
```

The subclasses exist so the common cases are catchable on their own. A private
profile and an unknown profile are the two you will meet most:

```python
from herascrape import (
    Client,
    HerascrapeError,
    PrivateAccountError,
    ProfileNotFoundError,
    RateLimitError,
)

client = Client()

try:
    page = client.user_followers("25025320")
except PrivateAccountError:
    ...  # the profile is private; nothing to read
except ProfileNotFoundError:
    ...  # no such profile, or it was deleted
except RateLimitError as exc:
    ...  # still limited after the client's own retries
    print(exc.retry_after)
except HerascrapeError as exc:
    print(f"request failed: {exc}")
```

Catching a base class catches its subclasses, so order the clauses from
specific to general. `except NotFoundError` also catches
`ProfileNotFoundError`.

## What is on an error

{class}`~herascrape.HerascrapeAPIError` carries the response:

| Attribute | Value |
| --- | --- |
| `status_code` | The HTTP status. |
| `error_code` | The API's machine-readable code, such as `private_account`. `None` if the body had none. |
| `detail` | The decoded error body. |
| `request_id` | The `x-request-id` header. Quote it in a support request. |

Two subclasses add one attribute each:

- {class}`~herascrape.RateLimitError` has `retry_after`, the seconds from the
  `Retry-After` header, or `None` when the response did not send one.
- {class}`~herascrape.ValidationError` has `field_errors`, a
  `dict[str, str]` of per-field messages when the 422 body carried them, and
  `None` otherwise.

```python
from herascrape import ValidationError

try:
    page = client.user_reels(user_id)
except ValidationError as exc:
    print(exc.field_errors)  # {"user_id": "..."} or None
```

The string form of an error is `"<status> <error_code>: <message>"`, so logging
the exception is usually enough to identify what happened.

## What is not an exception

An empty result is not an error. A profile with no live stories answers `200`
with an empty list, and a list endpoint with nothing to return answers `200`
with empty `items`. Check the payload, not for an exception.

## Retries happen first

Transient failures are retried inside the client before anything is raised, so
an exception that reaches you has already survived `max_retries` attempts. See
[Retries and rate limits](rate-limits.md) for which statuses are retried and
how long the waits are.
