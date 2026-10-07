# Interface and Instrument Configuration — v0.3.1

## What changed

- Replaced the dark security-style presentation with a light instrument-console theme inspired by modern laboratory hardware: anodized-silver surfaces, graphite headers, precise grid spacing and an electric-violet analytical accent.
- Enlarged **Local Analytical Workspace** in the application header.
- Added exactly two primary application tabs:
  1. **Spectrum Workspace** — file loading, Vocus and mipTOF generation, HDF5 inspection, spectrum analysis, peak review and export.
  2. **Instrument Configuration** — a full-width engineering configuration workspace.
- Moved all instrument parameters out of the narrow file inspector.
- Added plain-language definitions, defaults, accepted ranges and model-status labels for every configurable parameter.
- Preserved the read-only source-file boundary. Applying a configuration changes only the displayed educational response and never modifies the source HDF5 file.

## Scientific boundary

The configuration remains an educational engineering model. Values are demonstration defaults, not TOFWERK specifications. Context-only values are recorded for discussion but do not imply an implemented physical law. The application does not predict identification, selectivity, concentration, sensitivity or certified instrument performance.
