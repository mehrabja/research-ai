"""M20 — Minimal XLSX profiler using stdlib zipfile + xml.etree."""
from __future__ import annotations

import io
import re
import zipfile
from collections.abc import Iterable
from xml.etree import ElementTree as ET

from app.core.config import get_settings
from app.services.profilers import DataProfileResult
from app.services.profilers._accumulator import ColumnAccumulator

_NS_MAIN = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
_NS_REL = (
    "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"
)
_NS_PKG_REL = (
    "{http://schemas.openxmlformats.org/package/2006/relationships}"
)

_CELL_REF_RE = re.compile(r"^([A-Z]+)(\d+)$")


def _empty(error: str | None = None) -> DataProfileResult:
    return DataProfileResult(
        format="xlsx",
        row_count=0,
        column_count=0,
        schema_data={},
        quality={},
        statistics={},
        sample_rows=[],
        columns=[],
        error=error,
    )


def _col_letters_to_index(letters: str) -> int:
    idx = 0
    for ch in letters:
        idx = idx * 26 + (ord(ch) - ord("A") + 1)
    return idx - 1


def _read_shared_strings(zf: zipfile.ZipFile) -> list[str]:
    try:
        data = zf.read("xl/sharedStrings.xml")
    except KeyError:
        return []
    root = ET.fromstring(data)
    strings: list[str] = []
    for si in root.findall(f"{_NS_MAIN}si"):
        text_parts = []
        for t in si.iter(f"{_NS_MAIN}t"):
            text_parts.append(t.text or "")
        strings.append("".join(text_parts))
    return strings


def _read_first_sheet(zf: zipfile.ZipFile) -> tuple[str, str] | None:
    try:
        wb = zf.read("xl/workbook.xml")
        rels = zf.read("xl/_rels/workbook.xml.rels")
    except KeyError:
        return None
    wb_root = ET.fromstring(wb)
    rels_root = ET.fromstring(rels)
    rid_to_target: dict[str, str] = {}
    for rel in rels_root.findall(f"{_NS_PKG_REL}Relationship"):
        rid = rel.attrib.get("Id")
        target = rel.attrib.get("Target")
        if rid and target:
            rid_to_target[rid] = target
    for sheet in wb_root.iter(f"{_NS_MAIN}sheet"):
        rid = sheet.attrib.get(f"{_NS_REL}id")
        name = sheet.attrib.get("name") or "Sheet1"
        if not rid or rid not in rid_to_target:
            continue
        target = rid_to_target[rid]
        path = (
            target.lstrip("/")
            if target.startswith("/")
            else "xl/" + target
        )
        return name, path
    return None


def _row_cells(row_elem: ET.Element, shared: list[str]) -> dict[int, str]:
    out: dict[int, str] = {}
    for c in row_elem.findall(f"{_NS_MAIN}c"):
        ref = c.attrib.get("r", "")
        m = _CELL_REF_RE.match(ref)
        if not m:
            continue
        col_idx = _col_letters_to_index(m.group(1))
        t = c.attrib.get("t", "n")
        v = c.find(f"{_NS_MAIN}v")
        inline = c.find(f"{_NS_MAIN}is")
        value = ""
        if t == "s" and v is not None and v.text is not None:
            try:
                value = shared[int(v.text)]
            except (ValueError, IndexError):
                value = ""
        elif t == "inlineStr" and inline is not None:
            parts = [x.text or "" for x in inline.iter(f"{_NS_MAIN}t")]
            value = "".join(parts)
        elif t == "b" and v is not None and v.text is not None:
            value = "true" if v.text == "1" else "false"
        elif v is not None and v.text is not None:
            value = v.text
        out[col_idx] = value
    return out


def profile_xlsx(*, chunks: Iterable[bytes]) -> DataProfileResult:
    settings = get_settings()
    buf = bytearray()
    for raw in chunks:
        buf.extend(raw)
    try:
        zf = zipfile.ZipFile(io.BytesIO(bytes(buf)))
    except zipfile.BadZipFile as exc:
        return _empty(f"bad_zip: {exc}")

    with zf:
        try:
            total_uncompressed = sum(
                info.file_size for info in zf.infolist()
            )
        except Exception:  # noqa: BLE001
            return _empty("zip_infolist_error")
        if total_uncompressed > settings.data_xlsx_max_uncompressed_bytes:
            return _empty("xlsx_uncompressed_too_large")

        shared = _read_shared_strings(zf)
        sheet = _read_first_sheet(zf)
        if sheet is None:
            return _empty("no_sheet_found")
        sheet_name, sheet_path = sheet
        try:
            sheet_data = zf.read(sheet_path)
        except KeyError:
            return _empty("sheet_missing")

    sheet_root = ET.fromstring(sheet_data)
    sheet_data_elem = sheet_root.find(f"{_NS_MAIN}sheetData")
    if sheet_data_elem is None:
        return _empty()

    rows_iter = sheet_data_elem.findall(f"{_NS_MAIN}row")
    parsed_rows: list[dict[int, str]] = []
    scan_cap = settings.data_profile_max_rows_scanned
    scan_truncated = False
    for r in rows_iter:
        if len(parsed_rows) >= scan_cap:
            scan_truncated = True
            break
        cells = _row_cells(r, shared)
        if cells:
            parsed_rows.append(cells)

    if not parsed_rows:
        return _empty()

    header_cells = parsed_rows[0]
    max_col = max(header_cells.keys()) if header_cells else -1
    max_col = min(max_col, settings.data_profile_max_columns - 1)
    header = [header_cells.get(i) or f"col_{i}" for i in range(max_col + 1)]

    accs = [
        ColumnAccumulator(
            name=h,
            ordinal=i,
            distinct_cap=settings.data_profile_distinct_tracking_cap,
            top_values_limit=settings.data_profile_top_values_limit,
        )
        for i, h in enumerate(header)
    ]
    samples: list[dict[str, str]] = []
    row_count = 0

    for cells in parsed_rows[1:]:
        row_count += 1
        for i, acc in enumerate(accs):
            acc.add(cells.get(i, ""))
        if len(samples) < settings.data_profile_sample_rows:
            samples.append(
                {header[i]: cells.get(i, "") for i in range(len(header))}
            )

    cols = [a.finalize() for a in accs]
    schema_data = {
        "columns": [
            {"name": c.name, "ordinal": c.ordinal, "type": c.inferred_type}
            for c in cols
        ],
        "column_count": len(cols),
        "sheet_name": sheet_name,
    }
    quality = {
        "rows_scanned": row_count,
        "scan_truncated": scan_truncated,
    }
    return DataProfileResult(
        format="xlsx",
        row_count=row_count,
        column_count=len(cols),
        schema_data=schema_data,
        quality=quality,
        statistics={},
        sample_rows=samples,
        columns=cols,
        scan_truncated=scan_truncated,
    )
