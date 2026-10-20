from ._endpoints_async import AsyncEndpoints


class AsyncClient(AsyncEndpoints):
    """Asynchronous herascrape client.

    `api_key` defaults to the HERASCRAPE_API_KEY environment variable.
    Optional: `base_url`, `timeout`, `max_retries`, `rate_limit`.
    """
