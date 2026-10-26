---
myst:
  html_meta:
    description: "How the herascrape Python client retries transient failures with exponential backoff and throttles requests with a client-side token bucket."
---

# Retries and rate limits

## What is retried

A failed request is retried up to `max_retries` times (3 by default) when the
failure is one that usually clears on its own:

| Failure | Why it is retried |
| --- | --- |
| `HerascrapeTransportError` | Connection failure or timeout, so no response arrived. |
| `429` | Too many requests. The wait honours `Retry-After` when the response sends one. |
| `502` `UpstreamError` | Instagram answered the service with an error. |
| `503` `ServiceUnavailableError` | The upstream is briefly unavailable. |
| `400 invalid_cursor` | Instagram rejects a cursor intermittently; the same cursor usually works on the next attempt. |

Everything else is raised on the first attempt. A `401`, `403`, `404` or `422`
will not change by being asked again, and a `500` is not treated as transient.

Waits double from 0.5 s to a cap of 8 s, then lose up to half their length to
jitter, so concurrent clients do not retry in lockstep. A `429` that carries
`Retry-After` waits for that long instead, capped at 300 s.

When the retries are used up the last exception is raised. It is the real one,
not a wrapper, so `except RateLimitError` still catches a 429 that never
cleared.

```python
client = Client(max_retries=0)   # raise immediately, retry in your own code
client = Client(max_retries=8)   # ride out a longer upstream outage
```

Retried requests that eventually fail are not billed, since only successful
calls are.

## Client-side rate limit

Requests are also throttled before they are sent, by a token bucket that holds
`rate` tokens and starts full. The default is 50 requests per second, which
mirrors the per-key server limit, so steady use does not trip a server-side
`429`. The bucket is shared across threads and across tasks on one client, so
a pool of workers sharing a client shares one budget.

```python
from herascrape import Client, RateLimit

# 10 per second
Client(rate_limit=RateLimit(rate=10, period="s"))

# 1000 per hour
Client(rate_limit=RateLimit(rate=1000, period_length=1, period="h"))

# no client-side limit, the server's is the only one left
Client(rate_limit=None)
```

`period` is one of `"s"`, `"m"`, `"h"`, `"d"`, and `period_length` multiplies
it. `RateLimit(rate=600, period_length=5, period="m")` is 600 requests per
five minutes.

Lower the rate if you run several clients against one key, because each client
has its own bucket and the server sees their sum. Raise it only to match what
your key is actually allowed.

The limiter delays requests, it never drops them. `Client` blocks the calling
thread while it waits, `AsyncClient` awaits without blocking the event loop.
