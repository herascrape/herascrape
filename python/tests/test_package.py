def test_version_exposed():
    import herascrape

    assert isinstance(herascrape.__version__, str) and herascrape.__version__
