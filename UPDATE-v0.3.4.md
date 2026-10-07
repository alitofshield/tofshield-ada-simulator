# Peak Inspector FWHM and Resolving Power — v0.3.4

Version 0.3.4 is based on v0.3.3 and adds:

- centroid m/z;
- baseline-corrected full width at half maximum (FWHM) in Thomson;
- interpolated left and right half-height crossings;
- resolving power calculated as `centroid m/z / FWHM`;
- peak-quality classifications: Estimated, Undersampled, Overlapping, Truncated, Unavailable and No mass axis.

Calculations use the full selected-window arrays before display downsampling. The results are analytical estimates and are not official manufacturer instrument specifications.

All v0.3.3 features are retained, including direct DFT, radix-2 FFT, Vocus and mipTOF synthetic generation, Instrument Configuration, HDF5 inspection and read-only source handling.
