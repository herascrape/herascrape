# herascrape: Instagram API client for TypeScript & JavaScript

`herascrape` is the official TypeScript/JavaScript client for
[herascrape](https://herascrape.com/?utm_source=npm&utm_medium=readme&utm_campaign=herascrape), a hosted Instagram scraper API. It reads
Instagram's public data for you and hands back Instagram's own JSON: profiles,
followers, posts, reels, comments, hashtags, locations, audio, stories and
search. You do not manage the accounts, devices or proxies.

```ts
import { Client } from "herascrape";

const client = new Client({ apiKey: "hs_live_xxxxxxxx" });

const user = await client.userByUsername({ username: "instagram" });
console.log(user.username, user.follower_count);

for await (const follower of client.iterUserFollowers({
  userId: user.pk as string,
  maxItems: 100,
})) {
  console.log(follower.username);
}
```

- 39 endpoints, one method each, plus lazy `iter*` async iterators for lists.
- Async-only, built on the native `fetch` API. No runtime dependencies.
- Ships ESM, CommonJS and TypeScript declarations. Node 18+.
- Typed exception hierarchy: `NotFoundError`, `PrivateAccountError`,
  `RateLimitError` and the rest.
- Retries with backoff, `Retry-After` handling and a client-side rate limiter.

Documentation: [herascrape.com/docs](https://herascrape.com/docs?utm_source=npm&utm_medium=readme&utm_campaign=herascrape).

## Install

```bash
npm install herascrape
```

## Authentication

Create a key in the [dashboard](https://herascrape.com/api-keys?utm_source=npm&utm_medium=readme&utm_campaign=herascrape); the client
sends it in the `x-api-key` header. Pass it to the constructor:

```ts
import { Client } from "herascrape";

const client = new Client({ apiKey: "hs_live_xxxxxxxx" });
```

Or leave it out and the client reads `HERASCRAPE_API_KEY` from the environment.
With no key in either place, constructing a client throws
`AuthenticationError`. Keep keys out of source control.

Billing is per successful call, and failed calls are not billed. See
[pricing](https://herascrape.com/docs/getting-started/pricing?utm_source=npm&utm_medium=readme&utm_campaign=herascrape).

## Usage

Every method takes a single options object and returns the response `data` as a
plain object, exactly as Instagram sent it.

```ts
import { Client } from "herascrape";

const client = new Client({ apiKey: "hs_live_xxxxxxxx" });

// Profiles: look a username up once, then use the numeric pk.
const user = await client.userByUsername({ username: "instagram" });
const page = await client.userFollowers({ userId: user.pk as string });
console.log(page.items, page.has_more, page.next_cursor);

// Pagination: iter* walks the pages lazily.
for await (const reel of client.iterUserReels({
  userId: user.pk as string,
  maxItems: 50,
})) {
  console.log(reel.code);
}

// Search: session UUIDs are generated for you.
const hits = await client.searchUsers({ query: "nike" });
for (const hit of hits.items as Array<Record<string, unknown>>) {
  console.log(hit.pk, hit.username);
}

// Posts take a pk or a shortcode.
const post = await client.post({ postId: "B4XpqViUFUI" });
console.log(post.like_count, post.comment_count);

// Convert between a media pk and its shortcode.
console.log(await client.resolveMedia({ code: "B4XpqViUFUI" }));
```

Most list responses carry `items`, `next_cursor` and `has_more`. `postComments`
and `userPosts` keep Instagram's own paging shape, so they have no iterator and
you page them by hand, and `searchTop` returns `edges` with `next_cursor` only;
see
the [docs](https://herascrape.com/docs/getting-started/pagination?utm_source=npm&utm_medium=readme&utm_campaign=herascrape).

## Errors

Every exception inherits from `HerascrapeError`. API errors are
`HerascrapeApiError` subclasses carrying `statusCode`, `errorCode`, `detail`
and `requestId`.

```ts
import { Client, PrivateAccountError, ProfileNotFoundError } from "herascrape";

const client = new Client({ apiKey: "hs_live_xxxxxxxx" });

try {
  await client.userFollowers({ userId: "25025320" });
} catch (error) {
  if (error instanceof PrivateAccountError) console.log("private account");
  else if (error instanceof ProfileNotFoundError) console.log("no such profile");
  else throw error;
}
```

| Exception | When |
| --- | --- |
| `BadRequestError` | 400. `InvalidCursorError` and `InvalidParameterError` are subclasses. |
| `AuthenticationError` | 401. Missing or invalid key. |
| `ForbiddenError` | 403. `PrivateAccountError` is the private-profile case. |
| `NotFoundError` | 404. `ProfileNotFoundError` is the unknown-profile case. |
| `ValidationError` | 422. Per-field messages in `fieldErrors`. |
| `RateLimitError` | 429. Seconds to wait in `retryAfter`, when sent. |
| `ServerError` | 5xx. `InternalError`, `UpstreamError` and `ServiceUnavailableError` are subclasses. |
| `HerascrapeTransportError` | No response: connection failure or timeout. |

## Retries and rate limiting

The client retries connection errors and timeouts, 429, 502, 503 and
`invalid_cursor` up to `maxRetries` times (default 3), backing off from 0.5 s
to 8 s with jitter. A 429 with a `Retry-After` header waits that long, capped
at 300 s. It also throttles requests on the client with a token bucket that
defaults to 50 requests per second. Match it to your account's limit, which
all of its API keys share:

```ts
import { Client } from "herascrape";

const client = new Client({ rateLimit: { rate: 10, period: "s" } });
const unthrottled = new Client({ rateLimit: null }); // no client-side limit
```

Other constructor options: `timeout` (seconds, default 10), `maxRetries`, and
`baseUrl` (default `https://api.herascrape.com`).

## Endpoints

All 39 endpoints are `GET`s, grouped below. Paginable list endpoints also get a
matching `iter*` async iterator.

| Group | Methods |
| --- | --- |
| Users | `userByUsername`, `user`, `userFollowers`, `userFollowing`, `userPosts`, `userReels`, `userTagged`, `userStories`, `userHighlights`, `userReposts`, `userAbout`, `userSimilar` |
| Posts and comments | `post`, `postComments`, `postLikers`, `commentReplies`, `commentLikers` |
| Search | `searchUsers`, `searchHashtags`, `searchAudio`, `searchTop`, `searchPlaces`, `searchReels` |
| Hashtags | `hashtag`, `hashtagTop`, `hashtagRecent`, `hashtagReels` |
| Locations | `location`, `locationTop`, `locationRecent` |
| Audio | `audioTrending`, `audio`, `audioMedias` |
| Stories and highlights | `highlight`, `story` |
| Utility | `resolveMedia`, `oembed`, `balance`, `health` |

Coming from HikerAPI? The
[migration guide](https://herascrape.com/docs/guides/hikerapi-migration?utm_source=npm&utm_medium=readme&utm_campaign=herascrape) maps
each path to its herascrape equivalent.

## Disclaimer

herascrape is not affiliated with, authorized, maintained, or endorsed by
Instagram or Meta. Instagram is a trademark of Meta Platforms, Inc. You are
responsible for using the data in line with applicable law and Instagram's
terms.

## License

[MIT](LICENSE)
