# AGENTS.md

Guidance for AI agents (and humans) working in this repo. Keep changes minimal,
typed, and consistent with what is already here.

## What this is

The official **herascrape** API clients: a monorepo with a **Python** client
(`python/`) and a **TypeScript/JavaScript** client (`js/`), both generated from
one OpenAPI spec (`openapi.json`) by a shared generator (`codegen/`). Clients
return Instagram's own JSON unwrapped — they do not model responses.

## Layout

```
openapi.json         # the API surface — source of truth for endpoints + types
codegen/             # generate.py + names.py → emit the endpoint/type files
python/herascrape/   # Python client   (PyPI: herascrape)
js/                  # TypeScript/JS client (npm: herascrape)
python/docs/         # Sphinx reference, published to Read the Docs
ruff.toml            # Python lint/format config (line-length 80, py310)
.github/workflows/   # ci.yml, release-python.yml, release-js.yml
```

## Golden rules

- **Never hand-edit generated files** — they carry a `do not edit` header:
  - Python: `types.py`, `_endpoints_sync.py`, `_endpoints_async.py`
  - TS: `src/endpoints.ts`, `src/types.ts`

  Change the surface via `openapi.json` (or `codegen/`) and regenerate. CI
  re-runs the generator and fails on any diff.
- **Responses are plain `dict`/objects**, exactly as Instagram sends them — no
  pydantic/response models (IG shapes are uncontrollable). Inputs are typed:
  real params (Python), a single options object (TS).
- **Two client classes:** `Client` (sync) + `AsyncClient` (async) in Python;
  `Client` (async) in TS. Keep their surfaces identical, and keep **Python ⇄ TS
  parity** — a change in one almost always needs the mirror.
- Hand-written (edit these): `_base`, `client`, `async_client`, `_errors`,
  `_pagination`, `ratelimit` and their TS equivalents. Everything else is
  generated.

## Python (`python/`)

- 3.10+, **one runtime dep (`httpx`)**, pyright **strict**, ruff line-length 80.
- PEP 604 unions (`X | None`), lowercase generics (`list[str]`),
  **keyword-only** args, trailing commas, real annotations (no `__future__`).
- Tooling is **uv** (PEP 735 dev group; `tool.uv.package = true`).

```bash
uv sync --project python
uv run --project python ruff check python codegen
uv run --project python ruff format python codegen      # --check in CI
uv run --project python pyright --project python
uv run --project python pytest python/tests -m "not live" -v
```

## TypeScript (`js/`)

- Async-only, native `fetch`, **zero runtime deps**, Node 18+. Ships ESM + CJS +
  type declarations via tsup. Methods take one options object.
- eslint + prettier + `tsc` strict.

```bash
cd js && npm ci
npx eslint .
npx prettier --check "**/*.ts"
npx tsc --noEmit
npx vitest run --minWorkers=1 --maxWorkers=2    # always cap workers
npm run build
```

## Docs (`python/docs/`)

The Python client reference: Sphinx + MyST markdown + autodoc, built from
`.readthedocs.yaml` at the repo root and published at
[herascrape.readthedocs.io](https://herascrape.readthedocs.io/). Narrative
pages are hand-written; `reference/` is autodoc over the installed package, so
endpoint method docs come from the generated docstrings, which come from
`openapi.json`.

```bash
uv run --isolated --no-project --python 3.13 --with-editable ./python \
  --with-requirements python/docs/requirements.txt \
  -- sphinx-build -W -b html python/docs python/docs/_build/html
```

Read the Docs builds with `fail_on_warning` and CI runs the same `-W` build, so
a dead reference breaks the gate. Three rules: the docs site is the **library
reference only** (never mirror `herascrape.com/docs` into it, a higher-authority
copy of our own content can outrank us), `requirements.txt` is pinned, so bump
it deliberately, and **Read the Docs is for the Python client only** (TS docs
belong in TypeDoc on GitHub Pages, where TS developers look).

## Regenerate the clients

```bash
# from the repo root; needs js deps installed (prettier formats the emitted TS)
python -m codegen.generate
```

Regenerates both Python and TS from `openapi.json`. Commit the result; CI fails
if the generated files drift from the spec.

## Testing

- Unit tests run offline (`-m "not live"` / vitest) — keep them hermetic.
- **Live tests** (`python/tests/live`, `-m live`) hit the real API and need
  `HERASCRAPE_API_KEY`; they run only on schedule/dispatch, never on PRs.
- Never commit a real key — use the placeholder `hs_live_xxxxxxxx`. Hygiene tests
  and gitleaks enforce this in CI.

## Release / deploy

- Bump the version in **both** `python/herascrape/__init__.py` (`__version__`)
  and `js/package.json`; they must match, and the tag is `v<version>`.
- Cut a GitHub Release → both packages publish via **OIDC Trusted Publishing**
  (no tokens) with provenance:

  ```bash
  gh release create vX.Y.Z -R herascrape/herascrape --target main \
    --title "herascrape X.Y.Z" --notes "..."     # non-prerelease
  ```

- Dry-run first (safe):

  ```bash
  gh workflow run release-python.yml --ref main   # → TestPyPI
  gh workflow run release-js.yml --ref main       # → npm --dry-run
  ```

- Release / secret / dispatch ops need the **`herascrapeops`** gh account (the
  only one with org admin): `gh auth switch --user herascrapeops`. Prereleases
  never publish.

## Security

Never commit or publish secrets. Report issues to support@herascrape.com (see
`SECURITY.md`). Not affiliated with Instagram or Meta.
