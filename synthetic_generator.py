"""Educational synthetic HDF5 generators for Vocus CI-TOF and mipTOF.

These generators create plausible-looking, explicitly synthetic spectra for
interface demonstrations. They are not instrument emulators, analytical
methods, calibration tools, or sources of validated reference spectra.
"""

from __future__ import annotations

import hashlib
import math
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import h5py
import numpy as np


ATOMIC_MASS = {
    "H": 1.00782503223,
    "C": 12.0,
    "N": 14.00307400443,
    "O": 15.99491461957,
    "F": 18.99840316273,
    "Na": 22.9897692820,
    "P": 30.97376199842,
    "S": 31.9720711744,
    "Cl": 34.968852682,
    "K": 38.9637064864,
    "Br": 78.9183376,
    "I": 126.904473,
}

TARGET_LIBRARY: dict[str, dict[str, Any]] = {
    # Explosives and energetic materials
    "TNT": {"name": "2,4,6-Trinitrotoluene", "formula": "C7H5N3O6", "class": "Explosive"},
    "RDX": {"name": "RDX", "formula": "C3H6N6O6", "class": "Explosive"},
    "HMX": {"name": "HMX", "formula": "C4H8N8O8", "class": "Explosive"},
    "PETN": {"name": "Pentaerythritol tetranitrate", "formula": "C5H8N4O12", "class": "Explosive"},
    "NITROGLYCERIN": {"name": "Nitroglycerin", "formula": "C3H5N3O9", "class": "Explosive"},
    "TATP": {"name": "Triacetone triperoxide", "formula": "C9H18O6", "class": "Explosive"},
    "DNT": {"name": "Dinitrotoluene", "formula": "C7H6N2O4", "class": "Explosive marker"},
    "EGDN": {"name": "Ethylene glycol dinitrate", "formula": "C2H4N2O6", "class": "Explosive"},
    # Narcotics / forensic compounds
    "HEROIN": {"name": "Heroin", "formula": "C21H23NO5", "class": "Narcotic"},
    "COCAINE": {"name": "Cocaine", "formula": "C17H21NO4", "class": "Narcotic"},
    "FENTANYL": {"name": "Fentanyl", "formula": "C22H28N2O", "class": "Narcotic"},
    "METHAMPHETAMINE": {"name": "Methamphetamine", "formula": "C10H15N", "class": "Narcotic"},
    "AMPHETAMINE": {"name": "Amphetamine", "formula": "C9H13N", "class": "Narcotic"},
    "MDMA": {"name": "MDMA", "formula": "C11H15NO2", "class": "Narcotic"},
    "THC": {"name": "Delta-9-THC", "formula": "C21H30O2", "class": "Cannabinoid"},
    "CBD": {"name": "Cannabidiol", "formula": "C21H30O2", "class": "Cannabinoid"},
    # Toxic industrial / environmental compounds
    "AMMONIA": {"name": "Ammonia", "formula": "NH3", "class": "Toxic industrial chemical"},
    "CHLORINE": {"name": "Chlorine", "formula": "Cl2", "class": "Toxic industrial chemical"},
    "HYDROGEN SULFIDE": {"name": "Hydrogen sulfide", "formula": "H2S", "class": "Toxic industrial chemical"},
    "SULFUR DIOXIDE": {"name": "Sulfur dioxide", "formula": "SO2", "class": "Toxic industrial chemical"},
    "HYDROGEN CYANIDE": {"name": "Hydrogen cyanide", "formula": "HCN", "class": "Toxic industrial chemical"},
    "PHOSGENE": {"name": "Phosgene", "formula": "COCl2", "class": "Toxic industrial chemical"},
    "BENZENE": {"name": "Benzene", "formula": "C6H6", "class": "Industrial VOC"},
    "TOLUENE": {"name": "Toluene", "formula": "C7H8", "class": "Industrial VOC"},
    "FORMALDEHYDE": {"name": "Formaldehyde", "formula": "CH2O", "class": "Industrial VOC"},
    "ACETONE": {"name": "Acetone", "formula": "C3H6O", "class": "Industrial VOC"},
    "METHANOL": {"name": "Methanol", "formula": "CH4O", "class": "Industrial VOC"},
    "ETHYLENE OXIDE": {"name": "Ethylene oxide", "formula": "C2H4O", "class": "Toxic industrial chemical"},
    "DIPICOLINIC ACID": {"name": "Dipicolinic acid", "formula": "C7H5NO4", "class": "Bacterial-spore-associated marker"},
    "METHYL SALICYLATE": {"name": "Methyl salicylate", "formula": "C8H8O3", "class": "Chemical-agent simulant"},
}

TARGET_ALIASES = {
    "NG": "NITROGLYCERIN",
    "H2S": "HYDROGEN SULFIDE",
    "SO2": "SULFUR DIOXIDE",
    "HCN": "HYDROGEN CYANIDE",
    "DPA": "DIPICOLINIC ACID",
}

REAGENTS = {
    "I-": {"label": "Iodide", "mode": "adduct", "shift": 126.904473, "polarity": "negative"},
    "NO3-": {"label": "Nitrate", "mode": "adduct", "shift": 61.988366, "polarity": "negative"},
    "H3O+": {"label": "Hydronium (PTR)", "mode": "proton", "shift": 1.007276, "polarity": "positive"},
    "NH4+": {"label": "Ammonium", "mode": "adduct", "shift": 18.033823, "polarity": "positive"},
    "NO+": {"label": "Nitric oxide", "mode": "adduct", "shift": 29.997989, "polarity": "positive"},
    "O2+": {"label": "Molecular oxygen", "mode": "charge transfer", "shift": 0.0, "polarity": "positive"},
}

ISOTOPE_LIBRARY: dict[str, dict[str, Any]] = {
    "U-235": {"mass": 235.0439301, "element": "U", "label": "Uranium-235"},
    "U-238": {"mass": 238.0507884, "element": "U", "label": "Uranium-238"},
    "PU-239": {"mass": 239.0521636, "element": "Pu", "label": "Plutonium-239"},
    "PU-240": {"mass": 240.0538138, "element": "Pu", "label": "Plutonium-240"},
    "CS-137": {"mass": 136.9070893, "element": "Cs", "label": "Cesium-137"},
    "CO-60": {"mass": 59.9338222, "element": "Co", "label": "Cobalt-60"},
    "SR-90": {"mass": 89.9077376, "element": "Sr", "label": "Strontium-90"},
    "I-129": {"mass": 128.9049837, "element": "I", "label": "Iodine-129"},
    "I-131": {"mass": 130.9061246, "element": "I", "label": "Iodine-131"},
    "AM-241": {"mass": 241.0568293, "element": "Am", "label": "Americium-241"},
    "PB-206": {"mass": 205.9744653, "element": "Pb", "label": "Lead-206"},
    "PB-207": {"mass": 206.9758969, "element": "Pb", "label": "Lead-207"},
    "PB-208": {"mass": 207.9766525, "element": "Pb", "label": "Lead-208"},
    "FE-56": {"mass": 55.9349363, "element": "Fe", "label": "Iron-56"},
    "CU-63": {"mass": 62.9295977, "element": "Cu", "label": "Copper-63"},
    "ZN-64": {"mass": 63.9291420, "element": "Zn", "label": "Zinc-64"},
    "HG-202": {"mass": 201.9706434, "element": "Hg", "label": "Mercury-202"},
    "AS-75": {"mass": 74.9215946, "element": "As", "label": "Arsenic-75"},
}

NATURAL_ELEMENT_PEAKS = {
    "H": [(1.007825, 1.0)],
    "C": [(12.0, 1.0), (13.003355, 0.011)],
    "N": [(14.003074, 1.0), (15.000109, 0.0037)],
    "O": [(15.994915, 1.0), (17.999160, 0.002)],
    "S": [(31.972071, 1.0), (33.967868, 0.044)],
    "Cl": [(34.968853, 1.0), (36.965903, 0.32)],
    "Ar": [(39.962383, 1.0)],
    "Fe": [(53.939609, 0.063), (55.934936, 1.0), (56.935393, 0.023)],
    "Cu": [(62.929598, 1.0), (64.927790, 0.446)],
    "Zn": [(63.929142, 1.0), (65.926034, 0.574), (67.924845, 0.386)],
    "Pb": [(205.974465, 0.524), (206.975897, 0.477), (207.976652, 1.0)],
}


def _tokens(value: str | list[str]) -> list[str]:
    if isinstance(value, list):
        raw = value
    else:
        raw = re.split(r"[,;\n]+", value)
    return [str(item).strip() for item in raw if str(item).strip()]


def _formula_mass(formula: str) -> float:
    parts = re.findall(r"([A-Z][a-z]?)(\d*)", formula)
    if not parts or "".join(f"{el}{count}" for el, count in parts) != formula:
        raise ValueError(f"Unsupported molecular formula: {formula}")
    mass = 0.0
    for element, count_text in parts:
        if element not in ATOMIC_MASS:
            raise ValueError(f"No educational mass value is configured for {element}.")
        mass += ATOMIC_MASS[element] * (int(count_text) if count_text else 1)
    return mass


def _resolve_target(token: str) -> dict[str, Any]:
    key = TARGET_ALIASES.get(token.upper(), token.upper())
    if key in TARGET_LIBRARY:
        return {"key": key, **TARGET_LIBRARY[key]}
    # Permit an explicit molecular formula as an educational custom target.
    mass = _formula_mass(token)
    return {"key": token, "name": f"Custom formula {token}", "formula": token, "class": "Custom", "mass": mass}


def _normalise_reagent(value: str) -> tuple[str, dict[str, Any]]:
    key = value.strip().upper().replace(" ", "")
    key = {"IODIDE": "I-", "NITRATE": "NO3-", "HYDRONIUM": "H3O+", "AMMONIUM": "NH4+"}.get(key, key)
    if key not in REAGENTS:
        options = ", ".join(REAGENTS)
        raise ValueError(f"Unsupported reagent ion. Use one of: {options}.")
    return key, REAGENTS[key]


def _gaussian(axis: np.ndarray, center: float, height: float, sigma: float) -> np.ndarray:
    if center < axis[0] - 1 or center > axis[-1] + 1:
        return np.zeros_like(axis)
    return height * np.exp(-0.5 * ((axis - center) / sigma) ** 2)


def _seed(payload: dict[str, Any]) -> int:
    serialized = repr(sorted((key, str(value)) for key, value in payload.items())).encode()
    return int.from_bytes(hashlib.sha256(serialized).digest()[:8], "big")


def _write_common(file: h5py.File, instrument: str, payload: dict[str, Any]) -> None:
    file.attrs.update(
        {
            "ADA_Provenance": "SYNTHETIC_EDUCATIONAL_SIMULATION",
            "ADA_Validation_Status": "NOT_VALIDATED_FOR_IDENTIFICATION_OR_QUANTIFICATION",
            "ADA_Generator_Version": "0.3.7",
            "Generated_UTC": datetime.now(timezone.utc).isoformat(),
            "Instrument_Family_Simulated": instrument,
            "Source_Data": "Algorithmically generated; no measured spectrum embedded",
        }
    )
    limitations = file.create_group("SimulationLimitations")
    limitations.attrs["Notice"] = (
        "Educational synthetic spectrum. Peak positions and relative responses are simplified. "
        "Not TOFWERK output, not a reference library, and not suitable for detection claims."
    )
    limitations.attrs["No_Claim"] = "No compound identification, concentration, sensitivity, LOD, or selectivity claim"
    request_group = file.create_group("SimulationRequest")
    for key, value in payload.items():
        request_group.attrs[str(key)] = ", ".join(value) if isinstance(value, list) else str(value)


def _write_spectra(file: h5py.File, axis: np.ndarray, spectrum: np.ndarray, rng: np.random.Generator) -> None:
    full = file.create_group("FullSpectra")
    mass_axis = full.create_dataset("MassAxis", data=axis, compression="gzip", compression_opts=4)
    mass_axis.attrs.update({"unit": "Th", "description": "Synthetic calibrated mass-to-charge axis"})
    summed = full.create_dataset("SumSpectrum", data=spectrum.astype(np.float32), compression="gzip", compression_opts=4)
    summed.attrs.update({"unit": "counts", "provenance": "synthetic"})
    # A compact sequence of writes gives the viewer a realistic multidimensional option.
    writes = []
    for index in range(12):
        scale = 0.72 + 0.42 * math.exp(-0.5 * ((index - 6) / 2.4) ** 2)
        write = np.maximum(0, spectrum * scale + rng.normal(0, np.sqrt(np.maximum(spectrum, 1)) * 0.15))
        writes.append(write.astype(np.float32))
    tof = full.create_dataset("TofData", data=np.stack(writes), compression="gzip", compression_opts=4, chunks=(1, min(8192, axis.size)))
    tof.attrs.update({"unit": "counts", "dimensions": "write,mass_sample", "provenance": "synthetic"})


def generate_vocus(path: Path, payload: dict[str, Any]) -> dict[str, Any]:
    reagent_key, reagent = _normalise_reagent(str(payload.get("reagent", "I-")))
    target_tokens = _tokens(payload.get("targets", ""))
    environment_tokens = _tokens(payload.get("environment", "H2O,N2,O2,CO2"))
    if not target_tokens:
        raise ValueError("Enter at least one target substance or molecular formula.")
    targets = [_resolve_target(token) for token in target_tokens]
    for item in targets:
        item.setdefault("mass", _formula_mass(item["formula"]))

    axis = np.linspace(0.5, 500.0, 99_901, dtype=np.float64)
    rng = np.random.default_rng(_seed(payload))
    spectrum = np.maximum(0.0, rng.normal(13.0, 2.8, axis.size))
    peaks: list[dict[str, Any]] = []

    # Reagent and reagent-cluster peaks are prominent contextual signals.
    reagent_mass = 19.01839 if reagent_key == "H3O+" else (reagent["shift"] if reagent["shift"] > 0 else 31.989829)
    spectrum += _gaussian(axis, reagent_mass, 260_000, 0.018)
    peaks.append({"label": reagent_key, "formula": reagent_key, "mz": reagent_mass, "role": "reagent ion"})
    if reagent_key in {"I-", "NO3-"}:
        water_cluster = reagent_mass + 18.010565
        spectrum += _gaussian(axis, water_cluster, 42_000, 0.023)
        peaks.append({"label": f"{reagent_key} water cluster", "formula": f"[{reagent_key}+H2O]", "mz": water_cluster, "role": "reagent cluster"})

    for index, target in enumerate(targets):
        neutral_mass = float(target["mass"])
        center = neutral_mass + float(reagent["shift"])
        height = 115_000 / (1 + index * 0.24)
        spectrum += _gaussian(axis, center, height, 0.016 + center * 0.000025)
        # Small, explicitly simulated isotope/adduct-neighbor feature.
        spectrum += _gaussian(axis, center + 1.003355, height * 0.10, 0.019 + center * 0.000025)
        if neutral_mass > 45:
            fragment = max(5.0, center - 18.010565)
            spectrum += _gaussian(axis, fragment, height * 0.12, 0.021)
        ion_label = (
            f"[M+{reagent_key.replace('-', '').replace('+', '')}]{'-' if reagent['polarity'] == 'negative' else '+'}"
            if reagent["mode"] == "adduct"
            else ("[M+H]+" if reagent["mode"] == "proton" else "M+")
        )
        peaks.append({
            "label": target["name"], "formula": target["formula"], "mz": center,
            "role": "synthetic target candidate", "ion": ion_label, "class": target["class"],
        })

    environmental: list[dict[str, Any]] = []
    for index, token in enumerate(environment_tokens):
        try:
            mass = _formula_mass(token)
        except ValueError:
            continue
        center = mass + (reagent["shift"] if reagent["mode"] in {"adduct", "proton"} else 0)
        if center <= axis[-1]:
            height = 7_000 / (1 + index * 0.32)
            spectrum += _gaussian(axis, center, height, 0.026)
            environmental.append({"label": token, "formula": token, "mz": center, "role": "synthetic environmental contribution"})

    with h5py.File(path, "w") as file:
        _write_common(file, "Vocus CI-TOF", payload)
        instrument = file.create_group("Instrument")
        instrument.attrs.update({
            "Manufacturer_Reference": "TOFWERK family (educational simulation only)",
            "Model": "Synthetic Vocus CI-TOF",
            "Ionization": "Chemical ionization",
            "Reagent_Ion": reagent_key,
            "Reagent_Name": reagent["label"],
            "Polarity": reagent["polarity"],
            "Mass_Range_Th": "0.5-500",
            "Nominal_Resolving_Power": "illustrative only; not an instrument specification",
        })
        env = file.create_group("Environment")
        env.attrs.update({"Compounds": ", ".join(environment_tokens), "Temperature_C": 22.0, "Pressure_hPa": 1013.25, "Relative_Humidity_percent": 45.0})
        acquisition = file.create_group("Acquisition")
        acquisition.attrs.update({"Mode": "Synthetic replay", "Writes": 12, "Duration_s": 12.0, "Sample_Type": "Educational mixture"})
        annotations = file.create_group("SyntheticAnnotations")
        rows = peaks + environmental
        strings = h5py.string_dtype("utf-8")
        annotations.create_dataset("Label", data=np.array([row["label"] for row in rows], dtype=strings))
        annotations.create_dataset("Formula", data=np.array([row["formula"] for row in rows], dtype=strings))
        annotations.create_dataset("Role", data=np.array([row["role"] for row in rows], dtype=strings))
        annotations.create_dataset("Expected_mz", data=np.array([row["mz"] for row in rows]))
        _write_spectra(file, axis, spectrum, rng)
    return {"instrument": "Vocus CI-TOF", "reagent": reagent_key, "targets": [item["name"] for item in targets], "peak_count": len(peaks)}


def _normalise_isotope(token: str) -> str:
    value = token.strip().upper().replace(" ", "")
    match = re.fullmatch(r"(\d+)([A-Z]{1,2})", value)
    if match:
        value = f"{match.group(2)}-{match.group(1)}"
    value = value.replace("_", "-")
    return value


def _formula_elements(formula: str) -> list[str]:
    parts = re.findall(r"([A-Z][a-z]?)(\d*)", formula)
    if not parts:
        return []
    return [element for element, _ in parts]


def generate_miptof(path: Path, payload: dict[str, Any]) -> dict[str, Any]:
    isotope_tokens = _tokens(payload.get("isotopes", ""))
    environment_tokens = _tokens(payload.get("environment", "N2,O2,CO2,Ar,Fe"))
    if not isotope_tokens:
        raise ValueError("Enter at least one isotope, for example U-235 or Pu-239.")
    isotopes = []
    for token in isotope_tokens:
        key = _normalise_isotope(token)
        if key not in ISOTOPE_LIBRARY:
            raise ValueError(f"Unsupported isotope '{token}'. Choose it from the supplied isotope list.")
        isotopes.append({"key": key, **ISOTOPE_LIBRARY[key]})

    axis = np.linspace(0.5, 260.0, 103_801, dtype=np.float64)
    rng = np.random.default_rng(_seed(payload))
    spectrum = np.maximum(0.0, rng.normal(9.0, 2.1, axis.size))
    rows: list[dict[str, Any]] = []
    for index, isotope in enumerate(isotopes):
        height = 175_000 / (1 + index * 0.22)
        sigma = 0.018 + isotope["mass"] * 0.000018
        spectrum += _gaussian(axis, isotope["mass"], height, sigma)
        spectrum += _gaussian(axis, isotope["mass"] / 2, height * 0.012, sigma * 0.75)
        rows.append({"label": isotope["label"], "formula": isotope["key"], "mz": isotope["mass"], "role": "synthetic isotope ion"})

    used_elements: set[str] = set()
    environment_rows: list[dict[str, Any]] = []
    for token in environment_tokens:
        elements = _formula_elements(token)
        if not elements and token.capitalize() in NATURAL_ELEMENT_PEAKS:
            elements = [token.capitalize()]
        for element in elements:
            if element in used_elements or element not in NATURAL_ELEMENT_PEAKS:
                continue
            used_elements.add(element)
            for mass, relative in NATURAL_ELEMENT_PEAKS[element]:
                spectrum += _gaussian(axis, mass, 11_000 * relative, 0.015 + mass * 0.000018)
                environment_rows.append({"label": f"Natural {element}", "formula": element, "mz": mass, "role": "synthetic elemental background"})

    with h5py.File(path, "w") as file:
        _write_common(file, "mipTOF", payload)
        instrument = file.create_group("Instrument")
        instrument.attrs.update({
            "Manufacturer_Reference": "TOFWERK family (educational simulation only)",
            "Model": "Synthetic mipTOF",
            "Ionization": "Microwave-induced plasma",
            "Plasma_Source": "Synthetic MICAP-like educational model",
            "Polarity": "positive",
            "Analyte_Type": "Elements and isotopes",
            "Mass_Range_Th": "0.5-260",
        })
        env = file.create_group("Environment")
        env.attrs.update({
            "Entered_Compounds_or_Elements": ", ".join(environment_tokens),
            "Interpretation": "Compounds are atomized; simulated signals represent elemental ions, not intact molecular ions",
            "Carrier_or_Plasma_Gas": "air/nitrogen (educational setting)",
        })
        acquisition = file.create_group("Acquisition")
        acquisition.attrs.update({"Mode": "Synthetic elemental replay", "Writes": 12, "Duration_s": 12.0, "Sample_Type": "Educational aerosol"})
        annotations = file.create_group("SyntheticAnnotations")
        all_rows = rows + environment_rows
        strings = h5py.string_dtype("utf-8")
        annotations.create_dataset("Label", data=np.array([row["label"] for row in all_rows], dtype=strings))
        annotations.create_dataset("Formula", data=np.array([row["formula"] for row in all_rows], dtype=strings))
        annotations.create_dataset("Role", data=np.array([row["role"] for row in all_rows], dtype=strings))
        annotations.create_dataset("Expected_mz", data=np.array([row["mz"] for row in all_rows]))
        _write_spectra(file, axis, spectrum, rng)
    return {"instrument": "mipTOF", "isotopes": [item["key"] for item in isotopes], "environment_elements": sorted(used_elements), "peak_count": len(rows)}


def generator_catalog() -> dict[str, Any]:
    targets = [
        {"key": key, "name": item["name"], "formula": item["formula"], "class": item["class"]}
        for key, item in TARGET_LIBRARY.items()
    ]
    return {
        "reagents": [{"formula": key, **value} for key, value in REAGENTS.items()],
        "targets": targets,
        "isotopes": [{"key": key, **value} for key, value in ISOTOPE_LIBRARY.items()],
        "environment_examples": ["H2O", "N2", "O2", "CO2", "H2", "CH4", "O3", "NO", "NO2", "SO2", "Ar", "Fe", "Cu", "Zn", "Pb"],
    }
