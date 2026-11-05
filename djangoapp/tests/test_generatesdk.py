"""Unit tests for the ``generatesdk`` command (pydantic → zod + client).

Drives ``manage.py generatesdk`` against the synthetic module
``djangoapp.tests.sdk_fixture`` and pins the emitted TypeScript: models
marked with ``ExportedSchemaMixin`` become zod consts (exact class names,
Decimal → z.string(), Literal → z.enum, nullable/optional fields), client
functions named ``{method}_{view}`` wrap ninjaPost/ninjaGet/ninjaDelete,
and ops without a JSON response (or with an unmarked schema) skip visibly.
"""

from __future__ import annotations

from io import StringIO
from pathlib import Path

from django.core.management import call_command

from djangoapp.tests._base import BaseTestCase

OUT_PATH = Path("djangoapp/tests/out/sdk_fixture_sdk.ts")


class GeneratesdkTests(BaseTestCase):
    """``generatesdk`` output contract, driven against ``sdk_fixture``.

    - test_flagged_models_exported_with_exact_names, marked models → zod consts under class names
    - test_decimal_maps_to_string, Decimal → z.string()
    - test_literal_becomes_enum, string Literal → z.enum
    - test_nullable_and_optional, defaulted optional field → .nullable().optional()
    - test_dependencies_emitted_before_users, referenced models precede their users
    - test_unflagged_model_not_exported, unmarked model is never a schema export
    - test_get_named_method_view_with_typed_query, GET → ninjaGet + typed query model
    - test_post_named_method_view_with_scalar_query, scalar POST param rides params
    - test_delete_named_method_view_wraps_ninja_delete, DELETE → ninjaDelete
    - test_page_op_skipped_visibly, an op with no JSON response skips with a comment
    - test_mount_prefix_appears_in_urls, URLs carry the API mount prefix
    - test_unflagged_schema_op_skipped_visibly, unmarked response schema skips, named
    - test_api_less_module_emits_schemas_only, an API-less module (pages only)
      still exports its flagged models, with no client functions
    """

    emitted: str = ""

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        out = StringIO()
        call_command("generatesdk", "djangoapp.tests.sdk_fixture", OUT_PATH, stdout=out)
        with OUT_PATH.open(encoding="utf-8") as handle:
            cls.emitted = handle.read()

    @classmethod
    def tearDownClass(cls) -> None:
        OUT_PATH.unlink()
        super().tearDownClass()

    def test_flagged_models_exported_with_exact_names(self) -> None:
        """Marked models export as zod consts under their class names."""
        self.assertIn("export const Item = z.object({", self.emitted)
        self.assertIn("export const ItemPageProps = z.object({", self.emitted)
        self.assertIn("export const ItemResponse = z.object({", self.emitted)

    def test_decimal_maps_to_string(self) -> None:
        """Decimal → z.string() (money is a string on the wire)."""
        self.assertIn("price: z.string(),", self.emitted)

    def test_literal_becomes_enum(self) -> None:
        """A string Literal becomes z.enum of its values."""
        self.assertIn("label: z.enum(['a', 'b']),", self.emitted)

    def test_nullable_and_optional(self) -> None:
        """A defaulted optional field is .nullable().optional()."""
        self.assertIn("note: z.string().nullable().optional(),", self.emitted)

    def test_dependencies_emitted_before_users(self) -> None:
        """Referenced models are emitted before the models that use them."""
        self.assertLess(
            self.emitted.index("export const Item ="),
            self.emitted.index("export const ItemPageProps ="),
        )

    def test_unflagged_model_not_exported(self) -> None:
        """An unmarked model is never a schema export (a skip may name it)."""
        self.assertNotIn("export const SecretInternal", self.emitted)

    def test_get_named_method_view_with_typed_query(self) -> None:
        """A GET op takes a typed query model and wraps ninjaGet with params."""
        self.assertIn(
            "export const get_list_items = (query: z.input<typeof Filters>) =>",
            self.emitted,
        )
        self.assertIn(
            "ninjaGet(ItemResponse, `/fixture/items`, { params: query })",
            self.emitted,
        )

    def test_post_named_method_view_with_scalar_query(self) -> None:
        """A scalar POST param is a query param (ninja's own resolution)."""
        self.assertIn(
            "export const post_set_price = (publicId: string, query: { price: string }) =>",
            self.emitted,
        )
        self.assertIn(
            "ninjaPost(ItemResponse, `/fixture/items/${publicId}/price`, undefined, { params: query })",
            self.emitted,
        )

    def test_delete_named_method_view_wraps_ninja_delete(self) -> None:
        """A DELETE op wraps ninjaDelete."""
        self.assertIn(
            "export const delete_delete_item = (publicId: string) =>",
            self.emitted,
        )
        self.assertIn(
            "ninjaDelete(ItemResponse, `/fixture/items/${publicId}`)",
            self.emitted,
        )

    def test_page_op_skipped_visibly(self) -> None:
        """An op with no JSON response skips with a visible comment."""
        self.assertIn("// skipped: GET /fixture/page — no response schema (page op)", self.emitted)

    def test_mount_prefix_appears_in_urls(self) -> None:
        """Generated URLs carry the API's mount prefix (/fixture here)."""
        self.assertIn("`/fixture/items`,", self.emitted)
        self.assertIn("`/fixture/items/${publicId}/price`,", self.emitted)

    def test_unflagged_schema_op_skipped_visibly(self) -> None:
        """An op whose response schema isn't marked skips, naming the schema."""
        self.assertIn(
            "// skipped: POST /fixture/internal — response schema SecretInternal not exported",
            self.emitted,
        )

    def test_api_less_module_emits_schemas_only(self) -> None:
        """A module with no NinjaAPI (pages only) still exports its schemas."""
        # djangoapp.views.manage lost its API when its ops became page views;
        # its flagged props models must still reach the sdk.
        out = Path("djangoapp/tests/out/manage_sdk.ts")
        try:
            call_command("generatesdk", "djangoapp.views.manage", out)
            with out.open(encoding="utf-8") as handle:
                emitted = handle.read()
        finally:
            out.unlink()
        self.assertIn("export const ModelListProps = z.object({", emitted)
        self.assertNotIn("ninjaPost(", emitted)
