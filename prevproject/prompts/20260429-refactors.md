# Rename `.text` annotated attribute to `.annotated_text`

The annotation parameter name `.annotate(text=...)` on model instances clashes with the common word "text", forcing `getattr` fallbacks and `# type: ignore[attr-defined]` suppressions everywhere. Rename the **Python attribute** to `.annotated_text`. The **dict key `"text"`** in API responses stays unchanged (it's the external contract).

### Scope: what changes vs what stays

| Kind | Example | Action |
|------|---------|--------|
| Annotate param | `.annotate(text=...)` | → `.annotate(annotated_text=...)` |
| Instance attribute access | `obj.text` | → `obj.annotated_text` |
| `getattr` with `"text"` | `getattr(annotated_row, "text", ...)` | → `annotated_row.annotated_text` (direct access) |
| mypy suppressions | `# type: ignore[attr-defined]` on `.text` lines | Remove |
| Dict key in API output | `{"id": ..., "text": ...}` | **Keep as `"text"`** |
| Pydantic schema | `responses.py` discriminator `"text"` | **Keep as `"text"`** |
| Frontend `.text` | `opt.text`, `u.text` on response objects | **Keep** (reads dict key) |
| `CharTextFilter.text` | `filters.py` pydantic field | **Keep** (unrelated) |
| `text_field` | Django model field name | **Keep** (unrelated) |

### Checklist

- [x] **models.py** — `queryset_with_title()` annotate parameter
    - [x] Line 237: `.annotate(text=cls.title_annotation)` → `.annotate(annotated_text=cls.title_annotation)`
- [x] **models.py** — `search_text()` annotate parameter
    - [x] Line 266: `.annotate(text=cls.title_annotation)` → `.annotate(annotated_text=cls.title_annotation)`
- [x] **models.py** — `ProxyUser.search_text()` annotate parameters
    - [x] Lines 1652, 1667: `.annotate(text=cls.title_annotation)` → `.annotate(annotated_text=cls.title_annotation)`
- [x] **models.py** — `_build_row_update_response()` getattr fallback
    - [x] Line 932: `getattr(u, "text", "")` → `u.annotated_text`
- [x] **models.py** — `add_titles_to_foreign_key_columns()` attribute access
    - [x] Line 1109: `obj.text` → `obj.annotated_text`, remove `# type: ignore[attr-defined]`
- [x] **models.py** — Added `annotated_text: str` declaration on `BaseBaseModel` to satisfy mypy
- [x] **views.py** — search endpoint
    - [x] Line 89: `obj.text` → `obj.annotated_text`, remove `# type: ignore[attr-defined]`
- [x] **views.py** — row update references
    - [x] Line 496: `u.text` → `u.annotated_text`, remove `# type: ignore[attr-defined] # text is annotated`
- [x] **views.py** — `_generate_references()`
    - [x] Line 530: `obj.text` → `obj.annotated_text`, remove `# type: ignore[attr-defined]  # text is an annotated field`
- [x] **views.py** — row details title
    - [x] Line 804: `str(getattr(annotated_row, "text", row))` → `str(annotated_row.annotated_text)`
- [x] **views.py** — FK search results
    - [x] Line 978: `row.text` → `row.annotated_text`
- [x] **views.py** — SlotDemo prev/next navigation
    - [x] Line 1313: `str(getattr(annotated, "text", prev_row))` → `str(annotated.annotated_text)`
    - [x] Line 1317: `str(getattr(annotated, "text", next_row))` → `str(annotated.annotated_text)`
- [x] **serializers.py** — `_crud_value_foreignkey()`
    - [x] Line 425: `annotated_obj.text` → `annotated_obj.annotated_text`, remove `# type: ignore[attr-defined]`
- [x] **serializers.py** — `_row_update_value_foreignkey()`
    - [x] Line 568: `getattr(annotated_obj, "text", str(annotated_obj))` → `annotated_obj.annotated_text`
- [x] **tests/test_models.py** — search text annotation assertions
    - [x] Line 681: `user.text` → `user.annotated_text`
    - [x] Line 729: `user.text` → `user.annotated_text`
- [x] Run `./run checkall` and fix any failures
