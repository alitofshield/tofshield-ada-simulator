#!/usr/bin/env python3
"""Generate a compact synthetic TOFWERK-style fixture for viewer verification."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import h5py
import numpy as np


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "fixtures" / "synthetic_tofwerk_style_reference.h5"


def gaussian(axis: np.ndarray, center: float, amplitude: float, sigma: float) -> np.ndarray:
    return amplitude * np.exp(-0.5 * ((axis - center) / sigma) ** 2)


def main() -> None:
    rng = np.random.default_rng(7314)
    mass_axis = np.linspace(10.0, 500.0, 24_000, dtype=np.float64)
    centers = np.asarray([21.022, 59.049, 79.055, 137.024, 181.071, 227.125, 279.113, 311.164])
    amplitudes = np.asarray([2.8e5, 7.4e5, 1.7e5, 5.2e5, 2.3e5, 3.9e5, 8.7e5, 6.1e5])
    widths = np.asarray([0.027, 0.034, 0.038, 0.043, 0.048, 0.052, 0.058, 0.061])

    spectra = []
    for write_index in range(12):
        baseline = 180 + 0.12 * mass_axis + rng.gamma(shape=1.6, scale=35, size=mass_axis.size)
        spectrum = baseline
        modulation = 0.78 + 0.42 * np.exp(-0.5 * ((write_index - 7.0) / 2.2) ** 2)
        for peak_index, (center, amplitude, width) in enumerate(zip(centers, amplitudes, widths)):
            peak_scale = modulation if peak_index >= 5 else 0.92 + 0.03 * write_index
            spectrum = spectrum + gaussian(
                mass_axis,
                center + rng.normal(0, width * 0.03),
                amplitude * peak_scale,
                width,
            )
            if peak_index in {5, 6, 7}:
                spectrum = spectrum + gaussian(
                    mass_axis,
                    center + 1.00335,
                    amplitude * peak_scale * 0.12,
                    width * 1.04,
                )
        spectra.append(spectrum.astype(np.float32))
    tof_data = np.stack(spectra).reshape(12, 1, 1, mass_axis.size)
    sum_spectrum = np.sum(tof_data, axis=(0, 1, 2), dtype=np.float64)
    time_axis = np.arange(tof_data.shape[0], dtype=np.float64) * 2.0
    selected_trace = np.sum(tof_data[..., (mass_axis > 278.8) & (mass_axis < 279.4)], axis=(1, 2, 3))

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with h5py.File(OUTPUT, "w") as file:
        file.attrs["fixture_type"] = "synthetic"
        file.attrs["warning"] = "Synthetic reference data for software verification only"
        file.attrs["created_utc"] = datetime.now(tz=timezone.utc).isoformat()
        file.attrs["schema_note"] = "TOFWERK-style paths; not a vendor-generated acquisition"

        full = file.create_group("FullSpectra")
        mass_dataset = full.create_dataset("MassAxis", data=mass_axis.astype(np.float32))
        mass_dataset.attrs["unit"] = "Th"
        mass_dataset.attrs["description"] = "Synthetic static mass-to-charge axis"
        sum_dataset = full.create_dataset(
            "SumSpectrum", data=sum_spectrum, compression="gzip", compression_opts=4
        )
        sum_dataset.attrs["unit"] = "counts"
        sum_dataset.attrs["description"] = "Sum across all synthetic acquisition writes"
        tof_dataset = full.create_dataset(
            "TofData",
            data=tof_data,
            chunks=(1, 1, 1, 4096),
            compression="gzip",
            compression_opts=3,
        )
        tof_dataset.attrs["unit"] = "counts"
        tof_dataset.attrs["dimension_order"] = "writes,buffers,segments,samples"
        calibration = np.column_stack(
            [
                np.arange(12),
                np.full(12, 0.002415),
                np.full(12, -0.184),
                np.full(12, 0.5),
                np.linspace(-0.7, 0.8, 12),
                np.full(12, 11200.0),
            ]
        )
        cal_dataset = full.create_dataset("MassCalibration", data=calibration)
        cal_dataset.attrs["columns"] = np.asarray(
            ["write_index", "p0", "p1", "exponent", "mass_drift_ppm", "resolution"],
            dtype=h5py.string_dtype(),
        )

        traces = file.create_group("TimeSeries")
        time_dataset = traces.create_dataset("TimeSeconds", data=time_axis)
        time_dataset.attrs["unit"] = "s"
        trace_dataset = traces.create_dataset("SelectedIonTrace_279", data=selected_trace)
        trace_dataset.attrs["unit"] = "counts"
        trace_dataset.attrs["mass_window"] = "278.8–279.4 Th"

        instrument = file.create_group("Instrument")
        instrument.attrs["manufacturer"] = "Synthetic TOFWERK-style fixture"
        instrument.attrs["model"] = "Reference CI-TOF"
        instrument.attrs["instrument_id"] = "SYNTH-CITOF-001"
        instrument.attrs["detector"] = "MCP (simulated)"
        instrument.attrs["polarity"] = "positive"
        instrument.attrs["ionization_method"] = "Chemical ionization (simulated)"
        instrument.attrs["reagent_ion"] = "Demonstration reagent"
        instrument.attrs["source_temperature_c"] = 80.0
        instrument.attrs["source_pressure_mbar"] = 1.42
        instrument.attrs["extraction_voltage_v"] = 1350.0

        acquisition = file.create_group("Acquisition")
        acquisition.attrs["acquisition_id"] = "ADA-VIEWER-SYNTH-001"
        acquisition.attrs["start_time_utc"] = "2026-10-02T08:30:00Z"
        acquisition.attrs["duration_seconds"] = float(time_axis[-1] + 2.0)
        acquisition.attrs["writes"] = tof_data.shape[0]
        acquisition.attrs["buffers_per_write"] = tof_data.shape[1]
        acquisition.attrs["segments_per_buffer"] = tof_data.shape[2]
        acquisition.attrs["samples_per_spectrum"] = tof_data.shape[3]
        acquisition.attrs["sample_interval_ns"] = 0.2
        acquisition.attrs["operator"] = "Synthetic fixture generator"

        environment = file.create_group("Environment")
        environment.attrs["site"] = "Laboratory simulation"
        environment.attrs["ambient_temperature_c"] = 23.4
        environment.attrs["relative_humidity_percent"] = 34.1
        environment.attrs["ambient_pressure_hpa"] = 946.2
        environment.attrs["latitude"] = 24.7136
        environment.attrs["longitude"] = 46.6753
        environment.attrs["wind_speed_m_s"] = 2.4
        environment.attrs["wind_direction_deg"] = 318.0

        sample = file.create_group("Sample")
        sample.attrs["sample_id"] = "SYNTHETIC-REFERENCE-MIX"
        sample.attrs["sample_type"] = "Software verification fixture"
        sample.attrs["label_status"] = "synthetic; no compound identity asserted"

    print(OUTPUT)


if __name__ == "__main__":
    main()
