def test_version_exposed():
    import herascrape

    assert isinstance(herascrape.__version__, str) and herascrape.__version__


def test_public_names_exported():
    import herascrape

    exported = set(herascrape.__all__)
    assert {"Client", "AsyncClient", "RateLimit"} <= exported
    assert {"Page", "MediaIdResolution", "BalanceResponse"} <= exported
    assert {"HerascrapeError", "RateLimitError", "ProfileNotFoundError"} <= (
        exported
    )
    assert all(hasattr(herascrape, name) for name in exported)
