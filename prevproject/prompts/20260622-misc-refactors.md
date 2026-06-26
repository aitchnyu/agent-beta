## Move model tests into `tests/models/`

Group the model-focused test files under a dedicated `djangoapp/tests/models/` package, mirroring the existing `tests/views/` and `tests/commands/` packages. Use `git mv` so history is preserved, and rename each file to match the model/module it tests (drop the now-redundant `_model` suffix since the directory already says "models").

### Scope (what moves, what stays)

Move (model tests):
- `tests/test_models.py` -> `tests/models/test_base.py` (core model framework: `BaseModel`, `resolve_columns`, file upload, `ProxyUser`, `RowUpdate` + access timeout/redaction/notification, `public_id` property/getters) - mirrors `djangoapp/models/base.py`
- `tests/test_user_model.py` -> `tests/models/test_user.py` (drops redundant `_model`) - mirrors `User`
- `tests/test_articles.py` -> `tests/models/test_article.py` (Article + ArticleComment/ArticleImage/ArticleHistory/ArticleTag/ArticleNotification/ArticleSubscriber) - mirrors `Article`
- `tests/test_public_ids.py` -> `tests/models/test_public_ids.py` (keep name) - mirrors `djangoapp/models/public_ids.py` and `BaseModel.public_id`

Stay (not model tests):
- `tests/test_images.py` - shared helper (`_make_image` / `_make_png_bytes`, no `TestCase`); imported by `tests/playwright/test_articles.py`, `tests/views/test_articles.py`, and the moved `tests/models/test_article.py`
- `tests/test_filters.py`, `tests/test_serializers.py`, `tests/test_utils.py` - test other layers
- `tests/test_createrows.py`, `tests/test_deletenotifications.py`, `tests/test_maintain.py` - command tests (live under/with `tests/commands/`)

### Notes

- No inter-test imports break: only `test_images._make_image` is imported by the moved files (and it stays in `tests/`), so `from djangoapp.tests.test_images import _make_image` keeps resolving.
- `run` script `specialcoverage` (line 79) hard-codes the label `djangoapp.tests.test_models`; update it to `djangoapp.tests.models` so model coverage runs the whole package (improvement: it will now also exercise article/user/public_id model tests, not just `test_base.py`).
- Django test labels change: e.g. `djangoapp.tests.test_models.RowUpdateModelTest` -> `djangoapp.tests.models.test_base.RowUpdateModelTest`. Default `DiscoverRunner` finds `tests/models/` once it has an `__init__.py`.

### Plan

- Create `tests/models/__init__.py`.
- `git mv` each of the 4 files to its new path/name.
- Update `run:79` label.
- Verify discovery + lint.

### Checklist

#### Phase 1: Create package and move files

- [x] create `djangoapp/tests/models/__init__.py`
- [x] `git mv djangoapp/tests/test_models.py djangoapp/tests/models/test_base.py`
- [x] `git mv djangoapp/tests/test_user_model.py djangoapp/tests/models/test_user.py`
- [x] `git mv djangoapp/tests/test_articles.py djangoapp/tests/models/test_article.py`
- [x] `git mv djangoapp/tests/test_public_ids.py djangoapp/tests/models/test_public_ids.py`

#### Phase 2: Update references

- [x] update `run` `specialcoverage` (line 79): `djangoapp.tests.test_models` -> `djangoapp.tests.models`

#### Phase 3: Verify

- [x] `uv run ruff check` clean
- [x] `uv run mypy .` clean
- [x] discover + run the moved tests: `uv run manage.py test djangoapp.tests.models --exclude-tag playwright --noinput`
- [x] confirm `test_images._make_image` import still resolves (covered by the test run)
