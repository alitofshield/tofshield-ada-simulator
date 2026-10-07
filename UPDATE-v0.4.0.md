# TOFshield Simulator - Instrument Configurator v0.4.0

Version 0.4.0 is based directly on v0.3.9 and preserves its spectrum, configuration, FFT, FWHM, resolving-power, LOD/LOQ, acquisition-lock, guide and TOFWERK assessment functions.

## Added

- Companion-file correlation for PDF, MAT, CSV, TSV, XLSX, XLS, TXT, LOG, INI, JSON, YAML and YML files.
- Automatic sibling-file inventory when an HDF5 file is opened from an authorized local directory.
- Multiple companion-file upload for browser-loaded HDF5 data.
- Evidence-ranked relationships: confirmed, probable, possible or unresolved.
- Complete **Reset application** control that closes the active session, clears the UI, and removes viewer-owned temporary files.
- HDF5 string search across paths, dataset names, attributes, scalar previews and embedded configuration metadata.
- Time-based measurement panel for multidimensional HDF5 spectra, with selectable m/z and time intervals.
- Acquisition-log event markers when compatible TOFWERK log timestamps are available.

## Scientific boundary

File relationships provide provenance and run context; they do not by themselves establish chemical identity. Time traces show stored signal within a selected mass interval and require validated reagent-ion, adduct, interference and calibration methods for compound interpretation.
