# LOD and LOQ Detection Capability — v0.3.5

Version 0.3.5 is based on v0.3.4 and adds:

- Calibration-curve estimates using LOD = 3.3σ/S and LOQ = 10σ/S.
- Signal-to-noise estimates using 3:1 and 10:1 criteria.
- Recording of independently established, user-supplied limits.
- Analyte, formula, quantifier m/z, tolerance, matrix and concentration units.
- Replicate blank and calibration-point entry.
- LOD/LOQ threshold lines on the spectrum when response thresholds are available.
- Peak Inspector concentration, signal-to-noise and detection-status columns.
- Study JSON export and CSV analysis provenance.
- `/ADA/DetectionCapability` metadata in newly generated synthetic HDF5 files when a study is active.
- Automated numerical and API tests.

## Scientific boundary

The viewer reports calculated values as estimates unless the user records an
independently validated method. A single spectrum, FWHM or resolving power does
not establish LOD or LOQ. Estimates apply only to the recorded analyte, matrix,
ion, acquisition method and instrument configuration and should be confirmed
with independent samples near the proposed limits.
