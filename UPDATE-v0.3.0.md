# Instrument Configuration — v0.3.0

Extract this folder beside the existing viewer; keep the old installation as a backup. Run `bash start-viewer.sh` inside the new folder. Open http://127.0.0.1:8081 (stop the old viewer first).

For a meeting demonstration:
1. Select Vocus CI-TOF and enter ACETONE.
2. In Instrument Configuration select H3O+ (PTR example).
3. Enable “Apply illustrative response to analysis” and generate the HDF5.
4. Change dilution to 2 and press “Apply configuration & analyze”; the signal scales down.
5. Change calibration drift or additional response kernel to demonstrate peak shifts or broadening.
6. Set elapsed time below transport delay or choose Standby to demonstrate sample arrival and state effects.
7. Export configuration JSON and the configured CSV for discussion.

All seven groups from the email are present. Numeric defaults are illustrative inputs, not manufacturer specifications. Recorded-only fields are explicitly labelled: temperatures, pressures, reaction time, E/N, humidity, and vacuum. The empirical reaction multiplier is entered by the user, not inferred from those fields. Reagent chemistry affects new Vocus generation only; it cannot change chemistry in a previously recorded sample. Common response controls also apply to mipTOF; reagent chemistry does not alter the mipTOF elemental generator.

Model: transport delay = inlet volume / flow; first-order step response; dilution/loss, user reaction multiplier, reagent-relative multiplier, mass-dependent transmission, integration and detector gain, additive background/carryover, deterministic noise, saturation, ppm shift, configured range and state. Additional Gaussian broadening is computed at the median mass and cannot restore native resolution; it is not a mass-dependent TOFWERK analyzer model. Carryover is an additive demonstration offset, not a history-based adsorption model.

Source HDF5 files remain unchanged. Generated downloads contain baseline synthetic spectra plus the requested configuration; configured analysis is exported separately to CSV. Configuration changes require Apply; changing reagent requires regeneration. Applying defaults does change the response; turning the model off restores stored-data analysis. No automatic identity assignment, calibrated concentration, detection limits, or validated chemical selectivity are provided.

Verification: 14 automated tests passed (original viewer regression plus configuration validation, response changes, reagent synchronization, CSV export and unchanged source hash). JavaScript syntax checked. Visual browser execution unperformed: Chromium download was unavailable in the build environment.
