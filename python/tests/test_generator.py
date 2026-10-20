import json
import re
import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from codegen import generate  # noqa: E402
from codegen.names import PATH_METHOD_NAMES  # noqa: E402

_PKG = _REPO_ROOT / "python" / "herascrape"
_OPENAPI = _REPO_ROOT / "openapi.json"


def _openapi_paths() -> set[str]:
    paths: dict[str, object] = json.loads(_OPENAPI.read_text())["paths"]
    return set(paths)


def _sync_source() -> str:
    return (_PKG / "_endpoints_sync.py").read_text()


def _async_source() -> str:
    return (_PKG / "_endpoints_async.py").read_text()


def _nows(text: str) -> str:
    """Collapse all whitespace so wrapping can't break substring checks."""
    return re.sub(r"\s+", "", text)


def _method_src(src: str, name: str) -> str:
    """Source of one method, from its ``def`` to the next method def."""
    start = src.index(f"def {name}(")
    tail = src[start + len(f"def {name}(") :]
    nxt = re.search(r"\n    (?:async def|def) ", tail)
    end = start + len(f"def {name}(") + (nxt.start() if nxt else len(tail))
    return src[start:end]


def test_name_map_covers_all_paths():
    assert set(PATH_METHOD_NAMES) == _openapi_paths()
    assert len(PATH_METHOD_NAMES) == 37
    assert len(set(PATH_METHOD_NAMES.values())) == 37


def test_generated_sync_has_user_followers_signature():
    sig = _nows(_sync_source())
    assert (
        "defuser_followers(self,user_id:str,*,cursor:Optional[str]=None)->Any:"
        in sig
    )


def test_paginable_gets_iter():
    src = _sync_source()
    assert "def iter_user_followers(" in src
    assert "def iter_user(" not in src


def test_search_top_uses_edges():
    src = _sync_source()
    assert "def iter_search_top(" in src
    assert 'item_key="edges"' in _method_src(src, "iter_search_top")
    assert 'item_key="items"' in _method_src(src, "iter_search_users")
    assert src.count('item_key="edges"') == 1


def test_user_posts_has_no_iter():
    for src in (_sync_source(), _async_source()):
        assert "def user_posts(" in src
        assert "def iter_user_posts(" not in src


def test_balance_return_typed():
    sig = _nows(_sync_source())
    assert "defbalance(self)->BalanceResponse:" in sig
    assert "->MediaIdResolution:" in sig


def test_balance_usd_typed_as_str():
    src = _nows((_PKG / "types.py").read_text())
    assert "balance_usd:str" in src
    assert "balance_usd:float" not in src


def test_required_query_param_has_no_default():
    sig = _nows(_method_src(_sync_source(), "search_users"))
    assert "query:str," in sig
    assert "query:str=None" not in sig
    assert "search_session_id:Optional[str]=None" in sig


def test_resolve_media_requires_exactly_one():
    from herascrape._endpoints_sync import SyncEndpoints

    client = SyncEndpoints(api_key="hs_test")
    try:
        with pytest.raises(ValueError):
            client.resolve_media()
        with pytest.raises(ValueError):
            client.resolve_media(pk="1", code="abc")
    finally:
        client.close()


def test_async_mixin_structure():
    src = _nows(_async_source())
    assert (
        "asyncdefuser_followers(self,user_id:str,*,cursor:Optional[str]=None)"
        "->Any:" in src
    )
    assert "defiter_user_followers(" in src
    assert "->AsyncIterator[Any]:" in src


def test_regen_is_clean(tmp_path: Path):
    generate.generate(out_dir=tmp_path)
    for name in ("types.py", "_endpoints_sync.py", "_endpoints_async.py"):
        got = (tmp_path / name).read_text()
        want = (_PKG / name).read_text()
        assert got == want, f"{name} differs from a fresh regeneration"
