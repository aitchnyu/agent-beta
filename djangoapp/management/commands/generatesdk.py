"""Generate <feature>_sdk.ts for one module: zod schemas + typed client.

Walks the module's routers and ``ExportedSchemaMixin``-marked pydantic
models, emitting one file:

- a zod const per model, exact class name (``LogoutResponse``); fields
  verbatim — ``Decimal`` → ``z.string()``, ``Literal`` → ``z.enum``,
  ``X | None`` → ``.nullable()``, defaults → ``.optional()``, Field
  constraints → the matching zod; dependencies come before their users.
- a ``{method}_{view}`` function per JSON operation wrapping
  ninjaPost/ninjaGet/ninjaDelete (CSRF + 422→NinjaError stay in http.ts).
  URLs carry the API's mount prefix; scalars are query params, pydantic
  params are bodies on writes / query models on GETs; non-JSON or
  unexported operations are skipped with a comment.

Example shape (from ``users_sdk.ts``):

    import { z } from "zod"
    import { ninjaGet, ninjaPost } from "@/system/utils/http"

    export const UserSearchItem = z.object({
      public_id: z.string(),
      username: z.string(),
      title: z.string(),
    })

    ...

    export const post_edit_submit = (
      publicId: string,
      body: z.input<typeof UserUpdateSchema>,
    ) => ninjaPost(MessageResponse, `/users/api/${publicId}/edit`, body)

    // skipped: GET /users/list — no response schema (page op)

usage: manage.py generatesdk <module> <out-file-under-frontend/>
The output is generated code: regenerate, never hand-edit.
"""

from __future__ import annotations

import enum
import importlib
import pkgutil
import re
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal, Union, get_args, get_origin
from uuid import UUID

from django.core.management.base import BaseCommand, CommandError
from ninja import NinjaAPI
from ninja.constants import NOT_SET
from pydantic import BaseModel

from djangoapp.ninja_api import ExportedSchemaMixin

if TYPE_CHECKING:
    import argparse
    from collections.abc import Iterator

    from pydantic.fields import FieldInfo

HTTP_METHODS = {"get", "post", "put", "patch", "delete"}
NoneType = type(None)


class Command(BaseCommand):
    help = "Generate a typed zod client (<feature>_sdk.ts) for a module's routers."

    def add_arguments(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument("module", help="package.module whose routers to read")
        parser.add_argument(
            "out",
            help="output file path, relative to cwd (e.g. frontend/src/system/schemas/users_sdk.ts)",
        )

    def handle(self, **options: Any) -> None:
        module_name = str(options["module"])
        out_file = str(options["out"])
        try:
            module = importlib.import_module(module_name)
        except ImportError as exc:
            msg = f"cannot import {module_name!r}: {exc}"
            raise CommandError(msg) from exc

        generator = _SdkGenerator()
        flagged = list(_flagged_models(module))
        apis = [
            member for name in dir(module) if isinstance(member := getattr(module, name), NinjaAPI)
        ]
        if not apis and not flagged:
            msg = f"no NinjaAPI or exported schemas found in {module_name!r}"
            raise CommandError(msg)
        for api in apis:
            for registration in api._router_registrations:
                prefix, router = registration[0], registration[1]
                probe = NinjaAPI()
                probe.add_router("", router)
                for path, path_view in router.path_operations.items():
                    full_path = ("" if not prefix else "/" + prefix.strip("/")) + path
                    for operation in path_view.operations:
                        methods = {m.lower() for m in operation.methods} & HTTP_METHODS
                        if not methods:
                            continue
                        if len(methods) > 1:
                            msg = f"{full_path}: multiple methods on one operation"
                            raise CommandError(msg)
                        generator.add_call(operation, full_path, methods.pop())
        for model in flagged:
            generator.collect(model)

        rendered = generator.render()
        Path(out_file).parent.mkdir(parents=True, exist_ok=True)
        Path(out_file).write_text(rendered, encoding="utf-8")


class _ModelSet:
    """Models an sdk file needs, kept in dependency-first order."""

    def __init__(self) -> None:
        self._by_name: dict[str, type[BaseModel]] = {}
        self.order: list[type[BaseModel]] = []
        self._done: set[str] = set()

    def add(self, model: type[BaseModel]) -> str:
        """Register ``model`` and its model references, deps emitted first."""
        name = model.__name__
        if name in self._done:
            return name
        known = self._by_name.get(name)
        if known is not None and known is not model:
            msg = f"model name collision: {name!r} is two different classes"
            raise CommandError(msg)
        self._done.add(name)
        self._by_name[name] = model
        for field in model.model_fields.values():
            for referenced in _model_refs(field.annotation):
                self.add(referenced)
        self.order.append(model)
        return name

    def ordered(self) -> list[type[BaseModel]]:
        return self.order


def _model_refs(annotation: Any) -> list[type[BaseModel]]:
    """BaseModel classes directly referenced by an annotation (no recursion)."""
    origin = get_origin(annotation)
    if origin is None:
        if isinstance(annotation, type) and issubclass(annotation, BaseModel):
            return [annotation]
        return []
    return [
        arg for arg in get_args(annotation) if isinstance(arg, type) and issubclass(arg, BaseModel)
    ]


class _ClientCall:
    def __init__(self, fn_name: str, method: str, url: str, args: str, transport: str) -> None:
        self.fn_name = fn_name
        self.method = method
        self.url = url
        self.args = args
        self.transport = transport

    def text(self) -> str:
        return f"export const {self.fn_name} = ({self.args}) =>\n  {self.transport}\n"


class _SdkGenerator:
    def __init__(self) -> None:
        self.models = _ModelSet()
        self.calls: list[_ClientCall] = []
        self.skipped: list[str] = []
        self._fn_names: set[str] = set()

    def collect(self, model: type[BaseModel]) -> None:
        self.models.add(model)

    def add_call(self, operation: Any, path: str, method: str) -> None:
        fn_name = f"{method}_{operation.view_func.__name__}"
        if fn_name in self._fn_names:
            msg = f"client function name collision: {fn_name!r}"
            raise CommandError(msg)
        self._fn_names.add(fn_name)

        response_model = _unwrap_response(operation, "200") or _unwrap_response(operation, "201")
        if response_model is None:
            self.skipped.append(f"{method.upper()} {path} — no response schema (page op)")
            return
        if not issubclass(response_model, ExportedSchemaMixin):
            self.skipped.append(
                f"{method.upper()} {path} — response schema {response_model.__name__} not exported"
            )
            return
        self.models.add(response_model)

        path_params = [match.group(1) for match in re.finditer(r"\{([^}]+)\}", path)]
        args = [f"{_camel(p)}: string" for p in path_params]
        url = re.sub(r"\{([^}]+)\}", lambda m: "${" + _camel(m.group(1)) + "}", path)

        query_model: type[BaseModel] | None = None
        query_fields: list[str] = []
        body_model: type[BaseModel] | None = None
        for param in operation.signature.params:
            annotation = param.annotation
            if isinstance(annotation, type) and issubclass(annotation, BaseModel):
                if not issubclass(annotation, ExportedSchemaMixin):
                    self.skipped.append(
                        f"{method.upper()} {path} — schema {annotation.__name__} not exported"
                    )
                    return
                if method == "get":
                    if query_model is not None:
                        msg = f"{path}: more than one query model"
                        raise CommandError(msg)
                    query_model = annotation
                else:
                    if body_model is not None:
                        msg = f"{path}: more than one body model"
                        raise CommandError(msg)
                    body_model = annotation
                continue
            if param.name in path_params:
                continue
            # Scalars resolve from the query string on EVERY method (ninja's
            # own resolution), so they always ride the params object.
            query_fields.append(_param_line(param, self.models))
        if body_model is not None:
            self.models.add(body_model)
            args.append(f"body: z.input<typeof {body_model.__name__}>")
        if query_model is not None:
            self.models.add(query_model)
            args.append(f"query: z.input<typeof {query_model.__name__}>")
            uses_params = True
        elif query_fields:
            args.append("query: { " + ", ".join(query_fields) + " }")
            uses_params = True
        else:
            uses_params = False

        response_name = response_model.__name__
        if method == "get":
            transport = (
                f"ninjaGet({response_name}, `{url}`, {{ params: query }})"
                if uses_params
                else f"ninjaGet({response_name}, `{url}`)"
            )
        elif method == "delete":
            transport = (
                f"ninjaDelete({response_name}, `{url}`, body)"
                if body_model is not None
                else f"ninjaDelete({response_name}, `{url}`)"
            )
        elif body_model is None and not uses_params:
            transport = f"ninjaPost({response_name}, `{url}`)"
        else:
            data = "body" if body_model is not None else "undefined"
            params = ", { params: query }" if uses_params else ""
            transport = f"ninjaPost({response_name}, `{url}`, {data}{params})"
        self.calls.append(_ClientCall(fn_name, method, url, ", ".join(args), transport))

    def render(self) -> str:
        ordered_models = self.models.ordered()
        # `@` alias: a regenerated sdk never needs a hand-fixed relative path.
        http_import = "@/system/utils/http"
        imports = ['import { z } from "zod"\n']
        verbs = []
        if any(call.method == "get" for call in self.calls):
            verbs.append("ninjaGet")
        if any(call.method == "delete" for call in self.calls):
            verbs.append("ninjaDelete")
        if any(call.method not in ("get", "delete") for call in self.calls):
            verbs.append("ninjaPost")
        if verbs:
            imports.append(f'import {{ {", ".join(verbs)} }} from "{http_import}"\n')

        chunks = [
            (
                "// Auto-generated by ./run djangomanage generatesdk — zod schemas\n"
                "// from ExportedSchemaMixin models + typed client fns over http.ts.\n"
                "// Regenerate on payload changes; never hand-edit.\n"
            ),
            *imports,
            "\n",
        ]
        for model in ordered_models:
            fields = "\n".join(
                _field_line(name, field, self.models) for name, field in model.model_fields.items()
            )
            chunks.append(f"export const {model.__name__} = z.object({{\n{fields}\n}})\n\n")
        chunks.extend(call.text() + "\n" for call in self.calls)
        chunks.extend(f"// skipped: {skip}\n" for skip in self.skipped)
        rendered = re.sub(r"\n{3,}", "\n\n", "".join(chunks))
        return rendered.rstrip("\n") + "\n"


def _unwrap_response(operation: Any, status: str) -> type[BaseModel] | None:
    """Return the pydantic model behind a ninja response wrapper, or None."""
    wrapper = getattr(operation, "response_models", {}).get(int(status))
    if wrapper is None or wrapper is NOT_SET:
        return None
    fields = getattr(wrapper, "model_fields", {})
    if "response" not in fields:
        return None
    annotation = fields["response"].annotation
    if isinstance(annotation, type) and issubclass(annotation, BaseModel):
        return annotation
    return None


def _zod_expr(annotation: Any, models: _ModelSet) -> str:
    origin = get_origin(annotation)
    if origin is Union:
        non_none = [arg for arg in get_args(annotation) if arg is not NoneType]
        if len(non_none) == 1:
            return _zod_expr(non_none[0], models) + ".nullable()"
        msg = f"unsupported union: {annotation!r}"
        raise CommandError(msg)
    if origin is Literal:
        args = get_args(annotation)
        if all(isinstance(value, str) for value in args):
            values = ", ".join(repr(value) for value in args)
            return f"z.enum([{values}])"
        return "z.union([" + ", ".join(f"z.literal({value!r})" for value in args) + "])"
    if isinstance(annotation, type) and issubclass(annotation, enum.Enum):
        # StrEnum members serialize as their string value; other enums
        # (IntEnum) ride z.literal unions since z.enum is strings-only.
        enum_values = [member.value for member in annotation]
        if all(isinstance(value, str) for value in enum_values):
            rendered = ", ".join(repr(value) for value in enum_values)
            return f"z.enum([{rendered}])"
        return "z.union([" + ", ".join(f"z.literal({value!r})" for value in enum_values) + "])"
    if origin is list:
        (item,) = get_args(annotation) or (str,)
        return f"z.array({_zod_expr(item, models)})"
    if origin is dict:
        args = get_args(annotation)
        value_type = args[1] if len(args) > 1 else str
        return f"z.record(z.string(), {_zod_expr(value_type, models)})"
    if annotation is Decimal:
        return "z.string()"
    if annotation in (date, datetime, UUID):
        return "z.string()"
    if annotation is Any:
        return "z.any()"
    if annotation is str:
        return "z.string()"
    if annotation is int:
        return "z.number().int()"
    if annotation is float:
        return "z.number()"
    if annotation is bool:
        return "z.boolean()"
    if isinstance(annotation, type) and issubclass(annotation, BaseModel):
        models.add(annotation)
        return annotation.__name__
    msg = f"unsupported field type: {annotation!r}"
    raise CommandError(msg)


def _constraints(field: FieldInfo, expr: str) -> str:
    """Field(ge/le/min_length/max_length/multiple_of) → chained zod constraints."""
    numeric = expr.startswith("z.number()")
    for constraint in field.metadata:
        kind = type(constraint).__name__
        if numeric and kind == "Ge":
            expr += f".gte({constraint.ge})"
        elif numeric and kind == "Le":
            expr += f".lte({constraint.le})"
        elif kind == "MinLen":
            expr += f".min({constraint.min_length})"
        elif kind == "MaxLen":
            expr += f".max({constraint.max_length})"
        elif kind == "MultipleOf":
            expr += f".multipleOf({constraint.multiple_of})"
    return expr


def _field_line(name: str, field: FieldInfo, models: _ModelSet) -> str:
    wire = field.serialization_alias or field.validation_alias or name
    expr = _constraints(field, _zod_expr(field.annotation, models))
    if not field.is_required():
        expr += ".optional()"
    return f"  {wire}: {expr},"


def _param_line(param: Any, models: _ModelSet) -> str:
    """One scalar query field as a TS object-type member (not a zod expr)."""
    _ = models  # signature symmetry with _field_line
    # param.source is ninja's FieldInfo (a Query/Body param): its
    # is_required() is the one API that reflects the view's default.
    optional = "" if param.source.is_required() else "?"
    wire = param.alias or param.name
    return f"{wire}{optional}: {_ts_type(param.annotation)}"


def _ts_type(annotation: Any) -> str:
    """Plain TS type text for scalar params (a VALUE expression would be invalid)."""
    if get_origin(annotation) is Literal:
        return " | ".join(repr(value) for value in get_args(annotation))
    if annotation is Decimal or annotation in (date, datetime, UUID) or annotation is str:
        return "string"
    if annotation in (int, float):
        return "number"
    if annotation is bool:
        return "boolean"
    return "string"


def _camel(name: str) -> str:
    return re.sub(r"_([a-z])", lambda match: match.group(1).upper(), name)


def _flagged_models(module: object) -> Iterator[type[BaseModel]]:
    """Yield the module tree's ExportedSchemaMixin-marked BaseModel subclasses."""
    seen: set[type[BaseModel]] = set()
    yield from _flagged_in_module(module, seen)
    if hasattr(module, "__path__"):
        for info in pkgutil.walk_packages(module.__path__, prefix=f"{module.__name__}."):  # type: ignore[attr-defined]
            submodule = importlib.import_module(info.name)
            yield from _flagged_in_module(submodule, seen)


def _flagged_in_module(module: object, seen: set[type[BaseModel]]) -> Iterator[type[BaseModel]]:
    for name in dir(module):
        candidate = getattr(module, name)
        if (
            isinstance(candidate, type)
            and issubclass(candidate, BaseModel)
            and candidate not in seen
            and candidate.__module__.startswith(str(getattr(module, "__name__", "")))
            and issubclass(candidate, ExportedSchemaMixin)
        ):
            seen.add(candidate)
            yield candidate
