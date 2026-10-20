from pathlib import Path


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


def test_bundled_license_matches_repo_license():
    python_dir = Path(__file__).resolve().parents[1]
    bundled = python_dir / "LICENSE"
    root = python_dir.parent / "LICENSE"
    assert bundled.read_text(encoding="utf-8") == root.read_text(
        encoding="utf-8"
    )
