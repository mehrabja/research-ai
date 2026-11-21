from __future__ import annotations

import json

from app.domain.code_intelligence import Language
from app.services.parsers import parse_source
from app.services.parsers.notebook_parser import parse_notebook


def _notebook(cells: list[dict], *, kernel_language: str = "python") -> str:
    return json.dumps(
        {
            "nbformat": 4,
            "nbformat_minor": 5,
            "metadata": {
                "kernelspec": {
                    "name": f"{kernel_language}3",
                    "language": kernel_language,
                },
                "language_info": {"name": kernel_language},
            },
            "cells": cells,
        }
    )


def test_notebook_extracts_python_symbols_and_bounded_structure() -> None:
    source = _notebook(
        [
            {
                "cell_type": "markdown",
                "metadata": {},
                "source": ["# Experiment\n", "Private narrative is not persisted."],
            },
            {
                "cell_type": "code",
                "execution_count": 1,
                "metadata": {},
                "outputs": [
                    {
                        "output_type": "execute_result",
                        "data": {"text/plain": "SENSITIVE_OUTPUT_PAYLOAD"},
                    }
                ],
                "source": [
                    "import math\n",
                    "def area(radius):\n",
                    "    return math.pi * radius * radius\n",
                ],
            },
            {
                "cell_type": "code",
                "execution_count": None,
                "metadata": {},
                "outputs": [],
                "source": [
                    "%matplotlib inline\n",
                    "value = eval('2 + 2')\n",
                    "!echo this is observed, never run\n",
                ],
            },
            {
                "cell_type": "code",
                "execution_count": 1,
                "metadata": {},
                "outputs": [{"output_type": "stream", "text": "secret"}],
                "source": ["import os\n", "os.system('echo never run')\n"],
            },
        ]
    )

    result = parse_source(source=source, language=Language.NOTEBOOK)
    assert result.supported is True
    assert result.error is None
    assert result.parser == "jupyter-static"
    assert result.line_count > 0
    notebook_meta = result.analysis_meta["notebook"]
    assert notebook_meta["cell_count_total"] == 4
    assert notebook_meta["cell_type_counts"] == {"markdown": 1, "code": 3}
    assert notebook_meta["execution"]["executed_code_cells"] == 2
    assert notebook_meta["execution"]["unexecuted_code_cells"] == 1
    assert notebook_meta["execution"]["duplicate_execution_counts"] == 1
    assert notebook_meta["outputs"]["output_count"] == 2
    assert notebook_meta["outputs"]["output_type_counts"]["execute_result"] == 1
    assert notebook_meta["outputs"]["output_payloads_stored"] is False
    assert notebook_meta["python"]["magic_lines_removed"] == 2
    assert notebook_meta["python"]["shell_escape_lines_observed"] == 1
    assert notebook_meta["static_execution_indicators"]["eval_calls"] == 1
    assert notebook_meta["static_execution_indicators"]["os_system_calls"] == 1

    assert any(symbol.name == "area" for symbol in result.symbols)
    assert any(dep.dependency_name == "math" for dep in result.dependencies)
    area = next(symbol for symbol in result.symbols if symbol.name == "area")
    assert area.meta["notebook_cell_index"] == 1
    assert "SENSITIVE_OUTPUT_PAYLOAD" not in json.dumps(result.analysis_meta)
    assert "Private narrative" not in json.dumps(result.analysis_meta)
    assert notebook_meta["execution_performed"] is False


def test_notebook_metadata_only_for_non_python_kernel() -> None:
    source = _notebook(
        [
            {
                "cell_type": "code",
                "execution_count": 1,
                "metadata": {},
                "outputs": [],
                "source": ["library(stats)\n", "summary(cars)\n"],
            },
        ],
        kernel_language="r",
    )
    result = parse_notebook(source)
    metadata = result.analysis_meta["notebook"]
    assert metadata["analysis_mode"] == "structure_only"
    assert metadata["python"]["cells_skipped"] == 1
    assert result.symbols == ()
    assert result.dependencies == ()


def test_notebook_parser_never_executes_cell_source(tmp_path) -> None:
    marker = tmp_path / "notebook-executed.txt"
    source = _notebook(
        [
            {
                "cell_type": "code",
                "execution_count": None,
                "metadata": {},
                "outputs": [],
                "source": [
                    "from pathlib import Path\n",
                    f"Path({str(marker)!r}).write_text('executed')\n",
                ],
            }
        ]
    )
    result = parse_notebook(source)
    assert result.error is None
    assert not marker.exists()


def test_notebook_limits_cell_count_and_source_size() -> None:
    source = _notebook(
        [
            {
                "cell_type": "code",
                "execution_count": None,
                "metadata": {},
                "outputs": [],
                "source": "def one():\n    return 1\n",
            },
            {
                "cell_type": "markdown",
                "metadata": {},
                "source": "more than the limit",
            },
        ]
    )
    result = parse_notebook(source, max_cells=1)
    assert result.analysis_meta["notebook"]["cells_truncated"] is True
    assert result.analysis_meta["notebook"]["cell_count_analyzed"] == 1

    limited = parse_notebook(source, max_cell_source_chars=10)
    assert limited.analysis_meta["notebook"]["source_truncated"] is True
    assert limited.analysis_meta["notebook"]["python"]["cells_skipped"] == 1


def test_notebook_rejects_invalid_json_and_invalid_cell_shape() -> None:
    invalid_json = parse_notebook("{not-json")
    assert invalid_json.error == "invalid notebook JSON"
    invalid_cells = parse_notebook(json.dumps({"nbformat": 4, "cells": {}}))
    assert invalid_cells.error == "notebook cells must be a JSON array"


def test_notebook_marks_unknown_nbformat_unsupported() -> None:
    result = parse_notebook(json.dumps({"nbformat": 3, "worksheets": []}))
    assert result.supported is False
    assert result.analysis_meta["notebook"]["unsupported_nbformat"] == 3



def test_notebook_tolerates_untrusted_cell_and_output_type_values() -> None:
    source = _notebook(
        [
            {
                "cell_type": [],
                "execution_count": None,
                "metadata": {},
                "outputs": [],
                "source": "unknown cell",
            },
            {
                "cell_type": "code",
                "execution_count": None,
                "metadata": {},
                "outputs": [{"output_type": []}],
                "source": "",
            },
        ]
    )
    result = parse_notebook(source)
    assert result.error is None
    metadata = result.analysis_meta["notebook"]
    assert metadata["cell_type_counts"]["unknown"] == 1
    assert metadata["outputs"]["output_type_counts"]["other"] == 1


def test_notebook_requires_integer_nbformat_version() -> None:
    result = parse_notebook(
        json.dumps({"nbformat": 4.0, "cells": []})
    )
    assert result.supported is False
