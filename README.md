# herascrape: Instagram API client for Python

`herascrape` is the official Python client for the
[herascrape](https://herascrape.com) Instagram API. It is an Instagram scraper
API that reads Instagram's private API for you and hands back Instagram's own
JSON: profiles, followers, posts, reels, comments, hashtags, locations, audio,
stories and search. You do not manage Instagram accounts, devices or proxies.

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

Documentation: [herascrape.com/docs](https://herascrape.com/docs). Interactive
reference: [api.herascrape.com/docs](https://api.herascrape.com/docs).

## Install

```bash
pip install herascrape
```

## Authentication

Create a key in the [dashboard](https://herascrape.com/api-keys). The client
sends it in the `x-api-key` header. Pass it directly, or leave it out and set
`HERASCRAPE_API_KEY`:

```bash
export HERASCRAPE_API_KEY="hs_live_xxxxxxxx"
```

```python
from herascrape import Client

client = Client()  # reads HERASCRAPE_API_KEY
```

With no key in either place, constructing a client raises
`AuthenticationError`. Keep keys out of source control.

Billing is per successful call, and failed calls are not billed. See
[pricing](https://herascrape.com/docs/getting-started/pricing).

## Usage

Every method returns the response `data` as a plain `dict`, exactly as
Instagram sent it. The shape follows Instagram, so check an endpoint's *What
comes back* section in the [docs](https://herascrape.com/docs) before mapping
fields.

### Profiles and lists

The user endpoints take the numeric id (`pk`), so look a username up once and
keep the `pk`.

```python
from herascrape import Client

client = Client()

user = client.user_by_username(username="instagram")
profile = client.user(user["pk"])
print(profile["full_name"], profile["is_verified"])

page = client.user_followers(user["pk"])
print(len(page["items"]), page["has_more"], page["next_cursor"])
```

### Pagination

One call fetches one Instagram page. List responses carry `items`,
`next_cursor` and `has_more`. Pass `next_cursor` back as `cursor=` and stop
when `has_more` is false:

```python
cursor = None
while True:
    page = client.user_followers(user["pk"], cursor=cursor)
    for follower in page["items"]:
        print(follower["username"])
    if not page["has_more"]:
        break
    cursor = page["next_cursor"]
```

Or let the `iter_*` twin of the method do it. It is lazy: pages are fetched
as you consume it, and it stops at `max_items` or on the last page.

```python
for reel in client.iter_user_reels(user["pk"], max_items=50):
    print(reel["code"])
```

Treat cursors as opaque and use each one only with the endpoint that issued
it.

Two endpoints keep Instagram's own paging shape instead of the standard
envelope, so page them by hand:

- `post_comments` returns `comments`, `has_more` and `next_min_id`. Pass
  `next_min_id` back as `min_id=` until `has_more` is false.
- `user_posts` returns `{feed, posts}`. Pass `feed.profile_grid_items_cursor`
  back as `cursor=` while `feed.more_available` is true.

### Posts and comments

```python
post = client.post("B4XpqViUFUI")  # pk or shortcode
print(post["like_count"], post["comment_count"])

comments = client.post_comments(post["pk"], user_id=post["user"]["pk"])
for comment in comments["comments"]:
    print(comment["user"]["username"], comment["text"])
```

### Search

```python
results = client.search_users(query="nike")
for hit in results["items"]:
    print(hit["pk"], hit["username"], hit["is_verified"])

for tag in client.iter_search_hashtags(query="travel", max_items=20):
    print(tag["name"], tag["media_count"])
```

Search needs session UUIDs (`search_session_id`, `serp_session_id`, and
`browse_session_id` for audio). The client generates them, and the `iter_*`
helpers reuse the same ones on every page. If you continue a search by hand
with `cursor=`, pass the same IDs back.

### Convert and check

```python
ids = client.resolve_media(code="B4XpqViUFUI")
print(ids["pk"], ids["code"])

balance = client.balance()
print(balance["balance_usd"], balance["currency"])
```

`resolve_media` converts between a media `pk` and its shortcode. Pass exactly
one of `pk` or `code`.

### Async

`AsyncClient` mirrors `Client`. The `iter_*` helpers are async iterators, and
one client-side rate limiter is shared by every concurrent task.

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

        names = ["natgeo", "nasa"]
        profiles = await asyncio.gather(
            *(client.user_by_username(username=name) for name in names)
        )
        print([profile["follower_count"] for profile in profiles])


asyncio.run(main())
```

Use `with Client() as client:` or call `client.close()` to release the
connection pool.

## Errors

Every exception raised by the client inherits from `HerascrapeError`. API
errors are `HerascrapeAPIError` subclasses carrying `status_code`,
`error_code`, `detail` and `request_id`.

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
    followers = client.user_followers("25025320")
except PrivateAccountError:
    print("private account")
except ProfileNotFoundError:
    print("no such profile")
except RateLimitError as exc:
    print(f"still rate limited after retries: {exc.retry_after}s")
except HerascrapeError as exc:
    print(f"request failed: {exc}")
```

| Exception | When |
| --- | --- |
| `BadRequestError` | 400. `InvalidCursorError` and `InvalidParameterError` are subclasses. |
| `AuthenticationError` | 401. Missing or invalid key. |
| `ForbiddenError` | 403. `PrivateAccountError` is the private-profile case. |
| `NotFoundError` | 404. `ProfileNotFoundError` is the unknown-profile case. |
| `ValidationError` | 422. Per-field messages in `field_errors`. |
| `RateLimitError` | 429. Seconds to wait in `retry_after`, when sent. |
| `ServerError` | 5xx. `InternalError` (500), `UpstreamError` (502) and `ServiceUnavailableError` (503) are subclasses. |
| `HerascrapeTransportError` | No response: connection failure or timeout. |

## Retries and rate limiting

The client retries transient failures up to `max_retries` times (default 3):
connection errors and timeouts, 429, 502, 503 and `invalid_cursor`. Waits
back off exponentially from 0.5 s to a cap of 8 s, with jitter. A 429 with a
`Retry-After` header waits that long, capped at 300 s. Other 4xx responses and
500 are raised immediately.

Requests are also throttled on the client before they are sent, with a token
bucket that defaults to 50 requests per second. It is safe to share across
threads and tasks. Match it to your key's limit:

```python
from herascrape import Client, RateLimit

client = Client(rate_limit=RateLimit(rate=10, period="s"))
client = Client(rate_limit=RateLimit(rate=1000, period_length=1, period="h"))
client = Client(rate_limit=None)  # no client-side limit
```

`period` is one of `"s"`, `"m"`, `"h"`, `"d"`.

Other constructor options: `timeout` (seconds, default 10), `max_retries`, and
`base_url` (default `https://api.herascrape.com`).

## Endpoints

All 37 endpoints are `GET`s. Methods marked in the last column also have an
`iter_<method>` twin that walks every page lazily. `user_posts` and
`post_comments` page by hand, as described under
[Pagination](#pagination).

### Users

| Method | Endpoint | Returns | iter |
| --- | --- | --- | --- |
| `user_by_username(username)` | `/users/username/{username}` | Profile by handle | |
| `user(user_id)` | `/users/{user_id}` | Full profile by numeric id | |
| `user_followers(user_id)` | `/users/{user_id}/followers` | Followers | yes |
| `user_following(user_id)` | `/users/{user_id}/following` | Accounts followed | yes |
| `user_posts(user_id)` | `/users/{user_id}/posts` | Profile grid, in `{feed, posts}` shape | |
| `user_reels(user_id)` | `/users/{user_id}/reels` | Reels, optionally by views | yes |
| `user_tagged(user_id)` | `/users/{user_id}/tagged` | Posts the user is tagged in | yes |
| `user_stories(user_id)` | `/users/{user_id}/stories` | Active stories | |
| `user_highlights(user_id)` | `/users/{user_id}/highlights` | Story highlights | |
| `user_reposts(user_id)` | `/users/{user_id}/reposts` | Reposted content | yes |
| `user_about(user_id)` | `/users/{user_id}/about` | "About this account" details | |

### Posts and comments

| Method | Endpoint | Returns | iter |
| --- | --- | --- | --- |
| `post(post_id)` | `/posts/{post_id}` | A post or reel, by pk or shortcode | |
| `post_comments(post_id, user_id=)` | `/posts/{post_id}/comments` | Comments; `user_id` is the post owner | |
| `post_likers(post_id, user_id=)` | `/posts/{post_id}/likers` | Users who liked the post | |
| `comment_replies(comment_id, media_id=, user_id=)` | `/comments/{comment_id}/replies` | Replies to a comment | yes |
| `comment_likers(comment_id)` | `/comments/{comment_id}/likers` | Users who liked a comment | |

### Search

| Method | Endpoint | Returns | iter |
| --- | --- | --- | --- |
| `search_users(query=)` | `/search/users` | Accounts | yes |
| `search_hashtags(query=)` | `/search/hashtags` | Hashtags with post counts | yes |
| `search_audio(query=)` | `/search/audio` | Tracks and original sounds | yes |
| `search_top(query=)` | `/search/top` | Instagram's blended top results | yes |
| `search_places(query=)` | `/search/places` | Places; optional `lat` and `lng` | |

### Hashtags and locations

| Method | Endpoint | Returns | iter |
| --- | --- | --- | --- |
| `hashtag(name)` | `/hashtags/{name}` | Hashtag info | |
| `hashtag_top(name)` | `/hashtags/{name}/top` | Top posts | yes |
| `hashtag_recent(name)` | `/hashtags/{name}/recent` | Recent posts | yes |
| `hashtag_reels(name)` | `/hashtags/{name}/reels` | Reels | yes |
| `location(location_id)` | `/locations/{location_id}` | Location info | |
| `location_top(location_id)` | `/locations/{location_id}/top` | Top posts | yes |
| `location_recent(location_id)` | `/locations/{location_id}/recent` | Recent posts | yes |

### Audio, stories and highlights

| Method | Endpoint | Returns | iter |
| --- | --- | --- | --- |
| `audio_trending()` | `/audio/trending` | Trending audio | yes |
| `audio(audio_id)` | `/audio/{audio_id}` | Track info | |
| `audio_medias(audio_id)` | `/audio/{audio_id}/medias` | Reels using the audio | yes |
| `highlight(highlight_id)` | `/highlights/{highlight_id}` | Media in a highlight | |
| `story(reel_id)` | `/stories/{reel_id}` | Media in a story reel | |

### Utility

| Method | Endpoint | Returns | iter |
| --- | --- | --- | --- |
| `resolve_media(pk=, code=)` | `/resolve/media` | Media `pk` to shortcode and back; pass one of the two | |
| `oembed(url=)` | `/oembed` | oEmbed for a post URL, or the target of a share link | |
| `balance()` | `/system/balance` | Remaining balance | |
| `health()` | `/system/health` | Service status | |

## Coming from another Instagram API

The [HikerAPI migration guide](https://herascrape.com/docs/guides/hikerapi-migration)
maps each HikerAPI path to its herascrape equivalent.

## Disclaimer

herascrape is not affiliated with, authorized, maintained, or endorsed by
Instagram or Meta. Instagram is a trademark of Meta Platforms, Inc. You are
responsible for using the data in line with applicable law and Instagram's
terms.

## Security

Report vulnerabilities to security@herascrape.com. See
[SECURITY.md](SECURITY.md).

## License

[MIT](LICENSE)
