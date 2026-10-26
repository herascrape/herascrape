# herascrape: Instagram API client for Python & TypeScript

[![PyPI](https://img.shields.io/pypi/v/herascrape?label=pypi)](https://pypi.org/project/herascrape/)
[![npm](https://img.shields.io/npm/v/herascrape?label=npm)](https://www.npmjs.com/package/herascrape)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue)](LICENSE)
[![Docs](https://img.shields.io/badge/docs-herascrape.com-4f46e5)](https://herascrape.com/docs)

`herascrape` is the official Python and TypeScript/JavaScript client for
[herascrape](https://herascrape.com), a hosted Instagram scraper API. It reads
Instagram's private API for you and returns Instagram's own JSON:
**profiles, followers and following, posts, reels, stories, highlights,
comments, hashtags, locations, audio, and search.** You bring an API key; the
service runs the accounts, devices and proxies.

- `pip install herascrape` · `npm i herascrape`
- 37 `GET` endpoints, one method each, plus lazy `iter_*` paginators for lists.
- Real-time: every call fetches live from Instagram. Flat $0.0004 per
  successful call; failed calls are not billed.
- **Python**: sync (`Client`) and async (`AsyncClient`). **TypeScript**: one
  async `Client`, ESM + CJS, bundled `.d.ts` types.
- Typed errors, retries with backoff and `Retry-After`, and a client-side rate
  limiter.
- Minimal footprint: `httpx` (Python) / native `fetch` (Node), Python 3.10+,
  Node 18+.

Docs: [herascrape.com/docs](https://herascrape.com/docs) · interactive
reference: [api.herascrape.com/docs](https://api.herascrape.com/docs).
Also from herascrape: [herascrape-mcp](https://github.com/herascrape/herascrape-mcp),
the Instagram MCP server for AI agents, and
[hikerapi-to-herascrape](https://github.com/herascrape/hikerapi-to-herascrape) to
migrate from HikerAPI.

## Install

```bash
pip install herascrape      # Python 3.10+
npm install herascrape      # Node 18+
```

## Quick start

Python:

```python
from herascrape import Client

client = Client(api_key="hs_live_xxxxxxxx")

user = client.user_by_username(username="instagram")
print(user["username"], user["follower_count"])

for follower in client.iter_user_followers(user["pk"], max_items=100):
    print(follower["username"])
```

TypeScript / JavaScript:

```ts
import { Client } from "herascrape";

const client = new Client({ apiKey: "hs_live_xxxxxxxx" });

const user = await client.userByUsername({ username: "instagram" });
console.log(user.username, user.follower_count);

for await (const follower of client.iterUserFollowers({
  userId: user.pk,
  maxItems: 100,
})) {
  console.log(follower.username);
}
```

Both return Instagram's own JSON as plain objects (a `dict` in Python, a
`Record` in TypeScript). Method names are `snake_case` in Python and
`camelCase` in TypeScript; **response fields are Instagram's own** (snake_case)
in both.

## Authentication

Create a key in the [dashboard](https://herascrape.com/api-keys); the client
sends it in the `x-api-key` header. Pass it to the constructor:

```python
client = Client(api_key="hs_live_xxxxxxxx")
```

```ts
const client = new Client({ apiKey: "hs_live_xxxxxxxx" });
```

Or leave it out and the client reads `HERASCRAPE_API_KEY` from the environment.
With no key in either place, constructing the client raises an authentication
error. Keep keys out of source control.

Billing is per successful call; failed calls are not billed. See
[pricing](https://herascrape.com/docs/getting-started/pricing).

## Usage (Python)

Every method returns the response `data` as a plain `dict`, exactly as
Instagram sent it. The shape follows Instagram, so check an endpoint's *What
comes back* section in the [docs](https://herascrape.com/docs) before mapping
fields.

### Profiles and lists

The user endpoints take the numeric id (`pk`), so look a username up once and
keep the `pk`.

```python
client = Client(api_key="hs_live_xxxxxxxx")

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

Or let the `iter_*` twin of the method do it. It is lazy: pages are fetched as
you consume it, and it stops at `max_items` or on the last page.

```python
for reel in client.iter_user_reels(user["pk"], max_items=50):
    print(reel["code"])
```

Treat cursors as opaque and use each one only with the endpoint that issued it.

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

comments = client.post_comments(post["pk"])
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
    async with AsyncClient(api_key="hs_live_xxxxxxxx") as client:
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

Use `with Client(...) as client:` or call `client.close()` to release the
connection pool.

## Usage (TypeScript)

The TypeScript client mirrors Python one-to-one: every method takes a single
**options object**, every list has an `iter*` async-iterator twin, and the
error hierarchy is the same. It ships ESM + CJS with bundled `.d.ts` types and
has **zero runtime dependencies** (native `fetch`, Node 18+). See
[js/README.md](js/README.md) for the full TypeScript guide.

```ts
import { Client, NotFoundError, RateLimitError } from "herascrape";

const client = new Client({ apiKey: process.env.HERASCRAPE_API_KEY });

// one page
const page = await client.userFollowers({ userId: "25025320" });
console.log(page.items.length, page.has_more, page.next_cursor);

// lazy pagination
for await (const reel of client.iterUserReels({
  userId: "25025320",
  maxItems: 50,
})) {
  console.log(reel.code);
}

// search — session ids are generated and replayed across pages for you
const hits = await client.searchUsers({ query: "nike" });

// typed errors
try {
  await client.user({ userId: "0" });
} catch (err) {
  if (err instanceof NotFoundError) console.log("no such profile");
  else if (err instanceof RateLimitError) console.log("rate limited", err.retryAfter);
  else throw err;
}

// client-side rate limit (default 50/s), configurable or disabled
const limited = new Client({
  apiKey: "hs_live_xxxxxxxx",
  rateLimit: { rate: 10, period: "s" },
});
```

## Errors

Every exception raised by the client inherits from `HerascrapeError`. API
errors are `HerascrapeAPIError` (`HerascrapeApiError` in TypeScript) subclasses
carrying `status_code` / `error_code` / `detail` / `request_id` (camelCase in
TypeScript).

```python
from herascrape import (
    Client,
    HerascrapeError,
    PrivateAccountError,
    ProfileNotFoundError,
    RateLimitError,
)

client = Client(api_key="hs_live_xxxxxxxx")

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

Both clients retry transient failures up to `max_retries` times (default 3):
connection errors and timeouts, 429, 502, 503 and `invalid_cursor`. Waits back
off exponentially from 0.5 s to a cap of 8 s, with jitter. A 429 with a
`Retry-After` header waits that long, capped at 300 s. Other 4xx responses and
500 are raised immediately.

Requests are also throttled on the client before they are sent, with a token
bucket that defaults to **50 requests per second**, shared across threads and
tasks. Match it to your account's limit:

```python
from herascrape import Client, RateLimit

client = Client(api_key="hs_live_xxxxxxxx", rate_limit=RateLimit(rate=10, period="s"))
client = Client(api_key="hs_live_xxxxxxxx", rate_limit=RateLimit(rate=1000, period_length=1, period="h"))
client = Client(api_key="hs_live_xxxxxxxx", rate_limit=None)  # no client-side limit
```

`period` is one of `"s"`, `"m"`, `"h"`, `"d"`. Other constructor options:
`timeout` (seconds, default 10), `max_retries`, and `base_url` (default
`https://api.herascrape.com`). The TypeScript client takes the same options as
`{ apiKey, rateLimit, timeout, maxRetries, baseUrl }`.

## Endpoints

All 37 endpoints are `GET`s. The Python method is `snake_case`; the TypeScript
method is the same name in `camelCase` and takes an options object. Rows marked
`iter` also have an `iter_<method>` (Python) / `iter<Method>` (TypeScript) twin
that walks every page lazily. `user_posts` and `post_comments` page by hand (see
[Pagination](#pagination)).

### Users

| Python | TypeScript | Endpoint | Returns | iter |
| --- | --- | --- | --- | --- |
| `user_by_username` | `userByUsername` | `/users/username/{username}` | Profile by handle | |
| `user` | `user` | `/users/{user_id}` | Full profile by numeric id | |
| `user_followers` | `userFollowers` | `/users/{user_id}/followers` | Followers | yes |
| `user_following` | `userFollowing` | `/users/{user_id}/following` | Accounts followed | yes |
| `user_posts` | `userPosts` | `/users/{user_id}/posts` | Profile grid, `{feed, posts}` shape | |
| `user_reels` | `userReels` | `/users/{user_id}/reels` | Reels, optionally by views | yes |
| `user_tagged` | `userTagged` | `/users/{user_id}/tagged` | Posts the user is tagged in | yes |
| `user_stories` | `userStories` | `/users/{user_id}/stories` | Active stories | |
| `user_highlights` | `userHighlights` | `/users/{user_id}/highlights` | Story highlights | |
| `user_reposts` | `userReposts` | `/users/{user_id}/reposts` | Reposted content | yes |
| `user_about` | `userAbout` | `/users/{user_id}/about` | "About this account" details | |

### Posts and comments

| Python | TypeScript | Endpoint | Returns | iter |
| --- | --- | --- | --- | --- |
| `post` | `post` | `/posts/{post_id}` | A post or reel, by pk or shortcode | |
| `post_comments` | `postComments` | `/posts/{post_id}/comments` | Comments | |
| `post_likers` | `postLikers` | `/posts/{post_id}/likers` | Users who liked the post | |
| `comment_replies` | `commentReplies` | `/comments/{comment_id}/replies` | Replies to a comment | yes |
| `comment_likers` | `commentLikers` | `/comments/{comment_id}/likers` | Users who liked a comment | |

### Search

| Python | TypeScript | Endpoint | Returns | iter |
| --- | --- | --- | --- | --- |
| `search_users` | `searchUsers` | `/search/users` | Accounts | yes |
| `search_hashtags` | `searchHashtags` | `/search/hashtags` | Hashtags with post counts | yes |
| `search_audio` | `searchAudio` | `/search/audio` | Tracks and original sounds | yes |
| `search_top` | `searchTop` | `/search/top` | Instagram's blended top results | yes |
| `search_places` | `searchPlaces` | `/search/places` | Places; optional `lat` and `lng` | |

### Hashtags and locations

| Python | TypeScript | Endpoint | Returns | iter |
| --- | --- | --- | --- | --- |
| `hashtag` | `hashtag` | `/hashtags/{name}` | Hashtag info | |
| `hashtag_top` | `hashtagTop` | `/hashtags/{name}/top` | Top posts | yes |
| `hashtag_recent` | `hashtagRecent` | `/hashtags/{name}/recent` | Recent posts | yes |
| `hashtag_reels` | `hashtagReels` | `/hashtags/{name}/reels` | Reels | yes |
| `location` | `location` | `/locations/{location_id}` | Location info | |
| `location_top` | `locationTop` | `/locations/{location_id}/top` | Top posts | yes |
| `location_recent` | `locationRecent` | `/locations/{location_id}/recent` | Recent posts | yes |

### Audio, stories and highlights

| Python | TypeScript | Endpoint | Returns | iter |
| --- | --- | --- | --- | --- |
| `audio_trending` | `audioTrending` | `/audio/trending` | Trending audio | yes |
| `audio` | `audio` | `/audio/{audio_id}` | Track info | |
| `audio_medias` | `audioMedias` | `/audio/{audio_id}/medias` | Reels using the audio | yes |
| `highlight` | `highlight` | `/highlights/{highlight_id}` | Media in a highlight | |
| `story` | `story` | `/stories/{reel_id}` | Media in a story reel | |

### Utility

| Python | TypeScript | Endpoint | Returns | iter |
| --- | --- | --- | --- | --- |
| `resolve_media` | `resolveMedia` | `/resolve/media` | Media `pk` ⇄ shortcode; pass one of the two | |
| `oembed` | `oembed` | `/oembed` | oEmbed for a post URL, or a share link's target | |
| `balance` | `balance` | `/system/balance` | Remaining balance | |
| `health` | `health` | `/system/health` | Service status | |

## Coming from another Instagram API

The [HikerAPI migration guide](https://herascrape.com/docs/guides/hikerapi-migration)
maps each HikerAPI path to its herascrape equivalent.

## Disclaimer

herascrape is not affiliated with, authorized, maintained, or endorsed by
Instagram or Meta. Instagram is a trademark of Meta Platforms, Inc. You are
responsible for using the data in line with applicable law and Instagram's
terms.

## Security

Report vulnerabilities to support@herascrape.com. See
[SECURITY.md](SECURITY.md).

## License

[MIT](LICENSE)
