# herascrape: Instagram API client for Python

`herascrape` is the official Python client for
[herascrape](https://herascrape.com/?utm_source=pypi&utm_medium=readme&utm_campaign=herascrape), a hosted Instagram scraper API. It reads
Instagram's private API for you and hands back Instagram's own JSON: profiles,
followers, posts, reels, comments, hashtags, locations, audio, stories and
search. You do not manage the accounts, devices or proxies.

```python
from herascrape import Client

client = Client(api_key="hs_live_xxxxxxxx")

user = client.user_by_username(username="instagram")
print(user["username"], user["follower_count"])

for follower in client.iter_user_followers(user["pk"], max_items=100):
    print(follower["username"])
```

- 37 endpoints, one method each, plus lazy `iter_*` paginators for the lists.
- Sync (`Client`) and async (`AsyncClient`) with the same surface.
- Typed exception hierarchy: `NotFoundError`, `PrivateAccountError`,
  `RateLimitError` and the rest.
- Retries with backoff, `Retry-After` handling and a client-side rate limiter.
- Typed package (`py.typed`), Python 3.10+, one dependency: `httpx`.

Documentation: [herascrape.com/docs](https://herascrape.com/docs?utm_source=pypi&utm_medium=readme&utm_campaign=herascrape) for the
API, [herascrape.readthedocs.io](https://herascrape.readthedocs.io/) for
this library's reference.

## Install

```bash
pip install herascrape
```

## Authentication

Create a key in the [dashboard](https://herascrape.com/api-keys?utm_source=pypi&utm_medium=readme&utm_campaign=herascrape); the client
sends it in the `x-api-key` header. Pass it to the constructor:

```python
from herascrape import Client

client = Client(api_key="hs_live_xxxxxxxx")
```

Or leave it out and the client reads `HERASCRAPE_API_KEY` from the environment.
With no key in either place, constructing a client raises `AuthenticationError`.
Keep keys out of source control.

Billing is per successful call, and failed calls are not billed. See
[pricing](https://herascrape.com/docs/getting-started/pricing?utm_source=pypi&utm_medium=readme&utm_campaign=herascrape).

## Usage

Every method returns the response `data` as a plain `dict`, exactly as
Instagram sent it. Check an endpoint's *What comes back* section in the
[docs](https://herascrape.com/docs?utm_source=pypi&utm_medium=readme&utm_campaign=herascrape) before mapping fields.

```python
from herascrape import Client

client = Client()

# Profiles: look a username up once, then use the numeric pk.
user = client.user_by_username(username="instagram")
page = client.user_followers(user["pk"])
print(len(page["items"]), page["has_more"], page["next_cursor"])

# Pagination: iter_* walks the pages lazily.
for reel in client.iter_user_reels(user["pk"], max_items=50):
    print(reel["code"])

# Search: session UUIDs are generated for you.
for hit in client.search_users(query="nike")["items"]:
    print(hit["pk"], hit["username"])

# Posts take a pk or a shortcode.
post = client.post("B4XpqViUFUI")
print(post["like_count"], post["comment_count"])

# Convert between a media pk and its shortcode.
print(client.resolve_media(code="B4XpqViUFUI"))
```

Most list responses carry `items`, `next_cursor` and `has_more`. `post_comments`
and `user_posts` keep Instagram's own paging shape, so page those by hand, and
`search_top` returns `edges` with `next_cursor` only; see
the [docs](https://herascrape.com/docs/getting-started/pagination?utm_source=pypi&utm_medium=readme&utm_campaign=herascrape).

### Async

```python
import asyncio

from herascrape import AsyncClient


async def main() -> None:
    async with AsyncClient() as client:
        user = await client.user_by_username(username="instagram")
        async for follower in client.iter_user_followers(
            user["pk"], max_items=100
        ):
            print(follower["username"])


asyncio.run(main())
```

## Errors

Every exception inherits from `HerascrapeError`. API errors are
`HerascrapeAPIError` subclasses carrying `status_code`, `error_code`, `detail`
and `request_id`.

```python
from herascrape import Client, PrivateAccountError, ProfileNotFoundError

client = Client()

try:
    followers = client.user_followers("25025320")
except PrivateAccountError:
    print("private account")
except ProfileNotFoundError:
    print("no such profile")
```

| Exception | When |
| --- | --- |
| `BadRequestError` | 400. `InvalidCursorError` and `InvalidParameterError` are subclasses. |
| `AuthenticationError` | 401. Missing or invalid key. |
| `ForbiddenError` | 403. `PrivateAccountError` is the private-profile case. |
| `NotFoundError` | 404. `ProfileNotFoundError` is the unknown-profile case. |
| `ValidationError` | 422. Per-field messages in `field_errors`. |
| `RateLimitError` | 429. Seconds to wait in `retry_after`, when sent. |
| `ServerError` | 5xx. `InternalError`, `UpstreamError` and `ServiceUnavailableError` are subclasses. |
| `HerascrapeTransportError` | No response: connection failure or timeout. |

## Retries and rate limiting

The client retries connection errors and timeouts, 429, 502, 503 and
`invalid_cursor` up to `max_retries` times (default 3), backing off from 0.5 s
to 8 s with jitter. A 429 with a `Retry-After` header waits that long, capped
at 300 s. It also throttles requests on the client with a token bucket that
defaults to 50 requests per second. Match it to your account's limit, which
all of its API keys share:

```python
from herascrape import Client, RateLimit

client = Client(rate_limit=RateLimit(rate=10, period="s"))
client = Client(rate_limit=None)  # no client-side limit
```

Other constructor options: `timeout` (seconds, default 10), `max_retries`, and
`base_url` (default `https://api.herascrape.com`).

## Endpoints

All 37 endpoints are `GET`s. The full table with paths is in the
[repository README](https://github.com/herascrape/herascrape#endpoints).

| Group | Methods |
| --- | --- |
| Users | `user_by_username`, `user`, `user_followers`, `user_following`, `user_posts`, `user_reels`, `user_tagged`, `user_stories`, `user_highlights`, `user_reposts`, `user_about`, `user_similar` |
| Posts and comments | `post`, `post_comments`, `post_likers`, `comment_replies`, `comment_likers` |
| Search | `search_users`, `search_hashtags`, `search_audio`, `search_top`, `search_places`, `search_reels` |
| Hashtags | `hashtag`, `hashtag_top`, `hashtag_recent`, `hashtag_reels` |
| Locations | `location`, `location_top`, `location_recent` |
| Audio | `audio_trending`, `audio`, `audio_medias` |
| Stories and highlights | `highlight`, `story` |
| Utility | `resolve_media`, `oembed`, `balance`, `health` |

Coming from HikerAPI? The
[migration guide](https://herascrape.com/docs/guides/hikerapi-migration?utm_source=pypi&utm_medium=readme&utm_campaign=herascrape) maps
each path to its herascrape equivalent.

## Disclaimer

herascrape is not affiliated with, authorized, maintained, or endorsed by
Instagram or Meta. Instagram is a trademark of Meta Platforms, Inc. You are
responsible for using the data in line with applicable law and Instagram's
terms.

## License

MIT
