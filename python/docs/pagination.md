---
myst:
  html_meta:
    description: "Cursor pagination in the herascrape Python client: the items/next_cursor/has_more envelope, lazy iter_* helpers, and the two endpoints that keep Instagram's own paging shape."
---

# Pagination

One call fetches one Instagram page. Most list endpoints answer in the same
shape:

```python
{"items": [...], "next_cursor": "QVFE...", "has_more": True}
```

Page it by hand by passing `next_cursor` back as `cursor=` until `has_more` is
false:

```python
cursor = None
while True:
    page = client.user_followers("25025320", cursor=cursor)
    for follower in page["items"]:
        print(follower["username"])
    if not page["has_more"]:
        break
    cursor = page["next_cursor"]
```

## iter_* helpers

Every paginable method has an `iter_` twin that walks the pages for you. It is
lazy: a page is fetched when you ask for an item that is not in the one you
have, and it stops at `max_items` or at the last page.

```python
for reel in client.iter_user_reels("25025320", max_items=50):
    print(reel["code"])
```

The twin takes the same arguments as the method it wraps, minus `cursor`, plus
`max_items`. On {class}`~herascrape.AsyncClient` it is an async iterator:

```python
async for follower in client.iter_user_followers("25025320", max_items=100):
    print(follower["username"])
```

`max_items` is a ceiling on items yielded, not on requests. The walk stops
after the request that reaches the ceiling, so that page is fetched, and
billed, in full however few of its items you consume. Bound a walk with
`max_items` rather than with a `break`, which costs the same but hides what
you spent.

Nothing is cached. Iterating the same call twice fetches and bills twice.

## Cursors are opaque

Treat a cursor as a token to hand back, never as something to parse, build or
store long term. Use each one with the endpoint that issued it.

An expired or malformed cursor comes back as a `400 invalid_cursor`, which the
client retries automatically (see
[Retries and rate limits](rate-limits.md)); if it still fails,
{class}`~herascrape.InvalidCursorError` is raised and the walk should restart
from the first page.

## Search sessions

The search endpoints carry session UUIDs (`search_session_id`,
`serp_session_id`, and `browse_session_id` for audio). Instagram uses them to
tie the pages of one search journey together. The client generates them when
you leave them out, and the `iter_*` helpers reuse the same ones across every
page of a walk:

```python
for tag in client.iter_search_hashtags(query="travel", max_items=20):
    print(tag["name"], tag["media_count"])
```

If you page a search by hand, pass the same session ids back with each
`cursor=` call. A cursor sent with other session ids is rejected as
`invalid_cursor`.

```python
first = client.search_users(query="nike")
more = client.search_users(
    query="nike",
    cursor=first["next_cursor"],
    search_session_id=...,  # the ids you used on the first call
    serp_session_id=...,
)
```

## The two exceptions

Two endpoints keep Instagram's own paging shape instead, so they have no
`iter_` twin and are paged by hand. A third, `search_top`, returns `edges` and
`next_cursor` with no `has_more`; its `iter_search_top` twin handles that.

`user_posts` returns `{"feed": ..., "posts": {...}}`, with `posts` keyed by
media id and the grid order in `feed.profile_grid_items`. Pass
`feed.profile_grid_items_cursor` back as `cursor=` while
`feed.more_available` is true:

```python
cursor = None
while True:
    page = client.user_posts("25025320", cursor=cursor)
    for post in page["posts"].values():
        print(post["code"])
    feed = page["feed"]
    if not feed.get("more_available"):
        break
    cursor = feed["profile_grid_items_cursor"]
```

`post_comments` returns `comments`, `has_more` and `next_min_id`. Pass
`next_min_id` back as `min_id=`:

```python
min_id = None
while True:
    page = client.post_comments("B4XpqViUFUI", min_id=min_id)
    for comment in page["comments"]:
        print(comment["user"]["username"], comment["text"])
    if not page["has_more"]:
        break
    min_id = page["next_min_id"]
```

## Endpoints that return a single page

Some endpoints have no cursor at all because Instagram does not paginate them:
`post_likers`, `comment_likers` and `search_places` return one capped page.
`user_followers` and `user_following` do paginate, but Instagram reshuffles
the list on every request, so one walk sees about 70-90% of it; walk it again
and merge by `pk` to fill the gaps. Some business and verified accounts list
only about 45-49 followers before `has_more` goes false.
