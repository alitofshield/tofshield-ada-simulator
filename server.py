#!/usr/bin/env python3
"""Local, read-only HDF5 spectrum viewer for TOFshield ADA.

The service deliberately binds to localhost by default. HDF5 files can be
opened from configured local roots or uploaded into a private cache directory.
No data is sent to a cloud service.
"""

from __future__ import annotations

import csv
import json
import io
import math
import os
import re
import tempfile
import threading
import time
import uuid
from acquisition_context import recorded_context
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import unquote

import h5py
import numpy as np
from flask import Flask, Response, jsonify, request, send_from_directory
from werkzeug.exceptions import HTTPException, RequestEntityTooLarge
from werkzeug.utils import secure_filename

from instrument_config import FIELDS, normalize, transform
from detection_capability import calculate_study, classify_peak
from synthetic_generator import generate_miptof, generate_vocus, generator_catalog
from companion_context import SUPPORTED_EXTENSIONS, companion_inventory


APP_ROOT = Path(__file__).resolve().parent
STATIC_ROOT = APP_ROOT / "static"
FIXTURE_PATH = APP_ROOT / "fixtures" / "synthetic_tofwerk_style_reference.h5"
VALID_EXTENSIONS = {".h5", ".hdf5", ".hdf"}
MAX_DATASETS = 8_000
MAX_METADATA_ITEMS = 1_500
MAX_ATTRIBUTE_ARRAY = 64
MAX_SPECTRUM_POINTS = 120_000
TEAM_SHARE_IMPORT_MARKER = "team-share-worker"
STREAM_COPY_CHUNK_BYTES = 1024 * 1024


def _configured_roots() -> list[Path]:
    configured = os.environ.get("ADA_HDF5_ROOTS", "")
    raw_roots = [item for item in configured.split(os.pathsep) if item.strip()]
    if not raw_roots:
        raw_roots = [str(Path.home()), "/media", "/mnt"]
    roots: list[Path] = []
    for item in raw_roots:
        path = Path(item).expanduser()
        try:
            resolved = path.resolve(strict=False)
        except OSError:
            continue
        if resolved not in roots:
            roots.append(resolved)
    return roots


ALLOWED_ROOTS = _configured_roots()
UPLOAD_LIMIT_MB = int(os.environ.get("ADA_VIEWER_MAX_UPLOAD_MB", "2048"))
UPLOAD_ROOT = Path(
    os.environ.get(
        "ADA_VIEWER_UPLOAD_DIR",
        str(Path.home() / ".cache" / "tofshield-ada-hdf5-viewer" / "uploads"),
    )
).expanduser()
UPLOAD_ROOT.mkdir(parents=True, exist_ok=True)
GENERATED_ROOT = Path(
    os.environ.get(
        "ADA_VIEWER_GENERATED_DIR",
        str(Path.home() / ".cache" / "tofshield-ada-hdf5-viewer" / "generated"),
    )
).expanduser()
GENERATED_ROOT.mkdir(parents=True, exist_ok=True)


app = Flask(__name__, static_folder=None)
app.config["MAX_CONTENT_LENGTH"] = UPLOAD_LIMIT_MB * 1024 * 1024


@dataclass
class OpenFile:
    path: Path
    display_name: str
    provenance: str
    opened_at: float
    manifest: dict[str, Any]
    owned_upload: bool = False
    companion_paths: list[Path] | None = None


_registry: dict[str, OpenFile] = {}
_registry_lock = threading.Lock()


def _json_value(value: Any) -> Any:
    """Convert an HDF5/numpy value into a compact JSON-safe value."""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    if isinstance(value, np.generic):
        return _json_value(value.item())
    if isinstance(value, np.ndarray):
        if value.size > MAX_ATTRIBUTE_ARRAY:
            return {
                "summary": f"array with {value.size:,} values",
                "shape": list(value.shape),
                "dtype": str(value.dtype),
            }
        return [_json_value(item) for item in value.tolist()]
    if isinstance(value, (list, tuple)):
        return [_json_value(item) for item in value[:MAX_ATTRIBUTE_ARRAY]]
    if isinstance(value, (bool, int, float, str)) or value is None:
        if isinstance(value, float) and not math.isfinite(value):
            return str(value)
        return value
    return str(value)


def _dataset_scalar(dataset: h5py.Dataset) -> Any | None:
    if dataset.size > MAX_ATTRIBUTE_ARRAY:
        return None
    try:
        value = dataset[()]
    except (OSError, TypeError, ValueError):
        return None
    return _json_value(value)


def _read_attributes(obj: h5py.Group | h5py.Dataset) -> dict[str, Any]:
    values: dict[str, Any] = {}
    for key in obj.attrs.keys():
        try:
            values[str(key)] = _json_value(obj.attrs[key])
        except (OSError, TypeError, ValueError) as exc:
            values[str(key)] = f"Unreadable attribute: {exc}"
    return values


CATEGORY_PATTERNS: dict[str, tuple[str, ...]] = {
    "instrument": (
        "instrument",
        "device",
        "model",
        "serial",
        "detector",
        "ion source",
        "ionization",
        "reagent",
        "polarity",
        "voltage",
        "current",
        "temperature source",
        "drift",
        "funnel",
    ),
    "environment": (
        "environment",
        "ambient",
        "humidity",
        "pressure",
        "temperature",
        "weather",
        "wind",
        "latitude",
        "longitude",
        "altitude",
        "gnss",
        "gps",
        "location",
        "site",
    ),
    "acquisition": (
        "acquisition",
        "timestamp",
        "date",
        "time",
        "duration",
        "sample",
        "write",
        "segment",
        "buffer",
        "cycle",
        "period",
        "interval",
        "trigger",
    ),
    "calibration": (
        "calibration",
        "massaxis",
        "mass axis",
        "coefficient",
        "resolution",
        "reference mass",
        "ppm",
    ),
}


def _categorize(path: str, key: str) -> str:
    haystack = f"{path} {key}".lower().replace("_", " ")
    for category, patterns in CATEGORY_PATTERNS.items():
        if any(pattern in haystack for pattern in patterns):
            return category
    return "other"


def _append_metadata(
    metadata: dict[str, list[dict[str, Any]]],
    path: str,
    key: str,
    value: Any,
    source: str,
) -> None:
    if sum(len(items) for items in metadata.values()) >= MAX_METADATA_ITEMS:
        return
    category = _categorize(path, key)
    metadata[category].append(
        {"path": path, "name": key, "value": value, "source": source}
    )


def _infer_instrument_context(
    metadata: dict[str, list[dict[str, Any]]],
    datasets: list[dict[str, Any]],
    groups: list[dict[str, Any]],
) -> dict[str, Any]:
    """Infer only strongly evidenced instrument family and explicit targets.

    Spectrum peaks are never interpreted as identities here. Suggestions come
    only from descriptive HDF5 metadata fields whose names explicitly identify
    targets, analytes, compounds, substances, elements, or isotopes.
    """
    entries = [item for items in metadata.values() for item in items]
    evidence_text = " ".join(
        f"{item['path']} {item['name']} {item['value']}" for item in entries
    ).lower()
    evidence_text += " " + " ".join(item["path"].lower() for item in datasets + groups)
    vocus_patterns = (r"\bvocus\b", r"\bci[-_ ]?tof\b", r"\bptr[-_ ]?tof\b")
    mip_patterns = (r"\bmiptof\b", r"\bmip[-_ ]?tof\b", r"\bicp[-_ ]?tof\b")
    vocus_hits = [pattern for pattern in vocus_patterns if re.search(pattern, evidence_text)]
    mip_hits = [pattern for pattern in mip_patterns if re.search(pattern, evidence_text)]
    if vocus_hits and not mip_hits:
        family, confidence = "vocus", "explicit metadata or object-name match"
    elif mip_hits and not vocus_hits:
        family, confidence = "miptof", "explicit metadata or object-name match"
    else:
        family, confidence = "unknown", "ambiguous" if vocus_hits and mip_hits else "no explicit instrument-family evidence"

    target_name = re.compile(r"targets?|analytes?|compounds?|substances?|isotopes?|elements?", re.I)
    excluded_name = re.compile(r"environment|background|reagent|calibr|reference", re.I)
    suggestions: list[str] = []
    target_evidence: list[dict[str, str]] = []
    for item in entries:
        name = str(item["name"])
        path = str(item["path"])
        if "/ada/detectioncapability" in path.lower():
            continue
        if re.search(r"type|class|category|description|interpretation", name, re.I):
            continue
        if not target_name.search(name) or excluded_name.search(f"{path} {name}"):
            continue
        value = item["value"]
        if not isinstance(value, (str, list, tuple)):
            continue
        raw_values = value if isinstance(value, list) else re.split(r"[,;\n]+", str(value))
        for raw in raw_values:
            candidate = str(raw).strip()
            if not candidate or len(candidate) > 100 or candidate.lower() in {"none", "unknown", "n/a"}:
                continue
            if candidate not in suggestions:
                suggestions.append(candidate)
                target_evidence.append({"path": path, "field": name})
            if len(suggestions) >= 50:
                break
    return {
        "family": family,
        "confidence": confidence,
        "suggested_targets": suggestions,
        "target_evidence": target_evidence,
        "limitations": "Instrument selection uses descriptive HDF5 metadata and object names only. Target suggestions use explicit target/analyte/compound/substance/element/isotope fields; peaks are not identified automatically.",
    }


def _dataset_units(dataset: h5py.Dataset) -> str | None:
    for key in ("unit", "units", "Unit", "Units", "UNIT", "UNITS"):
        if key in dataset.attrs:
            return str(_json_value(dataset.attrs[key]))
    return None


def _is_numeric(dataset: h5py.Dataset) -> bool:
    return np.issubdtype(dataset.dtype, np.number)


def _candidate_score(path: str, role: str) -> int:
    lower = path.lower().replace("_", "")
    if role == "x":
        scores = {
            "/fullspectra/massaxis": 100,
            "massaxis": 85,
            "masstocharge": 80,
            "moverz": 78,
            "/mz": 75,
            "m/z": 75,
            "mass": 50,
        }
    else:
        scores = {
            "/fullspectra/sumspectrum": 100,
            "sumspectrum": 90,
            "averagespectrum": 85,
            "intensity": 70,
            "spectrum": 60,
            "tofdata": 55,
            "counts": 50,
        }
    return max((score for needle, score in scores.items() if needle in lower), default=0)


def _find_spectrum_candidates(
    file: h5py.File, datasets: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    numeric: list[tuple[str, tuple[int, ...], int, str | None]] = []
    for item in datasets:
        if not item["numeric"]:
            continue
        numeric.append(
            (
                item["path"],
                tuple(item["shape"]),
                int(item["size"]),
                item.get("units"),
            )
        )

    x_candidates = [item for item in numeric if len(item[1]) == 1 and _candidate_score(item[0], "x")]
    y_candidates = [item for item in numeric if _candidate_score(item[0], "y")]
    candidates: list[dict[str, Any]] = []
    seen: set[tuple[str | None, str]] = set()

    for y_path, y_shape, y_size, y_units in sorted(
        y_candidates, key=lambda item: _candidate_score(item[0], "y"), reverse=True
    ):
        sample_count = y_shape[-1] if y_shape else y_size
        matching_x = [item for item in x_candidates if item[2] == sample_count]
        matching_x.sort(key=lambda item: _candidate_score(item[0], "x"), reverse=True)
        x_item = matching_x[0] if matching_x else None
        key = (x_item[0] if x_item else None, y_path)
        if key in seen:
            continue
        seen.add(key)
        mode = "vector" if len(y_shape) == 1 else "sum_last_axis"
        score = _candidate_score(y_path, "y") + (
            _candidate_score(x_item[0], "x") if x_item else 0
        )
        candidates.append(
            {
                "id": f"candidate-{len(candidates) + 1}",
                "x_path": x_item[0] if x_item else None,
                "y_path": y_path,
                "x_units": (x_item[3] if x_item else None) or (
                    "Th" if x_item and "mass" in x_item[0].lower() else "index"
                ),
                "y_units": y_units or "a.u.",
                "sample_count": int(sample_count),
                "source_shape": list(y_shape),
                "mode": mode,
                "score": score,
                "label": f"{y_path} vs {x_item[0] if x_item else 'sample index'}",
                "warning": (
                    None
                    if x_item
                    else "No compatible mass axis was found. The x-axis is sample index, not m/z."
                ),
            }
        )

    candidates.sort(key=lambda item: item["score"], reverse=True)
    for index, item in enumerate(candidates):
        item["id"] = f"candidate-{index + 1}"
    return candidates[:30]


def inspect_hdf5(path: Path, display_name: str, provenance: str) -> dict[str, Any]:
    metadata: dict[str, list[dict[str, Any]]] = {
        "instrument": [],
        "environment": [],
        "acquisition": [],
        "calibration": [],
        "other": [],
    }
    datasets: list[dict[str, Any]] = []
    groups: list[dict[str, Any]] = []
    warnings: list[str] = []

    with h5py.File(path, "r", swmr=True) as file:
        for key, value in _read_attributes(file).items():
            _append_metadata(metadata, "/", key, value, "attribute")

        def visitor(name: str, obj: h5py.Group | h5py.Dataset) -> None:
            if len(datasets) >= MAX_DATASETS:
                return
            object_path = f"/{name}" if name else "/"
            attributes = _read_attributes(obj)
            for key, value in attributes.items():
                _append_metadata(metadata, object_path, key, value, "attribute")

            if isinstance(obj, h5py.Group):
                groups.append(
                    {
                        "path": object_path,
                        "attributes": attributes,
                        "member_count": len(obj),
                    }
                )
                return

            scalar = _dataset_scalar(obj)
            if scalar is not None:
                _append_metadata(metadata, object_path, obj.name.rsplit("/", 1)[-1], scalar, "dataset")
            chunks = list(obj.chunks) if obj.chunks else None
            compression = obj.compression if obj.compression else None
            datasets.append(
                {
                    "path": object_path,
                    "shape": list(obj.shape),
                    "dtype": str(obj.dtype),
                    "size": int(obj.size),
                    "dimensions": int(obj.ndim),
                    "numeric": _is_numeric(obj),
                    "units": _dataset_units(obj),
                    "chunks": chunks,
                    "compression": compression,
                    "attributes": attributes,
                    "scalar_preview": scalar,
                }
            )

        file.visititems(visitor)
        spectrum_candidates = _find_spectrum_candidates(file, datasets)

        if len(datasets) >= MAX_DATASETS:
            warnings.append(
                f"Dataset inventory was limited to {MAX_DATASETS:,} objects for responsiveness."
            )
        if not spectrum_candidates:
            warnings.append(
                "No spectrum pair was detected automatically. Select compatible numeric datasets manually."
            )
        if "/FullSpectra/MassCalibration" in file:
            warnings.append(
                "Dynamic mass calibration is present. The stored mass axis may not represent every acquisition write."
            )
        if "/FullSpectra/MassAxis" not in file:
            alternative_axis = next(
                (item["x_path"] for item in spectrum_candidates if item["x_path"]),
                None,
            )
            if alternative_axis:
                warnings.append(
                    "The standard /FullSpectra/MassAxis dataset was not found. "
                    f"The compatible stored axis at {alternative_axis} is displayed as provided; "
                    "verify its calibration provenance before analytical interpretation."
                )
            else:
                warnings.append(
                    "No compatible stored mass axis was found. The viewer will use sample index "
                    "and will not label the x-axis as m/z."
                )

        root_keys = sorted(list(file.keys()))
        file_driver = file.driver
        hdf5_userblock = int(file.userblock_size)

    stat = path.stat()
    instrument_context = _infer_instrument_context(metadata, datasets, groups)
    evidence_text = " ".join(
        f"{item['path']} {item['name']} {item['value']}"
        for items in metadata.values() for item in items
    )
    sibling_paths = []
    if provenance in {"local path", "assessment table"}:
        try:
            sibling_paths = [item for item in path.parent.iterdir() if item != path]
        except OSError:
            sibling_paths = []
    return {
        "file": {
            "display_name": display_name,
            "provenance": provenance,
            "size_bytes": stat.st_size,
            "size_human": _human_bytes(stat.st_size),
            "modified_utc": datetime.fromtimestamp(
                stat.st_mtime, tz=timezone.utc
            ).isoformat(),
            "hdf5_driver": file_driver,
            "hdf5_userblock_bytes": hdf5_userblock,
            "root_objects": root_keys,
            "dataset_count": len(datasets),
            "group_count": len(groups),
        },
        "metadata": metadata,
        "datasets": datasets,
        "groups": groups,
        "spectrum_candidates": spectrum_candidates,
        "recommended_candidate_id": spectrum_candidates[0]["id"] if spectrum_candidates else None,
        "instrument_context": instrument_context,
        "acquisition_locked": provenance not in ("synthetic example", "synthetic generator"),
        "acquisition_context": recorded_context(metadata, FIELDS),
        "companion_context": companion_inventory(sibling_paths, display_name, evidence_text),
        "warnings": warnings,
    }


def _human_bytes(value: int) -> str:
    amount = float(value)
    for unit in ("B", "KiB", "MiB", "GiB", "TiB"):
        if amount < 1024 or unit == "TiB":
            return f"{amount:.1f} {unit}" if unit != "B" else f"{int(amount)} B"
        amount /= 1024
    return f"{amount:.1f} TiB"


def _is_allowed_local_path(path: Path) -> bool:
    for root in ALLOWED_ROOTS:
        try:
            path.relative_to(root)
            return True
        except ValueError:
            continue
    return False


def _validate_hdf5_path(path: Path, require_allowed_root: bool = True) -> Path:
    try:
        resolved = path.expanduser().resolve(strict=True)
    except FileNotFoundError as exc:
        raise ValueError("The selected file does not exist.") from exc
    if require_allowed_root and not _is_allowed_local_path(resolved):
        roots = ", ".join(str(root) for root in ALLOWED_ROOTS)
        raise ValueError(f"The file is outside the configured read roots: {roots}")
    if not resolved.is_file():
        raise ValueError("The selected path is not a regular file.")
    if resolved.suffix.lower() not in VALID_EXTENSIONS:
        raise ValueError("Choose an HDF5 file ending in .h5, .hdf5, or .hdf.")
    if not h5py.is_hdf5(resolved):
        raise ValueError("The selected file does not have a valid HDF5 signature.")
    return resolved


def _register_file(
    path: Path, display_name: str, provenance: str, owned_upload: bool = False
) -> tuple[str, dict[str, Any]]:
    manifest = inspect_hdf5(path, display_name, provenance)
    file_id = uuid.uuid4().hex
    with _registry_lock:
        _registry[file_id] = OpenFile(
            path=path,
            display_name=display_name,
            provenance=provenance,
            opened_at=time.time(),
            manifest=manifest,
            owned_upload=owned_upload,
            companion_paths=[],
        )
    return file_id, manifest


def _get_open_file(file_id: str) -> OpenFile:
    with _registry_lock:
        item = _registry.get(file_id)
    if item is None:
        raise ValueError("This file session has expired. Open the HDF5 file again.")
    return item


def _manifest_evidence_text(manifest: dict[str, Any]) -> str:
    return " ".join(
        f"{item.get('path', '')} {item.get('name', '')} {item.get('value', '')}"
        for items in manifest.get("metadata", {}).values() for item in items
    )


def _search_manifest(manifest: dict[str, Any], query: str, limit: int = 250) -> list[dict[str, Any]]:
    needle = query.casefold()
    matches: list[dict[str, Any]] = []
    def add(kind: str, path: str, name: str, value: Any) -> None:
        haystack = f"{path} {name} {value}"
        if needle in haystack.casefold() and len(matches) < limit:
            value_text = str(value)
            position = value_text.casefold().find(needle)
            start = max(0, position - 100) if position >= 0 else 0
            matches.append({"kind": kind, "path": path, "name": name, "value": value_text[start:start + 300]})
    for category, items in manifest.get("metadata", {}).items():
        for item in items:
            add(f"parameter:{category}", item.get("path", ""), item.get("name", ""), item.get("value", ""))
    for item in manifest.get("datasets", []):
        add("dataset", item.get("path", ""), item.get("dtype", ""), item.get("scalar_preview", ""))
        for key, value in item.get("attributes", {}).items():
            add("dataset attribute", item.get("path", ""), key, value)
    for item in manifest.get("groups", []):
        add("group", item.get("path", ""), "group", "")
        for key, value in item.get("attributes", {}).items():
            add("group attribute", item.get("path", ""), key, value)
    return matches


def _relative_time_axis(file: h5py.File, count: int) -> tuple[np.ndarray, str, str | None]:
    candidates: list[tuple[int, str, np.ndarray]] = []
    def visitor(name: str, obj: h5py.Group | h5py.Dataset) -> None:
        if not isinstance(obj, h5py.Dataset) or not _is_numeric(obj) or not obj.shape or obj.shape[0] != count:
            return
        lower = name.lower()
        score = 100 if lower.endswith("timingdata/buftimes") else 80 if "timestamp" in lower else 50 if "time" in lower else 0
        if not score or obj.size > count * 100:
            return
        values = np.asarray(obj[...], dtype=np.float64).reshape(count, -1)
        values = np.nanmean(values, axis=1)
        candidates.append((score, f"/{name}", values))
    file.visititems(visitor)
    if candidates:
        _, path, values = max(candidates, key=lambda item: item[0])
        finite = np.isfinite(values)
        if np.count_nonzero(finite) >= 2:
            first = values[np.flatnonzero(finite)[0]]
            relative = values - first
            positive_steps = np.diff(relative[finite])
            positive_steps = positive_steps[positive_steps > 0]
            # TOFWERK BufTimes can be stored in days; identify that representation conservatively.
            if positive_steps.size and np.median(positive_steps) < 0.01:
                relative = relative * 86400.0
            if np.all(np.diff(relative[finite]) >= 0):
                return relative, "seconds from acquisition start", path
    return np.arange(count, dtype=np.float64), "acquisition index", None


def _find_integer_setting(file: h5py.File, setting: str) -> int | None:
    """Return an exact, positive scalar acquisition setting without inferring units."""
    wanted = setting.casefold()
    found: list[int] = []

    def consider(name: str, value: Any) -> None:
        if name.rsplit("/", 1)[-1].casefold() != wanted:
            return
        try:
            array = np.asarray(value).reshape(-1)
            if array.size == 1 and np.isfinite(float(array[0])):
                number = int(array[0])
                if number > 0 and float(array[0]) == number:
                    found.append(number)
        except (TypeError, ValueError, OverflowError):
            pass

    def visitor(name: str, obj: h5py.Group | h5py.Dataset) -> None:
        if isinstance(obj, h5py.Dataset) and obj.size == 1:
            try:
                consider(name, obj[()])
            except (OSError, TypeError, ValueError):
                pass
        for key, value in obj.attrs.items():
            consider(f"{name}/{key}", value)

    for key, value in file.attrs.items():
        consider(f"/{key}", value)
    file.visititems(visitor)
    return found[0] if found and all(value == found[0] for value in found) else None


def _time_resolved_source(
    file: h5py.File, selected: h5py.Dataset, selected_path: str, sample_count: int,
) -> tuple[h5py.Dataset, int, int, str]:
    """Resolve conventional or flattened TOFWERK acquisitions conservatively."""
    if selected.ndim >= 2 and selected.shape[-1] == sample_count:
        return selected, int(selected.shape[0]), int(np.prod(selected.shape[1:-1]) or 1), "stored multidimensional acquisition"

    writes = _find_integer_setting(file, "NbrWrites")
    samples = _find_integer_setting(file, "NbrSamples")
    segments = _find_integer_setting(file, "NbrSegments") or 1
    if not writes or not samples or samples != sample_count:
        raise ValueError(
            "No time-resolved acquisition could be reconstructed: the selected spectrum is one-dimensional "
            "and compatible NbrSamples/NbrWrites metadata was not found."
        )
    candidates: list[tuple[int, str, h5py.Dataset]] = []

    def visitor(name: str, obj: h5py.Group | h5py.Dataset) -> None:
        if not isinstance(obj, h5py.Dataset) or not _is_numeric(obj):
            return
        conventional = obj.ndim >= 2 and obj.shape[0] == writes and obj.shape[-1] == samples
        flattened = obj.ndim == 1 and obj.size == writes * segments * samples
        if not conventional and not flattened:
            return
        lower = name.casefold()
        score = 100 if "tofdata" in lower else 70 if "raw" in lower else 30
        if selected_path.strip("/").rsplit("/", 1)[0] == name.rsplit("/", 1)[0]:
            score += 20
        candidates.append((score, f"/{name}", obj))

    file.visititems(visitor)
    if not candidates:
        raise ValueError(
            f"EIT unavailable: the file records {writes} writes and {samples} samples per spectrum, "
            "but no stored dataset has writes on its first dimension and mass samples on its last dimension. "
            "The file may contain only an accumulated spectrum."
        )
    _, path, source = max(candidates, key=lambda item: item[0])
    if source.ndim >= 2:
        inner_count = int(np.prod(source.shape[1:-1]) or 1)
        return source, writes, inner_count, f"time-resolved TOFWERK acquisition read from {path} with shape {source.shape}"
    return source, writes, segments, f"flattened TOFWERK acquisition reconstructed from {path}"


def _load_time_series(
    open_file: OpenFile, candidate_id: str | None, mass_min: float | None,
    mass_max: float | None, time_min: float | None, time_max: float | None,
    aggregation: str, max_points: int = 5000,
) -> dict[str, Any]:
    candidates = open_file.manifest.get("spectrum_candidates", [])
    candidate = next((item for item in candidates if item["id"] == candidate_id), candidates[0] if candidates else None)
    if candidate is None:
        raise ValueError("No compatible time-resolved spectrum dataset was detected.")
    with h5py.File(open_file.path, "r", swmr=True) as file:
        selected = file[candidate["y_path"]]
        x_dataset = file[candidate["x_path"]] if candidate.get("x_path") else None
        sample_count = int(x_dataset.size) if x_dataset is not None else int(selected.shape[-1])
        dataset, count, segment_count, storage = _time_resolved_source(
            file, selected, candidate["y_path"], sample_count
        )
        x = _read_x(x_dataset, sample_count)
        start, stop = _window_indices(x, mass_min, mass_max)
        if stop <= start:
            raise ValueError("The selected mass range contains no samples.")
        values = np.empty(count, dtype=np.float64)
        if dataset.ndim == 1:
            for index in range(count):
                offset = index * segment_count * sample_count
                slab = np.asarray(dataset[offset:offset + segment_count * sample_count], dtype=np.float64)
                slab = slab.reshape(segment_count, sample_count)[:, start:stop]
                values[index] = np.nanmean(slab) if aggregation == "mean" else np.nansum(slab)
        else:
            for index in range(count):
                slab = np.asarray(dataset[index, ..., start:stop], dtype=np.float64)
                values[index] = np.nanmean(slab) if aggregation == "mean" else np.nansum(slab)
        times, time_units, time_source = _relative_time_axis(file, count)
        events: list[dict[str, Any]] = []
        if "/AcquisitionLog/Log" in file:
            try:
                log = file["/AcquisitionLog/Log"][:]
                if log.dtype.names and "timestring" in log.dtype.names and "logtext" in log.dtype.names:
                    parsed = []
                    for row in log:
                        stamp = _json_value(row["timestring"])
                        text = _json_value(row["logtext"])
                        try: moment = datetime.fromisoformat(stamp)
                        except (ValueError, TypeError): continue
                        parsed.append((moment, text))
                    if parsed:
                        origin = parsed[0][0]
                        events = [{"time": (moment - origin).total_seconds(), "label": text} for moment, text in parsed]
            except (OSError, ValueError, TypeError):
                events = []
    mask = np.isfinite(times) & np.isfinite(values)
    if time_min is not None: mask &= times >= time_min
    if time_max is not None: mask &= times <= time_max
    times, values = times[mask], values[mask]
    if not times.size:
        raise ValueError("The selected time period contains no measurements.")
    if times.size > max_points:
        indices = np.linspace(0, times.size - 1, max_points, dtype=int)
        times, values = times[indices], values[indices]
    return {
        "candidate": candidate, "time": times.tolist(), "intensity": values.tolist(),
        "time_units": time_units, "time_source": time_source,
        "mass_range": {"min": float(x[start]), "max": float(x[stop - 1])},
        "time_range": {"min": float(times[0]), "max": float(times[-1])},
        "events": events, "aggregation": aggregation,
        "storage_interpretation": storage, "write_count": count, "segment_count": segment_count,
        "limitations": "This trace aggregates the selected stored m/z interval for each first-dimension acquisition. It does not assign compound identity without a validated ion/adduct method.",
    }


def _read_x(dataset: h5py.Dataset | None, sample_count: int) -> np.ndarray:
    if dataset is None:
        return np.arange(sample_count, dtype=np.float64)
    values = np.asarray(dataset[...], dtype=np.float64).reshape(-1)
    if values.size != sample_count:
        raise ValueError("The x-axis and spectrum datasets do not have matching lengths.")
    return values


def _read_y(dataset: h5py.Dataset, start: int, stop: int, mode: str) -> np.ndarray:
    if dataset.ndim == 1:
        return np.asarray(dataset[start:stop], dtype=np.float64)
    if dataset.ndim < 1:
        raise ValueError("The selected intensity dataset is scalar, not a spectrum.")
    if dataset.shape[-1] < stop:
        raise ValueError("The requested spectrum window exceeds the dataset length.")

    accumulator = np.zeros(stop - start, dtype=np.float64)
    row_count = 0
    first_dimension = dataset.shape[0]
    for index in range(first_dimension):
        slab = np.asarray(dataset[index, ..., start:stop], dtype=np.float64)
        accumulator += np.sum(slab, axis=tuple(range(max(0, slab.ndim - 1))))
        row_count += int(np.prod(slab.shape[:-1])) if slab.ndim > 1 else 1
    if mode == "mean" and row_count:
        accumulator /= row_count
    return accumulator


def _finite_xy(x: np.ndarray, y: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    mask = np.isfinite(x) & np.isfinite(y)
    return x[mask], y[mask]


def _window_indices(x: np.ndarray, x_min: float | None, x_max: float | None) -> tuple[int, int]:
    if x.size == 0 or (x_min is None and x_max is None):
        return 0, int(x.size)
    low = float(np.nanmin(x)) if x_min is None else x_min
    high = float(np.nanmax(x)) if x_max is None else x_max
    if low > high:
        low, high = high, low
    if np.all(np.diff(x) >= 0):
        start = int(np.searchsorted(x, low, side="left"))
        stop = int(np.searchsorted(x, high, side="right"))
        return max(0, start), min(int(x.size), max(start + 1, stop))
    indices = np.flatnonzero((x >= low) & (x <= high))
    if indices.size == 0:
        return 0, 0
    return int(indices[0]), int(indices[-1] + 1)


def _downsample_envelope(
    x: np.ndarray, y: np.ndarray, max_points: int
) -> tuple[np.ndarray, np.ndarray]:
    if x.size <= max_points or max_points < 4:
        return x, y
    bins = max(2, max_points // 2)
    boundaries = np.linspace(0, x.size, bins + 1, dtype=np.int64)
    out_x: list[float] = []
    out_y: list[float] = []
    for index in range(bins):
        start, stop = int(boundaries[index]), int(boundaries[index + 1])
        if stop <= start:
            continue
        chunk = y[start:stop]
        min_offset = int(np.nanargmin(chunk))
        max_offset = int(np.nanargmax(chunk))
        for offset in sorted({min_offset, max_offset}):
            point_index = start + offset
            out_x.append(float(x[point_index]))
            out_y.append(float(y[point_index]))
    return np.asarray(out_x), np.asarray(out_y)


def _interpolated_crossing(x0: float, y0: float, x1: float, y1: float, level: float) -> float:
    if y1 == y0:
        return float((x0 + x1) / 2)
    fraction = (level - y0) / (y1 - y0)
    return float(x0 + np.clip(fraction, 0, 1) * (x1 - x0))


def _peak_width_metrics(
    x: np.ndarray, y: np.ndarray, index: int, mass_axis: bool
) -> dict[str, Any]:
    """Estimate baseline-corrected FWHM from full, non-decimated window data."""
    result: dict[str, Any] = {
        "centroid_mz": float(x[index]),
        "fwhm": None,
        "resolving_power": None,
        "quality": "Unavailable",
    }
    if not mass_axis:
        result["quality"] = "No mass axis"
        return result
    if x.size < 5 or index <= 0 or index >= x.size - 1 or not np.all(np.diff(x) > 0):
        result["quality"] = "Truncated" if index <= 0 or index >= x.size - 1 else "Unavailable"
        return result

    left_valley = index - 1
    while left_valley > 0 and y[left_valley - 1] <= y[left_valley]:
        left_valley -= 1
    right_valley = index + 1
    while right_valley < y.size - 1 and y[right_valley + 1] <= y[right_valley]:
        right_valley += 1

    baseline = float(max(y[left_valley], y[right_valley]))
    height = float(y[index] - baseline)
    if not math.isfinite(height) or height <= 0:
        result["quality"] = "Overlapping"
        return result
    half_height = baseline + height / 2

    left = index
    while left > left_valley and y[left] > half_height:
        left -= 1
    right = index
    while right < right_valley and y[right] > half_height:
        right += 1
    if y[left] > half_height or y[right] > half_height:
        result["quality"] = "Truncated" if left_valley == 0 or right_valley == y.size - 1 else "Overlapping"
        return result

    left_x = _interpolated_crossing(x[left], y[left], x[left + 1], y[left + 1], half_height)
    right_x = _interpolated_crossing(x[right - 1], y[right - 1], x[right], y[right], half_height)
    width = float(right_x - left_x)
    if not math.isfinite(width) or width <= 0:
        return result

    interior = (x >= left_x) & (x <= right_x)
    weights = np.maximum(y[interior] - baseline, 0)
    if weights.size and float(np.sum(weights)) > 0:
        centroid = float(np.sum(x[interior] * weights) / np.sum(weights))
    else:
        centroid = float(x[index])
    samples_across = int(np.count_nonzero(interior))
    quality = "Estimated"
    if samples_across < 4:
        quality = "Undersampled"

    result.update({
        "centroid_mz": centroid,
        "fwhm": width,
        "resolving_power": float(centroid / width) if mass_axis and width > 0 else None,
        "quality": quality,
        "baseline": baseline,
        "half_height": half_height,
        "left_half_mz": left_x,
        "right_half_mz": right_x,
        "samples_across_fwhm": samples_across,
    })
    return result


def _top_peaks(
    x: np.ndarray, y: np.ndarray, limit: int = 20, mass_axis: bool = True
) -> list[dict[str, Any]]:
    if x.size < 3:
        return []
    local = np.flatnonzero((y[1:-1] > y[:-2]) & (y[1:-1] >= y[2:])) + 1
    if local.size == 0:
        local = np.asarray([int(np.nanargmax(y))])
    order = local[np.argsort(y[local])[::-1]]
    selected: list[int] = []
    min_separation = max(1, x.size // 2_000)
    for candidate in order:
        if all(abs(int(candidate) - prior) >= min_separation for prior in selected):
            selected.append(int(candidate))
        if len(selected) >= limit:
            break
    peaks: list[dict[str, Any]] = []
    for index in selected:
        peak = {"mz": float(x[index]), "intensity": float(y[index]), "index": int(index)}
        peak.update(_peak_width_metrics(x, y, index, mass_axis))
        peaks.append(peak)
    return peaks


def _parse_optional_float(value: str | None) -> float | None:
    if value is None or value == "":
        return None
    parsed = float(value)
    if not math.isfinite(parsed):
        raise ValueError("Range values must be finite numbers.")
    return parsed


def _load_spectrum(
    open_file: OpenFile,
    candidate_id: str | None,
    x_min: float | None,
    x_max: float | None,
    max_points: int,
    aggregation: str,
    instrument_configuration=None,
    detection_study=None,
) -> dict[str, Any]:
    if instrument_configuration and open_file.manifest.get("acquisition_locked"):
        raise ValueError("Acquisition settings are locked for imported HDF5 data. Start a new simulation to change model settings.")
    candidates = open_file.manifest["spectrum_candidates"]
    candidate = next(
        (item for item in candidates if item["id"] == candidate_id),
        candidates[0] if candidates else None,
    )
    if candidate is None:
        raise ValueError("No compatible spectrum datasets were detected in this file.")
    if aggregation not in {"sum", "mean"}:
        raise ValueError("Aggregation must be sum or mean.")
    max_points = max(500, min(int(max_points), MAX_SPECTRUM_POINTS))

    with h5py.File(open_file.path, "r", swmr=True) as file:
        if candidate["y_path"] not in file:
            raise ValueError("The selected spectrum dataset is no longer available.")
        y_dataset = file[candidate["y_path"]]
        sample_count = int(y_dataset.shape[-1]) if y_dataset.ndim else 0
        x_dataset = file[candidate["x_path"]] if candidate["x_path"] else None
        x_all = _read_x(x_dataset, sample_count)
        start, stop = _window_indices(x_all, None if instrument_configuration else x_min, None if instrument_configuration else x_max)
        if stop <= start:
            raise ValueError("The selected x-axis range contains no data points.")
        x = x_all[start:stop]
        y = _read_y(y_dataset, start, stop, aggregation)

    x, y = _finite_xy(x, y)
    if x.size == 0:
        raise ValueError("The selected spectrum contains no finite data points.")
    model_report = None
    if instrument_configuration:
        if not candidate["x_path"]:
            raise ValueError("Configuration analysis requires a stored mass axis, not sample index.")
        x, y, model_report = transform(x, y, instrument_configuration)
        start, stop = _window_indices(x, x_min, x_max)
        x, y = x[start:stop], y[start:stop]
        if not x.size:
            raise ValueError("Configured mass range contains no points.")
    peaks = _top_peaks(x, y, mass_axis=bool(candidate["x_path"]))
    if detection_study:
        for peak in peaks:
            peak.update(classify_peak(peak.get("centroid_mz", peak["mz"]), peak["intensity"], detection_study))
    shown_x, shown_y = _downsample_envelope(x, y, max_points)
    positive = y[y > 0]
    return {
        "candidate": candidate,
        "instrument_configuration": instrument_configuration,
        "configuration_report": model_report,
        "detection_study": detection_study,
        "aggregation": aggregation,
        "x": shown_x.tolist(),
        "y": shown_y.tolist(),
        "raw_point_count": int(x.size),
        "displayed_point_count": int(shown_x.size),
        "range": {"min": float(np.min(x)), "max": float(np.max(x))},
        "stats": {
            "minimum": float(np.min(y)),
            "maximum": float(np.max(y)),
            "mean": float(np.mean(y)),
            "median": float(np.median(y)),
            "positive_minimum": float(np.min(positive)) if positive.size else None,
            "total": float(np.sum(y)),
        },
        "peaks": peaks,
    }


@app.get("/")
def index() -> Response:
    return send_from_directory(STATIC_ROOT, "index.html")


@app.get("/static/<path:filename>")
def static_files(filename: str) -> Response:
    return send_from_directory(STATIC_ROOT, filename)


@app.get("/api/config")
def config() -> Response:
    return jsonify(
        {
            "allowed_roots": [str(path) for path in ALLOWED_ROOTS],
            "upload_limit_mb": UPLOAD_LIMIT_MB,
            "fixture_available": FIXTURE_PATH.exists(),
            "version": "0.4.8",
            "instrument_fields": FIELDS,
            "generator_catalog": generator_catalog(),
        }
    )


@app.get("/api/health")
def health() -> Response:
    return jsonify({"status": "ok", "service": "tofshield-ada-hdf5-viewer"})


@app.post("/api/detection-capability")
def detection_capability() -> Response:
    return jsonify(calculate_study(request.get_json(silent=True) or {}))


@app.post("/api/open-path")
def open_path() -> Response:
    payload = request.get_json(silent=True) or {}
    raw_path = str(payload.get("path", "")).strip()
    if not raw_path:
        return jsonify({"error": "Enter a local HDF5 file path."}), 400
    path = _validate_hdf5_path(Path(raw_path), require_allowed_root=True)
    file_id, manifest = _register_file(path, path.name, "local path")
    return jsonify({"file_id": file_id, "manifest": manifest})


@app.post("/api/open-reviewed")
def open_reviewed() -> Response:
    payload = request.get_json(silent=True) or {}
    relative = str(payload.get("path", ""))
    parts = Path(relative).parts
    if not parts or parts[0] != "HDF5" or ".." in parts or Path(relative).is_absolute():
        return jsonify({"error": "Choose a file from the TOFWERK HDF5 table."}), 400
    report = json.loads((STATIC_ROOT / "tofwerk-assessment.json").read_text())
    row = next((row for row in report["rows"] if row["path"] == relative), None)
    if row is None:
        return jsonify({"error": "This file is not in the assessment table."}), 400
    for root in ALLOWED_ROOTS:
        candidate = root.joinpath(*parts[1:]) if root.name == "HDF5" else root.joinpath(*parts)
        if not candidate.is_file():
            continue
        path = _validate_hdf5_path(candidate, require_allowed_root=True)
        file_id, manifest = _register_file(path, path.name, "assessment table")
        context = manifest["instrument_context"]
        reviewed_family = {"Vocus CI-TOF": "vocus", "mipTOF": "miptof"}.get(row["instrument"])
        if reviewed_family and context.get("family") == "unknown" and context.get("confidence") != "ambiguous":
            context.update(family=reviewed_family, confidence="Assessment-table instrument classification",
                           limitations=row.get("instrumentBasis", "Based on the reviewed delivery context."),
                           source="assessment")
        return jsonify({"file_id": file_id, "manifest": manifest})
    return jsonify({"error": "File not found in the configured HDF5 folder. Connect the ADA drive, or use Choose or drop a file in Spectrum Workspace."}), 404


@app.post("/api/upload")
def upload() -> Response:
    uploaded = request.files.get("file")
    if uploaded is None or not uploaded.filename:
        return jsonify({"error": "Choose an HDF5 file to upload."}), 400
    original_name = Path(uploaded.filename).name
    suffix = Path(original_name).suffix.lower()
    if suffix not in VALID_EXTENSIONS:
        return jsonify({"error": "Choose a file ending in .h5, .hdf5, or .hdf."}), 400
    safe_name = secure_filename(original_name) or f"dataset{suffix}"
    destination = UPLOAD_ROOT / f"{uuid.uuid4().hex}-{safe_name}"
    uploaded.save(destination)
    try:
        path = _validate_hdf5_path(destination, require_allowed_root=False)
        file_id, manifest = _register_file(
            path, original_name, "browser upload", owned_upload=True
        )
    except Exception:
        destination.unlink(missing_ok=True)
        raise
    return jsonify({"file_id": file_id, "manifest": manifest})


@app.post("/api/internal/team-share-import")
def import_team_share_hdf5() -> Response:
    if request.headers.get("X-ADA-Internal-Import") != TEAM_SHARE_IMPORT_MARKER:
        return jsonify({"error": "Not found."}), 404

    encoded_key = request.headers.get("X-ADA-Team-Share-Key", "")
    try:
        object_key = unquote(encoded_key, errors="strict")
    except UnicodeDecodeError as exc:
        raise ValueError("The Team Share object key is invalid.") from exc
    original_name = Path(object_key).name
    suffix = Path(original_name).suffix.lower()
    if not original_name or suffix not in VALID_EXTENSIONS:
        raise ValueError("Choose a Team Share file ending in .h5, .hdf5, or .hdf.")

    maximum_bytes = int(app.config["MAX_CONTENT_LENGTH"])
    if request.content_length is not None and request.content_length > maximum_bytes:
        raise RequestEntityTooLarge()

    safe_name = secure_filename(original_name) or f"dataset{suffix}"
    unique_prefix = uuid.uuid4().hex
    partial = UPLOAD_ROOT / f"{unique_prefix}-{safe_name}.part"
    destination = UPLOAD_ROOT / f"{unique_prefix}-{safe_name}"
    received_bytes = 0

    try:
        with partial.open("xb") as output:
            while True:
                chunk = request.stream.read(STREAM_COPY_CHUNK_BYTES)
                if not chunk:
                    break
                received_bytes += len(chunk)
                if received_bytes > maximum_bytes:
                    raise RequestEntityTooLarge()
                output.write(chunk)

        if received_bytes == 0:
            raise ValueError("The Team Share object is empty.")
        if request.content_length is not None and received_bytes != request.content_length:
            raise ValueError("The Team Share transfer was incomplete.")

        os.replace(partial, destination)
        path = _validate_hdf5_path(destination, require_allowed_root=False)
        file_id, manifest = _register_file(
            path,
            original_name,
            "Team Share/R2",
            owned_upload=True,
        )
    except Exception:
        partial.unlink(missing_ok=True)
        destination.unlink(missing_ok=True)
        raise

    return jsonify({"file_id": file_id, "manifest": manifest})


@app.post("/api/file/<file_id>/companions")
def upload_companions(file_id: str) -> Response:
    item = _get_open_file(file_id)
    uploads = request.files.getlist("files")
    if not uploads:
        return jsonify({"error": "Choose one or more companion files."}), 400
    saved: list[Path] = []
    for uploaded in uploads[:200]:
        if not uploaded.filename:
            continue
        original_name = Path(uploaded.filename).name
        suffix = Path(original_name).suffix.lower()
        if suffix not in SUPPORTED_EXTENSIONS:
            continue
        safe_name = secure_filename(original_name) or f"companion{suffix}"
        destination = UPLOAD_ROOT / f"{uuid.uuid4().hex}-{safe_name}"
        uploaded.save(destination)
        saved.append(destination)
    if not saved:
        return jsonify({"error": "No supported companion files were selected."}), 400
    item.companion_paths = (item.companion_paths or []) + saved
    item.manifest["companion_context"] = companion_inventory(
        item.companion_paths, item.display_name, _manifest_evidence_text(item.manifest)
    )
    return jsonify({"companion_context": item.manifest["companion_context"]})


@app.delete("/api/file/<file_id>")
def close_file(file_id: str) -> Response:
    with _registry_lock:
        item = _registry.pop(file_id, None)
    if item is None:
        return jsonify({"status": "already closed"})
    paths = list(item.companion_paths or [])
    if item.owned_upload:
        paths.append(item.path)
    for path in paths:
        try:
            if path.parent in {UPLOAD_ROOT, GENERATED_ROOT}:
                path.unlink(missing_ok=True)
        except OSError:
            pass
    return jsonify({"status": "closed"})


@app.post("/api/open-fixture")
def open_fixture() -> Response:
    if not FIXTURE_PATH.exists():
        return jsonify({"error": "The synthetic example fixture is not installed."}), 404
    path = _validate_hdf5_path(FIXTURE_PATH, require_allowed_root=False)
    file_id, manifest = _register_file(path, path.name, "synthetic example")
    return jsonify({"file_id": file_id, "manifest": manifest})


@app.post("/api/generate/<instrument>")
def generate_synthetic(instrument: str) -> Response:
    payload = request.get_json(silent=True) or {}
    detection_result = calculate_study(payload["detection_study"]) if payload.get("detection_study") else None
    cfg = normalize(payload.get("instrument_configuration", {}))
    if "instrument_configuration" in payload:
        payload["instrument_configuration"] = cfg
        if instrument == "vocus":
            payload["reagent"] = cfg["reagent"]
    instrument_key = instrument.strip().lower()
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    token = uuid.uuid4().hex[:8]
    if instrument_key == "vocus":
        filename = f"ADA_Synthetic_Vocus_CI_TOF_{stamp}_{token}.h5"
        path = GENERATED_ROOT / filename
        summary = generate_vocus(path, payload)
    elif instrument_key == "miptof":
        filename = f"ADA_Synthetic_mipTOF_{stamp}_{token}.h5"
        path = GENERATED_ROOT / filename
        summary = generate_miptof(path, payload)
    else:
        return jsonify({"error": "Choose either the Vocus CI-TOF or mipTOF generator."}), 404
    try:
        if "instrument_configuration" in payload:
            with h5py.File(path, "a") as generated:
                group = generated.create_group("InstrumentConfiguration")
                for key, value in cfg.items():
                    group.attrs[key] = value
                group.attrs["Application"] = "Requested configuration; applied at analysis time, stored spectra remain baseline synthetic data"
        if detection_result:
            with h5py.File(path, "a") as generated:
                group = generated.create_group("ADA/DetectionCapability")
                for key, value in detection_result.items():
                    if value is not None:
                        group.attrs[key] = value
                group.attrs["Provenance"] = "User-entered study stored by ADA Viewer v0.4.8"
        file_id, manifest = _register_file(path, filename, "synthetic generator", owned_upload=True)
    except Exception:
        path.unlink(missing_ok=True)
        raise
    return jsonify(
        {
            "file_id": file_id,
            "manifest": manifest,
            "generation_summary": summary,
            "download_url": f"/api/file/{file_id}/download",
        }
    )


@app.get("/api/file/<file_id>/download")
def download_hdf5(file_id: str) -> Response:
    item = _get_open_file(file_id)
    return send_from_directory(
        item.path.parent,
        item.path.name,
        as_attachment=True,
        download_name=item.display_name,
        mimetype="application/x-hdf5",
    )


@app.get("/api/file/<file_id>/spectrum")
def spectrum(file_id: str) -> Response:
    item = _get_open_file(file_id)
    result = _load_spectrum(
        item,
        request.args.get("candidate"),
        _parse_optional_float(request.args.get("x_min")),
        _parse_optional_float(request.args.get("x_max")),
        int(request.args.get("max_points", "30000")),
        request.args.get("aggregation", "sum"),
        normalize(json.loads(request.args["instrument_configuration"])) if request.args.get("instrument_configuration") else None,
        calculate_study(json.loads(request.args["detection_study"])) if request.args.get("detection_study") else None,
    )
    return jsonify(result)


@app.get("/api/file/<file_id>/search")
def search_hdf5(file_id: str) -> Response:
    item = _get_open_file(file_id)
    query = request.args.get("q", "").strip()
    if len(query) < 2:
        return jsonify({"error": "Enter at least two characters to search."}), 400
    matches = _search_manifest(item.manifest, query)
    return jsonify({
        "query": query,
        "matches": matches,
        "count": len(matches),
        "limited": len(matches) >= 250,
        "scope": "HDF5 paths, dataset names, attributes, scalar values and embedded configuration metadata",
    })


@app.get("/api/file/<file_id>/time-series")
def time_series(file_id: str) -> Response:
    item = _get_open_file(file_id)
    return jsonify(_load_time_series(
        item,
        request.args.get("candidate"),
        _parse_optional_float(request.args.get("mass_min")),
        _parse_optional_float(request.args.get("mass_max")),
        _parse_optional_float(request.args.get("time_min")),
        _parse_optional_float(request.args.get("time_max")),
        request.args.get("aggregation", "sum"),
        max(100, min(int(request.args.get("max_points", "5000")), 20_000)),
    ))


@app.get("/api/file/<file_id>/export.csv")
def export_csv(file_id: str) -> Response:
    item = _get_open_file(file_id)
    result = _load_spectrum(
        item,
        request.args.get("candidate"),
        _parse_optional_float(request.args.get("x_min")),
        _parse_optional_float(request.args.get("x_max")),
        MAX_SPECTRUM_POINTS,
        request.args.get("aggregation", "sum"),
        normalize(json.loads(request.args["instrument_configuration"])) if request.args.get("instrument_configuration") else None,
        calculate_study(json.loads(request.args["detection_study"])) if request.args.get("detection_study") else None,
    )
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["x", "intensity", "x_units", "intensity_units", "analysis_mode", "instrument_configuration", "detection_capability"])
    x_units = result["candidate"]["x_units"]
    y_units = result["candidate"]["y_units"]
    for x_value, y_value in zip(result["x"], result["y"], strict=True):
        writer.writerow([f"{x_value:.12g}", f"{y_value:.12g}", x_units, y_units, "illustrative configured response" if result["configuration_report"] else "stored data", json.dumps(result["instrument_configuration"]), json.dumps(result["detection_study"])])
    filename = f"{Path(item.display_name).stem}-spectrum.csv"
    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.errorhandler(RequestEntityTooLarge)
def too_large(_: RequestEntityTooLarge) -> tuple[Response, int]:
    return (
        jsonify(
            {
                "error": (
                    f"The upload exceeds {UPLOAD_LIMIT_MB:,} MiB. Use the local-path option "
                    "to inspect large files without copying them."
                )
            }
        ),
        413,
    )


@app.errorhandler(Exception)
def handle_error(error: Exception) -> tuple[Response, int]:
    if isinstance(error, HTTPException):
        return jsonify({"error": error.description}), error.code or 500
    if isinstance(error, (ValueError, OSError, KeyError, TypeError)):
        return jsonify({"error": str(error)}), 400
    app.logger.exception("Unexpected error")
    return jsonify({"error": "Unexpected viewer error. See the terminal for details."}), 500


def main() -> None:
    host = os.environ.get("ADA_VIEWER_HOST", "127.0.0.1")
    port = int(os.environ.get("ADA_VIEWER_PORT", "8081"))
    debug = os.environ.get("ADA_VIEWER_DEBUG", "0") == "1"
    app.run(host=host, port=port, debug=debug, threaded=True)


if __name__ == "__main__":
    main()
