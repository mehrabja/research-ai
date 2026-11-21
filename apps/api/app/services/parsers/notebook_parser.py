"""Static, non-executing Jupyter Notebook inspection.

The parser reads notebook JSON and Python syntax trees only. It never invokes
a kernel, executes a cell, renders output, downloads dependencies, or stores
cell source/output payloads in analysis metadata.
"""
from __future__ import annotations

import ast
import json
import re
from collections import Counter
from dataclasses import replace
from typing import Any

from app.services.parsers.base import CodeParseResult, RawDependency, RawSymbol
from app.services.parsers.python_parser import parse_python

PARSER_NAME = "jupyter-static"
PARSER_VERSION = "m21.1"

_PYTHON_KERNELS = frozenset({"python", "ipython"})
_PYTHON_CELL_MAGICS = frozenset(
    {"time", "timeit", "capture", "prun", "debug", "pypy", "python"}
)
_CELL_MAGIC_RE = re.compile(r"^%%([A-Za-z][A-Za-z0-9_-]*)")
_OUTPUT_TYPES = frozenset({"stream", "display_data", "execute_result", "error"})

_EMPTY_INDICATORS = {
    "eval_calls": 0,
    "exec_calls": 0,
    "dynamic_import_calls": 0,
    "subprocess_calls": 0,
    "os_system_calls": 0,
    "get_ipython_calls": 0,
}


def _failed(source: str, error: str) -> CodeParseResult:
    return CodeParseResult(
        parser=PARSER_NAME,
        parser_version=PARSER_VERSION,
        supported=True,
        symbols=(),
        dependencies=(),
        line_count=source.count("\n") + (0 if source.endswith("\n") else 1),
        character_count=len(source),
        module_docstring=None,
        error=error[:500],
        analysis_meta={
            "analysis_kind": "jupyter_notebook",
            "static_only": True,
            "execution_performed": False,
        },
    )


def _safe_label(value: Any, *, default: str = "unknown") -> str:
    if not isinstance(value, str):
        return default
    value = " ".join(value.split())
    if not value:
        return default
    return value[:80]


def _cell_source(value: Any) -> str | None:
    if isinstance(value, str):
        return value
    if isinstance(value, list) and all(isinstance(part, str) for part in value):
        return "".join(value)
    return None


def _strip_ipython_lines(source: str) -> tuple[str, int, int, bool]:
    """Remove line/cell magics before Python AST parsing; never run them."""
    kept: list[str] = []
    magic_lines = 0
    shell_escape_lines = 0
    skip_cell = False

    for line in source.splitlines():
        stripped = line.lstrip()
        if not stripped:
            kept.append(line)
            continue

        if stripped.startswith("%%"):
            magic_lines += 1
            match = _CELL_MAGIC_RE.match(stripped)
            magic_name = match.group(1).lower() if match else ""
            if magic_name in {"bash", "sh", "script", "javascript", "js", "html", "sql", "r"}:
                shell_escape_lines += int(magic_name in {"bash", "sh", "script"})
                skip_cell = True
            elif magic_name not in _PYTHON_CELL_MAGICS:
                skip_cell = True
            continue

        if stripped.startswith(("%", "!")):
            magic_lines += 1
            if stripped.startswith("!"):
                shell_escape_lines += 1
            continue

        kept.append(line)

    return "\n".join(kept), magic_lines, shell_escape_lines, skip_cell


def _static_indicators(source: str) -> dict[str, int]:
    indicators = dict(_EMPTY_INDICATORS)
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return indicators

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if isinstance(func, ast.Name):
            if func.id == "eval":
                indicators["eval_calls"] += 1
            elif func.id == "exec":
                indicators["exec_calls"] += 1
            elif func.id == "__import__":
                indicators["dynamic_import_calls"] += 1
            elif func.id == "get_ipython":
                indicators["get_ipython_calls"] += 1
        elif isinstance(func, ast.Attribute):
            if isinstance(func.value, ast.Name):
                if func.value.id == "os" and func.attr == "system":
                    indicators["os_system_calls"] += 1
                elif func.value.id == "subprocess" and func.attr in {
                    "run", "call", "Popen", "check_call", "check_output"
                }:
                    indicators["subprocess_calls"] += 1
    return indicators


def parse_notebook(
    source: str,
    *,
    max_cells: int = 2000,
    max_cell_source_chars: int = 250_000,
) -> CodeParseResult:
    """Analyze bounded notebook structure and Python syntax without execution."""
    if max_cells < 1 or max_cell_source_chars < 1:
        return _failed(source, "invalid notebook analysis limits")

    try:
        notebook = json.loads(source)
    except (json.JSONDecodeError, RecursionError):
        return _failed(source, "invalid notebook JSON")

    if not isinstance(notebook, dict):
        return _failed(source, "notebook root must be a JSON object")

    nbformat = notebook.get("nbformat")
    if isinstance(nbformat, bool) or nbformat != 4:
        return CodeParseResult(
            parser=PARSER_NAME,
            parser_version=PARSER_VERSION,
            supported=False,
            symbols=(),
            dependencies=(),
            line_count=source.count("\n") + (0 if source.endswith("\n") else 1),
            character_count=len(source),
            module_docstring=None,
            error=None,
            analysis_meta={
                "analysis_kind": "jupyter_notebook",
                "static_only": True,
                "execution_performed": False,
                "unsupported_nbformat": nbformat,
            },
        )

    cells = notebook.get("cells")
    if not isinstance(cells, list):
        return _failed(source, "notebook cells must be a JSON array")

    metadata = notebook.get("metadata")
    if not isinstance(metadata, dict):
        metadata = {}
    kernelspec = metadata.get("kernelspec")
    if not isinstance(kernelspec, dict):
        kernelspec = {}
    language_info = metadata.get("language_info")
    if not isinstance(language_info, dict):
        language_info = {}
    kernel_name = _safe_label(kernelspec.get("name"))
    kernel_language = _safe_label(
        language_info.get("name") or kernelspec.get("language")
    ).lower()
    is_python = kernel_language in _PYTHON_KERNELS

    selected_cells = cells[:max_cells]
    cells_truncated = len(cells) > len(selected_cells)
    cell_type_counts: Counter[str] = Counter()
    output_type_counts: Counter[str] = Counter()
    execution_counts: list[int] = []
    unexecuted_code_cells = 0
    total_outputs = 0
    total_source_chars = 0
    total_lines = 0
    source_truncated = False
    malformed_cells = 0
    python_cells_analyzed = 0
    python_cells_failed = 0
    python_cells_skipped = 0
    magic_line_count = 0
    shell_escape_line_count = 0
    static_indicators = dict(_EMPTY_INDICATORS)
    symbols: list[RawSymbol] = []
    dependencies: list[RawDependency] = []
    complexity_sum = 0.0
    complexity_functions = 0
    cell_diagnostics: list[dict[str, Any]] = []

    for cell_index, cell in enumerate(selected_cells):
        if not isinstance(cell, dict):
            malformed_cells += 1
            continue

        raw_cell_type = cell.get("cell_type")
        cell_type = raw_cell_type if raw_cell_type in {
            "code", "markdown", "raw"
        } else "unknown"
        cell_type_counts[cell_type] += 1

        raw_source = _cell_source(cell.get("source", ""))
        if raw_source is None:
            malformed_cells += 1
            continue

        remaining_chars = max_cell_source_chars - total_source_chars
        if remaining_chars <= 0:
            source_truncated = True
            break
        cell_source = raw_source
        if len(cell_source) > remaining_chars:
            cell_source = cell_source[:remaining_chars]
            source_truncated = True
        total_source_chars += len(cell_source)
        total_lines += (
            cell_source.count("\n")
            + (1 if cell_source and not cell_source.endswith("\n") else 0)
        )

        if cell_type != "code":
            continue

        execution_count = cell.get("execution_count")
        if (
            isinstance(execution_count, int)
            and not isinstance(execution_count, bool)
            and execution_count >= 0
        ):
            execution_counts.append(execution_count)
        else:
            unexecuted_code_cells += 1

        outputs = cell.get("outputs", [])
        if isinstance(outputs, list):
            total_outputs += len(outputs)
            for output in outputs[:1000]:
                if not isinstance(output, dict):
                    continue
                output_type = output.get("output_type")
                label = output_type if output_type in _OUTPUT_TYPES else "other"
                output_type_counts[label] += 1

        if not is_python:
            python_cells_skipped += 1
            continue
        if source_truncated and len(cell_source) < len(raw_source):
            python_cells_skipped += 1
            continue

        python_source, magic_count, shell_count, skip_cell = _strip_ipython_lines(
            cell_source
        )
        magic_line_count += magic_count
        shell_escape_line_count += shell_count
        if skip_cell:
            python_cells_skipped += 1
            continue

        parsed = parse_python(python_source)
        if parsed.error is not None:
            python_cells_failed += 1
            if len(cell_diagnostics) < 100:
                cell_diagnostics.append(
                    {
                        "cell_index": cell_index,
                        "diagnostic": "python_syntax_error",
                    }
                )
            continue

        python_cells_analyzed += 1
        static = _static_indicators(python_source)
        for key, value in static.items():
            static_indicators[key] += value

        for symbol in parsed.symbols:
            symbol_meta = dict(symbol.meta)
            symbol_meta["notebook_cell_index"] = cell_index
            symbols.append(replace(symbol, meta=symbol_meta))
        for dependency in parsed.dependencies:
            dependency_meta = dict(dependency.meta)
            dependency_meta["notebook_cell_index"] = cell_index
            dependencies.append(
                replace(dependency, meta=dependency_meta)
            )

        if parsed.complexity_score is not None:
            functions = sum(
                1
                for symbol in parsed.symbols
                if symbol.symbol_type in ("function", "method")
            )
            complexity_sum += parsed.complexity_score * functions
            complexity_functions += functions

    previous_execution_count: int | None = None
    out_of_order_execution_counts = 0
    duplicate_execution_counts = 0
    seen_execution_counts: set[int] = set()
    for count in execution_counts:
        if count in seen_execution_counts:
            duplicate_execution_counts += 1
        seen_execution_counts.add(count)
        if previous_execution_count is not None and count < previous_execution_count:
            out_of_order_execution_counts += 1
        previous_execution_count = count

    analysis_meta = {
        "analysis_kind": "jupyter_notebook",
        "notebook": {
            "nbformat": 4,
            "nbformat_minor": (
                notebook.get("nbformat_minor")
                if isinstance(notebook.get("nbformat_minor"), int)
                and not isinstance(notebook.get("nbformat_minor"), bool)
                else None
            ),
            "kernel_name": kernel_name,
            "kernel_language": kernel_language,
            "analysis_mode": "python_ast" if is_python else "structure_only",
            "cell_count_total": len(cells),
            "cell_count_analyzed": len(selected_cells),
            "cell_type_counts": dict(cell_type_counts),
            "cells_truncated": cells_truncated,
            "source_chars_scanned": total_source_chars,
            "source_truncated": source_truncated,
            "line_coordinate_system": "cell_local",
            "execution": {
                "executed_code_cells": len(execution_counts),
                "unexecuted_code_cells": unexecuted_code_cells,
                "duplicate_execution_counts": duplicate_execution_counts,
                "out_of_order_execution_counts": out_of_order_execution_counts,
            },
            "outputs": {
                "output_count": total_outputs,
                "output_type_counts": dict(output_type_counts),
                "output_payloads_stored": False,
            },
            "python": {
                "cells_analyzed": python_cells_analyzed,
                "cells_with_syntax_errors": python_cells_failed,
                "cells_skipped": python_cells_skipped,
                "magic_lines_removed": magic_line_count,
                "shell_escape_lines_observed": shell_escape_line_count,
                "cell_diagnostics": cell_diagnostics,
            },
            "static_execution_indicators": {
                **static_indicators,
                "note": "Static indicators only; not a security verdict.",
            },
            "malformed_cells": malformed_cells,
            "cell_source_stored": False,
            "execution_performed": False,
        },
    }
    complexity = (
        round(complexity_sum / complexity_functions, 3)
        if complexity_functions
        else None
    )
    return CodeParseResult(
        parser=PARSER_NAME,
        parser_version=PARSER_VERSION,
        supported=True,
        symbols=tuple(symbols),
        dependencies=tuple(dependencies),
        line_count=total_lines,
        character_count=total_source_chars,
        module_docstring=None,
        error=None,
        complexity_score=complexity,
        analysis_meta=analysis_meta,
    )


__all__ = ["parse_notebook"]
