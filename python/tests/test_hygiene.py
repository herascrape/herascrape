import re
from pathlib import Path

import pytest

PYTHON_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = PYTHON_DIR.parent
READMES = [REPO_ROOT / "README.md", PYTHON_DIR / "README.md"]
SKIPPED_DIRS = {
    ".git",
    ".venv",
    "venv",
    "__pycache__",
    ".pytest_cache",
    ".ruff_cache",
    ".pyright",
    "node_modules",
    "build",
    "dist",
}
KEY_PATTERN = re.compile(r"hs_(?:live|test)_[A-Za-z0-9]{16,}")
LOCAL_PATH_PATTERN = re.compile(r"/(?:Users|home)/\w")
PLACEHOLDER_KEY = "hs_live_xxxxxxxx"


def _skipped(path: Path) -> bool:
    return any(
        part in SKIPPED_DIRS or part.endswith(".egg-info")
        for part in path.relative_to(REPO_ROOT).parts
    )


def _source_files() -> list[Path]:
    return [
        path
        for path in REPO_ROOT.rglob("*")
        if path.is_file() and not _skipped(path)
    ]


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="ignore")


def test_no_real_key_pattern_committed():
    found = [
        f"{path.relative_to(REPO_ROOT)}: {match}"
        for path in _source_files()
        for match in KEY_PATTERN.findall(_text(path))
        if match != PLACEHOLDER_KEY
    ]
    assert found == []


def test_no_local_paths_committed():
    found = [
        str(path.relative_to(REPO_ROOT))
        for path in _source_files()
        if LOCAL_PATH_PATTERN.search(_text(path))
    ]
    assert found == []


@pytest.mark.parametrize("readme", READMES, ids=["root", "python"])
def test_readme_has_disclaimer(readme: Path):
    text = " ".join(_text(readme).split())
    assert re.search(
        r"not affiliated with, authorized, maintained, or endorsed by "
        r"Instagram",
        text,
    )


@pytest.mark.parametrize("readme", READMES, ids=["root", "python"])
def test_readme_has_install_and_sample(readme: Path):
    text = _text(readme)
    assert "pip install herascrape" in text
    assert "HERASCRAPE_API_KEY" in text
    assert "x-api-key" in text


@pytest.mark.parametrize("readme", READMES, ids=["root", "python"])
def test_readme_uses_placeholder_key_only(readme: Path):
    assert PLACEHOLDER_KEY in _text(readme)


def test_quickstart_reads_key_from_env():
    source = _text(PYTHON_DIR / "examples" / "quickstart.py")
    assert "HERASCRAPE_API_KEY" in source
    assert "api_key=" not in source
