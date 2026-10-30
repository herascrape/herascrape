---
myst:
  html_meta:
    description: "Python client for the herascrape Instagram API. 39 GET endpoints as typed methods, sync and async, cursor pagination helpers, typed errors, one dependency."
---

# herascrape Python client

`herascrape` is the official Python client for
[herascrape](https://herascrape.com/?utm_source=readthedocs&utm_medium=docs&utm_campaign=herascrape), a hosted Instagram API. The service runs
the accounts, devices and proxies and reads Instagram's private API. The client
turns each of its 39 `GET` endpoints into one method and hands back Instagram's
own JSON.

These pages are the **library reference**: the classes, methods, exceptions and
constructor options that ship in the package. The service is documented
separately at [herascrape.com/docs](https://herascrape.com/docs?utm_source=readthedocs&utm_medium=docs&utm_campaign=herascrape), which covers
endpoint semantics, response fields, pricing and API keys, with a live
request console at
[api.herascrape.com/docs](https://api.herascrape.com/docs).

## Install

```bash
pip install herascrape
```

Python 3.10 or newer, one runtime dependency (`httpx`), and the package ships
`py.typed` so its signatures reach your type checker.

## First call

```python
from herascrape import Client

client = Client(api_key="hs_live_xxxxxxxx")

user = client.user_by_username(username="instagram")
print(user["username"], user["follower_count"])

for follower in client.iter_user_followers(user["pk"], max_items=100):
    print(follower["username"])
```

Methods return the response payload as a plain `dict`, exactly as Instagram
sent it. Responses are not remodelled, so a field Instagram adds reaches you
without waiting for a client release. The shapes are Instagram's, so read an
endpoint's *What comes back* section in the
[service docs](https://herascrape.com/docs?utm_source=readthedocs&utm_medium=docs&utm_campaign=herascrape) before mapping fields.

```{toctree}
:maxdepth: 2
:caption: Guides

quickstart
pagination
error-handling
rate-limits
```

```{toctree}
:maxdepth: 2
:caption: Reference

reference/index
```

## Elsewhere

- Source: [github.com/herascrape/herascrape](https://github.com/herascrape/herascrape)
- Package: [pypi.org/project/herascrape](https://pypi.org/project/herascrape/)
- TypeScript client: [npmjs.com/package/herascrape](https://www.npmjs.com/package/herascrape)
- MCP server for AI agents: [herascrape-mcp](https://github.com/herascrape/herascrape-mcp)
- Moving off HikerAPI: [migration guide](https://herascrape.com/docs/guides/hikerapi-migration?utm_source=readthedocs&utm_medium=docs&utm_campaign=herascrape)

herascrape is not affiliated with, authorized, maintained, or endorsed by
Instagram or Meta. Instagram is a trademark of Meta Platforms, Inc.
