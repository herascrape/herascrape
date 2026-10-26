# Types and options

```{eval-rst}
.. autoclass:: herascrape.RateLimit
   :members:
   :undoc-members:
   :no-show-inheritance:
```

The response types are `TypedDict`s: they describe a `dict` the client hands
back and cost nothing at runtime. `Page` is the list envelope every paginable
endpoint answers with. `MediaIdResolution` and `BalanceResponse` are the
declared return types of `resolve_media()` and `balance()`, the two endpoints
whose shape is the service's own. Every other method returns Instagram's JSON,
typed `Any`.

```{eval-rst}
.. autoclass:: herascrape.Page
   :members: next_cursor, has_more
   :undoc-members:

.. Autodoc skips ``items``: the name collides with ``dict.items``.
.. py:attribute:: herascrape.Page.items
   :type: list[Any]

.. autoclass:: herascrape.MediaIdResolution
   :members:
   :undoc-members:

.. autoclass:: herascrape.BalanceResponse
   :members:
   :undoc-members:
```
