"""Read bounded companion-file context and establish evidence-based links to HDF5 runs."""

from __future__ import annotations

import csv
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable


SUPPORTED_EXTENSIONS = {
    ".pdf": "Experiment report / human-readable labels",
    ".mat": "MATLAB workspace / derived analysis",
    ".csv": "Tabular export / peak or time-series results",
    ".tsv": "Tabular export / peak or time-series results",
    ".xlsx": "Spreadsheet / annotations or derived results",
    ".xls": "Legacy spreadsheet / annotations or derived results",
    ".txt": "Text notes / operator context",
    ".log": "Processing or acquisition log",
    ".ini": "Instrument or processing configuration",
    ".json": "Structured metadata or processing result",
    ".yaml": "Structured metadata or processing result",
    ".yml": "Structured metadata or processing result",
}
MAX_TEXT_CHARS = 1_000_000
MAX_FILES = 200


def _clean(value: Any) -> str:
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return str(value)


def _read_pdf(path: Path) -> tuple[str, dict[str, Any]]:
    try:
        from pypdf import PdfReader
    except ImportError:
        return "", {"warning": "PDF text extraction requires the pypdf package."}
    reader = PdfReader(str(path))
    text = "\n".join((page.extract_text() or "") for page in reader.pages)
    return text[:MAX_TEXT_CHARS], {"pages": len(reader.pages)}


def _read_mat(path: Path) -> tuple[str, dict[str, Any]]:
    try:
        from scipy.io import loadmat, whosmat
        variables = whosmat(str(path))
        details = {"variables": [{"name": n, "shape": list(s), "type": t} for n, s, t in variables[:500]]}
        # Load only modest files to recover string labels while avoiding large arrays.
        strings: list[str] = []
        if path.stat().st_size <= 64 * 1024 * 1024:
            data = loadmat(str(path), squeeze_me=True, chars_as_strings=True)
            for name, value in data.items():
                if name.startswith("__"):
                    continue
                if getattr(value, "dtype", None) is not None and value.dtype.kind in "USO" and getattr(value, "size", 0) <= 5000:
                    strings.append(f"{name}: {_clean(value)}")
        return "\n".join([item["name"] for item in details["variables"]] + strings)[:MAX_TEXT_CHARS], details
    except NotImplementedError:
        # MATLAB v7.3 files are HDF5 containers. Record the category without guessing semantics.
        return "", {"warning": "MATLAB v7.3/HDF5 file; variable extraction was not performed."}
    except ImportError:
        return "", {"warning": "MAT-file extraction requires the scipy package."}
    except Exception as exc:
        return "", {"warning": f"MAT-file metadata could not be read: {exc}"}


def _read_xlsx(path: Path) -> tuple[str, dict[str, Any]]:
    try:
        from openpyxl import load_workbook
    except ImportError:
        return "", {"warning": "Spreadsheet extraction requires the openpyxl package."}
    workbook = load_workbook(path, read_only=True, data_only=True)
    parts: list[str] = []
    sheets: list[str] = []
    for sheet in workbook.worksheets:
        sheets.append(sheet.title)
        parts.append(sheet.title)
        for row_number, row in enumerate(sheet.iter_rows(values_only=True)):
            if row_number >= 5_000:
                break
            parts.extend(_clean(value) for value in row if value is not None)
            if sum(len(item) for item in parts) >= MAX_TEXT_CHARS:
                break
    workbook.close()
    return "\n".join(parts)[:MAX_TEXT_CHARS], {"sheets": sheets}


def extract_companion(path: Path) -> tuple[str, dict[str, Any]]:
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        return _read_pdf(path)
    if suffix == ".mat":
        return _read_mat(path)
    if suffix in {".xlsx", ".xls"}:
        if suffix == ".xls":
            return "", {"warning": "Legacy .xls files are inventoried but not parsed; convert to .xlsx or CSV."}
        return _read_xlsx(path)
    if suffix in {".csv", ".tsv"}:
        delimiter = "\t" if suffix == ".tsv" else ","
        parts: list[str] = []
        with path.open("r", encoding="utf-8", errors="replace", newline="") as handle:
            for index, row in enumerate(csv.reader(handle, delimiter=delimiter)):
                if index >= 10_000:
                    break
                parts.extend(row)
                if sum(len(item) for item in parts) >= MAX_TEXT_CHARS:
                    break
        return "\n".join(parts)[:MAX_TEXT_CHARS], {}
    text = path.read_text(encoding="utf-8", errors="replace")[:MAX_TEXT_CHARS]
    if suffix == ".json":
        try:
            value = json.loads(text)
            text = json.dumps(value, ensure_ascii=False)
        except json.JSONDecodeError:
            pass
    return text, {}


def _tokens(value: str) -> list[str]:
    stop = {"hdf5", "data", "file", "sample", "instrument", "acquisition", "spectrum", "fullspectra"}
    return [token for token in re.findall(r"[A-Za-z][A-Za-z0-9+_-]{2,}", value) if token.lower() not in stop]


def relate_companion(path: Path, hdf5_name: str, evidence_text: str) -> dict[str, Any]:
    text, details = extract_companion(path)
    lower_text = text.lower()
    hdf_name = Path(hdf5_name).name
    stem = Path(hdf_name).stem
    evidence: list[dict[str, str]] = []
    score = 0
    if hdf_name.lower() in lower_text:
        evidence.append({"kind": "exact_filename", "detail": f"References {hdf_name} exactly"})
        score += 100
    elif stem.lower() in lower_text:
        evidence.append({"kind": "filename_stem", "detail": f"References acquisition identifier {stem}"})
        score += 70
    # Match YYYYMMDD_HHMMSS or date/time fragments from the HDF5 filename.
    date_tokens = re.findall(r"(?:19|20)\d{2}[._-]?\d{2}[._-]?\d{2}|\d{2}h\d{2}m\d{2}s", stem, re.I)
    for token in date_tokens:
        normalized = re.sub(r"[^0-9]", "", token)
        if token.lower() in lower_text or (len(normalized) >= 6 and normalized in re.sub(r"[^0-9]", "", lower_text)):
            evidence.append({"kind": "timestamp", "detail": f"Shares timestamp/date token {token}"})
            score += 25
    common: list[str] = []
    for token in dict.fromkeys(_tokens(evidence_text)):
        if len(token) >= 4 and token.lower() in lower_text:
            common.append(token)
        if len(common) >= 12:
            break
    if common:
        evidence.append({"kind": "shared_terms", "detail": "Shared run terms: " + ", ".join(common)})
        score += min(30, len(common) * 3)
    relation = "confirmed" if score >= 100 else "probable" if score >= 50 else "possible" if score >= 20 else "unresolved"
    return {
        "name": path.name,
        "extension": path.suffix.lower(),
        "category": SUPPORTED_EXTENSIONS.get(path.suffix.lower(), "Other companion file"),
        "size_bytes": path.stat().st_size,
        "relation": relation,
        "score": score,
        "evidence": evidence,
        "details": details,
    }


def companion_inventory(paths: Iterable[Path], hdf5_name: str, evidence_text: str) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    for path in list(paths)[:MAX_FILES]:
        if path.suffix.lower() not in SUPPORTED_EXTENSIONS or not path.is_file():
            continue
        try:
            rows.append(relate_companion(path, hdf5_name, evidence_text))
        except Exception as exc:
            rows.append({
                "name": path.name, "extension": path.suffix.lower(),
                "category": SUPPORTED_EXTENSIONS[path.suffix.lower()], "size_bytes": path.stat().st_size,
                "relation": "unresolved", "score": 0, "evidence": [],
                "details": {"warning": f"Could not inspect file: {exc}"},
            })
    rows.sort(key=lambda row: (-row["score"], row["name"].lower()))
    return {
        "files": rows,
        "supported_extensions": SUPPORTED_EXTENSIONS,
        "limitations": "Relationships are evidence links, not analytical identifications. Exact filename references are strongest; shared terms and timestamps require analyst review.",
    }
