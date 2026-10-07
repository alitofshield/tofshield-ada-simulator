# HDF5 Instrument and Target Context — v0.3.6

Version 0.3.6 is based on v0.3.5 and adds:

- Blank Vocus compound and mipTOF isotope/element target fields at startup.
- Clearing of targets whenever a different HDF5 file is opened, preventing
  target information from leaking across files.
- Automatic selection of the Vocus Data Source panel when descriptive HDF5
  metadata or object names explicitly indicate Vocus, CI-TOF, or PTR-TOF.
- Automatic selection of the mipTOF Data Source panel when descriptive HDF5
  metadata or object names explicitly indicate mipTOF or ICP-TOF.
- Conservative target population only from explicitly named target, analyte,
  compound, substance, isotope, or element metadata fields.
- Data-quality messages explaining what was detected, what was populated, and
  when the viewer deliberately leaves fields blank.

## Scientific boundary

The viewer does not infer a compound, element, or isotope from a spectral peak.
If metadata is absent or ambiguous, the Open HDF5 panel stays selected and all
target fields remain blank. Automatic panel selection is a user-interface aid,
not verification of instrument provenance or chemical identity.
