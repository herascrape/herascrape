from ._endpoints_sync import SyncEndpoints


class Client(SyncEndpoints):
    """Synchronous herascrape client.

    `api_key` defaults to the HERASCRAPE_API_KEY environment variable.
    Optional: `base_url`, `timeout`, `max_retries`, `rate_limit`.
    """
