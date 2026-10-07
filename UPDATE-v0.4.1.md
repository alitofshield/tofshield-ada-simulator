# TOFshield Simulator - Instrument Configurator v0.4.1

## Changes

- Renames the time-dependent panel to **Extracted Ion Trace (EIT)**.
- Reconstructs flattened TOFWERK acquisitions only when `NbrSamples`, `NbrWrites`, `NbrSegments`, the mass axis and a numeric source dataset agree exactly.
- Reports the dataset and storage interpretation used for the EIT.
- Adds a separate HDF5 Inspector window with preserved Parameters, Datasets and Data Quality categories.
- HDF5 Find now reports the match count and provides Previous/Next navigation.
- Adds separate investigation windows for the mass spectrum, EIT and Fourier/FFT graphs.
- Preserves range, time-period, scale and transform controls in the graph windows.

## Scientific boundary

The reshape logic reconstructs storage organization; it does not infer compound identity or replace manufacturer documentation. If acquisition metadata and dataset dimensions do not agree exactly, the EIT is not generated.
