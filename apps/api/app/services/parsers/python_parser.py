"""M20 — Python parser via stdlib ``ast``."""
from __future__ import annotations

import ast

from app.services.parsers.base import (
    CodeParseResult,
    RawDependency,
    RawSymbol,
)

PARSER_NAME = "ast"
PARSER_VERSION = "py311"

_COMPLEXITY_NODES = (
    ast.If, ast.For, ast.AsyncFor, ast.While, ast.Try,
    ast.With, ast.AsyncWith, ast.BoolOp,
)


def _signature_for_function(node: ast.AST) -> str:
    assert isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    args = node.args
    parts: list[str] = []
    for a in args.posonlyargs:
        parts.append(a.arg)
    if args.posonlyargs:
        parts.append("/")
    for a in args.args:
        parts.append(a.arg)
    if args.vararg:
        parts.append("*" + args.vararg.arg)
    elif args.kwonlyargs:
        parts.append("*")
    for a in args.kwonlyargs:
        parts.append(a.arg)
    if args.kwarg:
        parts.append("**" + args.kwarg.arg)
    prefix = "async def" if isinstance(node, ast.AsyncFunctionDef) else "def"
    returns = ""
    if node.returns is not None:
        try:
            returns = f" -> {ast.unparse(node.returns)}"
        except Exception:  # noqa: BLE001
            returns = ""
    return f"{prefix} {node.name}({', '.join(parts)}){returns}"


def _signature_for_class(node: ast.ClassDef) -> str:
    bases = []
    for b in node.bases:
        try:
            bases.append(ast.unparse(b))
        except Exception:  # noqa: BLE001
            continue
    if bases:
        return f"class {node.name}({', '.join(bases)})"
    return f"class {node.name}"


def _docstring(node: ast.AST) -> str | None:
    body = getattr(node, "body", None)
    if not body:
        return None
    first = body[0]
    if isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant):
        v = first.value.value
        if isinstance(v, str):
            return v.strip()[:4000] or None
    return None


def _complexity(node: ast.AST) -> int:
    return sum(1 for n in ast.walk(node) if isinstance(n, _COMPLEXITY_NODES))


def _is_constant_name(name: str) -> bool:
    return name.isupper() and len(name) > 1


def _safe_unparse(node: ast.AST) -> str:
    try:
        return ast.unparse(node)[:200]
    except Exception:  # noqa: BLE001
        return ""


def parse_python(source: str) -> CodeParseResult:
    line_count = source.count("\n") + (0 if source.endswith("\n") else 1)
    char_count = len(source)
    try:
        tree = ast.parse(source)
    except SyntaxError as exc:
        return CodeParseResult(
            parser=PARSER_NAME,
            parser_version=PARSER_VERSION,
            supported=True,
            symbols=(),
            dependencies=(),
            line_count=line_count,
            character_count=char_count,
            module_docstring=None,
            error=f"SyntaxError: {exc.msg} (line {exc.lineno})",
            complexity_score=None,
        )

    symbols: list[RawSymbol] = []
    dependencies: list[RawDependency] = []
    module_complexity = 0

    module_docstring = _docstring(tree)

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                dependencies.append(
                    RawDependency(
                        dependency_name=alias.name,
                        dependency_type="import",
                        line_number=node.lineno,
                        is_relative=False,
                        meta={"asname": alias.asname} if alias.asname else {},
                    )
                )
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            is_relative = node.level > 0
            prefix = "." * node.level
            dependencies.append(
                RawDependency(
                    dependency_name=f"{prefix}{module}",
                    dependency_type="from_import",
                    line_number=node.lineno,
                    is_relative=is_relative,
                    meta={"names": [a.name for a in node.names]},
                )
            )

    for node in tree.body:
        if isinstance(node, ast.Assign):
            for tgt in node.targets:
                if isinstance(tgt, ast.Name):
                    name = tgt.id
                    stype = (
                        "constant" if _is_constant_name(name) else "variable"
                    )
                    try:
                        sig = f"{name} = {ast.unparse(node.value)}"
                    except Exception:  # noqa: BLE001
                        sig = name
                    symbols.append(
                        RawSymbol(
                            symbol_type=stype,
                            name=name,
                            qualified_name=name,
                            parent_name=None,
                            line_start=node.lineno,
                            line_end=getattr(node, "end_lineno", node.lineno)
                            or node.lineno,
                            column_start=node.col_offset,
                            column_end=getattr(
                                node, "end_col_offset", None
                            ),
                            signature=sig[:500],
                        )
                    )
        elif isinstance(node, ast.AnnAssign) and isinstance(
            node.target, ast.Name
        ):
            name = node.target.id
            stype = "constant" if _is_constant_name(name) else "variable"
            try:
                sig = f"{name}: {ast.unparse(node.annotation)}"
                if node.value is not None:
                    sig += f" = {ast.unparse(node.value)}"
            except Exception:  # noqa: BLE001
                sig = name
            symbols.append(
                RawSymbol(
                    symbol_type=stype,
                    name=name,
                    qualified_name=name,
                    parent_name=None,
                    line_start=node.lineno,
                    line_end=getattr(node, "end_lineno", node.lineno)
                    or node.lineno,
                    signature=sig[:500],
                )
            )

    def _visit(node: ast.AST, parent: str | None) -> None:
        nonlocal module_complexity
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            qualified = f"{parent}.{node.name}" if parent else node.name
            stype = "method" if parent else "function"
            sym = RawSymbol(
                symbol_type=stype,
                name=node.name,
                qualified_name=qualified,
                parent_name=parent,
                line_start=node.lineno,
                line_end=getattr(node, "end_lineno", node.lineno)
                or node.lineno,
                column_start=node.col_offset,
                column_end=getattr(node, "end_col_offset", None),
                signature=_signature_for_function(node)[:500],
                docstring=_docstring(node),
                meta={
                    "decorators": [
                        _safe_unparse(d) for d in node.decorator_list
                    ]
                },
            )
            symbols.append(sym)
            module_complexity += _complexity(node)
            for child in node.body:
                _visit(child, qualified)
            return
        if isinstance(node, ast.ClassDef):
            qualified = f"{parent}.{node.name}" if parent else node.name
            sym = RawSymbol(
                symbol_type="class",
                name=node.name,
                qualified_name=qualified,
                parent_name=parent,
                line_start=node.lineno,
                line_end=getattr(node, "end_lineno", node.lineno)
                or node.lineno,
                column_start=node.col_offset,
                column_end=getattr(node, "end_col_offset", None),
                signature=_signature_for_class(node)[:500],
                docstring=_docstring(node),
                meta={
                    "decorators": [
                        _safe_unparse(d) for d in node.decorator_list
                    ]
                },
            )
            symbols.append(sym)
            for child in node.body:
                _visit(child, qualified)
            return

    for node in tree.body:
        _visit(node, None)

    complexity = None
    fn_count = sum(
        1 for s in symbols if s.symbol_type in ("function", "method")
    )
    if fn_count > 0:
        complexity = round(module_complexity / fn_count, 3)

    return CodeParseResult(
        parser=PARSER_NAME,
        parser_version=PARSER_VERSION,
        supported=True,
        symbols=tuple(symbols),
        dependencies=tuple(dependencies),
        line_count=line_count,
        character_count=char_count,
        module_docstring=module_docstring,
        error=None,
        complexity_score=complexity,
    )
