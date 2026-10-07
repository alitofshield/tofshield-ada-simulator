# Instrument Context and Target-State Correction — v0.3.7

Version 0.3.7 is based on v0.3.6 and corrects three related issues:

- A detected instrument family is now shown explicitly in both the Data Source
  heading and the Instrument Configuration workspace.
- When mipTOF is detected, the mipTOF panel is selected, Vocus reagent-ion and
  reaction-chamber controls are hidden, and the Vocus illustrative response
  model is disabled.
- `Analyte_Type = Elements and isotopes` is treated as a description, not a
  target.
- `/ADA/DetectionCapability` analytes are kept separate from sample targets.
  A prior TNT LOD/LOQ study therefore cannot enter the mipTOF isotope list.
- All LOD/LOQ example values—including TNT, its formula, m/z, calibration
  points and blank responses—have been removed from startup defaults.
- Selecting a known isotope updates the blank LOD/LOQ identity fields with that
  isotope and its catalog m/z, without inventing calibration data.

Spectral peaks remain observations only and are not automatically assigned a
compound, element, or isotope identity.
