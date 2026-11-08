"""Unit tests for the ``generatesdk`` command (pydantic → zod + client).

Drives ``render_sdk`` against the synthetic api
``djangoapp.tests.sdk_fixture.fixture_api`` (whose op router nests one
add_router level under the mounted router) and pins the emitted
TypeScript: every model REACHABLE from an endpoint (responses, bodies,
query models, transitive field refs) becomes a zod const, client
functions named ``{method}_{view}`` wrap ninjaPost/ninjaGet/ninjaDelete
with the JOINED mount prefix in their URLs, props-shaped models not
referenced by any endpoint never emit, and non-JSON ops skip visibly.
"""

from __future__ import annotations

from django.core.management.base import CommandError

from djangoapp.management.commands.generatesdk import _join, render_sdk
from djangoapp.tests._base import BaseTestCase


class GeneratesdkTests(BaseTestCase):
    """``generatesdk`` output contract, driven against ``sdk_fixture``.

    - test_endpoint_models_exported_with_exact_names, reachable models → zod consts under class names
    - test_decimal_maps_to_string, Decimal → z.string()
    - test_literal_becomes_enum, string Literal → z.enum
    - test_nullable_and_optional, defaulted optional field → .nullable().optional()
    - test_dependencies_emitted_before_users, referenced models precede their users
    - test_body_model_emits_and_rides_the_client, a request body model emits and types the fn's body arg
    - test_props_model_not_referenced_never_emits, endpoint-unreachable models never emit
    - test_get_named_method_view_with_typed_query, GET → ninjaGet + typed query model
    - test_post_named_method_view_with_scalar_query, scalar POST param rides params
    - test_delete_named_method_view_wraps_ninja_delete, DELETE → ninjaDelete
    - test_non_json_op_skipped_visibly, an op with no JSON response skips with a comment
    - test_nested_mount_prefix_joins_in_urls, a router nested via add_router emits at its joined path
    - test_symbol_must_be_dotted, a bare name errors with the expected shape hint
    - test_symbol_must_resolve, an unknown attribute errors naming the module
    - test_symbol_must_be_an_api, a non-NinjaAPI attribute errors naming its type
    """

    emitted: str = ""

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.emitted = render_sdk("djangoapp.tests.sdk_fixture.fixture_api")

    def test_endpoint_models_exported_with_exact_names(self) -> None:
        """Every endpoint-reachable model exports as a zod const."""
        self.assertIn("export const Item = z.object({", self.emitted)
        self.assertIn("export const ItemResponse = z.object({", self.emitted)
        self.assertIn("export const Filters = z.object({", self.emitted)

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
            self.emitted.index("export const ItemResponse ="),
        )

    def test_body_model_emits_and_rides_the_client(self) -> None:
        """A request body model emits and types the client fn's body arg."""
        self.assertIn("export const ItemCreate = z.object({", self.emitted)
        self.assertIn(
            "export const post_create_item = (body: z.input<typeof ItemCreate>) =>",
            self.emitted,
        )
        self.assertIn(
            "ninjaPost(ItemResponse, `/fixture/nested/items/create`, body)",
            self.emitted,
        )

    def test_props_model_not_referenced_never_emits(self) -> None:
        """A model unreachable from any endpoint (page props) never emits."""
        self.assertNotIn("ItemPageProps", self.emitted)

    def test_get_named_method_view_with_typed_query(self) -> None:
        """A GET op takes a typed query model and wraps ninjaGet with params."""
        self.assertIn(
            "export const get_list_items = (query: z.input<typeof Filters>) =>",
            self.emitted,
        )
        self.assertIn(
            "ninjaGet(ItemResponse, `/fixture/nested/items`, { params: query })",
            self.emitted,
        )

    def test_post_named_method_view_with_scalar_query(self) -> None:
        """A scalar POST param is a query param (ninja's own resolution)."""
        self.assertIn(
            "export const post_set_price = (publicId: string, query: { price: string }) =>",
            self.emitted,
        )
        self.assertIn(
            "ninjaPost(ItemResponse, `/fixture/nested/items/${publicId}/price`, undefined, { params: query })",
            self.emitted,
        )

    def test_delete_named_method_view_wraps_ninja_delete(self) -> None:
        """A DELETE op wraps ninjaDelete."""
        self.assertIn(
            "export const delete_delete_item = (publicId: string) =>",
            self.emitted,
        )
        self.assertIn(
            "ninjaDelete(ItemResponse, `/fixture/nested/items/${publicId}`)",
            self.emitted,
        )

    def test_non_json_op_skipped_visibly(self) -> None:
        """An op with no JSON response skips with a visible comment."""
        self.assertIn(
            "// skipped: GET /fixture/nested/page — no response schema (non-JSON)",
            self.emitted,
        )

    def test_nested_mount_prefix_joins_in_urls(self) -> None:
        """A router nested via add_router emits at the JOINED path."""
        self.assertIn("`/fixture/nested/items`,", self.emitted)

    def test_root_nested_mount_contributes_no_path(self) -> None:
        """A ``/``-mounted router (the combined-api pattern) emits at the parent's path.

        A naive join would 404 on ``//path``.
        """
        self.assertEqual(_join("", "/"), "")
        self.assertEqual(_join("/fixture", "/"), "/fixture")
        self.assertEqual(_join("/fixture", ""), "/fixture")
        self.assertEqual(_join("/fixture", "/nested"), "/fixture/nested")

    def test_symbol_must_be_dotted(self) -> None:
        """A bare symbol name errors with the dotted-shape hint."""
        with self.assertRaises(CommandError) as ctx:
            render_sdk("notdotted")
        self.assertIn("dotted path", str(ctx.exception))

    def test_symbol_must_resolve(self) -> None:
        """An unknown attribute errors naming the module."""
        with self.assertRaises(CommandError) as ctx:
            render_sdk("djangoapp.tests.sdk_fixture.no_api")
        self.assertIn("has no attribute 'no_api'", str(ctx.exception))

    def test_symbol_must_be_an_api(self) -> None:
        """A non-NinjaAPI attribute errors naming its actual type."""
        with self.assertRaises(CommandError) as ctx:
            render_sdk("djangoapp.tests.sdk_fixture.router")
        self.assertIn("is a Router, not a NinjaAPI", str(ctx.exception))
